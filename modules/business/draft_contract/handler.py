"""draft_contract — merge caller-supplied fields into contract templates.

Three templates: mutual_nda, services_agreement, freelance_work_order.
Each declares required fields; any missing field raises ModuleError and no
document is produced. Output is a TEMPLATE DRAFT — not legal advice, and
the module says so in every response.
"""
from __future__ import annotations

EXEC_PRICE_USD = 0.001

DISCLAIMER = (
    "TEMPLATE DRAFT — NOT LEGAL ADVICE. This document was generated from a "
    "template and has not been reviewed by an attorney. Have qualified legal "
    "counsel review and adapt it before use or signature."
)

TEMPLATES = {
    "mutual_nda": {
        "required": ["party_a_name", "party_b_name", "effective_date",
                     "confidentiality_years", "governing_state"],
        "optional": ["purpose"],
        "body": (
            "MUTUAL NON-DISCLOSURE AGREEMENT\n"
            "================================\n\n"
            "This Mutual Non-Disclosure Agreement (\"Agreement\") is entered into as of "
            "{effective_date} (the \"Effective Date\"), by and between {party_a_name} "
            "(\"Party A\") and {party_b_name} (\"Party B\") (each a \"Party\" and "
            "collectively the \"Parties\").\n\n"
            "1. PURPOSE. The Parties wish to explore {purpose} (the \"Purpose\") and in "
            "connection therewith may disclose Confidential Information to each other.\n\n"
            "2. CONFIDENTIAL INFORMATION. \"Confidential Information\" means all "
            "non-public information disclosed by one Party to the other, whether orally "
            "or in writing, that is designated as confidential or that reasonably should "
            "be understood to be confidential given the nature of the information and "
            "the circumstances of disclosure.\n\n"
            "3. OBLIGATIONS. Each Party agrees (a) to hold the other Party's Confidential "
            "Information in strict confidence; (b) not to disclose it to any third party "
            "without prior written consent; and (c) to use it solely for the Purpose.\n\n"
            "4. TERM. The obligations of confidentiality survive for {confidentiality_years} "
            "years from the Effective Date.\n\n"
            "5. GOVERNING LAW. This Agreement is governed by the laws of the State of "
            "{governing_state}.\n\n"
            "AGREED (template draft — signatures not collected by this module):\n\n"
            "Party A: ______________________________   Date: ____________\n\n"
            "Party B: ______________________________   Date: ____________\n"
        ),
        "defaults": {"purpose": "a potential business relationship"},
    },
    "services_agreement": {
        "required": ["client_name", "provider_name", "effective_date", "services_description",
                     "fee_amount", "fee_currency", "term_months", "governing_state"],
        "optional": ["payment_terms"],
        "body": (
            "SERVICES AGREEMENT\n"
            "==================\n\n"
            "This Services Agreement (\"Agreement\") is entered into as of {effective_date} "
            "(the \"Effective Date\"), by and between {client_name} (\"Client\") and "
            "{provider_name} (\"Provider\").\n\n"
            "1. SERVICES. Provider agrees to perform the following services: "
            "{services_description} (the \"Services\").\n\n"
            "2. FEES. Client shall pay Provider {fee_amount} {fee_currency} for the Services, "
            "{payment_terms}.\n\n"
            "3. TERM. This Agreement begins on the Effective Date and continues for "
            "{term_months} months unless terminated earlier as provided herein.\n\n"
            "4. INDEPENDENT CONTRACTOR. Provider is an independent contractor and nothing in "
            "this Agreement creates an employment, partnership, or agency relationship.\n\n"
            "5. CONFIDENTIALITY. Each party shall keep confidential all non-public "
            "information received from the other in connection with the Services.\n\n"
            "6. GOVERNING LAW. This Agreement is governed by the laws of the State of "
            "{governing_state}.\n\n"
            "AGREED (template draft — signatures not collected by this module):\n\n"
            "Client: ______________________________   Date: ____________\n\n"
            "Provider: ______________________________   Date: ____________\n"
        ),
        "defaults": {"payment_terms": "in accordance with invoices issued monthly, net 30"},
    },
    "freelance_work_order": {
        "required": ["client_name", "freelancer_name", "work_description",
                     "deliverables", "fee_amount", "fee_currency", "due_date"],
        "optional": ["revisions_included"],
        "body": (
            "FREELANCE WORK ORDER\n"
            "====================\n\n"
            "Client: {client_name}\n"
            "Freelancer: {freelancer_name}\n\n"
            "1. WORK. Freelancer agrees to perform the following work: {work_description}.\n\n"
            "2. DELIVERABLES. {deliverables}\n\n"
            "3. FEE. {fee_amount} {fee_currency}, payable on acceptance of the Deliverables.\n\n"
            "4. DUE DATE. {due_date}.\n\n"
            "5. REVISIONS. This work order includes {revisions_included} rounds of revisions.\n\n"
            "6. RIGHTS. Upon full payment, all rights in the Deliverables transfer to Client, "
            "unless otherwise agreed in writing.\n\n"
            "AGREED (template draft — signatures not collected by this module):\n\n"
            "Client: ______________________________   Date: ____________\n\n"
            "Freelancer: ______________________________   Date: ____________\n"
        ),
        "defaults": {"revisions_included": "two (2)"},
    },
}


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")

    template_name = inputs.get("template")
    if template_name not in TEMPLATES:
        raise ModuleError(
            "unknown template %r; available: %s" % (template_name, sorted(TEMPLATES))
        )
    template = TEMPLATES[template_name]

    fields = inputs.get("fields")
    if not isinstance(fields, dict):
        raise ModuleError("fields must be an object")
    missing = [f for f in template["required"]
               if not isinstance(fields.get(f), str) or not fields[f].strip()]
    if missing:
        raise ModuleError(
            "template %r is missing required fields: %s"
            % (template_name, ", ".join(missing))
        )

    merged = dict(template["defaults"])
    for key in template["required"] + template["optional"]:
        if isinstance(fields.get(key), str) and fields[key].strip():
            merged[key] = fields[key].strip()

    try:
        document = template["body"].format(**merged)
    except KeyError as e:
        raise ModuleError("template rendering failed on placeholder %s" % (e,))

    output_format = inputs.get("output_format", "markdown")
    if output_format not in ("markdown", "text"):
        raise ModuleError("output_format must be 'markdown' or 'text'")
    if output_format == "text":
        document = document.replace("=", "").replace("#", "")

    word_count = len(document.split())
    ctx.log("draft_contract.rendered",
            {"template": template_name, "word_count": word_count})
    ctx.bill(EXEC_PRICE_USD, "draft_contract " + template_name)

    return {
        "status": "drafted",
        "template_used": template_name,
        "document": document,
        "fields_used": sorted(merged.keys()),
        "word_count": word_count,
        "disclaimer": DISCLAIMER,
    }
