"""
audit.py – Audit data-classes for the PS-06 Privacy Shield (Backend 3).

These types are the sole public contract between verify_service.py and any
caller.  They are intentionally plain dataclasses (no Pydantic) to keep this
module dependency-free.

Verdict values
--------------
CLEAN   – all applicable checks passed; no residual PII detected.
PARTIAL – one or more checks are unsupported for this content type; the
          supported checks all passed.  Callers must not treat PARTIAL as
          fully verified.
FAIL    – at least one supported check detected residual PII.

CheckStatus values
------------------
PASSED      – check ran and found no residual PII.
FAILED      – check ran and found residual PII.
UNSUPPORTED – check cannot run (missing dependency / wrong content type).
              UNSUPPORTED must never be treated as PASSED.

ResidualHit
-----------
Describes one detected residual occurrence.  Raw PII values are NEVER stored
here; only safe, opaque metadata (category, page, region).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Literal

# ── Verdict ──────────────────────────────────────────────────────────────────

Verdict = Literal["CLEAN", "PARTIAL", "FAIL"]

# ── Per-check status ──────────────────────────────────────────────────────────

CheckStatus = Literal["PASSED", "FAILED", "UNSUPPORTED"]


@dataclass(frozen=True)
class CheckResult:
    """Result of a single verification check."""

    name: str
    status: CheckStatus
    # Human-readable reason; must NEVER contain raw PII values.
    reason: str = ""
    # Method note: how the check was performed (safe, no PII).
    method_note: str = ""


@dataclass(frozen=True)
class ResidualHit:
    """Safe description of a single residual PII occurrence.

    Fields
    ------
    category  : PII type category (e.g. ``"AADHAAR"``, ``"PAN"``).
    page      : 1-based page number for multi-page documents; ``None`` for
                text or single-page images.
    region    : Opaque spatial descriptor (e.g. ``"bbox:x=10,y=20,w=80,h=15"``).
                Never contains the raw value itself.
    """

    category: str
    page: int | None = None
    region: str | None = None


# ── Top-level result ──────────────────────────────────────────────────────────


@dataclass
class AuditResult:
    """Complete audit result returned by ``verify_cleaned_output``."""

    verdict: Verdict
    checks: list[CheckResult] = field(default_factory=list)
    residuals: list[ResidualHit] = field(default_factory=list)
    # Free-text notes; must NEVER contain raw PII values.
    notes: list[str] = field(default_factory=list)
    # Names of interfaces that are not yet implemented in this repo.
    missing_interfaces: list[str] = field(default_factory=list)
    # Number of checks that actually ran (PASSED or FAILED, not UNSUPPORTED).
    ran: int = 0
    # ISO-8601 UTC timestamp of when the audit was completed.
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-friendly representation containing safe fields only."""
        return {
            "verdict": self.verdict,
            "checks": [{"name": c.name, "status": c.status,
                        "reason": c.reason, "method_note": c.method_note}
                       for c in self.checks],
            "residuals": [{"category": r.category, "page": r.page,
                           "region": r.region} for r in self.residuals],
            "ran": self.ran,
            "timestamp": self.timestamp,
            "notes": list(self.notes),
            "missing_interfaces": list(self.missing_interfaces),
        }
