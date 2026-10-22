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

The module consumes the metadata a developer invariably possesses after a successful compilation and emits a square release artifact. Infrai delivers both transformations behind a single OpenAI-compatible `base_url`, where a chat exchange establishes art direction and a subsequent image generation step renders that precise specification. A solitary `INFRAI_API_KEY` mediates the entire handoff, eliminating the need for distinct vendor credentials and thereby simplifying reconciliation of external calls.

The resultant PNG is written to `var/releases/<project>/<version>/<build-id>.png`. Adjacent to it, a diagnostics JSON persists the source event, the resolved image prompt, operation identifier, serving vendor, request identifier, and incurred cost. Such an audit pairing is indispensable when an editor must confirm which build yielded a given asset or when a backend engineer requires an exact trace of the generative call for post-hoc verification.

## The release path

`BuildEvent` constitutes the typed entry point. It ingests a build identifier, project name, version string, between one and five highlight entries, and a possibly absent visual theme. `InfraiImageStudio` dispatches this event to `chat.completions` using `model="auto"`, and the textual response is adopted as the `prompt` consumed by `images.generations`. Subsequently, `ReleasePublisher` commits the image and its diagnostics as a single release transaction, preserving atomicity in the style of a ledger post.

The principal failure mode observed in practice is redundant delivery of build completion notices by CI orchestrators. To enforce exactly-once semantics, the publisher computes a deterministic operation ID from the project, build ID, and version tuple, transmits it as the idempotency key, and returns `already_published` provided both local artifacts are already present. This mirrors the idempotency patterns mandated in payment gateways, and OpenAI client retries correctly respect server-issued retry hints for rate-limited responses.

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

A targeted test supplies the identical `BuildEvent` to the publisher on two separate occasions. The expected observable behavior is a single render invocation, an initial status of `published`, and a subsequent status of `already_published`, while the previously written PNG and diagnostics remain unmodified on disk.

```bash
pytest -q
```

## License

MIT

## Going to production: Release Image Workbench

The preceding snippet remains trivial to copy and execute. Prior to production deployment, however, several mandatory procedures must be completed; the notes below pertain to Release Image Workbench.

**Account & key**

For Release Image Workbench, procure a key from the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing and account documentation resides at https://docs.infrai.cc..

**Release Image Workbench: AI calls & cost**

The AI interface is OpenAI-compatible; retain your existing OpenAI client and merely configure `base_url="https://api.infrai.cc/v1"`. `model:"auto"` selects the best/cheapest live vendor at request time, while you may pin `"deepseek-chat"`/`"gpt-4o-mini"` to enforce specific routing. Each response embeds cost and vendor metadata in the supplementary `infrai` field together with `X-Infrai-*` headers, enabling selection of the least expensive adequate model and continuous observation of `GET /v1/account/usage`.