from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from .schemas import SafeReceipt


def build_receipt(*, input_kind: str, page_count: int, category_counts: dict[str, int], confidence_band_counts: dict[str, int], actions_by_category: dict[str, int], review_pages: list[int] | None = None, review_regions: list[str] | None = None, ocr_warnings: list[str] | None = None, residual_verdict: dict[str, Any] | None = None, app_version: str = "0.1.0") -> SafeReceipt:
    uid = uuid.uuid4().hex
    receipt = SafeReceipt(
        run_id=uid,
        app_version=app_version,
        timestamp=datetime.now(timezone.utc),
        input_kind=input_kind,
        page_count=max(page_count, 0),
        category_counts={str(k): int(v) for k, v in (category_counts or {}).items()},
        confidence_band_counts={str(k): int(v) for k, v in (confidence_band_counts or {}).items()},
        actions_by_category={str(k): int(v) for k, v in (actions_by_category or {}).items()},
        review_pages=list(review_pages or []),
        review_regions=list(review_regions or []),
        ocr_warnings=["OCR_REVIEW" for _ in (ocr_warnings or [])],
        residual_verdict={
            key: value
            for key, value in (residual_verdict or {}).items()
            if key in {"verdict", "categories", "pages", "regions"}
        },
    )
    return receipt


def redact_receipt_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def safe_export_filename(ext: str = "png") -> str:
    digest = hashlib.sha256(os.urandom(8)).hexdigest()[:8]
    return f"shielded_{digest}.{ext}"


__all__ = ["build_receipt", "redact_receipt_text", "safe_export_filename"]
