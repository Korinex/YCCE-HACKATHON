# PS-06 Privacy Shield — Backend Flow, Explained End to End

*Written for the three backend people. Everything here was executed on a merged checkout of
`feat/backend-core` + `feat/backend-intelligence-jeeya` + `feat/backend-proof-integration` on 2026-10-03.
Function names are real; use them when a judge asks "show me the code".*

---

## 0. One-screen architecture

```text
                        BROWSER (Next.js, localhost:3000)
                                    │  multipart / JSON, relative URLs only
                                    ▼
   FastAPI  ── 127.0.0.1 only ──  POST /api/v1/analyze   ← app/main.py        (B1)
   │                                        │
   │  no disk, no logs, no egress           ├─► analyze_content()              ← app/pipeline.py   (B2)
   │                                        │     ├─ normalize_digits()          Devanagari/Arabic-Indic → ASCII
   │                                        │     ├─ 15 recognizer rules          candidates from regex
   │                                        │     ├─ _in_context(±40 chars)       label/keyword evidence
   │                                        │     ├─ overlap resolution           longest span, Aadhaar beats phone/bank
   │                                        │     ├─ _classify()                  VALIDATED | FORMAT_ONLY | REVIEW
   │                                        │     ├─ score = strength × OCRf     1.0 / 0.6 / 0.35 × min(1, ocr/0.9)
   │                                        │     └─ _masked() + sensitivity + rule name
   │                                        ├─► extract_text_and_boxes()       ← app/ocr_engine.py (B2)
   │                                        │     RapidOCR (onnx, CPU) → word tokens + conf → PaddleOCR fallback
   │                                        ├─► detect_qr_codes()               ← app/qr.py         (B2)
   │                                        │     cv2.QRCodeDetector → UNVERIFIED + quiet-zone cover box
   │                                        └─► SessionStore().create() + register_findings()  ← app/session.py (B1)
   │                                             uuid4 request_id · TTL 600 s · RAM only
   ▼
 GET  /api/v1/session/{id}   → status/TTL only            POST /api/v1/redact      (B1)
   │                                                        ├─ get_session(request_id)  ← rejects unknown/expired
   │                                                        ├─ render_text_redaction()  ← app/redact_engine.py
   │                                                        │    MASK · UIDAI_FIRST8 · REPLACE_TOKEN · REMOVE · KEEP
   │                                                        ├─ render_image_redaction() opaque boxes + EXIF strip + lossless PNG
   │                                                        ├─ sanitize_pdf_bytes()       ← app/pdf_engine.py  ⚠ PLACEHOLDER (see §6)
   │                                                        ├─ verify_cleaned_output()    ← app/verify_service.py (B3)
   │                                                        │    ①DETECTOR_RESCAN ②STRING_SEARCH ③METADATA_INSPECT ④QR_REDECODE
   │                                                        │    any FAILED→FAIL · any UNSUPPORTED→PARTIAL · else CLEAN · ran=0..4
   │                                                        ├─ evaluate_export_gate()     ← app/gate.py (B3)
   │                                                        │    audit≠CLEAN · unresolved REVIEW · READABLE/UNREADABLE OCR
   │                                                        │    kept high-risk · malformed ids → block_reason codes, NO BYTES
   │                                                        ├─ build_receipt()          ← app/receipt.py (B1) privacy-safe
   │                                                        └─ safe_output_filename()   → shielded_8c23cb40.txt
   └────────────────────────────────────────────────────────────────────────────────────────
   POST /api/v1/verify → re-run the 4 checks on an existing output (B3 service, B1 route)
   DELETE /api/v1/session/{id} → explicit wipe ; @app.on_event("shutdown") → SessionStore().shutdown()
```

---

## 1. Stage 1 — normalisation (why offsets stay valid)

`normalize_digits()` uses `str.translate` with a 1:1 digit map (`०१२३४५६७८९`, `٠١٢٣٤٥٦٧٨٩` → `0-9`).
Because it is a **translate**, length and every character index are preserved, so `start/end` found on the
normalised string still point at the original — that is why a Devanagari Aadhaar can be redacted in the raw text.
Test: `test_indic_digit_normalization_preserves_digit_offsets`.

