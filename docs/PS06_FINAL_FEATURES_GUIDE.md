# PS-06 Privacy Shield — Final Frozen Features Guide

**Source of truth:** `PS06-MASTER-BUILD.md` v3.0 plus the corrections in `Markdown Live Preview-raw2.pdf`.

**Status:** Final feature freeze. After this document is accepted, one feature must be removed before another feature is added.

**Repository baseline:** `Korinex/YCCE-HACKATHON`, skeleton commit `c851779`.

---

## 1. Product positioning

Use this sentence in the demo:

> Before you share this text, image, or document, Privacy Shield finds likely sensitive data, explains why it matched, removes it irreversibly, verifies the cleaned artifact, and produces a privacy-safe audit summary.

Use the corrected privacy wording:

> No external upload in the local demo. The local server processes content on `127.0.0.1` and holds the current session in volatile memory for up to 10 minutes so the redaction and verification steps can finish. The original is not written to disk, logged, or sent to an external model/API.

Local processing is risk reduction, not a safe harbour. The device, swap space, browser cache, clipboard, screen capture, and malicious extensions remain outside the prototype’s control.

---

## 2. The nine frozen features

### F1 — SCOUT: detect and explain

Accept pasted text, PNG/JPG images, PDFs up to 10 pages, and password-protected PDFs when the user supplies the password locally. Return document metadata, findings, OCR quality, context evidence, validation class, confidence, sensitivity, and bounding boxes.

The pipeline is:

```text
normalise digits → detect candidates → resolve overlaps → apply secondary rules
→ score context → assign validity class → assign confidence band
→ assign sensitivity → default action MASK
```

The tool must never claim identity, issuer, ownership, current status, entitlement, or authenticity verification from a format/checksum match.

### F2 — SHIELD: interactive irreversible redaction

The user can choose per finding:

- `MASK`
- `UIDAI_FIRST8`
- `REPLACE_TOKEN`
- `REMOVE`
- `KEEP`

Masking is the default. Text is replaced or removed. Images are rendered into a new artifact with opaque fills. PDFs are flattened into newly rendered pages so the original text layer, annotations, attachments, form fields, and hidden objects do not survive.

The output filename must be random, for example:

```text
shielded_7c31ab90.pdf
```

Never echo the original filename, person name, or identifier.

### F3 — PROOF OF REMOVAL: fail-closed verification

After redaction, run four checks:

1. Re-run the detector on the output.
2. Search the rebuilt text layer/raw strings.
3. Inspect metadata, attachments, comments, form fields, hidden layers, and thumbnails where supported.
4. Re-decode QR content and compare rectangles against high-risk findings.

The result is:

```text
CLEAN | FAIL | PARTIAL
```

If a residual high-risk match remains, export is blocked and the UI names the category/region without exposing the raw value. If only some checks run, show the count, such as `3/4 checks ran`; never show a green “clean” badge for a partial result.

Use the honest limitation:

> Detector re-scan shares the detector’s blind spots. Metadata and QR checks are independent checks where supported.

### F4 — VALIDATION TIERS: fail-safe classification

Use these exact classes:

- `VALIDATED` — a tested checksum/format rule and required context passed. This still does not prove issuance or ownership.
- `FORMAT_ONLY` — the structure looks like an identifier, but there is no trustworthy public checksum/issuer check.
- `REVIEW` — uncertainty, weak context, low OCR confidence, or a failed/unsupported secondary check.

Do not use the word `VALIDATED` to imply that a phone is active, an IFSC is assigned, a card exists, a UPI handle works, or an ID was issued. In explanations, use terms such as `FORMAT_MATCH`, `CHECKSUM_PASS`, and `ISSUER_NOT_CHECKED`.

Strict Share mode is **ON by default**:

- Any undecided `REVIEW` finding blocks export.
- Any unreadable OCR quality blocks export.
- Any high-risk finding kept with `KEEP` blocks export.
- A failed/partial proof check blocks export.
- Strict mode never allows a kept high-risk value to be labelled safe.

Review mode may allow an explicit user decision, but the result must not be labelled “safe” when high-risk content was kept or verification was partial.

### F5 — NO-UPLOAD EVIDENCE

The demo must run with Wi-Fi disabled. The local API binds to `127.0.0.1`, not `0.0.0.0`. There is no analytics SDK, telemetry, external model call, or cloud upload.

