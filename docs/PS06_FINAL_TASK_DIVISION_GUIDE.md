# PS-06 Privacy Shield — Final Four-Person Task Division Guide

**Source of truth:** `PS06-MASTER-BUILD.md` v3.0 and `Markdown Live Preview-raw2.pdf`.

**Goal:** four people work in parallel with no shared-file collisions, then integrate one fail-closed golden path.

**Repository baseline:** `Korinex/YCCE-HACKATHON`, skeleton commit `c851779`.

---

## 1. Branches and file ownership

Create these branches from the current `main`:

```text
feat/backend-core
feat/backend-intelligence
feat/backend-proof-integration
feat/frontend
```

Ownership is strict:

| Person | Track | Primary responsibility | Files they may edit |
|---|---|---|---|
| Backend 1 | Core/API + SHIELD | Contracts, session cache, redaction, PDF/image/text export, receipt | `server/app/main.py`, `schemas.py`, `session.py`, `redact_engine.py`, `pdf_engine.py`, `receipt.py`, `server/tests/test_core.py` |
| Backend 2 | Detection/OCR + QR | SCOUT, validation tiers, OCR, QR layer | `server/app/validators/*`, `pipeline.py`, `ocr_engine.py`, `qr.py`, `server/tests/test_intelligence.py`, `server/tests/vectors/*` |
| Backend 3 | Proof/Integration/QA | PROOF OF REMOVAL, fail-closed gate, verify service, hostile set, evidence board | `server/app/audit.py`, `gate.py`, `verify_service.py`, `integration/*`, `scripts/*`, `docs/*` |
| Frontend | UI + user flow | All UI, mock fixtures, controls, receipt/evidence presentation | `client/src/*` |

### Shared-file rule

Only Backend 1 edits `main.py` and `schemas.py`. Backend 2 and Backend 3 publish Python interfaces and fixtures for Backend 1 to import. The Frontend uses the frozen JSON fixtures and never edits backend files. Contract changes require agreement from at least three people and a review comment in the PR.

---

## 2. Backend 1 — Core/API + SHIELD

### Mission

Build the local FastAPI shell and the complete artifact-generation path. This person owns the current request session because `/redact` receives only the request ID and decisions.

### Implement

#### A. API and schemas

Implement these routes:

```text
POST /api/v1/analyze
POST /api/v1/redact
POST /api/v1/verify
POST /api/v1/session
GET  /api/v1/health
```

Bind the local demo server to `127.0.0.1`; do not bind to `0.0.0.0`. CORS is not a security boundary.

`/analyze` accepts text, PNG/JPG, PDF, and optional local PDF password. It creates a random `request_id`, stores the current session in volatile memory, and returns document metadata plus findings from Backend 2.

`/redact` accepts only:

```json
{
  "request_id": "req_9f2a",
  "decisions": [
    {"id":"f_007","action":"MASK","decided_by_user":true}
  ],
  "strict_mode": true
}
```

The backend must retrieve the original content and findings from the session cache. It must reject unknown/expired IDs and decisions for findings not belonging to that session.

`/verify` calls Backend 3’s verification service on an existing output. `/session` exposes only safe status/TTL metadata, never raw values. `/health` reports service and OCR availability without secrets.

#### B. Volatile session cache

Store only in memory:

- Original bytes/text for the current request
- Findings and document metadata
- OCR quality and QR metadata required by the workflow
- Creation/expiry timestamps

Rules:

- TTL: maximum 10 minutes.
- Random, unguessable request ID.
- Clear on successful export/verification, explicit cleanup, expiry, and shutdown.
- Never write session content to disk.
- Never log request bodies, raw matches, passwords, OCR text, or original filenames.
- UI and receipt must say: `No external upload. Local processing. Volatile session cache: up to 10 minutes.`

#### C. SHIELD artifact generation

Text:

- `MASK` → same-length block mask or safe masked form.
- `UIDAI_FIRST8` → keep only the last four digits in the approved masked format.
- `REPLACE_TOKEN` → `[REDACTED: TYPE]`.
- `REMOVE` → delete span.
- `KEEP` → preserve only when explicitly selected; Strict mode blocks high-risk KEEP.

Images:

- Decode from memory.
- Draw fully opaque boxes with a 2–3 pixel pad.
- Cover the complete QR quiet zone where applicable.
- Strip EXIF/location metadata.
- Encode a new lossless PNG.

