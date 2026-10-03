# Backend 3 integration status

Backend 3's audit and export gate are implemented in `server/app/audit.py`,
`server/app/verify_service.py`, and `server/app/gate.py`. `AuditResult` is a
plain dataclass containing per-check status, safe residual category/page/region,
method notes, a UTC timestamp, and the count of checks that actually ran.
Audit records do not contain matched strings, QR contents, or file bytes.

The end-to-end text path is **BLOCKED / NOT READY** in this checkout. Backend 1
must implement the `/api/v1/analyze` session-backed route, the `/api/v1/redact`
redaction/export route, and the server-side session data needed to associate
original findings and QR rectangles with cleaned output. The current route
returns HTTP 501 for analysis and redaction. Backend 2 must provide its detector
pipeline and image OCR extractor in this checkout; until then detector rescan
is unsupported and image string search cannot run. QR signature verification
remains deferred; rectangle/count checks do not establish authenticity.

The integration test uses synthetic text only and asserts the real analyze API
response. It is expected to fail with an explicit Backend 1 blocker until the
routes are implemented. Gate and audit unit tests remain independently
executable. No real Aadhaar, PAN, or bank document is used.
