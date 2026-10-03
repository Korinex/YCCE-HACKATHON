# PS-06 Privacy Shield — Pitch & Defense Guide (backend edition)

*Every "we measured/verified" statement below was checked against the merged three-track tree on 2026-10-03.
External numbers carry a source and a date — quote them with the date, and never round up.*

---

## 1. Why we are making this (the actual argument)

**The premise:** in India, sensitive personal data does not mainly leak from hacked vaults. It leaks from **copies in motion** — the Aadhaar photo a field agent WhatsApps, the bank statement an employee forwards to a personal mailbox, the discharge summary photographed in a corridor, the judgment uploaded to a public portal, the KYC PDF attached to a ticket thread.

* The core database is not the weak point. UIDAI told Parliament (17 Dec 2025) that *"till date, no breach of Aadhaar card holders' data has occurred from the UIDAI database"* and describes a defence-in-depth architecture over ~134 crore holders and 16,000+ crore authentications. Yet the same country has a **₹99-per-lookup market in Aadhaar/PAN/voter-ID profiles** (Business Today, 27 Jun 2025) and an advertised dark-web set of **815 million** Indians' PII for **$80,000** (Resecurity, 15 Oct 2023). That gap *is* the product space: the data that gets sold was **handed over**, one document at a time.
* Masking is already required of the people handling it. The Supreme Court's 2018 Aadhaar judgment: no entity in possession of Aadhaar numbers shall make any database or record public **"unless the Aadhaar numbers have been redacted or blacked out through appropriate means, both in print and electronic form"**; UIDAI requires the first 8 digits masked (`XXXX XXXX 1234`), and RBI/SEBI/IRDAI repeat it. Compliance exists **on paper** and fails **per document**, because the check happens in a human's hands at 6 p.m. on a Friday.
* Manual "redaction" demonstrably does not work. The Federal Judicial Center reviewed ~4.68M US court records (2024) and found 22,391 exposed SSN/ITINs in 4,525 documents; filers had **attempted** redaction on roughly a third of them, and **6,198 of those (28%) were black boxes** that could be opened by *select-and-delete the rectangle, or highlight-copy-paste the page into a word processor*. A 2015 FJC pass found 314 SSNs sitting intact **in the metadata** of "redacted" files.
* The law now has a clock. DPDP Rules 2025 notified **13 Nov 2025**; Rule 7 requires notifying the Data Protection Board without delay plus a detailed report within **72 hours** and telling affected people; penalties run to **₹250 crore** (safeguards) and **₹200 crore** (notification failure) (Legal500/consent.in/Seclore, Nov 2025–2026). IBM's *Cost of a Data Breach 2025* puts India's average breach at **₹220 million**, +13% YoY, with **Shadow AI** a top-3 cost driver (+₹17.9M) while only **42%** of organisations have an AI policy — i.e. people are pasting these documents into chatbots too.

**So:** every organisation in India has a *document-sharing* exposure, an *existing masking obligation*, no *evidence* that it was done, and a toolset that **trusts the person who pressed the button**. We replaced trust with a re-test.

**Product sentence:** detect → explain → irreversibly remove → **prove on the artifact** → only then allow the download, with a privacy-safe receipt as the audit trail.

---

## 2. What we use, what we don't use, and why we don't use it