PDFs:

- Decrypt in memory only when the user supplies the password.
- Never derive passwords from name/DOB.
- Render every page at source DPI.
- Apply redaction fills with page offsets.
- Rebuild a new flattened PDF.
- Remove the original text layer, metadata, XMP, attachments, JavaScript, annotations, form fields, and embedded files.
- If flattening is not proven by hour 3.5, degrade to page images as the shareable output.

Filenames use `shielded_<random8>.<ext>` and never include the original filename, person name, or identifier.

#### D. Receipt

Generate a privacy-safe receipt with:

- Random run ID
- App version and timestamp
- Input kind and page count
- Counts by category
- Confidence-band counts
- Actions by category
- Review pages/regions
- OCR warnings
- Residual verdict and named categories only
- Local-processing/session-TTL statement
- KYC advisory: prefer a masked Aadhaar or offline e-KYC artifact

Raise/fail tests if raw Aadhaar, PAN, phone, email, address, medical text, OCR text, original filename, or deterministic identifier hash enters the receipt.

### Tests required

- All endpoint request/response schema tests.
- Session TTL and expiry.
- Unknown request ID and unknown finding ID.
- Invalid PDF password.
- Text action behavior.
- Opaque image output and metadata stripping.
- Flattened PDF does not retain extractable source text.
- Blocked export returns `sanitized_file_b64: null`.
- No raw values in logs/receipt/filename.

### Do not edit

Do not edit `validators/*`, `pipeline.py`, `ocr_engine.py`, `qr.py`, `audit.py`, `gate.py`, `verify_service.py`, or `client/src/*`.

---

## 3. Backend 2 — Detection/OCR + QR

### Mission

Build SCOUT and VALIDATION TIERS as deterministic, test-first modules. Return findings through a stable Python interface; Backend 1 owns the API wiring.

### Implement

#### A. Recognizers

Implement the master-build recognizer table:

- Aadhaar: candidate pattern plus Verhoeff.
- VID: 16 digits beginning with 1 plus context.
- PAN: correct pattern and entity character; always `FORMAT_ONLY`.
- GSTIN: structure plus optional check digit.
- IFSC: four letters + `0` + six alphanumeric.
- Bank account: 9–18 digits only when account/bank/IFSC context is within ±40 characters.
- UPI: known PSP suffixes can reach `VALIDATED`; unknown suffixes are `REVIEW` unless strong context supports them.
- Phone: Indian mobile format; not active-number verification.
- Card: 13–19 digits plus Luhn; not existence verification.
- Passport, voter ID, driving licence, vehicle: pattern plus context, `FORMAT_ONLY`.
- Email: format match only.
- Health term: context lexicon, `REVIEW`.

Normalize Devanagari and Arabic-Indic digits to ASCII before matching. Resolve overlaps by longest span, with Aadhaar before phone/bank.

#### B. Classes and confidence

Use exactly:

```text
VALIDATED | FORMAT_ONLY | REVIEW
```

Use explanations such as:

```text
FORMAT_MATCH
CHECKSUM_PASS
ISSUER_NOT_CHECKED
```

Never call a format/checksum result identity/authenticity verification.

Use:

```text
score = format_strength × OCR_factor
format_strength = 1.0 valid / 0.6 format-only / 0.35 review
OCR_factor = min(1, ocr_confidence / 0.9) for OCR; 1.0 for text
HIGH ≥ 0.75, MEDIUM ≥ 0.50, LOW < 0.50
```

A checksum-failing candidate can never be `VALIDATED`.

#### C. OCR

- Primary engine: RapidOCR.
- Fallback: PaddleOCR.
- Keep word-level boxes and per-token confidence.
- Text path never invokes OCR.
- Page quality: `GOOD`, `DEGRADED`, `UNREADABLE`.
- Low confidence or unsupported handwriting/script becomes `REVIEW`/review-required.

#### D. QR

Implement `qr.py` behind the hour-1.5 gate:

- Detect and decode supported secure QR.
- Return limited fields only.
- Return `VERIFIED_FOR_THIS_ARTIFACT`, `UNVERIFIED`, or `UNSUPPORTED_AT_CARD`.
- Never say “identity verified.”
- Tell Backend 1 the quiet-zone box for redaction.
- Re-decode the output through Backend 3’s proof check.

If two safe test cards are not available at the gate, ship QR detect/cover only or remove the QR demo beat.

