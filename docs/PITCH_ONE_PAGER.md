# PS-06 Privacy Shield — Pitch One-Pager (read this 10 minutes before walking on stage)

**Team:** Khudaija (Backend 1 — core/API/SHIELD) · Jeeya (Backend 2 — SCOUT/OCR/QR) · Shifa (Backend 3 — PROOF/gate/QA) · Frontend
**Repo baseline:** `Korinex/YCCE-HACKATHON` skeleton `c851779` · Feature freeze: F1–F9, remove one before adding one.

---

## 1. The sentence (say it exactly, verbatim from the features guide)

> Before you share this text, image, or document, Privacy Shield finds likely sensitive data, explains why it matched, removes it irreversibly, verifies the cleaned artifact, and produces a privacy-safe audit summary.

## 2. The 30-second hook

"Every Aadhaar, PAN, bank statement and prescription in India moves as a **copy**: a screenshot on WhatsApp, a forwarded PDF, an attachment in an email. The UIDAI core database is hardened and reports no breach of its own DB. The leak is never the vault — it is the **photocopy you sent**. Today that last step is 'human remembers to blur it'. We turned that step into a **tool that proves it worked** before the file leaves your machine: detect, explain, redact irreversibly, re-verify the output, and only then hand you a download."

## 3. The claim ladder — never skip a rung

| Rung | Say this | Never say this |
|---|---|---|
| Detection | "found 5 likely identifiers" | "we detected everything" |
| Explanation | "12 digits, first digit 2–9, Verhoeff checksum passes" | "we verified this person" |
| Redaction | "replaced and the page was re-rendered" | "guaranteed anonymous" |
| Proof | "4/4 checks ran, verdict CLEAN" | "100% safe" |
| Law | "supports your masking obligation" | "makes you DPDP-compliant / UIDAI-approved" |

## 4. 90-second demo (the only version that is guaranteed to work today)

1. Paste the synthetic 5-line document → **SCOUT**: findings list with `VALIDATED / FORMAT_ONLY / REVIEW`, masked value only (`XXXXXXXX2346`), confidence band, rule name.
2. Click one finding → **EVIDENCE DRAWER**: rule `aadhaar.verhoeff.v1`, context hit `aadhaar`, reason `CHECKSUM_PASS; ISSUER_NOT_CHECKED`.
3. Press-and-hold → value reveals for ≤5 s → auto-hides. Say: "the raw value never leaves the process; the API response is built from a field whitelist."
4. Choose `UIDAI_FIRST8` for Aadhaar → **SHIELD**: output line becomes `Aadhaar: XXXXXXXX2346`.
5. Click **Verify** → **PROOF OF REMOVAL**: detector re-scan + raw-string search + metadata + QR re-decode → `CLEAN, 4/4 checks ran` → download `shielded_8c23cb40.txt`.
6. **Hostile run** — click `KEEP` on the Aadhaar → `Export blocked`, `verdict FAIL`, residual reported as `AADHAAR, span:49-61`, **no bytes returned**. Closing line: "the tool refused to call itself safe. That refusal is the product."

*Extended (if you have 5 min):* image path (OCR box redaction + quiet-zone QR cover) → the `OCR_DEGRADED` warning path → Evidence Board per-entity table → Copy-Paste Showdown vs a black box.

## 5. Numbers you are allowed to state (each has a source and a date)

