# PS-06 Privacy Shield — Additional Five-Criteria Task List

## Purpose

This is the **additional work after each person’s assigned feature track**. It does not remove any of the nine frozen features. It makes the prototype defensible on:

1. Feasibility
2. Viability
3. Scalability
4. Stakeholder comfort
5. Economic comfort

The team must complete this list after Backend 1 finishes the core API/session/redaction work and before final demo freeze.

---

## Current repository status

Jeeya’s remote branch currently points to commit `9e8e98e` and contains the Backend 2 intelligence work plus a large set of agent/workflow documentation files. The working branch is clean in the local clone.

The visible remote currently exposes `origin/main` and Jeeya’s branch. Backend 1 and Backend 3 branches are not visible in this clone yet, so their completion must be confirmed through their PRs/branch links before integration.

Before merging, review the large `.agent/`, `.agents/`, `.gsd/`, and root workflow additions on Jeeya’s branch. Keep them only if the team intentionally wants them in the repository; otherwise isolate them from the product PR because they are unrelated to the PS6 runtime and increase review/merge noise.

---

# A. Shared integration tasks — all four people

These are mandatory and cannot be assigned to only one person.

## A1. Create the integration branch/PR

After the four task branches are ready, create one integration branch from the agreed base. Do not merge directly into `main` while the golden path is unstable.

```text
integration/ps06-golden-path
```

The integration branch must combine:

```text
SCOUT → SHIELD → PROOF OF REMOVAL → RECEIPT → DOWNLOAD
```

## A2. Confirm one contract owner

Backend 1 owns the final API/schema files. No other person edits the contract during integration. Backend 2 supplies the internal finding fixture. Backend 3 supplies the audit/gate fixture. Frontend consumes the public response only.

Any contract discrepancy must be written in the PR before changing code.

## A3. Run the same synthetic golden fixture

Use one synthetic fixture containing:

- A Verhoeff-passing Aadhaar test vector: `234123412346`
- A valid PAN-shaped value
- A phone number
- A known PSP UPI handle
- A normal email that must not be classified as UPI
- A failed-checksum 12-digit order number: `999999999998`
- One health keyword for `REVIEW`

No real identity data may be used in the repository, screenshots, recordings, or presentation.

## A4. Run the hostile fixture matrix

All four people must observe and sign off on these tests:

| Input | Required result |
|---|---|
| Different text with different identifiers | Output changes; no hardcoding |
| Different image layout | Bounding boxes change dynamically |
| Failed Aadhaar checksum | Never `VALIDATED` |
| Ordinary email | Must not become UPI merely because it contains `@` |
| Blurry/low-confidence image | Review-required warning; no clean claim |
| Locked PDF without password | Controlled refusal; no crash |
| `.txt` renamed `.png` | Controlled invalid-file error |
| Kept high-risk finding in Strict mode | Export blocked; no file bytes |
| Residual value in output | Proof fails; category/region shown without raw value |
| Unsupported proof check | `PARTIAL`, never `CLEAN` |
| Wi-Fi disabled | Full local path still works; no external calls |

## A5. Review raw-value leakage

Search the final product and generated artifacts for:

```text
raw_value
original_filename
password
OCR text
full Aadhaar
full PAN
full phone
full email
```

Raw values may exist only in the server’s volatile session/internal finding during the active workflow. They must not appear in API responses, receipts, logs, filenames, browser clipboard, screenshots, or audit summaries.

## A6. Run the complete demo twice

- **Normal run:** all required decisions made; proof passes; download enabled.
- **Hostile run:** one high-risk finding kept; proof fails; download blocked; no sanitized bytes returned.

The person running the demo must be able to explain every visible state without opening the source code.

---

# B. Backend 1 — Khudaija additional tasks

## B1. Add a runtime envelope

Document and enforce:

```text
Bind address: 127.0.0.1
Maximum upload: 10 MB
Maximum PDF pages: 10
Session TTL: 10 minutes
Maximum OCR time per page: defined and tested
No raw content on disk
No raw content in logs
No external network calls
```

If the exact OCR time limit is not yet known, measure it on the team’s demo machine and document the observed value rather than inventing a guarantee.

## B2. Finish the server lifecycle

Confirm that:

- session data is cleared after successful export/verification;
- expired sessions are removed;
- unknown request IDs fail safely;
- shutdown clears the in-memory cache;
- PDF passwords are never written to session receipts or logs;
- blocked exports return `sanitized_file_b64: null`.

## B3. Add a health/capability response

The health response should expose only safe operational facts:

```json
{
  "status": "ok",
  "ocr_available": true,
  "pdf_available": true,
  "qr_available": false,
  "mode": "LOCAL"
}
```

Do not expose machine paths, environment variables, secrets, or raw model details.

## B4. Add dependency and installation documentation

Record:

- Python version
- OCR engine versions
- PDF library versions and licenses
- QR library version/license
- expected model size
- install command
- offline startup command
- known unsupported environments

This closes feasibility and economic comfort for the team.

## B5. Add resource protection

Reject or fail safely on:

- oversized upload;
- too many PDF pages;
- malformed image/PDF;
- repeated concurrent requests;
- session cache overflow;
- OCR timeout.

The error must be user-readable and must not include raw uploaded content.

---

# C. Backend 2 — Jeeya additional tasks

## C1. Publish the Backend 2 interface fixture

Create a small synthetic JSON fixture showing:

- one `VALIDATED` finding;
- one `FORMAT_ONLY` finding;
- one `REVIEW` finding;
- one OCR finding with `bbox` and `ocr_confidence`;
- one failed-checksum candidate;
- one ordinary email that is not UPI.

The fixture must use masked values only and must match the final schema expected by Backend 1 and the Frontend.

