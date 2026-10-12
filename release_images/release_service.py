import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from openai import APIStatusError

from .release_workflow import (
    BuildEvent,
    InfraiError,
    InfraiImageStudio,
    ReleaseArtifact,
    ReleasePublisher,
)

app = FastAPI(title="Release Image Workbench")


def publisher() -> ReleasePublisher:
    media_dir = Path(os.environ.get("RELEASE_MEDIA_DIR", "var/releases"))
    return ReleasePublisher(InfraiImageStudio(), media_dir)


@app.post("/releases/images", response_model=ReleaseArtifact)
def create_release_image(event: BuildEvent) -> ReleaseArtifact:
    try:
        return publisher().publish(event)
    except InfraiError as exc:
        status_code = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "error": exc.detail},
        ) from exc
    except APIStatusError as exc:
        raise HTTPException(status_code=502, detail="Image service request failed") from exc

