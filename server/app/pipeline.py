"""Orchestration interface for text detection and image OCR detection."""


def detect_pii_pipeline(
    text: str | None = None,
    image_bytes: bytes | None = None,
) -> list[dict]:
    raise NotImplementedError("Implement PII orchestration in the intelligence track")
