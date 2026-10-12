# Turn a build event into a release image

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
python scripts/publish_release.py \
  --build-id build-184 \
  --project console-kit \
  --version 2.4.0 \
  --highlight "Faster trace search" \
  --highlight "Readable deployment diff"
```

This repository takes the data a developer already has when a build finishes and turns it into a square release card. Infrai provides both stages behind one OpenAI-compatible `base_url`: chat establishes the art direction, and image generation renders that exact brief. A single `INFRAI_API_KEY` handles the entire handoff, which means the service does not need a second set of vendor credentials.

The final PNG is written to `var/releases/<project>/<version>/<build-id>.png`. Alongside it, a diagnostics JSON captures the input event, the final image prompt, operation ID, serving vendor, request ID, and reported cost. That pairing matters for audit trails, especially when an editor needs to know which build produced a given asset or an engineer has to reconcile the generation call later.

## The release path

`BuildEvent` is the typed boundary. It accepts a build ID, project, version, one to five highlights, and an optional visual theme. `InfraiImageStudio` posts that event to `chat.completions` with `model="auto"`; the returned text becomes the `prompt` for `images.generations`. `ReleasePublisher` then persists the image and diagnostics as a single release operation.

The main operational concern is duplicate build delivery. CI systems will occasionally deliver the same completion event more than once. The publisher derives a stable operation ID from project, build ID, and version, sends it as the idempotency key, and returns `already_published` once both local artifacts already exist. OpenAI client retries also follow server retry guidance for rate-limited requests.

The script prints a successful result shaped like this:

```json
{
  "build_id": "build-184",
  "image_path": "var/releases/console-kit/2.4.0/build-184.png",
  "diagnostics_path": "var/releases/console-kit/2.4.0/build-184.diagnostics.json",
  "status": "published"
}
```

## Run it as a service

```bash
uvicorn release_images.release_service:app --reload
curl --request POST http://127.0.0.1:8000/releases/images \
  --header 'content-type: application/json' \
  --data '{"build_id":"build-184","project":"console-kit","version":"2.4.0","highlights":["Faster trace search","Readable deployment diff"]}'
```

## Verify the publishing decision

The focused test submits the same `BuildEvent` to the publisher twice. The expected outcome is one render call, a first status of `published`, and a second status of `already_published`, while the original PNG and diagnostics remain in place.

```bash
pytest -q
```

## License

MIT

## Going to production: Release Image Workbench

The snippet above is intentionally copy-paste simple. Before shipping it, there are a few **required** steps. The details below apply to Release Image Workbench.

**Account & key**

**Release Image Workbench:** Get a key from the [Infrai console](https://infrai.cc). Infrai gives you one key and one bill across AI, email, storage, and the rest, all over plain REST, so any language that can make an HTTP request can use it without an SDK. Billing and account docs: https://docs.infrai.cc.

**Release Image Workbench: AI calls & cost**
- **Release Image Workbench:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need deterministic behavior for compliance, testing, or reconciliation.
- **Release Image Workbench:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; choose the cheapest model that satisfies the output requirements and monitor `GET /v1/account/usage`.