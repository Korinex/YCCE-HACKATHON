# Backend 3 operational acceptance runbook

This runbook follows the repository's existing README commands. It uses synthetic values only. Do not use real identity, bank, or medical documents.

## 1. Install

From the repository root, use the environment setup in `README.md`:

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Then in another terminal:

```powershell
cd client
npm install
```

Record Python/Node versions and installation errors. This task did not install dependencies. The observed machine had Python 3.14.3 and Node 24.13.1; `client/node_modules` was absent. Pillow/OpenCV are not listed in the server requirements. The attempted `npm run dev` failed because `next` was not recognized.

## 2. Start server

```powershell
cd server
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

In a separate terminal, check `http://127.0.0.1:8000/api/v1/health` or run the existing server tests with `python -m pytest tests -q` from `server`.

## 3. Start client

```powershell
cd client
npm run dev
```

Open `http://localhost:3000`. Verify the UI can connect to the server before beginning the path.

## 4. Normal golden path

Paste or upload synthetic input, inspect findings, choose a redaction action, request output, and inspect the output and receipt. Export is acceptable only when real audit checks ran and the result is CLEAN. Save the test environment and observations in `backend3-user-acceptance.md`.

**Current state: BLOCKED.** The server was started locally and `/api/v1/health` returned `{"status":"ok","ocr_available":false}`. The real analyze route returned HTTP 501 in the test run; Backend 1 must implement the analyze/session and redact/export routes. Do not record a successful golden path until the route works end to end.

## 5. Hostile path

Use synthetic tests to try malformed finding/action data, unreadable or empty OCR output, an unsupported PDF, residual text after redaction, and a KEEP decision with the sensitive value still present. Confirm the audit is FAIL or PARTIAL and the export gate blocks. Backend 3 unit tests cover the audit/gate subset; API-level blocked-output handling remains unavailable until Backend 1 implements the routes.

## Wi-Fi-off check

**PENDING HUMAN ACTION.** A human must disable Wi-Fi/networking, then repeat a local synthetic path and record whether it works. Codex did not disable networking and no offline rehearsal is claimed. A script/configuration check cannot prove the device has no network access.