| Area | We use | We deliberately do **not** use | Why not |
|---|---|---|---|
| Detection | Deterministic regex + **real check digits** (Verhoeff for Aadhaar, Luhn for cards, GSTIN/IFSC/PAN structure, UPI PSP-suffix whitelist) + ±40-char context | An ML/LLM NER detector (spaCy/Presidio NER, OpenAI Privacy Filter, any hosted model) | Determinism is what makes the answer **auditable and repeatable**: a judge, an auditor and our own re-scan must get the same finding. An ML detector has a recall tail we cannot bound, and — per OpenAI's own docs for Privacy Filter — it is a "redaction aid", not a safety guarantee, with missed spans in medical/legal text. We would need a GPU or a network call for marginal, unprovable recall. **If** we added a model it would only ever be a *candidate generator* feeding the same fail-closed tiers — never a "clean" verdict. |
| Names & addresses | Nothing — explicitly out of scope | NER for person names/addresses | Highest-false-positive class; a wrong name-redaction destroys document usefulness, and a missed one gives false comfort. We therefore print the honest line *"No format-defined identifiers found. Names and addresses are not checked (see limitations)"* instead of pretending coverage. |
| OCR | **RapidOCR** (ONNX, CPU, models shipped in the wheel) with **PaddleOCR** as optional fallback; word-level boxes + per-token confidence | Cloud OCR (Google Vision, Azure AI Vision, AWS Textract) and Tesseract alone | Cloud OCR means **uploading the very document we are protecting** — it would kill the no-upload claim and the Wi-Fi-off demo. Tesseract gives line text without a trustworthy per-token confidence, and confidence is what drives `REVIEW` and quality gates. PaddleOCR 3.x also broke the `use_angle_cls/show_log` API our adapter uses — which is why it is pinned (`2.10.0`) and kept **optional**, not required. |
| Redaction | Text span rewrite; **opaque rectangle + re-encode lossless PNG + EXIF/GPS strip** for images; PDF **flattening** as the design target | "Highlight/black box overlay" and PDF `/Redact` annotations alone; lossy JPEG output; keeping the original PDF objects | A drawn rectangle is a *new object on top of the text layer* — the FJC number above (28%) is what that actually achieves. A lossy re-encode re-creates pixels under the box. Annotations, attachments, XMP and thumbnails are exactly where old redactions leak, so the target design renders new pages and drops everything else. ⚠ Our current `pdf_engine` is a placeholder (§5) — we say "PDF not implemented", never "PDF done". |
| Verification | 4 independent checks **on the produced artifact** + fail-closed gate; `ran` counter; `PARTIAL ≠ clean` | Trusting the redaction library's success flag; a single "re-scan says OK" green tick | Re-scanning shares the detector's blind spots, so we pair it with raw-string search, metadata inspection and QR re-decode — and we tell the user which checks actually ran. |
| Storage | `SessionStore` singleton, dict in RAM, `uuid4` key, 600 s TTL, evicted on export/expiry/cleanup/shutdown | SQLite/Redis/disk temp files, cloud object storage, browser localStorage, a queue | Every one of those turns a 10-minute volatile session into a durable copy that must be protected forever. We accept the honest wording *"volatile session cache: up to 10 minutes"* instead of the false claim "nothing is stored". |
| Network | `127.0.0.1` only; no CDN, no external fonts, no analytics SDK, no telemetry | Any third-party JS, webfonts, error trackers (Sentry), captcha, "improve the product" flags | (a) privacy claim, (b) the offline demo must pass with Wi-Fi off, (c) a CDN font is a data leak via the Referer/IP path that nobody reviews. |
| Framework | FastAPI + Pydantic v2 + Next.js/TypeScript | A notebook/Gradio demo, or Electron desktop app | Contract-first: the schema *is* the test (`extra="forbid"`, `FORBIDDEN_PUBLIC_FIELDS`), which is how we caught our own leakage. Electron would be another binary to sign and update for a hackathon. |
| Identity | **Nothing.** No login, no key, no biometric read, no UIDAI/AuA, no DigiLocker API | Actual e-KYC/authenticator integration, "verified" badges | We are not a requesting entity; calling UIDAI would need licensed access **and** would mean uploading the document. Our QR labels are `VERIFIED_FOR_THIS_ARTIFACT / UNVERIFIED / UNSUPPORTED_AT_CARD` for exactly this reason. |
| Claims | Per-entity precision/recall/false-alarms/known-misses from a regenerated board | A blended "accuracy %" number | A single accuracy number is how PII tools hide a 40%-recall entity inside a 95% average. Frozen rule F9. |

---

## 3. What is different from everything already out there

