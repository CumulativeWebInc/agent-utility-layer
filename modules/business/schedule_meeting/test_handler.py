"""pytest for schedule_meeting — real .ics verified structurally."""
from ..conftest import FakeCtx
from . import handler


def make_ctx(**kw):
    return FakeCtx(handler=handler, **kw)


def _meeting(**over):
    payload = {
        "title": "A&R Sync",
        "start_iso": "2026-09-24T14:00:00-04:00",
        "end_iso": "2026-09-24T14:30:00-04:00",
        "description": "Weekly sync; bring updates, and the demo.",
        "location": "Studio A, 123 Main St",
        "organizer_name": "KingCode",
        "organizer_email": "ops@cumulativeweb.com",
        "attendees": ["a@example.com", "b@example.com"],
    }
    payload.update(over)
    return payload


def test_happy_path_produces_valid_ics():
    ctx = make_ctx()
    res = handler.execute(_meeting(), ctx)
    assert set(res.keys()) == {"status", "ics", "filename", "uid", "duration_minutes"}
    assert res["status"] == "generated"
    assert res["duration_minutes"] == 30
    ics = res["ics"]
    assert "BEGIN:VCALENDAR" in ics and "END:VCALENDAR" in ics
    assert "BEGIN:VEVENT" in ics and "END:VEVENT" in ics
    # -04:00 converted to UTC
    assert "DTSTART:20260924T180000Z" in ics
    assert "DTEND:20260924T183000Z" in ics
    assert ics.count("ATTENDEE") == 2
    assert "ORGANIZER" in ics and "mailto:ops@cumulativeweb.com" in ics
    assert res["filename"].endswith(".ics")


def test_special_characters_escaped():
    ctx = make_ctx()
    res = handler.execute(_meeting(description="a;b,c\\d\ne"), ctx)
    desc = [l for l in res["ics"].split("\r\n") if l.startswith("DESCRIPTION:")][0]
    assert "\\;" in desc and "\\," in desc and "\\\\" in desc and "\\n" in desc
    assert "\n" not in desc.replace("\\n", "")


def test_end_before_start_rejected():
    ctx = make_ctx()
    try:
        handler.execute(_meeting(start_iso="2026-09-24T15:00:00Z",
                                 end_iso="2026-09-24T14:00:00Z"), ctx)
    except handler.ModuleError as e:
        assert "after start_iso" in str(e)
    else:
        raise AssertionError("expected ModuleError for end before start")


def test_invalid_iso_rejected():
    ctx = make_ctx()
    try:
        handler.execute(_meeting(start_iso="tomorrow at 2"), ctx)
    except handler.ModuleError as e:
        assert "ISO-8601" in str(e)
    else:
        raise AssertionError("expected ModuleError for bad ISO")


def test_invalid_attendee_email_rejected():
    ctx = make_ctx()
    try:
        handler.execute(_meeting(attendees=["not-an-email"]), ctx)
    except handler.ModuleError as e:
        assert "attendee" in str(e)
    else:
        raise AssertionError("expected ModuleError for bad attendee email")


def test_uids_unique_and_no_external_send():
    ctx = make_ctx()
    a = handler.execute(_meeting(), ctx)
    b = handler.execute(_meeting(), ctx)
    assert a["uid"] != b["uid"]
    # no approval requested: the module never sends anything
    assert ctx.approvals_requested == []
    assert ctx.bills[0]["amount_usd"] == 0.001


def test_long_lines_folded_at_75_octets():
    ctx = make_ctx()
    res = handler.execute(_meeting(description="x" * 300), ctx)
    for line in res["ics"].split("\r\n"):
        assert len(line.encode("utf-8")) <= 76  # 75 + 1 continuation space
    assert " " in [l[0] for l in res["ics"].split("\r\n") if l.startswith(" ")]
