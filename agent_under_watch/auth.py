"""A stand-in for the organisation's real authentication system.

The key idea: the gateway learns WHO is logged in from here, never from the agent.
An agent only holds an opaque session_id; it cannot claim to be acting for anyone else.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from .models import Session


class AuthService:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def start_session(
        self,
        agent_id: str,
        subject_id: str | None,
        started_at: datetime,
        step_up_verified: bool = False,
        session_id: str | None = None,
    ) -> Session:
        sid = session_id or uuid.uuid4().hex[:12]
        session = Session(sid, agent_id, subject_id, started_at, step_up_verified)
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def pause(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].paused = True

    def resume(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].paused = False
