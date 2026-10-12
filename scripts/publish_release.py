import argparse
import json
from pathlib import Path

from release_images.release_workflow import BuildEvent, InfraiImageStudio, ReleasePublisher


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish an image for a completed build")
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--highlight", action="append", required=True)
    parser.add_argument("--media-dir", type=Path, default=Path("var/releases"))
    args = parser.parse_args()

    event = BuildEvent(
        build_id=args.build_id,
        project=args.project,
        version=args.version,
        highlights=args.highlight,
    )
    result = ReleasePublisher(InfraiImageStudio(), args.media_dir).publish(event)
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()