### Required vectors

Must pass:

```text
234123412346
999941057058
999988887779
345678901238
876543210988
600011122234
455566677786
```

Must fail:

```text
999999999998
123456789012
987654321098
234123412345
```

Concession vector:

```text
999999999999  # checksum may pass; never claim it is a real identity
```

### Tests required

- Per-validator positive and negative tests.
- Context-window tests.
- UPI suffix versus ordinary email test.
- Overlap-resolution tests.
- Devanagari-digit normalization tests.
- OCR box/confidence tests.
- QR supported/unsupported tests.
- No false `VALIDATED` class for a checksum-only or format-only claim.

### Do not edit

Do not edit `main.py`, `schemas.py`, `session.py`, redaction/PDF code, `audit.py`, `gate.py`, `verify_service.py`, or `client/src/*`.

---

## 4. Backend 3 — Proof, Integration, and QA

### Mission

Own the question judges will ask: **“Is the file actually clean?”** Build the proof service, fail-closed state machine, hostile test set, evidence board, and integration scripts. Do not wire routes; Backend 1 does that.

### Implement

#### A. `audit.py` / `verify_service.py`

Return:

```json
{
  "checks": [
    {"id":"rescan","pass":true},
    {"id":"raw_search","pass":true},
    {"id":"metadata","pass":true,"scope":"metadata,attachments,comments,form_fields,hidden_layers,thumbnails"},
    {"id":"qr_redecode","pass":true,"status":"ran|unsupported"}
  ],
  "rectangles_vs_findings":"PASS",
  "residuals":[],
  "verdict":"CLEAN|FAIL|PARTIAL",
  "ran":4,
  "method_note":"Checks 1-2 share detector blind spots; checks 3-4 are independent",
  "ts":"..."
}
```

Never expose residual raw values. Name only the category/page/region.

#### B. Fail-closed gate

Implement:

```text
ANALYZED
  ├─ unresolved REVIEW or unreadable OCR in Strict mode → BLOCKED
  └─ all required decisions → REDACTED
       ├─ F3 FAIL/PARTIAL → BLOCKED
       └─ F3 CLEAN → EXPORT ENABLED
```

Also block when a high-risk finding is kept in Strict mode. A blocked response must contain no file bytes.

#### C. Integration and hostile set

Own:

```text
integration/test_golden_path.py
integration/test_break_matrix.py
integration/hostile_set/*
scripts/test_golden_path.py
scripts/test_wifi_off.py
docs/*
```

Hostile fixtures:

1. WhatsApp-compressed screenshot
2. Angled PVC photo
3. Devanagari-digit text
4. Locked bank PDF
5. Deliberately leaking black-box PDF
6. Empty document

Use synthetic or consented fixtures only. Never commit real personal data.

#### D. Evidence board

Produce per-entity precision, recall, false-alarm rate, known misses, and review burden. Never combine all entities into one accuracy number. The board must be regenerated from the final build, not typed from memory.

#### E. Offline rehearsal

Run the full path with Wi-Fi disabled. Counters must remain at zero. Record the exact limitations and the session TTL statement.

### Tests required

- Normal golden path.
- Different input and different layout.
- Toggle one finding to `KEEP`; proof must fail and name the leak.
- Blurry image.
- Renamed `.txt` as `.png`.
- Empty document.
- Locked PDF without password.
- Residual high-risk content.
- Partial proof check.
- Wi-Fi-off path.
- Audit summary contains no raw values.

### Do not edit

Do not edit `main.py`, `schemas.py`, validators, OCR, redaction/PDF engines, or `client/src/*`. Publish service interfaces and fixtures for Backend 1 and the Frontend.

---

## 5. Frontend — complete UI

### Mission

Build the user-facing SCOUT → SHIELD → PROOF → RECEIPT journey against mock JSON first, then switch to live endpoints.

### Implement in `client/src/*`

- `UploadZone`: drag-drop PNG/JPG/PDF, textarea, encrypted-PDF password field only when requested.
- `InteractiveInspector`: text highlights; image/PDF canvas boxes.
- `ActionControlPanel`: Mask, Remove, Keep, UIDAI_FIRST8, REPLACE_TOKEN; class and confidence chips.
- `SummaryPanel`: counts by type, sensitivity labels, arithmetic line; no risk enum.
- `StrictModeSwitch`: ON by default and explains blocking.
- `ExportBar`: download only when `export_blocked=false`; otherwise show block modal with `block_reason`.
- `ReceiptView`: receipt copy button copies the receipt only.
- `EvidenceDrawer`: press-and-hold reveal, auto-hide within five seconds.
- `EvidenceBoard`: hostile-set runner and per-entity metrics on demand.
- Offline status indicator and honest local-session/TTL copy.

