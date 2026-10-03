"""OCR adapter interface. The feature track will add EasyOCR or PyTesseract."""


def extract_text_and_boxes(image_bytes: bytes) -> list[dict]:
    raise NotImplementedError("Implement OCR extraction in the intelligence track")
