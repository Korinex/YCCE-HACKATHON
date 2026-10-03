"""PAN structure checks only; no issuer or checksum lookup is performed."""

from __future__ import annotations

import re

_PAN = re.compile(r"[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]")


def validate_pan(value: str) -> tuple[bool, str]:
    candidate = re.sub(r"\s+", "", value).upper()
    if _PAN.fullmatch(candidate):
        return True, "FORMAT_MATCH; FORMAT_ONLY; ISSUER_NOT_CHECKED"
    return False, "FORMAT_INVALID"