| Existing solution | What it actually does | Where it stops | Our difference |
|---|---|---|---|
| **Adobe Acrobat / Foxit "Redact"** | Applies a real redaction, but the human must find every identifier and accept the boxes | Zero discovery, zero verification, per-seat licence | We find, explain, then **prove**; refuse when proof is partial |
| **Microsoft Purview DLP / AWS Macie / Google Sensitive Data Protection** | Scan data **at rest** in repos/mailboxes, policy alerts | Cloud-side, at-rest, alert-only — and the data path goes through a cloud | Last-mile, **on-device**, at the moment of sharing, output-producing |
| **BigID / Varonis / Cyera / OneTrust / Securiti** (DSPM + privacy governance) | Enterprise inventory, RoPA, DSAR, risk scoring | Quarterly inventory, not a per-document guarantee; heavy procurement; cost per data source | An **embedded primitive** any flow can call before it sends; ₹0 licence; receipts, not dashboards |
| **Microsoft Presidio / LLM Guard / gateway maskers (e.g. WSO2 `pii-masking-regex`)** | Regex+NER annotator library; masks prompt payloads | Generic English entities; no Indian check digits; no irreversible artifact; no proof; "masked" ≠ "safe to share" | Verhoeff/Luhn/GSTIN/UPI semantics, Devanagari digit normalisation, UIDAI_FIRST8, irreversible rendering, 4-check proof, fail-closed gate |
| **OpenAI Privacy Filter** (open-weight, Apache-2.0, 8 categories, ~F1 96%) | Excellent context-aware *detection* | Detect + tokenise only: no Indian formats, no image/PDF redaction, no artifact verification, no per-entity review burden, vendor caveat of missed spans | Complementary: we could even use it as a candidate generator; **our value is what happens after detection** |
| **Dark-web "protection" services / credit monitoring** | React after the leak | Too late by definition | Prevention + evidence before one click |
| **Manual blur in Paint / phone editor** | Draw over it | The FJC 28% finding; keeps text layer, metadata, quiet zone | Opaque fill + metadata strip + quiet-zone cover + re-decode check |
| **Aadhaar "masked copy" download from UIDAI** | Gives you a masked PDF of your own card | Per-card, manual, and doesn't help for statements/screenshots/other identifiers | Works on **whatever you already have**, 15 identifier types, batch-ready |

**Four things nobody in that list gives you:** (1) a **verdict on the artifact** (`CLEAN / FAIL / PARTIAL n/4`) instead of a success toast; (2) **fail-closed export** — the bytes do not exist when the check fails; (3) an **Indian identifier semantic layer** (checksums, PSP suffixes, Devanagari digits, the mandated masking shape, secure-QR quiet zone); (4) a **privacy-safe receipt** that is itself leak-tested — the artefact an auditor or a DPO can keep.

## 4. Why it is innovative (and what we refuse to claim)

Defensible novelty claims:
1. **Proof-of-removal as a first-class product step** — an irreversible-redaction tool that re-tests its own output with independent checks (string/raw-byte search, metadata/attachment/hidden-layer, QR re-decode) and *shares* the detector's blind-spot caveat with the user in the UI.
2. **Fail-closed state machine with honest states** — Strict Share mode ON by default; `PARTIAL` can never light up green; a `KEEP` on high-risk data **removes the download button**, not the warning.
3. **Validation tiers instead of a boolean** — `VALIDATED / FORMAT_ONLY / REVIEW`, with the invariant *a checksum-failing candidate can never be `VALIDATED`*, and a `confidence = format_strength × OCR_factor` that **measures** OCR degradation rather than hiding it. The vocabulary itself (`ISSUER_NOT_CHECKED`, `ACTIVE_STATUS_NOT_CHECKED`) is the innovation: an over-claiming UI is a *harm*, so we designed the words.
4. **Last-mile, no-egress architecture as a demoable property** — Wi-Fi off, `127.0.0.1`, RAM-only 600 s session, whitelisted public finding schema. We can *show* the counters at zero, not assert a policy.
5. **A default action that matches the law** — `UIDAI_FIRST8` produces `XXXXXXXX2346`, the exact form the SC 2018 direction and UIDAI guidelines require, so the tool's normal output is the compliant artefact.
6. **Evidence Board with per-entity metrics + known misses** — a tool willing to publish its misses on screen. Almost no privacy tool does that.

What we do **not** claim: new regexes, new checksums (Verhoeff 1969, Luhn 1954), new OCR, a new model, "the first PII redactor", any certification by anyone, or "guaranteed privacy". Our contribution is the **contract** (prove or refuse) plus the **Indian semantics**, not the primitives.

