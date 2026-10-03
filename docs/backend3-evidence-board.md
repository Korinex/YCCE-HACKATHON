# Backend 3 per-entity evidence board

**Overall status: BLOCKED.** The current checkout's `server/app/pipeline.py` raises `NotImplementedError`; no entity detector output can be measured here. Synthetic literal strings in audit tests exercise residual detection, not detector precision/recall. No values below are estimates.

| Entity | True positives / denominator | False positives / denominator | Precision | Recall | False-alarm count/rate | Known misses | Review burden |
|---|---:|---:|---:|---:|---:|---|---|
| AADHAAR | BLOCKED — detector unavailable | BLOCKED — detector unavailable | BLOCKED | BLOCKED | BLOCKED | BLOCKED — detector unavailable | BLOCKED |
| PAN | BLOCKED — detector unavailable | BLOCKED — detector unavailable | BLOCKED | BLOCKED | BLOCKED — detector unavailable | BLOCKED | BLOCKED |
| PHONE / CONTACT | BLOCKED — detector unavailable | BLOCKED — detector unavailable | BLOCKED | BLOCKED | BLOCKED — detector unavailable | BLOCKED | BLOCKED |
| BANK_ACCOUNT / FINANCIAL | BLOCKED — detector unavailable | BLOCKED — detector unavailable | BLOCKED | BLOCKED | BLOCKED — detector unavailable | BLOCKED | BLOCKED |
| HEALTH | BLOCKED — detector unavailable | BLOCKED — detector unavailable | BLOCKED | BLOCKED | BLOCKED — detector unavailable | BLOCKED | BLOCKED |

Required integration: Backend 2 must provide its actual detector and OCR implementation in this checkout. Then run a versioned synthetic corpus with labeled positive/negative examples per entity and publish the raw counts and denominators before calculating metrics. Do not combine entities or substitute unit-test literal searches for detector evaluation.
