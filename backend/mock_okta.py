"""In-memory mock OIDC authorization server for local F/A-18 portal demos.

When OKTA_ISSUER is unset the Flask app uses this module instead of a real IdP.
Codes and CSRF state tokens are short-lived and stored in process memory.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Optional

CODE_TTL_SECONDS = 120
STATE_TTL_SECONDS = 600


@dataclass
class MockUser:
    email: str
    password: str
    name: str
    clearance: str  # "granted" | "denied"
    callsign: str


USERS: dict[str, MockUser] = {
    "f18.pilot@boeing.com": MockUser(
        email="f18.pilot@boeing.com",
        password="HornetReady1",
        name="LT. Callsign Viper",
        clearance="granted",
        callsign="VIPER",
    ),
    "visitor@example.com": MockUser(
        email="visitor@example.com",
        password="NoClearance",
        name="Guest Visitor",
        clearance="denied",
        callsign="CIVILIAN",
    ),
}


@dataclass
class _StateRecord:
    created: float
    nonce: str
    redirect_uri: str
    client_id: str


@dataclass
class _CodeRecord:
    created: float
    user: MockUser
    state: str
    nonce: str
    client_id: str
    redirect_uri: str


@dataclass
class MockOktaStore:
    """Authorization-code + state store for the mock IdP."""

    states: dict[str, _StateRecord] = field(default_factory=dict)
    codes: dict[str, _CodeRecord] = field(default_factory=dict)

    def _purge(self) -> None:
        """
        What: Drop expired CSRF state and authorization-code records.
        Why: In-memory tokens must not live forever in a long-running demo process.
        Who: Every other MockOktaStore method before it reads or writes.
        Where: Process-local states/codes dicts.
        How: Keep entries younger than STATE_TTL_SECONDS / CODE_TTL_SECONDS.
        """
        now = time.time()
        self.states = {
            k: v
            for k, v in self.states.items()
            if now - v.created < STATE_TTL_SECONDS
        }
        self.codes = {
            k: v
            for k, v in self.codes.items()
            if now - v.created < CODE_TTL_SECONDS
        }

    def create_state(self, client_id: str, redirect_uri: str) -> tuple[str, str]:
        """
        What: Mint a CSRF state + nonce for an authorize request.
        Why: The login redirect and callback must agree on the same flow.
        Who: app.auth_login; mock_okta_hosted when SPA posts without a prior hop.
        Where: In-memory store.states.
        How: Purge, random token_urlsafe values, record client_id and redirect_uri.
        """
        self._purge()
        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(16)
        self.states[state] = _StateRecord(
            created=time.time(),
            nonce=nonce,
            redirect_uri=redirect_uri,
            client_id=client_id,
        )
        return state, nonce

    def peek_state(self, state: str) -> Optional[_StateRecord]:
        """
        What: Look up an authorize state without consuming it.
        Why: The hosted login page must accept the same state on GET and POST.
        Who: app.mock_okta_hosted.
        Where: store.states after purge.
        How: Drop expired tokens first, then dict.get so GET and POST can share the same key.
        """
        self._purge()
        return self.states.get(state)

    def authenticate(self, email: str, password: str) -> Optional[MockUser]:
        """
        What: Check email/password against the two built-in demo accounts.
        Why: The mock IdP must accept HornetReady1 / NoClearance only.
        Who: app.mock_okta_hosted POST.
        Where: USERS keyed by lowercase email.
        How: Lookup then exact password match; else None.
        """
        user = USERS.get((email or "").strip().lower())
        if user is None or user.password != password:
            return None
        return user

    def issue_code(
        self,
        user: MockUser,
        state: str,
        nonce: str,
        client_id: str,
        redirect_uri: str,
    ) -> str:
        """
        What: Create a short-lived authorization code bound to a user and state.
        Why: The callback exchanges this code for a session.
        Who: app.mock_okta_hosted after authenticate.
        Where: store.codes; CODE_TTL_SECONDS lifetime.
        How: Purge, token_urlsafe, store user/state/nonce/client/redirect.
        """
        self._purge()
        code = secrets.token_urlsafe(28)
        self.codes[code] = _CodeRecord(
            created=time.time(),
            user=user,
            state=state,
            nonce=nonce,
            client_id=client_id,
            redirect_uri=redirect_uri,
        )
        return code

    def exchange_code(self, code: str, state: str) -> Optional[_CodeRecord]:
        """
        What: One-time swap of an authorization code (+ state) for the user record.
        Why: The callback must not accept a replayed code.
        Who: app.auth_callback and the JSON shortcut in mock_okta_hosted.
        Where: store.codes.
        How: Pop the code; require matching state; return the record or None.
        """
        self._purge()
        rec = self.codes.pop(code, None)
        if rec is None:
            return None
        if rec.state != state:
            return None
        return rec


store = MockOktaStore()
