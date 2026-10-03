"""IFSC, phone, UPI, bank-account, and Luhn validator interfaces."""


def validate_financial_value(kind: str, value: str) -> tuple[bool, str]:
    raise NotImplementedError("Implement financial validators in the intelligence track")
