import json
from pathlib import Path

from release_images.release_workflow import BuildEvent, GeneratedImage, ReleasePublisher


class RecordingStudio:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def render(self, event: BuildEvent, operation_id: str) -> GeneratedImage:
        self.calls.append(operation_id)
        return GeneratedImage(
            content=b"PNG release image",
            diagnostics={"operation_id": operation_id, "vendor": "test", "cost_usd": "0"},
        )


def test_repeated_build_event_reuses_published_artifact(tmp_path: Path) -> None:
    event = BuildEvent(
        build_id="build-184",
        project="console-kit",
        version="2.4.0",
        highlights=["Faster trace search", "Readable deployment diff"],
    )
    studio = RecordingStudio()
    publisher = ReleasePublisher(studio, tmp_path)

    first = publisher.publish(event)
    second = publisher.publish(event)

    assert first.status == "published"
    assert second.status == "already_published"
    assert studio.calls == [ReleasePublisher.operation_id(event)]
    assert Path(first.image_path).read_bytes() == b"PNG release image"
    diagnostic = json.loads(Path(first.diagnostics_path).read_text(encoding="utf-8"))
    assert diagnostic["build"]["build_id"] == "build-184"
    assert diagnostic["release"]["operation_id"] == studio.calls[0]