Use no CDN, external fonts, analytics SDK, or remote model. The UI must never print raw PII in summaries, filenames, or receipts.

### Exact UI copy

```text
We couldn't read this reliably. Upload a clearer photo, or redact the whole page.
This PDF is locked. Enter its password here — it stays on your device and is never stored.
This input is out of scope today (handwriting / unsupported script / scan quality). Nothing was redacted.
Export blocked: one identifier is still in the file (row 3). Fix it or mark it for removal to continue.
No format-defined identifiers found. Names and addresses are not checked (see limitations).
```

### Frontend tests

- Mock JSON renders all finding classes.
- Toggle changes the decision payload.
- Strict mode blocks as specified.
- Evidence drawer auto-hides.
- Blocked response offers no download.
- Receipt copy contains no raw values.
- OCR/PDF warnings are understandable.
- API/network failure preserves local input and gives a retry option.

### Do not edit

Do not edit any `server/` file or contract docs. Report contract problems to Backend 1 and the team before changing types.

---

## 6. Integration order and time budget

### First 30 minutes — contract lock

All four people read the features guide, verify the interfaces, confirm the test vectors, and create branches. Backend 1 publishes the schema fixture. Backend 2 publishes detector fixture JSON. Backend 3 publishes AuditResult/gate fixtures. Frontend starts with these fixtures.

### Next 140–175 minutes — parallel build

- Frontend: UI against mocks.
- Backend 1: schemas, session, redaction/PDF/export.
- Backend 2: validators, OCR, QR gate.
- Backend 3: proof, gate, hostile set, evidence board.

### Integration order

1. Backend 2 hands its pipeline fixture to Backend 1.
2. Backend 3 hands its audit/gate fixture to Backend 1.
3. Backend 1 wires all routes and session handling.
4. Frontend switches from mock responses to live API.
5. Backend 3 runs the full golden path and break matrix.
6. Team runs Wi-Fi-off rehearsal.

### Degrade order

If time runs short:

1. Drop QR Reveal after Gate-01 fails.
2. Reduce Evidence Drawer polish.
3. Replace the No-Upload visual evidence with the spoken line plus Wi-Fi-off test.
4. Print the Evidence Board as a generated report instead of a polished screen.

Never cut:

- SCOUT
- SHIELD
- PROOF OF REMOVAL
- Strict mode
- Fail-closed export
- Honest limitation wording

---

## 7. CodeRabbit workflow for every person

```bash
git fetch origin
git checkout -b feat/<your-track> origin/main
# edit only owned files
python -m pytest -q <your tests>
git diff --check
git status --short
git add <owned files>
git commit -m "feat(<track>): <small change>"
git push -u origin feat/<your-track>
```

Open a draft PR into `main`. Use CodeRabbit in VS Code if available, then use the GitHub PR review as the shared review record.

Copy-paste review prompt:

> Review only this branch against the PS-06 master build and the stated file ownership. Check contract compatibility, privacy leakage, unsafe redaction, raw values in logs/receipts/filenames, fail-closed behavior, OCR uncertainty, malformed inputs, missing tests, accidental secrets, and scope creep. Do not redesign the product or add features. Classify each finding as blocker, important, or suggestion and propose the smallest fix for blockers.

Merge rules:

- No blocker remains.
- No raw personal data or real documents are committed.
- No contract change without approval from at least three teammates.
- Track tests cover normal and failure cases.
- `git diff --check` passes.
- Tests are rerun after accepted fixes.

---

## 8. Final team freeze line

The team ships:

```text
SCOUT · SHIELD · PROOF OF REMOVAL · VALIDATION TIERS
NO-UPLOAD EVIDENCE · COPY-PASTE SHOWDOWN · QR REVEAL (GATED)
EVIDENCE DRAWER · EVIDENCE BOARD
```

After the first complete golden path works, add no features. Only fix crashes, contract failures, privacy leaks, unsafe exports, validation problems, dependency failures, or demo-blocking UX.
