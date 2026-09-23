"""schedule_meeting — generate a real RFC 5545 .ics calendar file.

This module BUILDS the .ics content (deterministic, standards-compliant).
It does NOT contact any calendar provider and does NOT send invitations —
no external send happens, so no approval is required. Honestly labeled:
hand the returned .ics to your calendar client or send it via send_email
(which requires an approval).
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

EXEC_PRICE_USD = 0.001

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _parse_iso(value: str, what: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ModuleError("%s must be a non-empty ISO-8601 string" % what)
    text = value.strip()
    # tolerate trailing 'Z'
    probe = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        dt = datetime.fromisoformat(probe)
    except ValueError:
        raise ModuleError("%s is not a valid ISO-8601 datetime: %r" % (what, value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _escape_ics(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str):
    """RFC 5545 line folding at 75 octets; yields continuation lines."""
    encoded = line.encode("utf-8")
    out = []
    first = True
    while len(encoded) > 75:
        # cut on a UTF-8 boundary at <= 75 bytes
        cut = 75
        while cut > 0 and (encoded[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append((" " if not first else "") + encoded[:cut].decode("utf-8"))
        encoded = encoded[cut:]
        first = False
    out.append((" " if not first else "") + encoded.decode("utf-8"))
    return out


def _dt_utc(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")

    title = inputs.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ModuleError("title is required (non-empty string)")

    start = _parse_iso(inputs.get("start_iso"), "start_iso")
    end = _parse_iso(inputs.get("end_iso"), "end_iso")
    if end <= start:
        raise ModuleError("end_iso must be after start_iso")

    attendees = inputs.get("attendees", [])
    if not isinstance(attendees, list):
        raise ModuleError("attendees must be a list of email strings")
    for a in attendees:
        if not isinstance(a, str) or not EMAIL_RE.match(a.strip()):
            raise ModuleError("invalid attendee email: %r" % (a,))

    organizer_email = inputs.get("organizer_email", "")
    if organizer_email and (not isinstance(organizer_email, str) or not EMAIL_RE.match(organizer_email.strip())):
        raise ModuleError("invalid organizer_email: %r" % (organizer_email,))
    organizer_name = inputs.get("organizer_name", "")
    if not isinstance(organizer_name, str):
        raise ModuleError("organizer_name must be a string")

    description = inputs.get("description", "")
    location = inputs.get("location", "")
    if not isinstance(description, str) or not isinstance(location, str):
        raise ModuleError("description and location must be strings")

    uid = uuid.uuid4().hex + "@agent-utility-layer"
    dtstamp = _dt_utc(datetime.now(timezone.utc))

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Cumulative Web Inc//Agent Utility Layer//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        "UID:" + uid,
        "DTSTAMP:" + dtstamp,
        "DTSTART:" + _dt_utc(start),
        "DTEND:" + _dt_utc(end),
        "SUMMARY:" + _escape_ics(title.strip()),
    ]
    if organizer_email:
        org = "ORGANIZER"
        if organizer_name.strip():
            org += ';CN="%s"' % organizer_name.strip().replace('"', "")
        org += ":mailto:" + organizer_email.strip()
        lines.append(org)
    for a in attendees:
        lines.append("ATTENDEE;CN=%s:mailto:%s" % (a.strip().split("@")[0], a.strip()))
    if description:
        lines.append("DESCRIPTION:" + _escape_ics(description))
    if location:
        lines.append("LOCATION:" + _escape_ics(location))
    lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")

    folded = []
    for ln in lines:
        folded.extend(_fold(ln))
    ics = "\r\n".join(folded) + "\r\n"

    duration_minutes = int((end - start).total_seconds() // 60)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", title.strip())[:40] or "meeting"
    ctx.log("schedule_meeting.generated", {"uid": uid, "attendees": len(attendees)})
    ctx.bill(EXEC_PRICE_USD, "schedule_meeting ics generation")

    return {
        "status": "generated",
        "ics": ics,
        "filename": safe + ".ics",
        "uid": uid,
        "duration_minutes": duration_minutes,
    }
