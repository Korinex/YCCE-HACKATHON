"""Aadhaar and VID format checks. These checks do not identify a person."""

from __future__ import annotations

import re

_VERHOEFF_D = (
    (0,1,2,3,4,5,6,7,8,9),(1,2,3,4,0,6,7,8,9,5),(2,3,4,0,1,7,8,9,5,6),
    (3,4,0,1,2,8,9,5,6,7),(4,0,1,2,3,9,5,6,7,8),(5,9,8,7,6,0,4,3,2,1),
    (6,5,9,8,7,1,0,4,3,2),(7,6,5,9,8,2,1,0,4,3),(8,7,6,5,9,3,2,1,0,4),
    (9,8,7,6,5,4,3,2,1,0),
)
_VERHOEFF_P = (
    (0,1,2,3,4,5,6,7,8,9),(1,5,7,6,2,8,3,0,9,4),
    (5,8,0,3,7,9,6,1,4,2),(8,9,1,6,0,4,3,5,2,7),
    (9,4,5,3,1,2,6,8,7,0),(4,2,8,6,5,7,3,9,0,1),
    (2,7,9,3,8,0,6,4,1,5),(7,0,4,6,9,1,3,2,5,8),
)


def verhoeff_valid(value: str) -> bool:
    """Return whether a 12-digit value has a valid Verhoeff checksum."""
    digits = re.sub(r"[ -]", "", value)
    if not re.fullmatch(r"\d{12}", digits):
        return False
    check = 0
    for position, digit in enumerate(reversed(digits)):
        check = _VERHOEFF_D[check][_VERHOEFF_P[position % 8][int(digit)]]
    return check == 0


def validate_aadhaar(number: str) -> tuple[bool, str]:
    digits = re.sub(r"[ -]", "", number)
    if not re.fullmatch(r"[2-9]\d{11}", digits):
        return False, "FORMAT_INVALID"
    if not verhoeff_valid(digits):
        return False, "CHECKSUM_FAIL"
    return True, "CHECKSUM_PASS; ISSUER_NOT_CHECKED"


def validate_vid(value: str) -> tuple[bool, str]:
    digits = re.sub(r"[ -]", "", value)
    if re.fullmatch(r"1\d{15}", digits):
        return True, "FORMAT_MATCH; ISSUER_NOT_CHECKED"
    return False, "FORMAT_INVALID"