## 2. Stage 2 — candidate detection

`_RULES` is an **ordered** list of 15 `(type, compiled pattern)` pairs:
`AADHAAR, VID, CREDIT_CARD, GSTIN, PAN, IFSC, PASSPORT, VOTER_ID, DRIVING_LICENCE, VEHICLE, UPI, EMAIL, PHONE, BANK_ACCOUNT` + a `_HEALTH` lexicon.
Design points to say out loud:

* **Guard rails on the edges**: `(?<!\d)` / `(?![A-Z0-9])` stop "a digit inside a longer number" matches (so an 18-digit card number is not chopped into two "bank accounts").
* **Low-specificity rules require context**: `BANK_ACCOUNT` (9–18 digits) and `VID` only survive with `account|a/c|bank|ifsc` within ±40 chars; `PASSPORT/VOTER/DL/VEHICLE` are `FORMAT_ONLY` **only with** their context words, otherwise `REVIEW`.
* **Overlap resolution**: sort by `(-length, rule_rank, start)`, then keep a candidate only if it does not intersect an accepted one. `rule_rank` = position in `_RULES`, so **Aadhaar outranks phone/bank on ties** — exactly the frozen rule.
* **Email-vs-UPI guard**: a UPI-shaped handle whose suffix contains a dot is skipped unless UPI context exists — the intent is "gmail.com is an email, not a VPA".

## 3. Stage 3 — classification (the honesty engine)

`_classify()` returns `(tier, reason)`:

| type | rule | tier ceiling |
|---|---|---|
| Aadhaar | `[2-9]` + 12 digits + **Verhoeff** (`_VERHOEFF_D`/`_VERHOEFF_P` tables) | `VALIDATED` on `CHECKSUM_PASS`, else `REVIEW` — a checksum failure can **never** be VALIDATED |
| VID | `1` + 15 digits + context | `FORMAT_ONLY` |
| PAN | `[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]` (the 4th char is the **entity** character) | always `FORMAT_ONLY` — no public checksum claim is made |
| GSTIN | `\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]` | `FORMAT_ONLY` |
| IFSC | `[A-Z]{4}0[A-Z0-9]{6}` | `FORMAT_ONLY`, "issuer not checked" |
| Bank a/c | 9–18 digits + context | `FORMAT_ONLY` / else `REVIEW` |
| UPI | handle + PSP suffix; `_KNOWN_UPI` whitelist (`okaxis, oksbi, ybl, paytm, …`) | `VALIDATED` for known suffix, `REVIEW` otherwise |
| Phone | `[6-9]\d{9}` (+91/0 stripping) | format only, `ACTIVE_STATUS_NOT_CHECKED` |
| Card | 13–19 digits + **Luhn** | `LUHN_PASS; ISSUER_NOT_CHECKED` — never "card exists" |
| Email | format | `FORMAT_ONLY` |
| Health | lexicon (diabetes, HIV, prescription, test result, रक्तचाप, …) | `REVIEW` — masked only with confirmation in Strict mode |

`confidence = format_strength × OCR_factor`, `HIGH ≥ 0.75`, `MEDIUM ≥ 0.50`, `LOW < 0.50`; `review_required = tier is REVIEW or band != HIGH`.
`_masked()` gives `XXXXXXXX2346` (digits) or `r***@gmail.com` (email) or `[REDACTED]` — the masked form is what the UI and receipts use.

## 4. Stage 4 — OCR and QR (image inputs only)