## 5. Why a company would prefer this prototype over a bigger vendor

1. **No new data flow.** Nothing to vendor-risk-review, no DPA, no cross-border transfer question, nothing for the security team to block. A local binary/API inside their own boundary.
2. **₹0 marginal cost.** No per-page, per-seat or per-scan pricing; CPU-only; runs on the machine they already own. That is the pitch to a bank ops head whose DSPM quote is 6 figures.
3. **Embeddable at the choke point.** `analyze → redact → verify` is 3 calls; it drops into an existing mail-out portal, a field-agent app, an e-sign dispatch, a complaints inbox, before the send.
4. **Explainable to an auditor.** Fixed reason codes, `rule` names, per-check verdicts and a leak-tested receipt = evidence that survives a person leaving the company. Deterministic output means the audit replays identically.
5. **Fits the regulator's language.** Masking, "review required", "not legal certification", data-minimisation-by-TTL — the artefacts map onto what a DPDP audit and ISO/IEC 27701-style reviews ask for (we say *supports*, never *certifies*).
6. **They can verify the honesty themselves.** We refuse to export when unsure. Vendors promise; a fail-closed gate *can't* lie.

## 6. Who buys it, and who the real stakeholders are

**Paying units (in the order they will actually sign):**
1. **Banks / NBFCs / fintech — KYC & document ops, and their BPOs**: the team that forwards PAN/Aadhaar PDFs thousands of times a day; also e-sign/KYC vendors (**eMudhra, Digio, Leegality, Signzy, mSignly**, IDfy/KYCs) who need per-document masking before delivery.
2. **Insurance & healthcare**: claims attachments, discharge summaries, pre-auth emails (IRDAI/DPDP health data is the highest-consequence class; note IBM's global healthcare breach cost at **$7.42M**, still #1 for the 15th year).
3. **Judiciary & legal**: e-Courts Mission Mode Project Phase III (2023-27), High Court registries, law firms — they must mask published judgments and are already litigating it (Madras HC, *Theodore v. Registrar General*, 2024: redact personal details from the **published** judgment while records stay intact; Delhi HC's 2025-26 masking/de-indexing framework, incl. name-search restrictions for Indian Kanoon).
4. **RTAs, payroll & staffing**: mutual-fund RTAs (CAMS/KFIN), brokers' onboarding, payroll outsourcing — every employee file with Aadhaar + bank + PAN.
5. **Government data-handling layer**: CSCs, field agents, PSU/defence recruitment vendors — the **ThoughtGreen/Timing** exposure (May 2024): 1.6M documents, 496.4 GB open database of fingerprints, signatures, birth certificates of police/army/teachers/railway staff, records 2021-2024 **updating live**. A vendor storing *documents* is precisely our buyer.
6. **AI-platform / gateway vendors**: anyone routing enterprise text to an LLM needs a pre-egress masker with Indian formats and *provable* output — Shadow AI added **+₹17.9M** to the average Indian breach cost while only 42% have AI policies (IBM 2025).

**Stakeholders whose life changes (say these names in the "impact" answer):** data principals (the citizen whose copy circulates); the front-line employee who currently owns the risk and has no defence; DPO / Privacy Counsel; CISO & AppSec; the independent **Data Auditor** SDFs must appoint under the DPDP Rules; regulators (DPB, CERT-In, RBI/SEBI/IRDAI, UIDAI as the masking standard-setter); customers' trust; cyber-insurance underwriters (evidence reduces premium); and — always mention — **the person you refuse to help is protected too**: the tool's failure mode is "we won't let you send this", never "we said it's fine".

## 7. The incident answers (pick one, tell it properly)

**Default story — the ₹99 dossier (Business Today/Digit, 27 Jun 2025).** A Telegram bot sold full profiles — name, father's name, alternate numbers, current and previous addresses, Aadhaar, PAN, voter ID, DL — from just a 10-digit mobile number; ₹99 per lookup, ₹4,999 for unlimited monthly; journalists tested it and the data was accurate and only 3–4 years old. *Why it's ours:* that catalogue is not built by hacking UIDAI — it is built from **documents people sent**: KYC PDFs, application forms, screenshots, ticket attachments. Each one of those, masked by our tool, is a record that never enters the corpus. And the bot was removed only after reporting — nothing about the pipeline was fixed. Our gate closes a *class* of those exposures per document, at the sender's own machine, with a receipt.

**The scale story — Resecurity, 15 Oct 2023:** PII of **815 million** Indians (Aadhaar, passport, voter ID, DL) offered for **$80,000**; India's minister said CERT-In was investigating and legacy data was still being moved to safe storage. *Our line:* "an adversary does not need to break the vault when the photocopy is for sale; we protect the photocopy."

**The metadata story — FJC PACER 2024:** 6,198 SSNs (28% of those found) were "redacted" with black boxes; deleting the box or copy-pasting the page exposed them; one document with 3,099 SSNs was filed twice; 2015 study: 314 SSNs lived in metadata. *Our line:* "this is exactly our F6 Copy-Paste Showdown, and it's why our PDF path re-renders pages and our proof step searches raw strings, not just text."

**The judiciary-under-attack story:** AP High Court breach claims (May 2025) and Telangana HC defacement (Nov 2025) — courts hold "bank details, Aadhaar data, sealed records, witness statements" and are digitising faster than they can secure it (India Legal, Feb 2026); the US CM/ECF 2025 incident put sealed files and witness identities at risk. *Our line:* "a registry clerk needs a 30-second, offline, no-upload tool that says 'this is clean' only after proving it. That is our demo."

**The vendor-storage story — ThoughtGreen/Timing (May 2024):** 496.4 GB open database, no password, 1.6M documents with fingerprints and signatures, live-updating. *Our line:* "the breach happened because documents were collected into a pile. Our tool shrinks the pile — it is designed for 'send the masked copy, keep nothing'."

## 8. Judge-question bank (2–4 lines each; the answer a tired judge accepts)

**Product / value**
* *Isn't this just regex?* No — regex proposes, **check digits decide**: Verhoeff (Aadhaar) and Luhn (cards) plus context windows and overlap ranking decide the tier; then the artifact is re-tested. A regex can't prove removal or refuse an export.
* *Why not use Presidio/Privacy Filter?* They solve detection, which is the solved half. Our contribution is post-detection: Indian ID semantics, irreversible rendering, 4-check proof, fail-closed gate, receipt. We could consume either as a *candidate generator* — that's on our roadmap, and it could never be allowed to say "clean".
* *How is this better than Adobe's redact tool?* Adobe's tool passes a removal test **if the human finds every identifier**. Ours finds the candidates, explains them, and refuses to export until the output itself passes — plus ₹0 licence and offline.
* *What if a name or address is in the file?* Out of scope, and we say so **in the UI and the receipt** — that's the difference between a prototype and a lie.
* *Biggest risk?* Over-trust. Mitigated structurally: Strict mode ON, `PARTIAL` never green, review states, and per-entity metrics with our misses printed.
* *Why a prototype and not a startup?* It is a **primitive**: 3 endpoints, embed into the mail-out portal, measure block/allow. The demo shows the contract works; the business is a hardening + SDK question, not a discovery question.
* *Moat?* The **combination** (proof-of-removal + Indian formats + fail-closed + no-egress) and the tested vector corpus — not any one algorithm.

**Technical**
* *How do you know a redaction worked?* 4 checks: detector re-scan, raw-string/text-layer search, metadata/attachment/hidden-layer/thumbnail inspection, QR re-decode + rectangle comparison. Verdict `CLEAN/FAIL/PARTIAL`, and `ran=3/4` renders as 3/4.
* *False positives — won't you destroy useful documents?* Masking is the **default**, not automatic: the user decides per finding; `REVIEW` items block in Strict mode rather than being silently altered; low-specificity types (bank account, VID, DL, vehicle) require context, which is why an order number stays untouched unless it looks like an Aadhaar candidate.
* *A false negative is worse. Agreed?* Yes — hence: longest-span + Aadhaar-priority resolution, Devanagari normalisation, per-token OCR confidence feeding `REVIEW`, `UNREADABLE`/`DEGRADED` blocking export, and our acceptance gate "zero missed high-risk values in the curated set". We publish known misses.
* *Why CPU OCR — too slow?* Measured: **1.6 s/page** on a clean 1000×600 PNG, RapidOCR 1.4.4 CPU (Linux container); text scan is microseconds (0.0275 ms mean, 30 iterations × 8 synthetic cases). Slower than a GPU service, but it never leaves the device.
* *How do you handle a 500-page PDF?* We don't: **10-page cap**, `MAX_UPLOAD 10MB`, per-page OCR budget, page images as the degradation path. The PDF engine here is a placeholder — we show text and image paths live.
* *What exactly is stored?* For up to 10 minutes, in RAM, keyed by a random id: original content, findings, OCR tokens, page quality, metadata. Cleared on successful export, expiry, explicit delete, or shutdown. Nothing on disk, nothing in logs, nothing to any network.
* *Why keep the original at all?* Redaction and verification need the source; that is the honest trade. The alternative — hashing or zero-retention — would make proof impossible.
* *How is the raw value kept out of the response?* Two places: a field **whitelist** in `api_boundary.finding_for_api()` (and if the masked form would still contain the raw value it becomes `[REDACTED]`), and B1's schema, `extra="forbid"` + `FORBIDDEN_PUBLIC_FIELDS`, which makes a leak a **test failure**, not a code-review miss.
* *Passwords for locked PDFs?* Prompted locally, used for that one request, never in the receipt or logs, never derived from name/DOB; wrong password → controlled refusal.
* *Concurrency/scale boundary?* Single-user local-first reference. Production = isolated workers, auth, quotas, encrypted short-lived session store, concurrency limits, deletion monitoring, tenant isolation — we state that in the README rather than pretend.
* *Did you run it offline?* Yes — Wi-Fi off rehearsal is a scripted test in the QA track; no CDN, no webfonts, no analytics, `127.0.0.1` only.

**Privacy / legal**
* *Are we DPDP compliant now?* No — and we never say that. We reduce exposure on a document and produce evidence; compliance needs the surrounding programme (consent, records, breach process, audit). Claiming certification would be the first thing a judge should reject us for.
* *Does "no upload" mean "no storage"?* No. Local processing is **risk reduction**, not a safe harbour; the session is storage for 10 minutes. Our own copy says "Volatile session cache: up to 10 minutes".
* *Is a QR "verified"?* Never "identity verified". We say **"Signature verified for this presented artifact"**, `UNVERIFIED`, or `UNSUPPORTED_AT_CARD` — and we cover the complete quiet zone and prove the output QR no longer decodes.
* *Device-level threats?* Swap, clipboard, cache, screen capture, extensions, malware are outside the prototype's control — listed verbatim in our limitations slide.

**Process / team**
* *How did four people not collide?* Strict file ownership (`main.py`/`schemas.py` are B1-only; B2 owns `pipeline/validators/ocr/qr`; B3 owns `audit/gate/verify_service/integration/*`; Frontend owns `client/*`), published fixtures instead of shared code, contract changes needing three approvals. Our tracks merged **cleanly with zero overlapping files** — and the field-name mismatches that remained were caught by the proof layer, which is the integration argument we keep making.
* *How is quality assured?* Test-first per track (21 tests on B2, 30 on the merged server suite, 66 passing integration), CodeRabbit review on every branch, a break matrix of hostile inputs (renamed `.txt`→`.png`, blurry image, empty doc, locked PDF, kept high-risk finding, residual value, partial proof), and an evidence board regenerated from the final build.
* *What would you cut if you had half the time?* QR Reveal (gated), then drawer polish, then the no-upload visual, then the board's polish. Never SCOUT, SHIELD, PROOF, Strict mode, fail-closed export, or the honest wording.
* *What's your business model?* Per-seat/per-page licence on the hardened engine (SDK + CLI + gateway plugin), vertical packs (Indian formats first), and an evidence/audit add-on for DPOs. Zero-cost, offline, self-hosted for the reference build — that is deliberate: it makes deployment risk the reason they say yes.

## 9. Open defects — know them before someone finds them (answer = "yes, and here is our fix")

| # | Issue (verified 2026-10-03) | If a judge/CodeRabbit finds it, say |
|---|---|---|
| 1 | **B2→B1 span key mismatch**: `render_text_redaction()` reads `char_span`/`span`, findings carry `start`/`end` → redaction silently no-ops (fails **open** at the engine level; our proof layer caught it: `verdict=FAIL`, export blocked) | "This is our strongest slide. Two tracks disagreed on a field name; the artifact-level proof caught it and blocked the export. The engine now accepts both and we added a test that fails if cleaned output equals input." |
| 2 | **UPI false `VALIDATED`**: `if "KNOWN_SUFFIX" in reason` also matches `"UNKNOWN_SUFFIX; REVIEW"` → any unknown PSP suffix is labelled validated | "Real bug, violates our own rule that a format/whitelist result can't earn `VALIDATED`; fixed by comparing the suffix against the whitelist instead of substring-matching the reason, with a regression test on `user@paypal.com` → `REVIEW`." |
| 3 | **Ordinary email next to a `UPI:` label becomes a UPI finding** (±40-char context) | "Known context-window over-trigger; fix is to require the UPI suffix to *not* look like a public domain when it's an email, plus a break-matrix case." |
| 4 | **OCR glues label to value** (`PANABCPE1234F`, `IFSCHDFC0001234`) → letter-lookbehind rules miss PAN/IFSC in images | "Reproduced with real RapidOCR. We handle it in OCR post-processing: re-insert boundaries between label and value (letter→digit/digit→letter transitions) — a recall bug we would rather surface in our Evidence Board than hide." |
| 5 | **Driving-licence pattern** misses canonical forms (`DL-01-2019-0012345`) and the digits can be mis-typed `CREDIT_CARD` | "DL is context-gated FORMAT_ONLY; the pattern needs a state-code-first *and* letters-first variant, and card candidates should not swallow it. Overlap ranking fix." |
| 6 | **`pdf_engine.sanitize_pdf_bytes()` returns `%PDF-1.4\n<sha256 bytes>\n%%EOF`** — a placeholder, not a redacted PDF | "We do not claim PDF in the demo. It is explicitly marked not-implemented so nobody mistakes a stub for a redaction — and our freeze rule is 'no fake redaction'." |
| 7 | **`/api/v1/analyze` & `/api/v1/redact` return 501**; no `/verify` route yet | "Libraries are done and unit-tested; the last mile is the route wiring, which is exactly the integration step in our plan and our only demo blocker." |
| 8 | Two competing handoff contracts (B2 `api_boundary.py` vs B1 `schemas.py`): pixel vs normalised `bbox`, `context_hit` list vs single enum, `raw_masked` vs `value_masked`, gate `validity_class` vs `validation_tier`, gate's sensitivity enum missing `VEHICLE_ID`/`OTHER`, `ocr_quality=None` for text | "Caught by schema tests on merge, before the demo. One contract wins; we log the decision in the PR — that's what the ownership rule is for." |
| 9 | Dependency reality: `rapidocr_onnxruntime 1.4.4` pulls GUI **`opencv-python`**, which fails `import cv2` (`libGL.so.1`) on headless Linux, and pins `python<3.13`; Paddle 3.x API drift | "Documented in `BACKEND2_FEASIBILITY.md`. We pin `opencv-python-headless` for the Linux demo box, warm the model cache offline, and treat Paddle as optional." |
| 10 | `SESSION_TTL_SECONDS_DEMO = 1800` in B1's schema vs the frozen "up to 10 minutes" copy | "Privacy copy wins: demo mode must be ≤600 s or we change the sentence. Being wrong about our own TTL is the one thing we cannot afford." |

## 10. Per-person 60-second drill

* **Khudaija (B1):** "I own the API and the artefact: session lifecycle in RAM with a 600 s TTL and uuid4 keys, the redaction renderers for text and image, metadata strip + lossless re-encode, the random `shielded_xxxx` filename, and the receipt — whose schema has `extra='forbid'` and a forbidden-field list so a leak fails CI. I also bound the runtime: 127.0.0.1, 10 MB, 10 pages, no disk, no logs."
* **Jeeya (B2):** "I own finding things and explaining them: 15 Indian identifier rules with Verhoeff/Luhn/whitelist decisions, ±40-char context, offset-preserving Devanagari digit normalisation, longest-span overlap resolution, the tier + confidence formula, RapidOCR word boxes with per-token confidence and a page-quality gate, plus QR detection that returns a cover box and never the payload. 21 tests, all green."
* **Shifa (B3):** "I answer 'is the file actually clean?' — four checks, the `CLEAN/FAIL/PARTIAL` algebra with a `ran` counter, and the fail-closed gate whose block reasons are fixed codes. Plus the hostile set and the per-entity Evidence Board, regenerated from the build, never typed from memory."
* **Frontend:** "SCOUT→SHIELD→PROOF→RECEIPT with Strict mode visibly on, 5-second reveal, no download button when blocked, and exact copy for unreadable OCR, locked PDF and out-of-scope inputs."

**Closing line for the team:** "Detection tools tell you what they found. We tell you what we **proved**, and when we can't prove it, we take the download button away. That's the difference between a warning and a control."

---

## Sources (for the citations slide / anyone who asks)

* IBM, *Cost of a Data Breach Report 2025* — India newsroom release, 7 Aug 2025 (₹220M avg, +13%; Shadow AI +₹17.9M; 42% AI policy). Global figures via StationX 2026 summary of the same report ($4.44M, 241 days, healthcare $7.42M).
* MeitY **DPDP Rules 2025**, notified 13 Nov 2025 (G.S.R. 846(E)); Data Protection Board constituted same day (G.S.R. 844(E)); Rule 7 breach notification (72 h detailed report), Rule 6 safeguards/1-year log retention, Rules 12–14 SDF duties; penalties ₹250/200/200/150/50 crore — Legal500, India Briefing, Seclore, consent.in (Nov 2025 – Apr 2026).
* Federal Judicial Center, *Unredacted Personally Identifiable Information in Federal Court PACER Documents* (2024) — 4,681,055 documents; 22,391 unredacted SSN/ITINs in 4,525 docs (0.10%); ~⅓ were failed redactions; 6,198 (28%) black-box-only; and the 2015 FJC report (314 SSNs recoverable from metadata).
* Business Today / Digit, "Telegram bot sells Indian citizens' Aadhaar, PAN and other details for as low as ₹99", 27–28 Jun 2025.
* Resecurity alert as reported by The Hindu ("How the personal data of 815 million Indians got breached", Nov 2023) and Fortune India (31 Oct 2023).
* WebsitePlanet / Jeremiah Fowler via CSO Online (28 May 2024) — ThoughtGreen/Timing exposed database, 496.4 GB, 1.6M documents.
* PIB / TOI / Tribune, 17 Dec 2025 — "no breach of Aadhaar card holders' data from the UIDAI database", ~134 crore holders, 16,000+ crore authentications, ISO/IEC 27701:2019, NCIIPC protected-system status.
* Supreme Court of India (Aadhaar judgment, 2018) masking direction as summarised by M2P Fintech; UIDAI masked-Aadhaar guidelines (first-8 masking, QR remains scannable).
* Madras HC, *Theodore v. Registrar General* (2024) and Delhi HC masking/de-indexing framework (2025-26) on redaction of published judgments (Columbia Global Freedom of Expression; Chambers).
* India Legal, "Judiciary Under Siege" (27 Feb 2026) — AP HC breach claims May 2025, Telangana HC defacement Nov 2025, e-Courts Phase III security measures.
* OpenAI, "Introducing OpenAI Privacy Filter" (Apache-2.0 open-weight PII redactor; 8 categories; F1 96% on PII-Masking-300k; documented as a redaction aid with missed-span risk in medical/legal use).
* WSO2 API Platform "PII Redaction for LLMs" (2026) — regex+NER and gateway-side masking as the common industry pattern.
* In-repo: `docs/PS06_FINAL_FEATURES_GUIDE.md`, `docs/PS06_FINAL_TASK_DIVISION_GUIDE.md`, `docs/PS06_ADDITIONAL_FIVE_CRITERIA_TASK_LIST.md`, `docs/BACKEND2_FEASIBILITY.md`, `docs/BACKEND2_HANDOFF.md`, `docs/backend3-integration-status.md`, `server/tests/vectors/backend2_benchmark_metrics.json`.
