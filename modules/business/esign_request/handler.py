"""esign_request — create and track e-signature request records.

Creating a request is an EXTERNAL SEND (invitations to signers), so
ctx.approval_request is required first. Signature completion happens in the
human loop outside this module: status stays "pending_signature" and this
module never reports a signature it did not see. No fake "signed" results,
ever. Store key: "aul:esign_requests_v1".
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

EXEC_PRICE_USD = 0.001
APPROVAL_PRICE_USD = 0.01
STORE_KEY = "aul:esign_requests_v1"

ACTIONS = {"create", "get", "list", "cancel"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(ctx) -> dict:
    store = ctx.memory_get(STORE_KEY)
    return dict(store) if isinstance(store, dict) else {}


def _save(ctx, store: dict) -> None:
    ctx.memory_set(STORE_KEY, store)


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    action = inputs.get("action")
    if action not in ACTIONS:
        raise ModuleError("invalid action %r; must be one of %s" % (action, sorted(ACTIONS)))

    store = _load(ctx)
    ctx.log("esign_request.action", {"action": action})

    def _req_or_raise(rid):
        if not rid:
            raise ModuleError("request_id is required")
        r = store.get(rid)
        if r is None:
            raise ModuleError("no signature request found with id %r" % rid)
        return r

    if action == "create":
        document_name = inputs.get("document_name")
        if not isinstance(document_name, str) or not document_name.strip():
            raise ModuleError("document_name is required (non-empty string)")
        document_ref = inputs.get("document_ref", "")
        if not isinstance(document_ref, str):
            raise ModuleError("document_ref must be a string")
        signers = inputs.get("signers")
        if not isinstance(signers, list) or not signers:
            raise ModuleError("signers must be a non-empty list of {name, email}")
        clean_signers = []
        seen = set()
        for i, s in enumerate(signers):
            if not isinstance(s, dict):
                raise ModuleError("signers[%d] must be an object" % i)
            name = s.get("name")
            email = s.get("email")
            if not isinstance(name, str) or not name.strip():
                raise ModuleError("signers[%d].name is required" % i)
            if not isinstance(email, str) or not EMAIL_RE.match(email.strip()):
                raise ModuleError("signers[%d].email is invalid: %r" % (i, email))
            key = email.strip().lower()
            if key in seen:
                raise ModuleError("duplicate signer email: %r" % email)
            seen.add(key)
            clean_signers.append({
                "name": name.strip(),
                "email": email.strip(),
                "status": "pending_signature",
                "signed_at": None,
                "signing_token": "sig_" + uuid.uuid4().hex[:16],
            })
        expires_in_days = inputs.get("expires_in_days", 14)
        if not isinstance(expires_in_days, int) or not 1 <= expires_in_days <= 90:
            raise ModuleError("expires_in_days must be an integer 1..90")

        # EXTERNAL SEND: invitations go to the signers -> human approval first.
        approval_id = ctx.approval_request(
            "Send e-signature invitations for '%s' to %d signer(s): %s"
            % (document_name.strip(), len(clean_signers),
               ", ".join(s["email"] for s in clean_signers))
        )
        ctx.bill(APPROVAL_PRICE_USD, "esign_request human approval push")

        now = datetime.now(timezone.utc)
        rid = "esr_" + uuid.uuid4().hex[:12]
        request = {
            "id": rid,
            "document_name": document_name.strip(),
            "document_ref": document_ref,
            "message": inputs.get("message", "") if isinstance(inputs.get("message"), str) else "",
            "signers": clean_signers,
            "status": "pending_signature",
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=expires_in_days)).isoformat(),
            "approval_id": approval_id,
        }
        store[rid] = request
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "esign_request create")
        return {"status": "created", "request": request, "requests": [],
                "approval_id": approval_id, "count": 1}

    if action == "get":
        r = _req_or_raise(inputs.get("request_id"))
        ctx.bill(EXEC_PRICE_USD, "esign_request get")
        return {"status": "ok", "request": r, "requests": [],
                "approval_id": r["approval_id"], "count": 1}

    if action == "cancel":
        r = _req_or_raise(inputs.get("request_id"))
        if r["status"] == "cancelled":
            raise ModuleError("request %r is already cancelled" % r["id"])
        r["status"] = "cancelled"
        r["cancelled_at"] = _now()
        store[r["id"]] = r
        _save(ctx, store)
        ctx.bill(EXEC_PRICE_USD, "esign_request cancel")
        return {"status": "cancelled", "request": r, "requests": [],
                "approval_id": r["approval_id"], "count": 1}

    # list
    limit = inputs.get("limit", 50)
    if not isinstance(limit, int) or limit < 1 or limit > 500:
        raise ModuleError("limit must be an integer between 1 and 500")
    reqs = sorted(store.values(), key=lambda r: r.get("created_at", ""))[:limit]
    ctx.bill(EXEC_PRICE_USD, "esign_request list")
    return {"status": "ok", "request": {}, "requests": reqs,
            "approval_id": "", "count": len(reqs)}
