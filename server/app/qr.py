"""Local QR detection adapter that returns only safe metadata and cover bounds."""

from __future__ import annotations

from io import BytesIO
from typing import Any


def _quiet_box(points: Any, width: int, height: int, padding_ratio: float = 0.25) -> dict[str, int]:
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    left, right = min(xs), max(xs)
    top, bottom = min(ys), max(ys)
    pad = round(max(right-left, bottom-top) * padding_ratio)
    x1, y1 = max(0, int(left)-pad), max(0, int(top)-pad)
    x2, y2 = min(width, int(right)+pad), min(height, int(bottom)+pad)
    return {"x": x1, "y": y1, "w": x2-x1, "h": y2-y1}


def detect_qr_codes(image_bytes: bytes) -> list[dict[str, Any]] | None:
    """Detect/decode QR payloads locally but never return payload or PII fields.

    UIDAI signature verification is deliberately not claimed here. Decoded content
    therefore remains UNVERIFIED until a separately reviewed verifier is supplied.
    The expanded box includes a margin around the symbol for safe redaction.
    """
    try:
        import cv2
        import numpy as np
        from PIL import Image

        with Image.open(BytesIO(image_bytes)) as source:
            source.load()
            image = np.asarray(source.convert("RGB"))
        height, width = image.shape[:2]
        detector = cv2.QRCodeDetector()
        decoded_values: list[str]
        points = None
        if hasattr(detector, "detectAndDecodeMulti"):
            try:
                found, decoded_values, points, _ = detector.detectAndDecodeMulti(image)
                if not found:
                    points = None
            except Exception:
                points = None
        if points is None:
            decoded, points, _ = detector.detectAndDecode(image)
            decoded_values = [decoded] if decoded else []
        if points is None:
            return []
        point_sets = points if len(points.shape) == 3 else points[None, ...]
        results = []
        for index, quad in enumerate(point_sets):
            text = decoded_values[index] if index < len(decoded_values) else ""
            results.append({
                "id": f"qr_{index+1}", "decoded": bool(text),
                "validation_status": "UNVERIFIED" if text else "UNSUPPORTED_AT_CARD",
                "fields": [], "quiet_zone_box": _quiet_box(quad, width, height),
                "raw_payload_returned": False,
            })
        return results
    except Exception:
        # Missing optional CV dependencies and malformed images fail closed to review.
        return None
