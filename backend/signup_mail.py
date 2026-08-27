"""Signup request notifier.

Writes a mock .eml into backend/mailbox/. When SMTP_HOST is set, also sends
via SMTP. SIGNUP_NOTIFY_EMAIL defaults to program.access@localhost.
"""

from __future__ import annotations

import os
import re
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from pathlib import Path
from typing import Any

from copy_text import fill, get_copy

MAILBOX = Path(__file__).resolve().parent / "mailbox"
DEFAULT_NOTIFY = "program.access@localhost"
DEFAULT_FROM = "f18-portal@localhost"

# Permissive: jane@example.com and local demo addresses like user@localhost.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")


def notify_address() -> str:
    """
    What: Email address that receives access-request notifications.
    Why: Signup form, mailbox API, and /api/copy all show the same destination.
    Who: send_signup_notice, signup_config, api_copy, list_mailbox consumers.
    Where: SIGNUP_NOTIFY_EMAIL env; default program.access@localhost.
    How: Read env, strip; fall back to DEFAULT_NOTIFY.
    """
    return (os.environ.get("SIGNUP_NOTIFY_EMAIL") or DEFAULT_NOTIFY).strip()


def from_address() -> str:
    """
    What: From: address used on signup notification messages.
    Why: Mailbox .eml and SMTP need a sender independent of the applicant.
    Who: _build_message.
    Where: SIGNUP_FROM_EMAIL env; default f18-portal@localhost.
    How: Read env, strip; fall back to DEFAULT_FROM.
    """
    return (os.environ.get("SIGNUP_FROM_EMAIL") or DEFAULT_FROM).strip()


def smtp_configured() -> bool:
    """
    What: Whether real SMTP should be used in addition to the mailbox file.
    Why: Local demos write .eml only; hosted deploys can send for real.
    Who: send_signup_notice, signup_mailbox.
    Where: SMTP_HOST env.
    How: True when SMTP_HOST is a non-empty string.
    """
    return bool((os.environ.get("SMTP_HOST") or "").strip())


def _is_dev() -> bool:
    """
    What: True when Flask is running in development mode.
    Why: Mailbox listing must not leak applicant mail in production.
    Who: Public is_dev wrapper and mailbox list gate.
    Where: FLASK_DEBUG env (default on).
    How: Treat 0/false/False as production.
    """
    return os.environ.get("FLASK_DEBUG", "1") not in ("0", "false", "False")


def is_dev() -> bool:
    """
    What: Public wrapper for the development-mode check.
    Why: app.signup_mailbox should not import the private helper.
    Who: GET /api/auth/signup/mailbox.
    Where: Same FLASK_DEBUG rule as _is_dev.
    How: Delegate to _is_dev().
    """
    return _is_dev()


def validate_signup(payload: Any) -> tuple[dict | None, str | None]:
    """
    What: Parse and validate a request-access JSON body.
    Why: The notifier must not send empty or garbage applicant data.
    Who: app.signup.
    Where: POST /api/auth/signup JSON {name, email, organization?}.
    How: Require name/email, length limits, permissive email regex; return (data, err).
    """
    if not isinstance(payload, dict):
        return None, "JSON body with name and email is required."

    name = str(payload.get("name") or "").strip()
    email = str(payload.get("email") or "").strip()
    organization = str(payload.get("organization") or "").strip()

    if not name:
        return None, "Name is required."
    if len(name) > 120:
        return None, "Name is too long."
    if not email:
        return None, "Email is required."
    if len(email) > 254 or not EMAIL_RE.match(email):
        return None, "Enter a valid email address."
    if len(organization) > 200:
        return None, "Organization is too long."

    return {
        "name": name,
        "email": email,
        "organization": organization or None,
    }, None


def _safe_token(value: str) -> str:
    """
    What: Turn an email into a filesystem-safe mailbox filename token.
    Why: .eml names include the applicant address and must stay portable.
    Who: _write_mailbox.
    Where: backend/mailbox/*.eml.
    How: Replace non [A-Za-z0-9._+-] with _; cap at 80 chars.
    """
    cleaned = re.sub(r"[^A-Za-z0-9._+-]+", "_", value)
    return cleaned[:80] or "applicant"


