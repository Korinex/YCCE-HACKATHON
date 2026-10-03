# Requirements

## Functional requirements
1. Accept text, image, and PDF inputs safely.
2. Detect PII candidates in supported content types.
3. Keep raw values only in volatile memory and never return them to clients.
4. Produce public-safe findings with normalized spans and bounding boxes.
5. Maintain request-scoped session state with TTL expiry and cleanup.
6. Support redaction decisions and fail-closed verification/export protections.
7. Ensure outputs never leak source text, filenames, OCR text, or raw sensitive values.

## Non-functional requirements
- Bind local server to 127.0.0.1 only.
- Keep session data in memory only.
- Reject unknown or expired request IDs.
- Strip metadata and hidden elements from protected outputs.
- Use safe, random output filenames.
