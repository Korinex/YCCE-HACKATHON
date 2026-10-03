from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .schemas import SESSION_TTL_SECONDS, SessionRecord

MAX_SESSIONS = 128


class SessionStore:
    _instance: "SessionStore | None" = None
    _lock = threading.RLock()

    def __new__(cls) -> "SessionStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._sessions: dict[str, SessionRecord] = {}
        return cls._instance

    def create(
        self,
        *,
        content_type: str,
        content: Any = None,
        metadata: dict[str, Any] | None = None,
        ttl_seconds: int = SESSION_TTL_SECONDS,
    ) -> SessionRecord:
        if ttl_seconds < 1 or ttl_seconds > SESSION_TTL_SECONDS:
            raise ValueError("Session TTL must be between 1 and 600 seconds")
        request_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        session = SessionRecord(
            request_id=request_id,
            content_type=content_type,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            original_content=content if content is not None else "",
            document_metadata=metadata or {},
            ocr_metadata={},
            findings=[],
        )
        with self._lock:
            self.cleanup_expired()
            if len(self._sessions) >= MAX_SESSIONS:
                raise OverflowError("Session capacity reached")
            self._sessions[request_id] = session
        return session

    def get(self, request_id: str) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(request_id)
            if record is None:
                return None
            if record.is_expired:
                self._sessions.pop(request_id, None)
                return None
            return record

    def register_findings(self, request_id: str, findings: list[Any]) -> SessionRecord | None:
        with self._lock:
            record = self._sessions.get(request_id)
            if record is None or record.is_expired:
                self._sessions.pop(request_id, None)
                return None
            record.findings = list(findings)
            return record

    def delete(self, request_id: str) -> None:
        with self._lock:
            self._sessions.pop(request_id, None)

    def clear_all(self) -> None:
        with self._lock:
            self._sessions.clear()

    def cleanup_expired(self) -> list[str]:
        expired_ids: list[str] = []
        with self._lock:
            for request_id, record in list(self._sessions.items()):
                if record.is_expired:
                    expired_ids.append(request_id)
                    del self._sessions[request_id]
        return expired_ids

    def shutdown(self) -> None:
        self.clear_all()


def create_session(
    *,
    content_type: str,
    content: Any = None,
    metadata: dict[str, Any] | None = None,
    ttl_seconds: int = SESSION_TTL_SECONDS,
) -> SessionRecord:
    return SessionStore().create(
        content_type=content_type,
        content=content,
        metadata=metadata,
        ttl_seconds=ttl_seconds,
    )


def get_session(request_id: str) -> SessionRecord | None:
    return SessionStore().get(request_id)


def delete_session(request_id: str) -> None:
    SessionStore().delete(request_id)


__all__ = [
    "SessionStore",
    "create_session",
    "get_session",
    "delete_session",
    "SESSION_TTL_SECONDS",
]
