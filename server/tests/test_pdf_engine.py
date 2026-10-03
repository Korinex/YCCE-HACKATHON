from __future__ import annotations

import io

import pymupdf
import pytest
from PIL import Image

from app.pdf_engine import inspect_pdf, safe_pdf_filename, sanitize_pdf_bytes


def _pdf(page_count: int = 1, *, sensitive: bool = False) -> bytes:
    document = pymupdf.open()
    for index in range(page_count):
        page = document.new_page(width=200, height=100)
        page.insert_text((20, 50), f"SECRET-{index}" if sensitive else f"page-{index}")
    document.set_metadata(
        {
            "title": "synthetic metadata",
            "author": "synthetic author",
            "subject": "synthetic subject",
            "keywords": "synthetic",
        }
    )
    return document.tobytes(garbage=4, deflate=True)


def _encrypted_pdf(password: str) -> bytes:
    document = pymupdf.open()
    document.new_page().insert_text((20, 50), "SECRET")
    return document.tobytes(
        garbage=4,
        deflate=True,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw=password,
        owner_pw=f"owner-{password}",
    )


def test_pdf_passwords_and_page_limit_are_fail_closed():
    encrypted = _encrypted_pdf("synthetic-password")
    assert inspect_pdf(encrypted, password="synthetic-password") == 1
    with pytest.raises(ValueError, match="Invalid PDF password"):
        inspect_pdf(encrypted, password="wrong")
    with pytest.raises(ValueError, match="Invalid PDF password"):
        inspect_pdf(encrypted)
    with pytest.raises(ValueError, match="maximum page count"):
        inspect_pdf(_pdf(11))


def test_pdf_rebuild_removes_text_metadata_and_object_features():
    source = _pdf(sensitive=True)
    output = sanitize_pdf_bytes(
        source,
        findings=[{"page": 1, "bbox": {"x": 0.0, "y": 0.0, "w": 0.5, "h": 0.5}}],
    )
    assert output != source
    document = pymupdf.open(stream=output, filetype="pdf")
    assert "".join(page.get_text() for page in document) == ""
    assert document.metadata["title"] == ""
    assert document.metadata["author"] == ""
    assert document.metadata["subject"] == ""
    assert document.metadata["keywords"] == ""
    assert document.metadata["creator"] == ""
    assert document.metadata["producer"] == ""
    assert document.embfile_names() == []
    assert all(page.first_annot is None for page in document)
    assert all(page.first_widget is None for page in document)
    assert b"SECRET-0" not in output
    for marker in (
        b"/Metadata",
        b"/EmbeddedFiles",
        b"/JavaScript",
        b"/JS",
        b"/AcroForm",
        b"/Annots",
        b"SOURCE-XMP",
    ):
        assert marker not in output
    document.close()


def test_pdf_coordinates_cover_the_expected_rendered_region():
    source_doc = pymupdf.open()
    page = source_doc.new_page(width=200, height=100)
    page.draw_rect(pymupdf.Rect(0, 0, 100, 50), color=(1, 1, 1), fill=(1, 1, 1))
    source = source_doc.tobytes()
    source_doc.close()
    output = sanitize_pdf_bytes(
        source,
        findings=[{"page": 1, "bbox": {"x": 0.0, "y": 0.0, "w": 0.5, "h": 0.5}}],
    )
    result = pymupdf.open(stream=output, filetype="pdf")
    pixmap = result[0].get_pixmap(matrix=pymupdf.Matrix(150 / 72, 150 / 72))
    image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
    assert image.getpixel((20, 20)) == (0, 0, 0)
    assert image.getpixel((280, 120)) != (0, 0, 0)
    result.close()


def test_pdf_page_offsets_apply_findings_to_the_declared_page_only():
    source = _pdf(2)
    output = sanitize_pdf_bytes(
        source,
        findings=[{"page": 2, "bbox": {"x": 0.0, "y": 0.0, "w": 0.5, "h": 0.5}}],
    )
    result = pymupdf.open(stream=output, filetype="pdf")
    first = result[0].get_pixmap(matrix=pymupdf.Matrix(150 / 72, 150 / 72))
    second = result[1].get_pixmap(matrix=pymupdf.Matrix(150 / 72, 150 / 72))
    first_image = Image.open(io.BytesIO(first.tobytes("png"))).convert("RGB")
    second_image = Image.open(io.BytesIO(second.tobytes("png"))).convert("RGB")
    assert first_image.getpixel((20, 20)) != (0, 0, 0)
    assert second_image.getpixel((20, 20)) == (0, 0, 0)
    result.close()


def test_pdf_filename_is_random_and_has_no_source_name():
    filename = safe_pdf_filename()
    assert filename.startswith("shielded_")
    assert filename.endswith(".pdf")
    assert len(filename.removeprefix("shielded_").removesuffix(".pdf")) == 8
    assert "synthetic" not in filename
