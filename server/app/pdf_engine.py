from __future__ import annotations

import io
import os
import secrets
from typing import Any, Iterable, Literal

import pymupdf
from PIL import Image, ImageDraw

MAX_PDF_PAGES = 10
RENDER_DPI = 150
PDF_MODE: Literal["flatten", "page_images"] = os.getenv(
    "PDF_MODE", "page_images"
).lower()  # type: ignore[assignment]
if PDF_MODE not in {"flatten", "page_images"}:
    PDF_MODE = "page_images"


def _open_pdf(pdf_bytes: bytes, password: str | None) -> pymupdf.Document:
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes:
        raise ValueError("PDF input is empty")
    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except (pymupdf.FileDataError, ValueError) as exc:
        raise ValueError("Invalid PDF data") from exc
    if document.needs_pass:
        if not password or not document.authenticate(password):
            document.close()
            raise ValueError("Invalid PDF password")
    return document


def inspect_pdf(pdf_bytes: bytes, *, password: str | None = None) -> int:
    document = _open_pdf(pdf_bytes, password)
    try:
        page_count = document.page_count
        if page_count < 1:
            raise ValueError("PDF contains no pages")
        if page_count > MAX_PDF_PAGES:
            raise ValueError("PDF exceeds the maximum page count")
        return page_count
    finally:
        document.close()


def _normalized_rect(item: dict[str, Any], page: pymupdf.Page) -> pymupdf.Rect | None:
    bbox = item.get("bbox")
    if not isinstance(bbox, dict):
        return None
    try:
        x = max(0.0, min(1.0, float(bbox["x"])))
        y = max(0.0, min(1.0, float(bbox["y"])))
        width = max(0.0, min(1.0 - x, float(bbox["w"])))
        height = max(0.0, min(1.0 - y, float(bbox["h"])))
    except (KeyError, TypeError, ValueError):
        return None
    return pymupdf.Rect(
        page.rect.x0 + x * page.rect.width,
        page.rect.y0 + y * page.rect.height,
        page.rect.x0 + (x + width) * page.rect.width,
        page.rect.y0 + (y + height) * page.rect.height,
    )


def _page_findings(
    findings: Iterable[dict[str, Any]], page_number: int
) -> Iterable[dict[str, Any]]:
    for finding in findings:
        bbox = finding.get("bbox")
        finding_page = finding.get("page")
        if isinstance(bbox, dict) and bbox.get("page") is not None:
            finding_page = bbox["page"]
        if finding_page is None or int(finding_page) == page_number:
            yield finding


def _render_page(
    page: pymupdf.Page,
    findings: Iterable[dict[str, Any]],
) -> bytes:
    scale = RENDER_DPI / 72.0
    matrix = pymupdf.Matrix(scale, scale)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False, annots=False)
    image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
    draw = ImageDraw.Draw(image)
    for finding in findings:
        rect = _normalized_rect(finding, page)
        if rect is None or rect.is_empty:
            continue
        left = round((rect.x0 - page.rect.x0) * scale)
        top = round((rect.y0 - page.rect.y0) * scale)
        right = round((rect.x1 - page.rect.x0) * scale)
        bottom = round((rect.y1 - page.rect.y0) * scale)
        draw.rectangle((left, top, right, bottom), fill=(0, 0, 0))
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def sanitize_pdf_bytes(
    pdf_bytes: bytes,
    *,
    findings: list[dict[str, Any]] | None = None,
    password: str | None = None,
    mode: Literal["flatten", "page_images"] | None = None,
) -> bytes:
    """Rasterize every page into a new in-memory PDF.

    Both modes use the page-image rebuild. ``flatten`` is retained as the
    explicit secure mode name; preserving the source object tree is avoided.
    """
    selected_mode = mode or PDF_MODE
    if selected_mode not in {"flatten", "page_images"}:
        raise ValueError("Unsupported PDF mode")
    document = _open_pdf(pdf_bytes, password)
    output = pymupdf.open()
    try:
        if document.page_count < 1 or document.page_count > MAX_PDF_PAGES:
            raise ValueError("PDF exceeds the maximum page count")
        safe_findings = findings or []
        for page_number, page in enumerate(document, start=1):
            image_bytes = _render_page(
                page,
                _page_findings(safe_findings, page_number),
            )
            new_page = output.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, stream=image_bytes)
        output.set_metadata({})
        output.save(
            io.BytesIO(),
            garbage=4,
            clean=True,
            deflate=True,
        )
        return output.tobytes(garbage=4, clean=True, deflate=True)
    finally:
        document.close()
        output.close()


def safe_pdf_filename(ext: str = "pdf") -> str:
    return f"shielded_{secrets.token_hex(4)}.{ext}"


__all__ = [
    "MAX_PDF_PAGES",
    "PDF_MODE",
    "RENDER_DPI",
    "inspect_pdf",
    "sanitize_pdf_bytes",
    "safe_pdf_filename",
]
