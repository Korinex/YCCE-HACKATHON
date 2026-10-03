# Backend 2 feasibility, benchmark, and dependency record

This file addresses Backend 2 items C1–C6 in `PS6_ADDITIONAL_FIVE_CRITERIA_TASK_LIST.md` and the Backend 2 rows in `PS6_FEASIBILITY_VIABILITY_REVIEW.md`. It records measured facts separately from items that remain unverified.

## C1 — Backend 2 public interface fixture

`server/tests/vectors/backend2_public_findings.json` is the API-safe fixture. It contains a checksum-pass finding, format-only PAN finding, lexicon review finding, OCR finding with a pixel box and OCR confidence, checksum-failing Aadhaar candidate, and an ordinary email represented as `EMAIL`. The fixture contains no `raw_value` field or unmasked input string. `server/tests/vectors/backend2_degradation.json` supplies safe consumer fixtures for OCR and QR degradation states.

## C2 — OCR environment and measured baseline

### Current host snapshot

| Property | Observed value |
|---|---|
| OS | Windows 11 Home, 26H2 (environment panel) |
| CPU | 11th Gen Intel Core i3-1115G4 (environment panel) |
| RAM | 7.8 GiB reported total (environment panel) |
| Python | CPython 3.14.2 |
| Pillow | 12.1.0 |
| NumPy | 2.4.1 |
| RapidOCR / ONNX Runtime | Not installed |
| PaddleOCR / PaddlePaddle | Not installed |
| OpenCV QR decoder | Not installed |

The current host can measure text detection, but it cannot produce an OCR scan-time, peak-memory, fallback-rate, or model-size result. `server/scripts/benchmark_backend2.py` reports text metrics and will measure a generated English-print image only when an OCR engine returns tokens. It reports `null` for unavailable OCR measurements; it never substitutes the failed-adapter latency for OCR performance. Run from `server/`:

```powershell
python scripts/benchmark_backend2.py --output tests/vectors/backend2_benchmark_metrics.json
```

The current dependency pins below are a proposed reproducible profile for CPython 3.12. They have **not** been installed or image-tested in this environment. The present host uses Python 3.14.2, and the OCR packages were absent. Treat the observed i3/8-GiB machine as the initial CPU-only evaluation floor, not as a tested OCR minimum. Treat Python 3.12 as the evaluation target until the team records a successful clean install and image run.

### Engines, formats, and language limits

- Primary: `rapidocr_onnxruntime==1.4.4` + `onnxruntime==1.20.1`, CPU inference, using the package's default model configuration through the current adapter. The PyPI package metadata limits this legacy adapter to Python `<3.13`, so CPython 3.12 is the selected install target.
- Fallback: PaddleOCR 2.10.0 + PaddlePaddle 2.6.2 is optional and deferred from the MVP baseline. The existing adapter attempts it only if installed and RapidOCR is unavailable/weak.
- Target image formats: PNG and JPEG. No PDF renderer is owned by Backend 2.
- Language declaration: no OCR language is empirically supported by this branch yet. The Paddle fallback is configured with `lang="en"`; the RapidOCR adapter relies on package defaults. Do not claim Indic-script, handwriting, or document-wide multilingual coverage. The only proposed first evaluation fixture is clean, printed English text.
- Missing engines, empty OCR, and low confidence map to unreadable/degraded review fixtures. An OCR result is not a clean-page guarantee.

### Offline model preparation

The OCR dependencies and weights are optional and are not vendored. The RapidOCR wheel itself is 14.9 MB and includes its package assets; this branch has not inspected the installed model filenames/checksums or verified a no-network model load. PaddleOCR commonly fetches model weights into its local cache on first use, so it must be warmed while connected if the fallback profile is selected. Before an offline demo, install and warm the chosen engine while connected, then verify that a synthetic image runs with networking disabled. If the cache is absent or the warm-up check fails, show the OCR-unavailable review state and do not claim the offline image path passed. This offline warm-up has not yet been run because neither OCR engine is installed here.

## C3 — Safe explanations

`finding_for_api()` in `server/app/api_boundary.py` maps internal validator explanations to the public finding contract. It preserves `CHECKSUM_PASS`, `CHECKSUM_FAIL`, `FORMAT_MATCH`, `FORMAT_ONLY`, `ISSUER_NOT_CHECKED`, and `CONTEXT_MATCH`; OCR findings requiring review carry `OCR_REVIEW`. No explanation says an issuer checked a person, account, card, phone, or identity document. A checksum result remains a format/checksum result.