The current request cache retains the original content, findings, and document metadata in volatile memory for a maximum of 10 minutes, keyed by a random request ID. It must be cleared on successful redaction/verification, expiry, explicit session cleanup, or server shutdown. Expired or unknown IDs must fail safely.

The UI and receipt must say:

```text
No external upload. Local processing. Volatile session cache: up to 10 minutes.
```

Do not say “nothing was uploaded or stored” because the local in-memory session is storage for the duration of the workflow.

### F6 — COPY-PASTE SHOWDOWN

Create a rival artifact using a common shape/highlight method and label it honestly. First say:

> Adobe’s dedicated Redact tool would also pass a removal test, but the user must find every identifier manually and prove the output.

Run the showdown twice:

1. Normal: the cleaned output passes the proof checks.
2. Hostile: keep one high-risk finding; the proof check fails, names the leak category, returns no file bytes, and blocks download.

### F7 — QR REVEAL, gated

Detect and decode supported secure QR artifacts. Display only limited fields:

- Name present
- Date of birth present
- Gender present
- Address present
- Photo present
- Aadhaar last four digits
- Masked mobile/email indicators
- Signature verdict

Use these signature labels:

```text
VERIFIED_FOR_THIS_ARTIFACT
UNVERIFIED
UNSUPPORTED_AT_CARD
```

Say:

> Signature verified for this presented artifact.

Never say “identity verified.” Cover the complete QR quiet zone during redaction and prove that the output QR no longer decodes.

**Gate:** by hour 1.5, the team must open two real/consented test cards—a PVC card and a phone photo. If not, ship QR detection/cover only or remove the QR demo beat. Never use real personal data in the repository, recording, or presentation.

### F8 — EVIDENCE DRAWER

Each finding displays:

- Rule name
- Validity class
- Confidence band
- Context keywords
- Plain-language explanation
- Sensitivity category
- Masked value only by default

Press-and-hold may reveal a value for at most five seconds in the local UI. Never put raw values in receipts, logs, filenames, or audit summaries.

### F9 — EVIDENCE BOARD

Show a hostile set:

1. WhatsApp-compressed screenshot
2. Angled PVC-card photo
3. Devanagari-digit text
4. Locked bank-statement PDF
5. PDF with a deliberately leaking black box
6. Empty document

Report metrics per entity, never one blended “accuracy” number:

- Precision
- Recall
- False-alarm rate
- Known misses
- Review burden where measured

The acceptance gates are:

1. Zero missed high-risk values in the curated demo set.
2. Zero residual originals in tested exports.
3. Clear human review whenever OCR quality or confidence is insufficient.

---

## 3. Frozen recognizer coverage

| Type | Rule | Ceiling/default |
|---|---|---|
| Aadhaar | 12-digit candidate, first digit 2–9, Verhoeff | `VALIDATED` only when the required rule/context passes; default `MASK` |
| VID | 16 digits beginning with 1 plus context | `FORMAT_ONLY` |
| PAN | Correct structure and entity character | Always `FORMAT_ONLY`; no public checksum claim |
| GSTIN | Indian GST structure and optional check digit | `VALIDATED` or `FORMAT_ONLY` depending on implemented check |
| IFSC | Four letters + `0` + six alphanumeric | Format/check rule only; issuer not checked |
| Bank account | 9–18 digits plus nearby account/bank/IFSC context | `FORMAT_ONLY` |
| UPI | Handle plus known PSP suffix or strong context | `VALIDATED` only for known suffix; otherwise `REVIEW` |
| Phone | Indian mobile format | Format match only; not active-number verification |
| Credit card | 13–19 digits plus Luhn | Checksum/format only; not existence verification |
| Passport | Letter + seven digits plus passport context | `FORMAT_ONLY` |
| Voter ID | Three letters + seven digits plus voter/EPIC context | `FORMAT_ONLY` |
| Driving licence | Indian state/number pattern plus licence context | `FORMAT_ONLY` |
| Vehicle | Indian registration pattern | `FORMAT_ONLY` |
| Email | Standard format | Format match only |
| Health term | Diagnosis, HIV, diabetes, pregnancy, mental health, prescription, test result, etc. | `REVIEW`, mask only with confirmation in Strict mode |

Resolve overlapping matches by longest span, with Aadhaar considered before phone/bank. Normalise Devanagari and Arabic-Indic digits to ASCII before matching.

