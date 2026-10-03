"""Lazy local OCR adapters. No image is written to disk or sent remotely."""

from __future__ import annotations

from io import BytesIO
from typing import Any


def _image_array(image_bytes: bytes):
    from PIL import Image
    import numpy as np

    with Image.open(BytesIO(image_bytes)) as image:
        image.load()
        return np.asarray(image.convert("RGB"))


def _box(points: Any) -> dict[str, int]:
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    left, top, right, bottom = min(xs), min(ys), max(xs), max(ys)
    return {"x": max(0, round(left)), "y": max(0, round(top)),
            "w": max(0, round(right-left)), "h": max(0, round(bottom-top))}


def _word_tokens(text: str, confidence: float, bounds: dict[str, int], engine: str) -> list[dict[str, Any]]:
    """Split OCR lines at whitespace and retain the full line bounds for each token."""
    words = text.split()
    if not words:
        return []
    output = []
    for word in words:
        output.append({"text": word, "confidence": confidence,
                       "bounding_box": dict(bounds),
                       "engine": engine})
    return output


def _rapidocr(image) -> list[dict[str, Any]]:
    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    result, _ = engine(image)
    tokens = []
    for line in result or []:
        if len(line) < 3 or not str(line[1]).strip():
            continue
        confidence = min(1.0, max(0.0, float(line[2])))
        tokens.extend(_word_tokens(str(line[1]), confidence, _box(line[0]), "RapidOCR"))
    return tokens


def _paddleocr(image) -> list[dict[str, Any]]:
    from paddleocr import PaddleOCR

    engine = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    result = engine.ocr(image, cls=True)
    tokens = []
    for page in result or []:
        for line in page or []:
            if len(line) < 2 or not str(line[1][0]).strip():
                continue
            confidence = min(1.0, max(0.0, float(line[1][1])))
            tokens.extend(_word_tokens(str(line[1][0]), confidence, _box(line[0]), "PaddleOCR"))
    return tokens


def extract_text_and_boxes(image_bytes: bytes) -> list[dict[str, Any]]:
    """Return word/line tokens with confidence and pixel bounds.

    Engines are optional at runtime. If RapidOCR is missing or produces weak text,
    PaddleOCR is attempted; if neither is usable, an empty list signals review.
    """
    try:
        image = _image_array(image_bytes)
    except Exception:
        return []
    try:
        primary = _rapidocr(image)
    except Exception:
        primary = []
    average = sum(token["confidence"] for token in primary) / len(primary) if primary else 0.0
    if primary and average >= 0.55:
        return primary
    try:
        fallback = _paddleocr(image)
    except Exception:
        fallback = []
    fallback_average = sum(token["confidence"] for token in fallback) / len(fallback) if fallback else 0.0
    if fallback and fallback_average > average:
        return fallback
    return primary