def _build_message(applicant: dict, to_addr: str, submitted: datetime) -> EmailMessage:
    """
    What: Build the signup notification EmailMessage from copy templates.
    Why: Subject/body must be backend-configurable like the rest of the portal.
    Who: send_signup_notice.
    Where: Uses copy.json email.subject / email.body; SIGNUP_* for headers.
    How: get_copy + fill {name} {email} {organization} {notifyEmail} {submitted}.
    """
    email_copy = get_copy().get("email") or {}
    org = (
        applicant.get("organization")
        or email_copy.get("organizationFallback")
        or "(not provided)"
    )
    iso = submitted.isoformat()
    values = {
        "name": applicant["name"],
        "email": applicant["email"],
        "organization": org,
        "notifyEmail": to_addr,
        "submitted": iso,
    }
    subject_tpl = email_copy.get("subject") or "Program access request: {name}"
    body_tpl = email_copy.get("body") or (
        "A program access request was submitted.\n\n"
        "Name: {name}\nEmail: {email}\nOrganization: {organization}\n"
        "Submitted: {submitted}\n\n"
        "This message was generated by the F/A-18 Program Access Portal demo.\n"
    )
    msg = EmailMessage()
    msg["From"] = from_address()
    msg["To"] = to_addr
    msg["Subject"] = fill(subject_tpl, **values)
    msg["Date"] = format_datetime(submitted)
    msg["Message-ID"] = make_msgid(domain="f18-portal.local")
    msg["X-F18-Applicant-Email"] = applicant["email"]
    msg["X-F18-Applicant-Name"] = applicant["name"]
    if applicant.get("organization"):
        msg["X-F18-Applicant-Org"] = applicant["organization"]
    msg["X-F18-Submitted"] = iso
    msg.set_content(fill(body_tpl, **values))
    return msg


def _write_mailbox(msg: EmailMessage, applicant: dict, submitted: datetime) -> Path:
    """
    What: Persist the notification as a .eml under backend/mailbox/.
    Why: Demos without SMTP still have a readable record of the request.
    Who: send_signup_notice; later list_mailbox / _parse_eml.
    Where: backend/mailbox/{stamp}-{email}.eml.
    How: Unique filename; write bytes(msg); suffix -N on collision.
    """
    MAILBOX.mkdir(parents=True, exist_ok=True)
    stamp = submitted.strftime("%Y%m%dT%H%M%SZ")
    token = _safe_token(applicant["email"].replace("@", "_at_"))
    path = MAILBOX / f"{stamp}-{token}.eml"
    n = 1
    while path.exists():
        path = MAILBOX / f"{stamp}-{token}-{n}.eml"
        n += 1
    path.write_bytes(bytes(msg))
    return path


def _send_smtp(msg: EmailMessage) -> None:
    """
    What: Deliver the notification through the configured SMTP server.
    Why: Hosted deployments can mail a real SIGNUP_NOTIFY_EMAIL inbox.
    Who: send_signup_notice when SMTP_HOST is set.
    Where: SMTP_HOST/PORT/USER/PASSWORD plus SSL or STARTTLS.
    How: SMTP or SMTP_SSL, optional login, send_message, then quit.
    """
    host = (os.environ.get("SMTP_HOST") or "").strip()
    port = int(os.environ.get("SMTP_PORT") or "587")
    user = os.environ.get("SMTP_USER") or ""
    password = os.environ.get("SMTP_PASSWORD") or ""
    use_ssl = os.environ.get("SMTP_SSL", "0") in ("1", "true", "True")
    use_tls = os.environ.get("SMTP_STARTTLS", "1") not in ("0", "false", "False")
    timeout = float(os.environ.get("SMTP_TIMEOUT") or "15")

    if use_ssl:
        client = smtplib.SMTP_SSL(host, port, timeout=timeout)
    else:
        client = smtplib.SMTP(host, port, timeout=timeout)
    try:
        client.ehlo()
        if not use_ssl and use_tls:
            client.starttls()
            client.ehlo()
        if user:
            client.login(user, password)
        client.send_message(msg)
    finally:
        try:
            client.quit()
        except Exception:
            client.close()


