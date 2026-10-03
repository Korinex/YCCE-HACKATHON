from __future__ import annotations

import hashlib
import io
import os
import re
from typing import Any


def sanitize_pdf_bytes(pdf_bytes: bytes, *, password: str | None = None) -> bytes:
    """Create a sanitized PDF-like payload without storing source text or metadata."""
    if not pdf_bytes:
        raise ValueError("PDF content is required")
    if password:
        password = str(password)
    # Real PDF parsing is intentionally deferred; this module only guarantees safe in-memory processing.
    payload = b"%PDF-1.4\n" + hashlib.sha256(pdf_bytes).digest()[:32] + b"\n%%EOF\n"
    return payload


def safe_pdf_filename(ext: str = "pdf") -> str:
    digest = hashlib.sha256((str(os.urandom(8)) + str(__import__("time").time_ns())).encode()).hexdigest()[:8]
    return f"shielded_{digest}.{ext}"


__all__ = ["sanitize_pdf_bytes", "safe_pdf_filename"]
