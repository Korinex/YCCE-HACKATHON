# PS-06 Personal Data Privacy Shield

Local-first FastAPI service for privacy-safe handling of synthetic text, image, and PDF inputs. Backend 1 owns the API boundary, volatile sessions, public-safe schemas, redaction paths, and fail-closed export behavior.

## Current status

Backend 1 routes and safety controls are implemented and covered by the current test suite. Backend 2 detection and Backend 3 verification are integrated on this branch. Secure PDF processing uses PyMuPDF 1.28.2 under its AGPL-3.0-or-later license for this hackathon's local evaluation; production redistribution requires AGPL compliance or a commercial PyMuPDF license.

## Structure

- `server/` — FastAPI service and typed contracts
- `client/` — Next.js + TypeScript UI shell
- `integration/` — golden-path and false-positive test placeholders
- `docs/` — contract, demo, and judge-facing documentation

## Implemented API surface

- `GET /api/v1/health` — safe local capability status.
- `POST /api/v1/session` — creates a volatile request session.
- `GET /api/v1/session/{request_id}` — returns safe session status and remaining TTL.
- `DELETE /api/v1/session/{request_id}` — explicitly clears a session.
- `POST /api/v1/analyze` — validates text, PNG/JPG, and PDF inputs, then calls the Backend 2 adapter. It returns HTTP 503 when Backend 2 is unavailable rather than fabricating findings.
- `POST /api/v1/redact` — accepts only `request_id`, user decisions, and `strict_mode`; source content and findings are retrieved from the server-side session.
- `POST /api/v1/verify` — calls the Backend 3 adapter. Missing verification fails closed with `PARTIAL`; strict-mode export is blocked and returns no file bytes.

Public responses never include `raw_value`, `original_filename`, passwords, raw OCR/context text, or deterministic identifier hashes.

## Run the server

```bash
cd server
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Run the client

```bash
cd client
npm install
npm run dev
```

Open `http://localhost:3000`.

## Test

```bash
PYTHONPATH=server python3 -m pytest -q
```

## Runtime and privacy limits

- The service is local-only and should bind to `127.0.0.1`; it does not upload content externally or require external network calls during processing.
- Uploads are capped at 10 MiB and PDFs at 10 pages.
- Sessions are volatile, bounded in memory, and expire after 600 seconds by default. They are cleared after export, verification, expiry, cleanup, or shutdown.
- PDF processing uses `PDF_MODE=page_images` by default and supports `PDF_MODE=flatten` only when the configured PyMuPDF proof checks pass. PyMuPDF is installed from the pinned wheel before offline startup; runtime processing does not require network access.
- Detection validity is limited to safe classifications such as `FORMAT_ONLY` and `REVIEW` until Backend 2 provides its real detector and validators.
- QR extraction/signature verification is deferred; QR findings may only be marked `UNVERIFIED` or `UNSUPPORTED_AT_CARD`.
- OCR timing and production OCR capability are **NOT VERIFIED**.
- The project is not complete until the Backend 2 → redaction → Backend 3 verification golden path passes.

See [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) for the authoritative interface and current integration limitations.

### PDF dependency and offline setup

The PDF implementation is pinned to **PyMuPDF 1.28.2**. PyMuPDF is dual-licensed: AGPL-3.0-or-later or a commercial Artifex license. This hackathon uses the AGPL option for local evaluation only; production distribution must satisfy AGPL obligations or use a commercial license. Install while network access is available with `pip install -r server/requirements.txt`, then run the server offline from the prepared environment. No PDF bytes, passwords, or network requests are used at runtime.