def send_signup_notice(applicant: dict) -> dict:
    """
    What: Notify SIGNUP_NOTIFY_EMAIL of a validated access request.
    Why: Program contacts need the applicant details to grant access.
    Who: app.signup after validate_signup.
    Where: Always write mailbox .eml; SMTP only if SMTP_HOST is set.
    How: _build_message, _write_mailbox, optional _send_smtp; return ids.
    """
    to_addr = notify_address()
    submitted = datetime.now(timezone.utc).replace(microsecond=0)
    msg = _build_message(applicant, to_addr, submitted)
    path = _write_mailbox(msg, applicant, submitted)
    mocked = not smtp_configured()
    if not mocked:
        _send_smtp(msg)
    return {
        "id": msg["Message-ID"],
        "to": to_addr,
        "mocked": mocked,
        "path": str(path.name),
        "submitted": submitted.isoformat(),
    }


def _parse_eml(path: Path) -> dict[str, Any]:
    """
    What: Turn one mailbox .eml into a JSON-friendly dict.
    Why: The dev mailbox API should show subject, preview, and applicant.
    Who: list_mailbox.
    Where: backend/mailbox/*.eml written by _write_mailbox.
    How: email.policy parse; prefer plain body; pull X-F18-* headers.
    """
    from email import message_from_bytes
    from email.policy import default as email_policy

    raw = path.read_bytes()
    parsed = message_from_bytes(raw, policy=email_policy)
    body = parsed.get_body(preferencelist=("plain",))
    text = body.get_content() if body is not None else ""
    return {
        "id": parsed.get("Message-ID"),
        "to": parsed.get("To"),
        "from": parsed.get("From"),
        "subject": parsed.get("Subject"),
        "timestamp": parsed.get("X-F18-Submitted") or parsed.get("Date"),
        "filename": path.name,
        "applicant": {
            "name": parsed.get("X-F18-Applicant-Name"),
            "email": parsed.get("X-F18-Applicant-Email"),
            "organization": parsed.get("X-F18-Applicant-Org"),
        },
        "preview": (text or "").strip()[:500],
    }


def list_mailbox(limit: int = 8) -> list[dict[str, Any]]:
    """
    What: Newest mailbox messages for the dev listing endpoint.
    Why: Testers can confirm a signup without opening the filesystem.
    Who: app.signup_mailbox.
    Where: backend/mailbox .eml and legacy .json files.
    How: Sort by mtime desc; parse each; cap limit between 1 and 25.
    """
    MAILBOX.mkdir(parents=True, exist_ok=True)
    files = [p for p in MAILBOX.iterdir() if p.suffix.lower() in {".eml", ".json"} and p.is_file()]
    def _mtime(path: Path) -> float:
        """
        What: Modification time used to sort mailbox files newest-first.
        Why: list_mailbox should not use an undocumented lambda.
        Who: files.sort in list_mailbox.
        Where: backend/mailbox entries.
        How: Ask the filesystem for last-write time so newest mailbox files sort first.
        """
        return path.stat().st_mtime

    files.sort(key=_mtime, reverse=True)
    out: list[dict[str, Any]] = []
    for path in files[: max(1, min(limit, 25))]:
        if path.suffix.lower() == ".eml":
            try:
                out.append(_parse_eml(path))
            except Exception as exc:
                out.append({"filename": path.name, "error": str(exc)})
        else:
            try:
                import json

                data = json.loads(path.read_text(encoding="utf-8"))
                data.setdefault("filename", path.name)
                out.append(data)
            except Exception as exc:
                out.append({"filename": path.name, "error": str(exc)})
    return out
