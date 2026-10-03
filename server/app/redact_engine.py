from __future__ import annotations

import hashlib
import io
import os
import re
import time
from typing import Any

from PIL import Image

MASK_CHAR = "X"


def _mask_fragment(fragment: str) -> str:
    if not fragment:
        return fragment
    return MASK_CHAR * len(fragment)


def render_text_redaction(text: str, items: list[dict[str, Any]], rules: list[dict[str, Any]]) -> str:
    if not text:
        return text
    if not items:
        return text
    rule_map = {str(rule.get("id")): rule.get("action", "MASK") for rule in rules if isinstance(rule, dict) and "id" in rule}
    spans: list[tuple[int, int, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if item_id is None:
            continue
        action = rule_map.get(item_id, item.get("action", "MASK"))
        span = item.get("char_span") or item.get("span")
        if not isinstance(span, (list, tuple)) or len(span) != 2:
            continue
        start, end = int(span[0]), int(span[1])
        if start < 0 or end < start or end > len(text):
            continue
        spans.append((start, end, str(action)))
    if not spans:
        return text
    spans.sort(key=lambda s: (s[0], s[1]))
    out: list[str] = []
    cursor = 0
    for start, end, action in spans:
        if start < cursor:
            continue
        out.append(text[cursor:start])
        fragment = text[start:end]
        if action == "REMOVE":
            replacement = ""
        elif action == "REPLACE_TOKEN":
            replacement = "[REDACTED: TYPE]"
        elif action == "UIDAI_FIRST8":
            digits = re.sub(r"\D", "", fragment)
            replacement = "" if not digits else "X" * max(len(fragment) - 4, 0) + digits[-4:]
        elif action == "KEEP":
            replacement = fragment
        else:
            replacement = _mask_fragment(fragment)
        out.append(replacement)
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


def render_image_redaction(file_bytes: bytes, items: list[dict[str, Any]], rules: list[dict[str, Any]]) -> bytes:
    if not file_bytes:
        raise ValueError("Image bytes are required")
    try:
        image = Image.open(io.BytesIO(file_bytes)).convert("RGBA")
    except Exception as exc:  # pragma: no cover - defensive guard
        raise ValueError("Invalid image data") from exc

    rule_map = {str(rule.get("id")): rule.get("action", "MASK") for rule in rules if isinstance(rule, dict) and "id" in rule}
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if item_id is None:
            continue
        action = rule_map.get(item_id, item.get("action", "MASK"))
        if action == "KEEP":
            continue
        bbox = item.get("bbox") or item.get("bounding_box")
        if not isinstance(bbox, dict):
            continue
        x = float(bbox.get("x", 0.0))
        y = float(bbox.get("y", 0.0))
        w = float(bbox.get("w", 0.0))
        h = float(bbox.get("h", 0.0))
        x0 = max(0, int(round(x * image.width)) - 2)
        y0 = max(0, int(round(y * image.height)) - 2)
        x1 = min(image.width, int(round((x + w) * image.width)) + 2)
        y1 = min(image.height, int(round((y + h) * image.height)) + 2)
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                if 0 <= xx < image.width and 0 <= yy < image.height:
                    image.putpixel((xx, yy), (0, 0, 0, 255))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False)
    return buffer.getvalue()


def safe_output_filename(ext: str = "png") -> str:
    digest = hashlib.sha256((str(time.time_ns()) + os.urandom(8).hex()).encode("utf-8")).hexdigest()[:8]
    return f"shielded_{digest}.{ext}"


__all__ = ["render_text_redaction", "render_image_redaction", "safe_output_filename"]
