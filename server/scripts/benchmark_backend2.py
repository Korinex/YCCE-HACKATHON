"""Measure Backend 2 against a tiny synthetic corpus; print aggregate-only JSON."""

from __future__ import annotations

import importlib.util
import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.pipeline import analyze_image, detect_text

# Synthetic test data only. Never print these strings or store outputs containing them.
CASES = [
    ("aadhaar_checksum_pass", "AADHAAR", "Aadhaar: 234123412346"),
    ("aadhaar_checksum_fail", "AADHAAR", "Aadhaar: 999999999998"),
    ("pan_format", "PAN", "PAN: ABCPE1234F"),
    ("phone_format", "PHONE", "Phone: 9876543210"),
    ("upi_known_suffix", "UPI", "Pay to user@oksbi"),
    ("email_is_not_upi", "EMAIL", "Mail user@example.com"),
    ("health_review", "HEALTH_TERM", "Diagnosis: diabetes"),
    ("bare_order_number_is_not_bank", "NONE", "Reference 123456789012"),
]
ITERATIONS = 30


def _available(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _metrics() -> tuple[dict[str, dict[str, object]], dict[str, set[str]]]:
    by_case: dict[str, set[str]] = {}
    for case_id, _, text in CASES:
        by_case[case_id] = {str(finding["type"]) for finding in detect_text(text)}
    kinds = sorted({truth for _, truth, _ in CASES if truth != "NONE"} | {kind for values in by_case.values() for kind in values})
    expected = {case_id: truth for case_id, truth, _ in CASES}
    result = {}
    for kind in kinds:
        tp = sum(expected[case_id] == kind and kind in predicted for case_id, predicted in by_case.items())
        fp_ids = [case_id for case_id, predicted in by_case.items() if expected[case_id] != kind and kind in predicted]
        fn_ids = [case_id for case_id, predicted in by_case.items() if expected[case_id] == kind and kind not in predicted]
        predicted_count = tp + len(fp_ids)
        expected_count = sum(label == kind for label in expected.values())
        result[kind] = {
            "true_positive": tp,
            "false_positive": len(fp_ids),
            "false_negative": len(fn_ids),
            "precision": round(tp / predicted_count, 4) if predicted_count else None,
            "recall": round(tp / expected_count, 4) if expected_count else None,
            "false_alarm_case_ids": fp_ids,
            "known_miss_case_ids": fn_ids,
        }
    return result, by_case


def _image_metrics() -> dict[str, object]:
    rapid = _available("rapidocr_onnxruntime")
    paddle = _available("paddleocr")
    result: dict[str, object] = {
        "rapidocr_available": rapid,
        "paddleocr_available": paddle,
        "qr_cv2_available": _available("cv2"),
        "image_scan_ms_mean": None,
        "ocr_fallback_frequency": None,
        "status": "NOT_MEASURED_OCR_RUNTIME_UNAVAILABLE",
    }
    if not rapid and not paddle:
        return result
    try:
        from PIL import Image, ImageDraw
        from io import BytesIO

        image = Image.new("RGB", (900, 180), "white")
        ImageDraw.Draw(image).text((20, 50), "PAN: ABCPE1234F", fill="black")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        content = buffer.getvalue()
        warmup = analyze_image(content)  # excludes first model load from the average
        if not warmup["ocr_tokens"]:
            result["status"] = "OCR_RUNTIME_RETURNED_NO_TOKENS"
            return result
        durations, fallback = [], 0
        for _ in range(ITERATIONS):
            started = time.perf_counter()
            result_data = analyze_image(content)
            durations.append((time.perf_counter() - started) * 1000)
            if any(token.get("engine") == "PaddleOCR" for token in result_data["ocr_tokens"]):
                fallback += 1
        result["image_scan_ms_mean"] = round(statistics.mean(durations), 2)
        result["ocr_fallback_frequency"] = round(fallback / ITERATIONS, 4)
        result["status"] = "MEASURED_ON_SYNTHETIC_ENGLISH_PRINT"
    except Exception as exc:
        # Do not print exception text; library exceptions may include OCR input.
        result["status"] = f"NOT_MEASURED_RUNTIME_ERROR_{type(exc).__name__}"
    return result


def main() -> None:
    metrics, _ = _metrics()
    timings = []
    for _, _, text in CASES:
        detect_text(text)  # warm-up
        for _ in range(ITERATIONS):
            started = time.perf_counter()
            detect_text(text)
            timings.append((time.perf_counter() - started) * 1000)
    versions = {}
    for package in ("Pillow", "numpy", "rapidocr-onnxruntime", "paddleocr", "opencv-python", "onnxruntime"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    report = {
        "fixture": "synthetic_backend2_v1",
        "cases": len(CASES),
        "iterations_per_text_case": ITERATIONS,
        "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                    "cpu": platform.processor() or None, "package_versions": versions},
        "text_scan_ms_mean": round(statistics.mean(timings), 4),
        "per_entity": metrics,
        "image": _image_metrics(),
        "raw_values_in_report": False,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="Write aggregate-only JSON to this path")
    arguments = parser.parse_args()
    if arguments.output:
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
