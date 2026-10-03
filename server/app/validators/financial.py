"""Deterministic Indian payment and financial identifier format checks."""

from __future__ import annotations

import re

_IFSC = re.compile(r"[A-Z]{4}0[A-Z0-9]{6}")
_PHONE = re.compile(r"[6-9]\d{9}")
_GSTIN = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]")
_UPI = re.compile(r"[A-Z0-9._-]{2,256}@[A-Z][A-Z0-9.-]{1,63}", re.I)
_KNOWN_UPI = {
    "okaxis", "okhdfcbank", "oksbi", "okicici", "ybl", "ibl", "axl",
    "paytm", "upi", "apl", "rapl", "sbi", "icici", "hdfcbank", "axisbank",
    "kotak", "fbl", "freecharge", "jio", "airtel", "amazonpay",
}


def luhn_valid(value: str) -> bool:
    digits = re.sub(r"[ -]", "", value)
    if not re.fullmatch(r"\d{13,19}", digits):
        return False
    total = 0
    for offset, char in enumerate(reversed(digits)):
        digit = int(char)
        if offset % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def validate_financial_value(kind: str, value: str) -> tuple[bool, str]:
    kind = kind.upper()
    compact = re.sub(r"[\s-]", "", value)
    if kind == "IFSC":
        valid = bool(_IFSC.fullmatch(compact.upper()))
        return valid, "FORMAT_MATCH; ISSUER_NOT_CHECKED" if valid else "FORMAT_INVALID"
    if kind == "PHONE":
        digits = re.sub(r"[ -]", "", value)
        if digits.startswith("+91"):
            digits = digits[3:]
        elif len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        valid = bool(_PHONE.fullmatch(digits))
        return valid, "FORMAT_MATCH; ACTIVE_STATUS_NOT_CHECKED" if valid else "FORMAT_INVALID"
    if kind == "UPI":
        if not _UPI.fullmatch(value.strip()):
            return False, "FORMAT_INVALID"
        suffix = value.rsplit("@", 1)[-1].lower()
        if suffix in _KNOWN_UPI:
            return True, "KNOWN_SUFFIX; ISSUER_NOT_CHECKED"
        return False, "UNKNOWN_SUFFIX; REVIEW"
    if kind == "CREDIT_CARD":
        valid = luhn_valid(value)
        return valid, "LUHN_PASS; ISSUER_NOT_CHECKED" if valid else "CHECKSUM_FAIL_OR_FORMAT_INVALID"
    if kind == "GSTIN":
        valid = bool(_GSTIN.fullmatch(compact.upper()))
        return valid, "FORMAT_MATCH; FORMAT_ONLY; ISSUER_NOT_CHECKED" if valid else "FORMAT_INVALID"
    if kind == "BANK_ACCOUNT":
        digits = re.sub(r"[ -]", "", value)
        valid = bool(re.fullmatch(r"\d{9,18}", digits))
        return valid, "FORMAT_MATCH; FORMAT_ONLY; ISSUER_NOT_CHECKED" if valid else "FORMAT_INVALID"
    return False, "UNSUPPORTED_VALIDATOR"