Confidence formula:

```text
score = format_strength × OCR_factor
format_strength = 1.0 valid / 0.6 format-only / 0.35 review
OCR_factor = min(1, OCR_confidence / 0.9) for OCR; 1.0 for text
HIGH ≥ 0.75, MEDIUM ≥ 0.50, LOW < 0.50
```

A checksum-failing candidate can never be `VALIDATED`.

---

## 4. OCR and file rules

- Primary OCR: **RapidOCR**.
- Fallback: **PaddleOCR** when RapidOCR confidence is low on a clean/degraded scan.
- Keep word-level boxes and token confidence.
- Redact from OCR box coordinates, never character offsets.
- Text input never calls OCR.
- Page quality: `GOOD`, `DEGRADED`, or `UNREADABLE`.
- Unsupported handwriting/script/quality must produce an explicit review-required state.
- Locked PDFs prompt for the password locally. Never derive a password from name/DOB. Unknown password means an honest refusal, not a crash.

Use these UI strings exactly:

```text
We couldn't read this reliably. Upload a clearer photo, or redact the whole page.
This PDF is locked. Enter its password here — it stays on your device and is never stored.
This input is out of scope today (handwriting / unsupported script / scan quality). Nothing was redacted.
Export blocked: one identifier is still in the file (row 3). Fix it or mark it for removal to continue.
No format-defined identifiers found. Names and addresses are not checked (see limitations).
```

No CDN, external fonts, analytics SDK, or external network call is permitted in the offline demo.

---

## 5. Frozen endpoints

```text
POST /api/v1/analyze
POST /api/v1/redact
POST /api/v1/verify
POST /api/v1/session
```

### Analyze

Multipart file or JSON text, with optional local PDF password.

Response contains:

- `request_id`
- `doc.kind`, `pages`, `encrypted`, `ocr_quality`, `warnings`
- `detected_items`
- counts by type/class/sensitivity
- arithmetic line
- review count
- strict-mode block state

A finding contains:

```json
{
  "id": "f_007",
  "type": "AADHAAR",
  "raw_masked": "XXXX XXXX 1234 | f_007",
  "validity_class": "VALIDATED",
  "confidence": 0.98,
  "confidence_band": "HIGH",
  "rule": "aadhaar.verhoeff.v1",
  "reason": "12 digits, first digit 2-9, Verhoeff checksum passes",
  "context_hit": ["aadhaar"],
  "sensitivity": "GOVT_ID",
  "source": "text|ocr|qr",
  "ocr_confidence": 0.93,
  "page": 1,
  "bbox": {"x":120,"y":340,"w":210,"h":30,"space":"pixels"},
  "default_action": "MASK",
  "decided": false
}
```

Raw values do not cross the API response, enter logs, or enter receipts.

### Redact

```json
{
  "request_id": "req_9f2a",
  "decisions": [
    {"id":"f_007","action":"MASK","decided_by_user":true}
  ],
  "strict_mode": true
}
```

The backend retrieves original content/findings from the volatile session cache by `request_id`. It does not accept arbitrary finding IDs disconnected from that session.

If blocked:

```json
{
  "export_blocked": true,
  "sanitized_file_b64": null,
  "block_reason": "High-risk finding was kept",
  "audit": {"verdict":"FAIL"}
}
```

No file bytes may be returned when export is blocked.

### Verify

Re-run the four proof checks on an existing output and return `AuditResult`. A `PARTIAL` result must identify how many checks ran and must not be labelled clean.

### Session

The endpoint reports session status/TTL for the random request ID. The server cache holds original content, findings, and metadata for up to 10 minutes only. Unknown/expired IDs return a controlled error. The cache is cleared after the workflow or explicit cleanup.

---

## 6. Feature freeze line

The team ships:

```text
SCOUT
SHIELD
PROOF OF REMOVAL
VALIDATION TIERS
NO-UPLOAD EVIDENCE
COPY-PASTE SHOWDOWN
QR REVEAL (gated)
EVIDENCE DRAWER
EVIDENCE BOARD
```

The team does not add a feature after freeze unless one existing feature is removed and the acceptance tests remain green.

Never claim:

- 100% accuracy
- Guaranteed privacy
- Identity/authenticity verification
- DPDP/CERT-In/UIDAI certification or endorsement
- A comprehensive national breach/victim count
- That checksums prove a real issued identity
