"""send_calendar_invite — Crew C / communication pillar.

Build an iCalendar (.ics) invite by hand (no external deps) and deliver it
to every attendee via the configured SMTP provider (stdlib smtplib +
email.message). External send: requires ctx.approval_request(...) before
dispatch. No credential -> AuthMissing.
"""
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import make_msgid

from common import (  # noqa: E402
    ModuleError, AuthMissing, ApprovalDenied,
    validate_inputs, json_cred, ics_escape, smtp_send,
)

INPUTS_SCHEMA = {
    "type": "object",
    "properties": {
        "attendees": {"type": "array"},
        "title": {"type": "string", "minLength": 1},
        "start": {"type": "string", "minLength": 1},
        "end": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "location": {"type": "string"},
    },
    "required": ["attendees", "title", "start", "end"],
}

OUTPUT_KEYS = ["status", "invites_sent", "ics_uid"]

SMTP_SETUP_HINT = (
    "Store provider 'smtp' credentials (via apikey_vault) as JSON: "
    '{"host": "smtp.example.com", "port": 587, "username": "user", '
    '"password": "APP_PASSWORD", "from_addr": "bot@example.com", "use_tls": true}.'
)

PRICE_PER_EXEC_USD = 0.001


def _parse_dt(value, field):
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ModuleError("input '%s' must be ISO-8601 datetime, got %r" % (field, value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)  # naive datetimes are treated as UTC
    return dt.astimezone(timezone.utc)


def _ics_dt(dt):
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _build_ics(inputs, uid):
    start = _parse_dt(inputs["start"], "start")
    end = _parse_dt(inputs["end"], "end")
    if end <= start:
        raise ModuleError("input 'end' must be after 'start'")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Cumulative Web Inc//Agent Utility Layer//EN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        "UID:" + uid,
        "DTSTAMP:" + _ics_dt(datetime.now(timezone.utc)),
        "DTSTART:" + _ics_dt(start),
        "DTEND:" + _ics_dt(end),
        "SUMMARY:" + ics_escape(inputs["title"]),
    ]
    if inputs.get("description"):
        lines.append("DESCRIPTION:" + ics_escape(inputs["description"]))
    if inputs.get("location"):
        lines.append("LOCATION:" + ics_escape(inputs["location"]))
    lines.append("ORGANIZER;CN=CWI Agent:mailto:noreply@cumulativeweb.com")
    for attendee in inputs["attendees"]:
        lines.append("ATTENDEE;RSVP=TRUE:mailto:" + ics_escape(attendee))
    lines += ["END:VEVENT", "END:VCALENDAR", ""]
    return "\r\n".join(lines)


def _provider_send(cred, inputs):
    attendees = inputs["attendees"]
    for addr in attendees:
        if "@" not in addr:
            raise ModuleError("invalid attendee email: %r" % addr)
    uid = make_msgid(domain=cred["host"].split(":")[0])[1:-1] + "@cwi"
    ics = _build_ics(inputs, uid)
    msg = EmailMessage()
    msg["Subject"] = "Invitation: " + inputs["title"]
    msg["From"] = cred["from_addr"]
    msg["To"] = ", ".join(attendees)
    msg["Message-ID"] = make_msgid(domain=cred["host"].split(":")[0])
    msg.set_content("You are invited: %s\n\n%s\n\n%s - %s" % (
        inputs["title"], inputs.get("description", ""),
        inputs["start"], inputs["end"]))
    msg.add_attachment(ics.encode("utf-8"), maintype="text", subtype="calendar",
                       filename="invite.ics", params={"method": "REQUEST"})
    smtp_send(cred, msg)
    return {"status": "sent", "invites_sent": len(attendees), "ics_uid": uid}


def execute(inputs, ctx):
    validate_inputs(inputs, INPUTS_SCHEMA)
    approval_id = ctx.approval_request(
        "Send calendar invite %r to %d attendee(s)" % (inputs["title"], len(inputs["attendees"])))
    cred = json_cred(ctx, "smtp", SMTP_SETUP_HINT)
    result = _provider_send(cred, inputs)
    ctx.log("send_calendar_invite", {"title": inputs["title"], "approval_id": approval_id,
                                     "invites_sent": result["invites_sent"]})
    ctx.bill(PRICE_PER_EXEC_USD, "send_calendar_invite execution")
    assert set(result.keys()) == set(OUTPUT_KEYS), "output schema drift"
    return result