## C2. Freeze the OCR environment

Document and test:

- RapidOCR version/configuration;
- PaddleOCR fallback version/configuration, if installed;
- language packs actually supported;
- image dimensions and formats tested;
- expected CPU/RAM requirements;
- average scan time on the demo machine;
- what happens when OCR dependencies are unavailable.

Do not claim general Indian-language or handwriting support. State the exact tested conditions.

## C3. Add recognizer explainability

Every finding must expose a safe explanation such as:

```text
CHECKSUM_PASS
FORMAT_MATCH
CONTEXT_MATCH
ISSUER_NOT_CHECKED
OCR_REVIEW
```

The explanation must never imply that a person, account, card, phone, or identity document was verified with an issuer.

## C4. Add performance and false-positive evidence

Measure on the final synthetic test set:

- per-entity precision;
- per-entity recall;
- false-alarm count;
- known misses;
- average text scan time;
- average image scan time;
- OCR fallback frequency.

Do not report one blended “accuracy” score.

## C5. Add dependency/license safety

Write a short dependency note covering RapidOCR, PaddleOCR, QR decoding, and any model files. Confirm that the chosen packages can be used in the hackathon repository and that model downloads are not required during the offline demo.

## C6. Add graceful degradation fixtures

Provide fixtures for:

- OCR unavailable;
- OCR empty result;
- low-confidence OCR;
- unsupported script/handwriting;
- QR unsupported;
- QR present but unverified.

Backend 1 and Frontend must be able to test these without modifying your detector code.

---

# D. Backend 3 — Shifa additional tasks

## D1. Own the five-criteria acceptance report

Create a short final report with evidence for:

```text
FEASIBILITY: setup and runtime measurements
VIABILITY: user completes golden path
SCALABILITY: stated prototype boundary and future architecture
STAKEHOLDER COMFORT: privacy/limitation/error review
ECONOMIC COMFORT: zero paid services and dependency envelope
```

## D2. Add a user acceptance test

A person who did not write the feature should be able to:

1. upload/paste input;
2. understand the findings;
3. choose an action;
4. understand a blocked export;
5. complete a clean export when the proof passes;
6. read the receipt without seeing raw PII.

Record any confusion as a UX blocker for the Frontend teammate.

## D3. Add an operational acceptance test

Run from a clean clone or documented clean environment:

```text
install → start local server → start client → run golden path → run hostile path
```

Also run with Wi-Fi disabled and record that no external request is required.

## D4. Add a scalability boundary statement

Put this in the README or demo documentation:

> This prototype is a single-user, local-first reference implementation. A production deployment would need isolated processing workers, authentication, quotas, encrypted short-lived session storage, concurrency limits, deletion monitoring, and tenant isolation. Those controls are outside this offline prototype.

This is not a feature removal; it is an honest deployment boundary.

## D5. Validate evidence-board numbers

Regenerate the evidence board from the actual final fixtures and final code. Include known misses. Do not manually type numbers from memory and do not combine entities into a single accuracy number.

## D6. Perform the privacy red-team review

Check:

- raw PII in logs;
- raw PII in exceptions;
- raw PII in receipts;
- raw PII in filenames;
- raw PII in copied text;
- raw PII in browser storage;
- original content after session TTL;
- file bytes returned after blocked export.

---

# E. Frontend additional tasks

## E1. Add stakeholder-comfort UI

Add visible, plain-language states for:

- format-only result;
- checksum passed but issuer not checked;
- OCR review required;
- unsupported input;
- blocked export;
- partial proof result;
- local-session TTL.

The user should understand what the tool knows and does not know.

## E2. Protect the user from accidental disclosure

Confirm that:

- the raw reveal auto-hides within five seconds;
- raw values are never copied to clipboard;
- receipt copy copies only the privacy-safe receipt;
- download filenames contain no original filename/identifier;
- the UI does not show a green “safe” result for `PARTIAL` proof;
- Strict mode is visibly ON by default;
- keeping high-risk data in Strict mode explains why export is blocked.

## E3. Add first-run usability

A new user must see:

- what input types are supported;
- that processing is local;
- that the session may remain in memory for up to 10 minutes;
- what happens when OCR fails;
- what the limitation boundary is.

Do not hide this only in README text.

## E4. Add accessibility and low-stress states

Check keyboard navigation, visible focus, readable contrast, error announcements, and clear labels for Mask/Remove/Keep. Blocked export should explain the next action, not merely show an error code.

## E5. Add the 60-second demo path

The Frontend should provide a simple path for:

```text
paste synthetic text → show findings → keep one hostile finding → show blocked export
```

The extended demo can then show image/PDF/QR/evidence features.

---

# F. Final merge checklist

No final merge until all are true:

- Backend 1 confirms the final API/session contract.
- Backend 2 fixture is consumed by Backend 1 and Frontend.
- Backend 3 audit/gate fixture is consumed by Backend 1 and Frontend.
- Frontend runs against mocks and live API.
- Normal golden path passes.
- Hostile keep-one-finding path blocks export.
- Wi-Fi-off run passes.
- Session TTL/cleanup is tested.
- No raw PII leaks into logs, receipts, filenames, clipboard, or browser storage.
- PDF/QR degraded states are honest and tested.
- Dependency versions/licenses are documented.
- The final setup is reproducible without paid APIs.
- The five-criteria acceptance report is complete.
- CodeRabbit review blockers are resolved.
- The final branch contains no unrelated AI-agent scaffolding unless explicitly approved.

## Final rule

The nine frozen features remain. These tasks do not add another product feature. They add the evidence, operational limits, user safeguards, and acceptance proof needed to show that the existing prototype is feasible, viable, scalable within its stated boundary, comfortable for stakeholders, and economically practical.