* `ocr_engine._image_array()` decodes **from memory** (PIL → numpy RGB). Nothing touches disk.
* `_rapidocr()` runs RapidOCR (ONNX, CPU) and converts each line into **word tokens** via `_word_tokens()`, which splits on whitespace and apportions the line box by character count. Every token carries `confidence` + `bounding_box` + `engine`.
* Fallback: if RapidOCR is missing/weak (mean conf < 0.55), `_paddleocr()` is tried and wins only if its mean confidence is higher. **Both engines are optional** — every failure path is caught and returns `[]`, which becomes `page_quality = UNREADABLE` → `review_required` → Strict mode blocks the export. That is "OCR unavailable ≠ clean".
* `analyze_image()` rebuilds the text by joining tokens with a single space while assigning `start/end`, so OCR findings still have text offsets **and** pixel boxes. Redaction uses the **box**, never the offset — character offsets in a rendered image are meaningless.
* Quality thresholds: mean conf `<0.35` → `UNREADABLE`, `<0.70` → `DEGRADED`, else `GOOD`; anything not `GOOD` emits `OCR_{quality}_REVIEW_REQUIRED`.
* `qr.detect_qr_codes()` uses `cv2.QRCodeDetector.detectAndDecodeMulti` and returns **only** `{id, decoded, validation_status, fields:[], quiet_zone_box, raw_payload_returned:false}`. The payload is decoded *locally* to know what it is, then deliberately **not** returned. Signature status is `UNVERIFIED` (never "identity verified"), and `_quiet_box()` grows the symbol by 25% on the long side so the redaction covers the **quiet zone**, not just the modules — otherwise a partially covered QR still decodes.

## 5. Stage 5 — session, redaction, proof, gate, receipt

**Session (B1, `session.py`).** `SessionStore` is a process-wide singleton guarded by an `RLock`, holding `dict[request_id → SessionRecord]`. `request_id = uuid4().hex` (unguessable). `expires_at = now + 600 s`. `get()` **lazily evicts** expired records; `cleanup_expired()` sweeps; `shutdown()` clears everything and is registered on FastAPI's `shutdown` event. Only text/bytes + findings + metadata live here — never a filename, never a password, never a log line.

