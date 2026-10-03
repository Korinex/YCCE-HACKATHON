# Backend 3 privacy red-team review

Review date: 2026-10-03. Synthetic values only. Backend 3 code was reviewed and its audit/gate output leakage tests are included in the test suite. This is not a full product security audit.

| Surface / attack | Evidence and status | Owner / follow-up |
|---|---|---|
| Raw PII in Backend 3 logs | **PASS (code review)** — Backend 3 emits no log calls. Gate output uses fixed reason codes. Automated tests assert raw synthetic strings are absent from results. | Backend 3 regression tests |
| Raw PII in Backend 3 exceptions | **PASS (code review)** — caught exceptions contribute only the exception class name or a fixed safe code; input exception text is not returned. Unexpected exceptions escaping helper boundaries remain an integration risk. | Backend 3; retain synthetic leak tests |
| Raw PII in receipts | **NOT TESTED** — no receipt-producing route is implemented in this checkout. | Backend 1 must implement receipt contract and add leakage tests |
| Original filename leakage | **NOT TESTED** — Backend 3 accepts bytes/content type and does not generate filenames; API download naming is outside its owned code. | Backend 1 |
| Copied text / clipboard | **NOT TESTED** — browser UI behavior was not exercised. | Frontend |
| Browser storage | **NOT TESTED** — no browser storage review was performed. | Frontend |
| Session content after TTL / deletion | **NOT TESTED** — Backend 1 owns session storage, expiry, and deletion monitoring; those interfaces are absent here. | Backend 1 |
| File bytes returned on blocked export | **NOT TESTED / BLOCKED** — redact/export route returns HTTP 501; there is no response body to verify for the blocked-export case. | Backend 1 must enforce gate before serialization/download and test no bytes are returned |
| QR payload or authenticity disclosure | **PASS (Backend 3 code review)** — QR payloads are not included in audit output. Signature/authenticity remains UNVERIFIED and unsupported. | Backend 1/2 integration must preserve this limitation |
| Unsupported content / empty OCR | **PASS (unit tests)** — unsupported formats and unavailable/empty OCR produce PARTIAL/UNSUPPORTED rather than CLEAN. | Backend 3 |

Automated coverage: `integration/test_audit.py`, `integration/test_gate.py`, and `integration/test_break_matrix.py` use synthetic inputs. Human UX, frontend, session lifecycle, and blocked-download review remain outstanding.
