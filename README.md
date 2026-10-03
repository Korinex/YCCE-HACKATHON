# PS-06 Personal Data Privacy Shield

Skeleton repository for the YCCE hackathon project. The product will detect sensitive Indian personal data in text/images, explain the findings, let users choose Mask/Remove/Keep, and produce a clean shareable output.

## Current status

This commit is **skeleton-only**. It defines the architecture, shared API contracts, typed client bridge, placeholder components, and health/contract tests. Detection, OCR, validation algorithms, and redaction are intentionally deferred to feature tracks.

## Structure

- `server/` — FastAPI service and typed contracts
- `client/` — Next.js + TypeScript UI shell
- `integration/` — golden-path and false-positive test placeholders
- `docs/` — contract, demo, and judge-facing documentation

## Run the server

```bash
cd server
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
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
python -m compileall server
pytest -q server/tests
```

## Frozen implementation order

1. Contract/repository lock
2. Backend core and in-memory redaction
3. Indian validators and OCR adapter
4. Frontend interaction
5. Integration, break-tests, feature freeze, demo rehearsal

See [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) for the authoritative interface.