**Redaction (B1, `redact_engine.py`).** `render_text_redaction()` builds `(start, end, action)` spans, sorts them, walks the text with a cursor, and **skips any span that overlaps the cursor** (so nested findings can't corrupt output). Actions:
`MASK` → `X` per char · `REMOVE` → deleted · `REPLACE_TOKEN` → `[REDACTED: TYPE]` · `UIDAI_FIRST8` → `X`×(n−4) + last 4 digits (the UIDAI-mandated shape) · `KEEP` → untouched (and then the gate handles it).
`render_image_redaction()` paints fully opaque rectangles from `bounding_box`, strips EXIF/GPS by re-encoding a **lossless PNG** from memory. `safe_output_filename()` returns `shielded_<8 hex>.<ext>` from `os.urandom` — the original name never survives.

**Proof (B3, `verify_service.py`).** Four checks, verdict algebra `any FAILED → FAIL`, `any UNSUPPORTED → PARTIAL`, else `CLEAN`, with `ran` counting only PASSED/FAILED:

1. `DETECTOR_RESCAN` — feeds the cleaned artifact back through B2's `detect_pii_pipeline()`; finds anything → FAIL. Honest caveat we always state: *this shares the detector's blind spots*.
2. `STRING_SEARCH` — independent of the detector: searches the rebuilt text layer and **raw byte strings** for the original matched values; hit → FAIL with category + region only.
3. `METADATA_INSPECT` — Pillow/struct/zipfile: EXIF, XMP-ish trailers, attached/hidden members, thumbnails.
4. `QR_REDECODE` — re-runs the QR detector on the output and compares count/rectangles against the original high-risk findings; QR still decodes → FAIL.

`AuditResult.to_dict()` is the only serialisable view, and `ResidualHit` carries `category`, `page`, `region` (`span:49-61`) — never the matched string.

**Gate (B3, `gate.py`).** `evaluate_export_gate()` returns exactly `{"export_blocked": bool, "block_reasons": [codes]}`. It validates the *shape* of every input too (`ERR_MALFORMED_FINDINGS`, `ERR_UNKNOWN_DECISION_ID`, `ERR_DUPLICATE_FINDING_ID`, `ERR_UNSUPPORTED_ACTION`, `ERR_KEEP_WITHOUT_USER_DECISION`), then blocks on: `BLOCK_AUDIT_NOT_CLEAN` (also covers `PARTIAL` — "3/4 ran" is never a green tick), `BLOCK_STRICT_UNRESOLVED_REVIEW`, `BLOCK_STRICT_HIGH_RISK_KEEP`, `BLOCK_STRICT_UNREADABLE_OCR`. Reason codes are fixed strings: no IDs, no user content, deterministic de-duplication. **A blocked response carries no file bytes.**

**Receipt (B1, `receipt.py`).** `build_receipt()` emits exactly: `run_id, app_version, timestamp, input_kind, page_count, category_counts, confidence_band_counts, actions_by_category, review_pages, review_regions, ocr_warnings, residual_verdict, local_processing_only, session_ttl_seconds, kyc_advisory, not_legal_certification`. `redact_receipt_text()` is a second-line defence that scrubs anything identifier-shaped from free text, so even a buggy caller cannot leak into the receipt. `not_legal_certification` exists because the honest label is part of the schema, not a footnote.

**Public boundary (B2, `api_boundary.py`).** `finding_for_api()` **whitelists** fields (`id, type, raw_masked, validity_class, confidence, confidence_band, rule, reason, context_hit, sensitivity, source, ocr_confidence, page, bbox, default_action, decided`) and drops `raw_value`; it even re-masks to `[REDACTED]` if the raw value would survive inside the masked form. `raw_masked` = `XXXXXXXX2346 | f_49_61_aadhaar` — masked value plus opaque finding id, per the frozen contract.

---

## 6. Verified run on the merged tree (2026-10-03) — paste this if anyone doubts us

```text
STAGE 1 SCOUT: 10 findings
  GSTIN   FORMAT_ONLY MEDIUM FINANCIAL  XXXXXXXXXXXF1Z5 | f_24_39_gstin
  AADHAAR VALIDATED   HIGH   GOVT_ID    XXXXXXXX2346 | f_49_61_aadhaar
  PAN     FORMAT_ONLY MEDIUM GOVT_ID    XXXXXX234F | f_69_79_pan
  PHONE   FORMAT_ONLY MEDIUM CONTACT    XXXXXX3210 | f_87_97_phone
  UPI     VALIDATED   HIGH   FINANCIAL  [REDACTED] | f_104_115_upi
  AADHAAR REVIEW      LOW    GOVT_ID    XXXXXXXX9998 | f_157_169_aadhaar   ← order number, checksum fails
  HEALTH_TERM REVIEW  LOW    HEALTH     [REDACTED]  ×3
STAGE 2 SESSION: request_id=aaedd199… expires in 600s
STAGE 3 SHIELD: output == input → True      ⚠ redaction was a NO-OP (see fix ①)
STAGE 4 PROOF : verdict=FAIL ran=4/4  (DETECTOR_RESCAN FAILED, STRING_SEARCH FAILED,
                METADATA_INSPECT PASSED, QR_REDECODE PASSED)
STAGE 5 GATE  : blocked=True ['BLOCK_AUDIT_NOT_CLEAN','ERR_UNKNOWN_OCR_QUALITY','ERR_INVALID_VALIDITY_CLASS']
```

…then with the 4-line adapter below applied:

```text
NORMAL  changed=True verdict=CLEAN ran=4 blocked=False []
  Vendor: Rahul S | GSTIN XXXXXXXXXXXXXXX | Aadhaar: XXXXXXXXXXXX | PAN: XXXXXXXXXX | Mobile XXXXXXXXXX | UPI XXXXXXXXXXX
HOSTILE changed=True verdict=FAIL blocked=True ['BLOCK_AUDIT_NOT_CLEAN','BLOCK_STRICT_HIGH_RISK_KEEP']
  residual = (AADHAAR, page=None, region='span:49-61')   ← named category, raw value never printed
UIDAI_FIRST8 + REMOVE →  "Aadhaar: XXXXXXXX2346 | PAN: "
```

**Say this in the demo:** "our first merged run produced **no redaction at all** — a field-name mismatch between two tracks. Nothing shipped, because the proof layer and the gate said FAIL. A tool that prints a green tick would have exported the Aadhaar. This is the argument for PROOF OF REMOVAL in one sentence."

### The four fixes that make the merged path green (all tiny, all owned)

| # | Gap | Fix | Owner |
|---|---|---|---|
| ① | `render_text_redaction()` reads `char_span`/`span`; B2 emits `start`/`end` → **silent no-op, fails OPEN** | B1 accepts both: `span = item.get("char_span") or (item["start"], item["end"])` — or B2 emits `char_span` in `analyze_content` | B1 (1 line) + B2 |
| ② | Gate expects `validity_class`; B2 emits `validation_tier` → every run blocked with `ERR_INVALID_VALIDITY_CLASS` | emit both keys in the adapter (or rename in `api_boundary`) | B2 (1 line) |
| ③ | Gate's `_SENSITIVITY = {GOVT_ID, FINANCIAL, HEALTH, CONTACT}` but B2 also emits `VEHICLE_ID`/`OTHER` → `ERR_INVALID_SENSITIVITY` | agree the enum, add the two values to the gate set (or fold into `OTHER`) | B3 + B2 |
| ④ | Text path passes `ocr_quality=None` → `ERR_UNKNOWN_OCR_QUALITY` even for a clean text run | gate: treat `None` as `GOOD` for `content_type == "text"` | B3 |
| ⚠ | `pdf_engine.sanitize_pdf_bytes()` returns `%PDF-1.4\n<32-byte sha256>\n%%EOF` — **not a redacted PDF**; it is a placeholder that looks like success | do **not** offer PDF in the demo; state "PDF path not implemented", or land the real renderer per F2 (flatten pages, drop text layer/annotations/embedded files) | B1 — **before freeze** |
| ⚠ | `/api/v1/analyze` and `/api/v1/redact` still `raise HTTPException(501)`; `/api/v1/verify` route does not exist | wire B2's `analyze_content`, B1's engines, B3's `verify_cleaned_output` + `evaluate_export_gate` | B1 — the only blocker to the live demo |

Test state at that merge: `server/tests` **30 passed**; `integration` **66 passed, 9 failed** — 8 of the 9 are B3 audit expectations that assume B2's stub / a missing `cv2`, and 1 is the deliberate golden-path blocker `assert 501 == 200 → "BLOCKED: Backend 1 analyze/session API is still unimplemented"`.

---

## 7. What runs when the user clicks each button (map for the Q&A)

| UI action | Function you name out loud |
|---|---|
| "Analyze" on pasted text | `pipeline.analyze_content("text", …)` → `detect_text()` → 15 rules → `_classify()` → `SessionStore().create()` |
| "Analyze" on an image | `ocr_engine.extract_text_and_boxes()` → word boxes → `detect_text(text, tokens)` → `qr.detect_qr_codes()` for the cover box |
| Evidence drawer | `api_boundary.finding_for_api()` — field whitelist, `raw_value` dropped |
| "Mask / UIDAI_FIRST8 / Remove" | `redact_engine.render_text_redaction()` / `render_image_redaction()` |
| "Verify" | `verify_service.verify_cleaned_output()` → 4 checks → `AuditResult` |
| "Download" | `gate.evaluate_export_gate()` first → bytes only if `export_blocked == False` → `receipt.build_receipt()` + `safe_output_filename()` |
| "Clear my session" | `delete_session(request_id)`; also fires on TTL expiry, on export, and on server shutdown |

## 8. Security boundaries to recite from memory

1. `uvicorn --host 127.0.0.1` (never `0.0.0.0`); no CDN, no external fonts, no analytics SDK, no outbound call — demo runs with **Wi-Fi off**.
2. Session in RAM only, `uuid4` key, **600 s** TTL, cleared on export/expiry/cleanup/shutdown. Never written to disk, never logged (no request bodies, no raw matches, no OCR text, no filenames, no passwords).
3. Public finding = field whitelist. `raw_value` exists **only** inside `SessionRecord` for the length of the workflow.
4. Fail-closed everywhere: unknown/expired `request_id`, decision ids not in the session, malformed JSON, missing OCR engine, unreadable page, `PARTIAL` proof, kept high-risk value → **refuse**, with a human-readable reason.
5. PDF passwords are used in memory for that one request and never derived from name/DOB; a wrong password is an honest refusal, not a crash.
6. Reproducibility: `requirements.txt` (app) + `requirements-intelligence.txt` (pinned OCR/QR profile: `Pillow==11.3.0`, `numpy==1.26.4`, `rapidocr_onnxruntime==1.4.4`, `onnxruntime==1.20.1`, `opencv-python==4.10.0.84`), Paddle profile optional. All open source, no paid service, no model download at demo time (warm the cache while connected, then verify offline).