## C4 — Synthetic performance and false-positive evidence

The checked-in run in `server/tests/vectors/backend2_benchmark_metrics.json` uses eight labelled synthetic text cases and 30 measured scans per case. It reports per-entity precision/recall of 1.0, zero false alarms, zero known misses, and a mean text scan time of 0.0483 ms on the recorded Python 3.14 host. This is a tiny hand-built corpus and a text-only measurement, not a representative accuracy claim or a supported OCR performance number. Rerun with the agreed final corpus and record known misses before demo freeze.

No actual OCR scan time, OCR fallback frequency, or OCR memory measurement is available yet. Machine RAM above is a host snapshot, not a measured OCR peak.

## C5 — Pins, installation, model and license notes

Base optional profile (`server/requirements-intelligence.txt`):

```text
Pillow==11.3.0
numpy==1.26.4
rapidocr_onnxruntime==1.4.4
onnxruntime==1.20.1
opencv-python==4.10.0.84
```

Optional fallback profile (`server/requirements-intelligence-paddle.txt`) adds `paddlepaddle==2.6.2` and `paddleocr==2.10.0`. The Windows CPython 3.12 PaddlePaddle 2.6.2 wheel is about 81 MB, before model weights; this is why Paddle remains optional for the MVP. Install the profile only in a clean environment and check the platform-specific Paddle framework install instructions first.

Install the base profile from `server/` with `python -m pip install -r requirements-intelligence.txt`. The default application requirements do not install OCR/QR packages. All listed components are open source and no paid service is required; the complete transitive wheel/model bundle still needs a license-bundle review before redistribution.

| Component | Selected version | License notes |
|---|---:|---|
| RapidOCR Python adapter | 1.4.4 | Apache-2.0 project license. Upstream now describes the `rapidocr_onnxruntime` package as gradually unmaintained in favour of the unified `rapidocr` package; the old import stays pinned only because it matches this branch's adapter. PyPI lists Python `<3.13`. |
| RapidOCR model artifacts | package defaults; exact model files not captured | Upstream says its converted PaddleOCR-derived model artifacts are Apache-2.0; this branch has not downloaded or hashed the files. |
| ONNX Runtime | transitive; not installed here | MIT. Resolve and record the exact installed transitive version in the clean environment. |
| PaddleOCR / PaddlePaddle fallback | 2.10.0 / 2.6.2 | Apache-2.0 project packages; fallback is optional and not installed/tested here. |
| OpenCV QR | 4.10.0.84 | Python wrapper MIT; OpenCV core Apache-2.0. Wheel includes third-party components, including FFmpeg under LGPL-2.1; preserve/review wheel license notices. |
| Pillow | 11.3.0 | MIT-CMU. |
| NumPy | 1.26.4 | BSD license. |

Primary references: [RapidOCR 1.4.4 package release](https://pypi.org/project/rapidocr-onnxruntime/1.4.4/), [RapidOCR install and migration note](https://github.com/RapidAI/RapidOCRDocs/blob/main/docs/install_usage/rapidocr/install.md), [RapidOCR project/model licensing](https://github.com/RapidAI/RapidOCR/blob/main/README.md), [ONNX Runtime 1.20.1](https://pypi.org/project/onnxruntime/1.20.1/), [PaddleOCR 2.10.0](https://pypi.org/project/paddleocr/2.10.0/), [PaddlePaddle 2.6.2 wheels](https://pypi.org/project/paddlepaddle/2.6.2/), [OpenCV wheel licensing](https://pypi.org/project/opencv-python/4.10.0.84/), [Pillow 11.3.0](https://pypi.org/project/pillow/11.3.0/), and [NumPy 1.26.4](https://pypi.org/project/numpy/1.26.4/).

## C6 — Graceful degradation fixtures

The JSON fixture covers OCR unavailable, empty OCR, low confidence, unsupported script/handwriting, unsupported QR, and QR present but unverified. The QR examples contain no decoded content and require cover-box handling without any identity-verification label. These are consumer fixtures; image/model-specific behavior still needs validation after installing the optional profile.
