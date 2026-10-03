"""In-memory text/image redaction interfaces for the backend track."""


def render_text_redaction(text: str, items: list[dict], rules: list[dict]) -> str:
    raise NotImplementedError("Implement text redaction in the backend track")


def render_image_redaction(file_bytes: bytes, items: list[dict], rules: list[dict]) -> bytes:
    raise NotImplementedError("Implement image redaction in the backend track")
