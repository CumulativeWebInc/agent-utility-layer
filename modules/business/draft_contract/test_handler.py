"""pytest for draft_contract — field merge verified, gaps rejected."""
from ..conftest import FakeCtx
from . import handler


def make_ctx(**kw):
    return FakeCtx(handler=handler, **kw)


NDA_FIELDS = {
    "party_a_name": "Cumulative Web Inc",
    "party_b_name": "Acme Studio LLC",
    "effective_date": "2026-09-23",
    "confidentiality_years": "3",
    "governing_state": "Maryland",
}


def test_nda_happy_path_merges_all_fields():
    ctx = make_ctx()
    res = handler.execute({"template": "mutual_nda", "fields": NDA_FIELDS}, ctx)
    assert set(res.keys()) == {"status", "template_used", "document", "fields_used",
                               "word_count", "disclaimer"}
    assert res["status"] == "drafted"
    for v in ("Cumulative Web Inc", "Acme Studio LLC", "2026-09-23", "Maryland"):
        assert v in res["document"]
    assert "{" not in res["document"] and "}" not in res["document"]
    assert "NOT LEGAL ADVICE" in res["disclaimer"]
    assert res["word_count"] > 100


def test_missing_required_field_lists_whats_missing():
    ctx = make_ctx()
    fields = dict(NDA_FIELDS)
    del fields["governing_state"]
    try:
        handler.execute({"template": "mutual_nda", "fields": fields}, ctx)
    except handler.ModuleError as e:
        assert "governing_state" in str(e)
    else:
        raise AssertionError("expected ModuleError for missing field")


def test_unknown_template_rejected():
    ctx = make_ctx()
    try:
        handler.execute({"template": "merger_agreement", "fields": {}}, ctx)
    except handler.ModuleError as e:
        assert "available" in str(e)
    else:
        raise AssertionError("expected ModuleError for unknown template")


def test_services_agreement_renders_money_and_term():
    ctx = make_ctx()
    res = handler.execute({"template": "services_agreement", "fields": {
        "client_name": "Client Co", "provider_name": "Cumulative Web Inc",
        "effective_date": "2026-10-01", "services_description": "mixing and mastering",
        "fee_amount": "2500", "fee_currency": "USD", "term_months": "12",
        "governing_state": "Maryland"}}, ctx)
    assert "2500 USD" in res["document"]
    assert "12 months" in res["document"]
    assert "mixing and mastering" in res["document"]


def test_freelance_work_order_with_defaults():
    ctx = make_ctx()
    res = handler.execute({"template": "freelance_work_order", "fields": {
        "client_name": "Client Co", "freelancer_name": "Jane Doe",
        "work_description": "logo design", "deliverables": "3 logo concepts, source files",
        "fee_amount": "800", "fee_currency": "USD", "due_date": "2026-10-15"}}, ctx)
    assert "two (2)" in res["document"]  # default revisions_included
    assert "Jane Doe" in res["document"]


def test_blank_string_field_counts_as_missing():
    ctx = make_ctx()
    fields = dict(NDA_FIELDS)
    fields["party_b_name"] = "   "
    try:
        handler.execute({"template": "mutual_nda", "fields": fields}, ctx)
    except handler.ModuleError as e:
        assert "party_b_name" in str(e)
    else:
        raise AssertionError("expected ModuleError for blank field")


def test_bad_output_format_rejected():
    ctx = make_ctx()
    try:
        handler.execute({"template": "mutual_nda", "fields": NDA_FIELDS,
                         "output_format": "pdf"}, ctx)
    except handler.ModuleError:
        pass
    else:
        raise AssertionError("expected ModuleError for bad output_format")
