# PS-06 API Contract

This contract is frozen for the skeleton and feature tracks.

## `POST /api/v1/analyze`

`multipart/form-data`: `content_type` (`text` or `image`), plus `text` for text input or `file` for a PNG/JPG image.

Response fields: `status`, `request_id`, `content_type`, `extracted_text`, `detected_items`, `summary`, `warnings`.

Each detected item contains `id`, `type`, `raw_value`, `value_masked`, `is_valid`, `validation_method`, `validation_reason`, `confidence`, `start`, `end`, `bounding_box`, and `action`.

Supported types: `AADHAAR`, `PAN`, `PHONE`, `BANK_ACCOUNT`, `IFSC`, `UPI`, `CREDIT_CARD`.

Actions: `MASK`, `REMOVE`, `KEEP`. Risk scores: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.

## `POST /api/v1/redact`

JSON: `request_id`, `content_type`, optional `text`/`file_b64`, `detected_items`, and `redaction_rules` containing `{ id, action }`.

Response fields: `status`, optional `sanitized_text`, optional `sanitized_file_b64`, `download_filename`, and `protection_summary`.

## `GET /api/v1/health`

Returns `{ "status": "ok", "ocr_available": boolean }`.

The skeleton returns explicit `501 Not Implemented` responses for feature endpoints after input validation. This is intentional; no fake detection or redaction is permitted in the bootstrap commit.
