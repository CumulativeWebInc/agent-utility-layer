"""identity_verify — verification case workflow.

start -> submit_evidence -> decision (approve/reject) -> status.
Honest limit: v1 records and tracks evidence by reference; it does NOT
biometrically or document-AI verify anything. The decision is a recorded
human/operator verdict behind an approval gate.
"""
import secrets
from datetime import datetime, timezone

MEM_KEY = "identity_verify:cases"


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def _case_view(case: dict) -> dict:
    return {
        "case_id": case["case_id"],
        "action": case.get("last_action", "start"),
        "status": case["status"],
        "subject": case["subject"],
        "evidence": case["evidence"],
        "decided_at": case.get("decided_at"),
        "notes": case.get("notes", ""),
    }


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    action = inputs.get("action")
    if action not in ("start", "submit_evidence", "decision", "status"):
        raise ModuleError("action must be start, submit_evidence, decision, or status")
    cases = ctx.memory_get(MEM_KEY) or {}

    if action == "start":
        subject = inputs.get("subject")
        if not subject or not isinstance(subject, str):
            raise ModuleError("inputs.subject is required (string) for start")
        case_id = "case_" + secrets.token_hex(8)
        case = {"case_id": case_id, "subject": subject, "status": "pending",
                "evidence": [], "decided_at": None, "notes": "",
                "started_at": _now(), "last_action": "start"}
        cases[case_id] = case
        ctx.memory_set(MEM_KEY, cases)
        ctx.log("identity_verify", {"action": "start", "case_id": case_id, "subject": subject})
        ctx.bill(0.001, f"identity_verify start {case_id}")
        return _case_view(case)

    case_id = inputs.get("case_id")
    if not case_id or not isinstance(case_id, str):
        raise ModuleError("inputs.case_id is required (string)")
    case = cases.get(case_id)
    if case is None:
        raise ModuleError(f"case '{case_id}' not found")
    case["last_action"] = action

    if action == "status":
        ctx.log("identity_verify", {"action": "status", "case_id": case_id})
        return _case_view(case)

    if case["status"] != "pending":
        raise ModuleError(f"case is {case['status']}; only pending cases accept {action}")

    if action == "submit_evidence":
        evidence_type = inputs.get("evidence_type")
        evidence_ref = inputs.get("evidence_ref")
        if not evidence_type or not isinstance(evidence_type, str):
            raise ModuleError("inputs.evidence_type is required (string)")
        if not evidence_ref or not isinstance(evidence_ref, str):
            raise ModuleError("inputs.evidence_ref is required (string)")
        case["evidence"].append({"type": evidence_type, "ref": evidence_ref,
                                 "submitted_at": _now()})
        ctx.memory_set(MEM_KEY, cases)
        ctx.log("identity_verify", {"action": "submit_evidence", "case_id": case_id,
                                    "evidence_type": evidence_type})
        ctx.bill(0.001, f"identity_verify evidence {case_id}")
        return _case_view(case)

    # decision
    decision = inputs.get("decision")
    if decision not in ("approve", "reject"):
        raise ModuleError("inputs.decision must be approve or reject")
    notes = inputs.get("notes", "") or ""
    if not isinstance(notes, str):
        raise ModuleError("notes must be a string")
    ctx.approval_request(
        f"identity_verify: record {decision.upper()} verdict for '{case['subject']}' ({case_id})")
    case["status"] = "approved" if decision == "approve" else "rejected"
    case["decided_at"] = _now()
    case["notes"] = notes
    ctx.memory_set(MEM_KEY, cases)
    ctx.log("identity_verify", {"action": "decision", "case_id": case_id,
                                "verdict": case["status"]})
    ctx.bill(0.001, f"identity_verify decision {case_id}")
    return _case_view(case)
