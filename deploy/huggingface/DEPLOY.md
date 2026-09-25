# Deploying to Hugging Face Spaces (Docker SDK)

The app ships as one container: FastAPI serves the API and the built React app on
port 7860 (`Dockerfile.space` in the repo root).

## 1. Create the Space

Create a new Space with **SDK: Docker** (blank template). Then push this repository's
contents to it, with two files swapped in at deploy time:

```bash
git clone https://huggingface.co/spaces/<user>/<space> space && cd space
rsync -a --exclude .git --exclude node_modules --exclude .venv ../jailbreak-gauntlet/ ./
cp Dockerfile.space Dockerfile                     # Spaces builds ./Dockerfile
cp deploy/huggingface/README.md README.md          # Space front-matter (sdk, app_port)
git add -A && git commit -m "Deploy" && git push
```

(`docs/` screenshots can be left out to keep the Space small.)

## 2. Secrets and variables (Space → Settings)

| Name | Kind | Example | Notes |
|---|---|---|---|
| `OPENAI_API_KEY` | **secret** | your Gemini/OpenAI key | Leave unset for the offline demo guard |
| `OPENAI_BASE_URL` | variable | `https://generativelanguage.googleapis.com/v1beta/openai/` | Omit for OpenAI |
| `OPENAI_MODEL` | variable | `gemini-2.5-flash` | guard + parser |
| `OPENAI_JUDGE_MODEL` | variable | `gemini-2.5-flash-lite` | optional, cheaper judge |
| `OPENAI_REASONING_EFFORT` | variable | `none` | recommended for Gemini 2.5 (skip thinking) |
| `CLASSIFIER_USE_LLM` | variable | `false` | each labeled message costs one more call |

Production defaults are baked into `Dockerfile.space` and can be overridden the same way:
`VISITOR_MAX_MESSAGES=15` per `VISITOR_WINDOW_SECONDS=600`, `VISITOR_MAX_MODEL_CALLS=45`
(guard + judge + parser + labeler calls), `GLOBAL_DAILY_MODEL_CALLS=1500`,
`MAX_INPUT_CHARS=600`, `OPENAI_MAX_TOKENS=400`, `TRUSTED_PROXY_HOPS=1`.

## 3. Storage

SQLite is written to `/data` if the Space has persistent storage, otherwise `/tmp`
(wiped on restart). With `SEED_ON_STARTUP=true` (default) an ephemeral Space re-seeds the
labelled synthetic dataset on boot, so the dashboard is never empty.

## What production mode changes

- `APP_ENV=production`: `/docs` and `/openapi.json` off; admin endpoints (seed/wipe)
  are never mounted, even if `ENABLE_ADMIN=true`.
- Per-visitor (client IP from `X-Forwarded-For`, trusting `TRUSTED_PROXY_HOPS` proxies) and
  global daily limits are on whenever a real model is configured; visitors get a friendly
  message and a `Retry-After` header.
- The public JSONL export redacts level secrets, emails, URLs, IPs, phone/card numbers and
  credential-like strings, and replaces session ids with salted hashes. Client IPs are only
  kept in memory for rate limiting, never written to the database.

Limits are in-process memory: run a single replica (the Space default).

## Local smoke test of the production image (no Docker needed)

```bash
cd frontend && npm ci && npm run build && cd ../backend
APP_ENV=production STATIC_DIR=../frontend/dist uvicorn app.main:app --port 7860
# open http://localhost:7860
```
