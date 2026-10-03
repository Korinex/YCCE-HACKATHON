# Backend 2 detection handoff

Backend 1 can import `analyze_content` from `app.pipeline`. It accepts
`("text", str)` or `("image", bytes)` and returns the following server-side
result:

```python
{
    "detected_items": list[InternalFinding],
    "ocr_tokens": list[OCRToken],
    "qr_findings": list[QRFinding],
    "document": {
        "page_quality": "GOOD" | "DEGRADED" | "UNREADABLE" | None,
        "warnings": list[str],
        "qr_status": "AVAILABLE" | "UNAVAILABLE" | "NOT_APPLICABLE",
    },
}
```

For text, `ocr_tokens` and `qr_findings` are empty and page quality is `None`.
For images, OCR quality and warnings come from the image pipeline. QR findings
contain only decode status and cover bounds; decoded payloads and fields are
never returned. `UNAVAILABLE` means OpenCV QR detection is not installed and
must not be treated as "no QR present."

`detected_items[*].raw_value` and `ocr_tokens[*].text` contain original sensitive
values. Keep the complete result in the server-side `SessionRecord`; never
serialize it into an API response. To build public finding summaries, pass only
the internal findings through `findings_for_api` in `app.api_boundary`. The
public adapter discards `raw_value` and exposes the masked form, safe reason,
confidence, source, and bounds.

Backend 2 owns this detection interface and its implementation. Backend 1 owns
calling it from `/api/v1/analyze`, validating request limits, creating the
session, and selecting only safe response fields.
