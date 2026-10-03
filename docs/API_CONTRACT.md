# PS-06 API Contract

This contract describes the currently implemented Backend-1 API boundary. Raw source content and raw findings are server-only. The golden path is not complete until Backend 2 and Backend 3 provide their real implementations.

## `POST /api/v1/analyze`

`multipart/form-data`: `content_type` (`text`, `image`, or `pdf`), plus `text` for text input or `file` for a PNG/JPG/PDF input. A PDF may include a user-supplied local `password`; it is never persisted or returned.

The route validates file content, enforces a 10 MiB upload limit and a 10-page PDF limit, and stores accepted source content only in the volatile session. It calls the typed Backend-2 adapter. Because the repository's Backend-2 seam is still a stub, analysis currently fails safely with HTTP 503 instead of returning fabricated findings.

Response fields when Backend 2 is available: `status`, `request_id`, `content_type`, `extracted_text` (null for privacy), `detected_items`, `summary`, `warnings`, and safe `document_metadata`.

Each detected item contains only safe fields such as `id`, `type`, `value_masked`/`masked_display`, `is_valid`, `validation_method`, `validation_reason`, `confidence`, `confidence_band`, `char_span`, normalized `bbox`, `context_hit`, `page`, `rule`, and `reason`. It never contains `raw_value`, `original_filename`, raw context, OCR text, passwords, or deterministic hashes.

Supported categories include `AADHAAR`, `PAN`, `PHONE`, `BANK_ACCOUNT`, `IFSC`, `UPI`, `CREDIT_CARD`, `EMAIL`, `ADDRESS`, `MEDICAL`, and `NAME`.

Actions: `MASK`, `REMOVE`, `KEEP`, `UIDAI_FIRST8`, and `REPLACE_TOKEN`. Safe validity classes are `VALIDATED`, `FORMAT_ONLY`, and `REVIEW`; the latter two do not claim identity or issuer authenticity.

QR signature verification is deferred. QR-related findings may only use `UNVERIFIED` or `UNSUPPORTED_AT_CARD`.

## `POST /api/v1/redact`

JSON: `request_id`, `decisions`, and `strict_mode`. Each decision is `{ id, action, decided_by_user: true }`. Content and findings are retrieved from the volatile server-side session.

Response fields: `status`, optional `sanitized_text`, optional `sanitized_file_b64`, `download_filename`, `protection_summary`, and an optional safe `block_reason`.

The route never accepts client-submitted content or findings. In strict mode, unsafe high-risk `KEEP` decisions are rejected. Successful export clears the session. Output names use `shielded_<random8>.<ext>`. A blocked export contains `sanitized_file_b64: null` and no file bytes.

## `GET /api/v1/health`

Returns only safe capability facts:

```json
{
  "status": "ok",
  "ocr_available": false,
  "pdf_available": true,
  "qr_available": false,
  "mode": "LOCAL"
}
```

`ocr_available`, `pdf_available`, and `qr_available` reflect this local installation and are not claims about production availability.

## `POST /api/v1/verify`

JSON: `request_id`, optional `cleaned_content_type`, optional `cleaned_bytes_b64`, optional public residuals, and `strict_mode`.

The route calls the typed Backend-3 `verify_cleaned_output` boundary. Backend 3 is not present in this repository, so the adapter returns `PARTIAL` with an unsupported check. Strict-mode export is fail-closed: the response is blocked, contains `sanitized_file_b64: null`, and the session is cleared. No `CLEAN` result is fabricated.

## Session and processing limits

`POST /api/v1/session` creates a volatile request session. Sessions expire after 600 seconds and are cleared after export, verification, expiry, cleanup, or shutdown.

The service accepts text, PNG/JPG images, and PDF files up to 10 MiB. PDF processing is limited to 10 pages. The service is local-only and should be started on `127.0.0.1`; no external upload or network call is required.

PDF mode is reserved for `flatten` or `page_images`. Secure PDF rendering, flattening, metadata/XMP removal, attachment removal, and source-text absence are **NOT VERIFIED** in the current environment because no approved PDF library is installed. Do not treat the current PDF path as production-secure.

Install and offline startup:

```bash
cd server
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

No raw `raw_value` or `original_filename` is present in public API responses. Raw findings, source content, passwords, OCR text, and raw context remain server-side only.

## PDF processing

PDF processing uses PyMuPDF 1.28.2, pinned in `server/requirements.txt`. PyMuPDF is dual-licensed under AGPL-3.0-or-later or a commercial Artifex license; this branch uses AGPL for local hackathon evaluation. Install dependencies before offline startup with `pip install -r server/requirements.txt`. Runtime PDF processing is in memory and does not require network access. Production redistribution requires AGPL compliance or a commercial PyMuPDF license.
