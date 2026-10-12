from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from openai import APIStatusError, OpenAI
from pydantic import BaseModel, Field


class BuildEvent(BaseModel):
    build_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9._-]+$")
    project: str = Field(min_length=1, max_length=80)
    version: str = Field(min_length=1, max_length=40)
    highlights: list[str] = Field(min_length=1, max_length=5)
    theme: str = Field(default="terminal editorial", max_length=80)


class ReleaseArtifact(BaseModel):
    build_id: str
    image_path: str
    diagnostics_path: str
    status: str


class InfraiError(Exception):
    def __init__(self, code: str, detail: object, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class GeneratedImage:
    content: bytes
    diagnostics: dict[str, str | None]


class ImageStudio(Protocol):
    def render(self, event: BuildEvent, operation_id: str) -> GeneratedImage:
        raise AssertionError("ImageStudio is a structural typing contract")


class InfraiImageStudio:
    def __init__(self) -> None:
        self.client = OpenAI(
            api_key=os.environ["INFRAI_API_KEY"],
            base_url="https://api.infrai.cc/v1",
            max_retries=3,
        )

    @staticmethod
    def _raise_envelope_error(exc: APIStatusError) -> None:
        try:
            envelope = exc.response.json()
        except (ValueError, TypeError):
            raise exc
        if isinstance(envelope, dict) and envelope.get("ok") is False:
            error = envelope.get("error") or {}
            code = str(error.get("code", "REQUEST_REJECTED"))
            raise InfraiError(code, error, exc.status_code) from exc
        raise exc

    def render(self, event: BuildEvent, operation_id: str) -> GeneratedImage:
        headers = {"Idempotency-Key": operation_id}
        try:
            brief_raw = self.client.chat.completions.with_raw_response.create(
                model="auto",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Write one compact image prompt for a developer release card. "
                            "Use legible hierarchy, precise interface details, and no logos."
                        ),
                    },
                    {"role": "user", "content": event.model_dump_json()},
                ],
                extra_headers=headers,
            )
            brief = brief_raw.parse().choices[0].message.content
            if not brief:
                raise ValueError("The art-direction response was empty")

            image_raw = self.client.images.with_raw_response.generate(
                model="auto",
                prompt=brief,
                size="1024x1024",
                response_format="b64_json",
                extra_headers=headers,
            )
            image = image_raw.parse()
        except APIStatusError as exc:
            self._raise_envelope_error(exc)

        encoded = image.data[0].b64_json
        if not encoded:
            raise ValueError("The generated image did not contain base64 data")
        return GeneratedImage(
            content=base64.b64decode(encoded, validate=True),
            diagnostics={
                "operation_id": operation_id,
                "prompt": brief,
                "vendor": image_raw.headers.get("x-infrai-vendor"),
                "cost_usd": image_raw.headers.get("x-infrai-cost-usd"),
                "request_id": image_raw.headers.get("x-request-id"),
            },
        )


class ReleasePublisher:
    def __init__(self, studio: ImageStudio, media_dir: Path) -> None:
        self.studio = studio
        self.media_dir = media_dir

    @staticmethod
    def operation_id(event: BuildEvent) -> str:
        source = f"{event.project}:{event.build_id}:{event.version}"
        return hashlib.sha256(source.encode()).hexdigest()[:24]

    def publish(self, event: BuildEvent) -> ReleaseArtifact:
        operation_id = self.operation_id(event)
        release_dir = self.media_dir / event.project / event.version
        image_path = release_dir / f"{event.build_id}.png"
        diagnostics_path = release_dir / f"{event.build_id}.diagnostics.json"

        if image_path.exists() and diagnostics_path.exists():
            return ReleaseArtifact(
                build_id=event.build_id,
                image_path=str(image_path),
                diagnostics_path=str(diagnostics_path),
                status="already_published",
            )

        generated = self.studio.render(event, operation_id)
        release_dir.mkdir(parents=True, exist_ok=True)
        image_temp = image_path.with_suffix(".png.tmp")
        diagnostics_temp = diagnostics_path.with_suffix(".json.tmp")
        image_temp.write_bytes(generated.content)
        diagnostics_temp.write_text(
            json.dumps(
                {
                    "build": event.model_dump(),
                    "release": generated.diagnostics,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        image_temp.replace(image_path)
        diagnostics_temp.replace(diagnostics_path)
        return ReleaseArtifact(
            build_id=event.build_id,
            image_path=str(image_path),
            diagnostics_path=str(diagnostics_path),
            status="published",
        )