| # | Number | Source / date | Where to use it |
|---|---|---|---|
| 1 | Average cost of a data breach in India **₹220 million**, up 13% YoY (₹195M in 2024) | IBM *Cost of a Data Breach 2025*, 7 Aug 2025 | opening hook |
| 2 | **Shadow AI** is a top-3 breach cost driver in India: **+₹17.9M**; only **42%** of orgs have an AI policy | same IBM report | why local/no-upload matters |
| 3 | Global average breach **$4.44M**; average lifecycle **241 days** (181 to identify, 60 to contain) | IBM 2025 (via StationX 2026 summary) | framing "last-mile" |
| 4 | DPDP Rules notified **13 Nov 2025** (G.S.R. 846(E)); Data Protection Board stood up the same day; **Rule 7** = notify Board without delay + detailed report in **72 hours** + tell affected people | MeitY/Legal500/India Briefing, Nov 2025 | "why now" |
| 5 | DPDP penalties: **₹250 crore** (safeguards), **₹200 crore** (breach notification), ₹200 crore (children), ₹150 crore (SDF duties), ₹50 crore (general) | consent.in / Seclore rule summaries, 2025-26 | economic comfort |
| 6 | **28%** of leaked SSNs in US federal court records (6,198 of 22,391) had been "redacted" with a **black box** that could be deleted or copy-pasted out; about a third of all SSNs found were **failed redaction attempts** | FJC/Federal Judicial Center PACER study, 2024 | the single best slide for F3 + F6 |
| 7 | Telegram bot selling **Aadhaar + PAN + voter ID + address** lookups at **₹99 per lookup** (₹4,999 monthly), data 3–4 years old | Business Today / Digit, 27 Jun 2025 | the "photocopy economy" |
| 8 | **815 million** Indians' PII (Aadhaar, passport, voter ID, DL) offered on dark web for **$80,000** | Resecurity alert 15 Oct 2023, The Hindu explainer | severity |
| 9 | Aadhaar masking is already **mandatory law-adjacent**: SC (2018) — no entity shall publish records with Aadhaar numbers "unless redacted or blacked out, in print and electronic form"; UIDAI requires first-8 masked (`XXXX XXXX 1234`) | SC Aadhaar judgment 2018 / UIDAI guidelines | why `UIDAI_FIRST8` is a feature, not a gimmick |
| 10 | Our own measurement: **0.0275 ms** mean text scan per case, 8 synthetic cases × 30 iterations, precision/recall **1.0** on that corpus, `raw_values_in_report: false` | `server/tests/vectors/backend2_benchmark_metrics.json` (Jeeya) | **always** add: "tiny synthetic corpus, text-only — not an accuracy claim" |
| 11 | OCR on a Linux sandbox, clean 1000×600 printed PNG: RapidOCR 1.4.4 CPU, **1.6 s/page**, page quality `GOOD`, avg token confidence 0.985 | Arena verification run, 3 Oct 2026 | only say "measured on a Linux dev container, not on the demo laptop" |

## 6. Honest-limitation lines (say one of these unprompted — judges reward it)

- "Local processing is **risk reduction**, not a safe harbour. Device, swap, browser cache, clipboard, screen capture and extensions stay outside our control."
- "Detector re-scan shares the detector's blind spots. Metadata and QR checks are independent checks where supported."
- "No format-defined identifiers found. Names and addresses are not checked (see limitations)."
- "We do not verify identity, issuer, ownership, current status or authenticity. A checksum is a checksum."
- "This is a single-user, local-first reference implementation. Production would need isolated workers, auth, quotas, encrypted short-lived session storage, concurrency limits and deletion monitoring."

## 7. The five sentences that end a judge's question

1. "The output is not trusted — it is **re-tested** before you are allowed to download it."
2. "Strict Share mode is **on by default**: undecided review, unreadable OCR, kept high-risk value, or partial proof all **block the export**."
3. "Nothing is written to disk; the session lives in RAM for at most **10 minutes** (600 s, `SESSION_TTL_SECONDS`) and is cleared on export, expiry, cleanup, or shutdown."
4. "Our numbers are reported **per entity** — never one blended accuracy number."
5. "Everything is open source: **₹0 per page, ₹0 per seat, no paid API, works with the Wi-Fi off.**"

## 8. What we are NOT (say it before someone asks)

Not an anonymisation/k-anonymity tool · not a DLP replacement · not a document-management system · not a forensic recovery tool · not "certified" by anyone · not a name/address NER (deliberately out of scope, that is why a clean-but-scary `FORMAT_ONLY` result is not the same as "no PII") · not usable on handwriting · not a legal compliance guarantee.
