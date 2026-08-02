"""One-time short-lived WebSocket tickets for browser WebSocket clients.

Browser WebSocket APIs cannot attach an Authorization header.  A REST call
authenticated with the real session token mints a random ticket.  The ticket
is carried once in ``Sec-WebSocket-Protocol``, consumed before accept, and is
never a reusable session credential.
"""
from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class _TicketRecord:
    session_id: str
    expires_at_monotonic: float


class WebSocketTicketStore:
    def __init__(self, ttl_seconds: float = 30.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._tickets: Dict[str, _TicketRecord] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _digest(ticket: str) -> str:
        return hashlib.sha256(ticket.encode("utf-8")).hexdigest()

    def issue(self, session_id: str) -> str:
        raw = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self._lock:
            self._purge_locked(now)
            self._tickets[self._digest(raw)] = _TicketRecord(
                session_id=session_id,
                expires_at_monotonic=now + self.ttl_seconds,
            )
        return raw

    def consume(self, raw: str) -> Optional[str]:
        now = time.monotonic()
        with self._lock:
            self._purge_locked(now)
            record = self._tickets.pop(self._digest(raw), None)
        if record is None or record.expires_at_monotonic <= now:
            return None
        return record.session_id

    def _purge_locked(self, now: float) -> None:
        expired = [key for key, item in self._tickets.items() if item.expires_at_monotonic <= now]
        for key in expired:
            self._tickets.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._tickets.clear()


ticket_store = WebSocketTicketStore()

