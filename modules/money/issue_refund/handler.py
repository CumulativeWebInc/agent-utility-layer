"""issue_refund — refund a prior charge (full or partial) via the provider.

HIGH-STAKES MODULE: a human approval (ctx.approval_request) is REQUIRED before
any refund is attempted — no exceptions. Without provider credentials this
raises AuthMissing; it NEVER fabricates a refund or settlement.

Real provider path: Stripe Refunds via stdlib urllib. Credential from
ctx.auth_get('stripe') — never hardcoded, never logged, never in errors.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

PRICE_PER_EXEC_USD = 0.05
SUPPORTED_PROVIDERS = ("stripe", "test")  # "test" = labeled simulator for tests/demo ONLY


class ModuleError(Exception):
    """Bad input or provider failure."""


class AuthMissing(ModuleError):
    """No credential configured for the requested provider."""


class ApprovalDenied(ModuleError):
    """The human denied the refund."""


def _validate(inputs):
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    charge_id = inputs.get("charge_id")
    if not isinstance(charge_id, str) or not charge_id.strip():
        raise ModuleError("charge_id is required")
    amount = inputs.get("amount_cents")
    if amount is not None:
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ModuleError("amount_cents must be a positive integer when provided")
    provider = str(inputs.get("provider", "stripe"))
    if provider not in SUPPORTED_PROVIDERS:
        raise ModuleError(f"provider must be one of {list(SUPPORTED_PROVIDERS)}")
    reason = inputs.get("reason", "")
    if reason is not None and not isinstance(reason, str):
        raise ModuleError("reason must be a string")
    return {
        "charge_id": charge_id.strip(),
        "amount_cents": amount,
        "provider": provider,
        "reason": (reason or "").strip(),
    }


def _stripe_request(api_key, method, path, params=None):
    url = "https://api.stripe.com" + path
    body = urllib.parse.urlencode(params or {}).encode("utf-8") if method == "POST" else None
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": "Bearer " + api_key,
            "User-Agent": "CWI-AgentUtilityLayer/0.1 (+https://cumulativeweb.com)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8", "replace"))
            msg = payload.get("error", {}).get("message", payload)
        except Exception:
            msg = f"HTTP {e.code}"
        raise ModuleError(f"Stripe error {e.code}: {str(msg)[:300]}")
    except urllib.error.URLError as e:
        raise ModuleError(f"Stripe request failed: {getattr(e, 'reason', e)}")


def _stripe_refund(api_key, p):
    params = {"charge": p["charge_id"]}
    if p["amount_cents"] is not None:
        params["amount"] = str(p["amount_cents"])
    if p["reason"]:
        params["reason"] = "requested_by_customer" if p["reason"] else ""
    refund = _stripe_request(api_key, "POST", "/v1/refunds", params)
    return {
        "status": "succeeded" if refund.get("status") == "succeeded" else "pending",
        "refund_id": refund.get("id"),
        "amount_cents": refund.get("amount", p["amount_cents"]),
        "provider_status": refund.get("status"),
        "simulated": False,
    }


def execute(inputs: dict, ctx) -> dict:
    """Issue the refund. Approval is ALWAYS requested before any refund."""
    p = _validate(inputs)

    # HIGH-STAKES GATE — fires before any credential use, before any refund.
    amount_note = f"{p['amount_cents'] / 100:.2f}" if p["amount_cents"] else "FULL"
    approval_id = ctx.approval_request(
        f"Refund {amount_note} on charge {p['charge_id']} via {p['provider']}"
        + (f" — {p['reason']}" if p["reason"] else "")
    )

    if p["provider"] == "test":
        # Labeled simulator for tests/demo only. Never presented as a live refund.
        result = {
            "status": "succeeded",
            "refund_id": "re_test_" + uuid.uuid4().hex[:16],
            "amount_cents": p["amount_cents"],
            "provider_status": "succeeded",
            "simulated": True,
        }
    else:
        api_key = ctx.auth_get(p["provider"])  # raises AuthMissing when unconfigured
        result = _stripe_refund(api_key, p)

    if not result.get("refund_id"):
        raise ModuleError("Provider returned no refund id — treating as failure, no refund confirmed.")

    result.update({
        "charge_id": p["charge_id"],
        "approved": True,
        "approval_id": approval_id,
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    # Audit log carries no secrets — only ids and amounts.
    ctx.log("issue_refund.executed", {
        "refund_id": result["refund_id"],
        "charge_id": p["charge_id"],
        "amount_cents": result["amount_cents"],
        "provider": p["provider"],
        "approval_id": approval_id,
        "simulated": result["simulated"],
    })
    ctx.bill(PRICE_PER_EXEC_USD, f"issue_refund {result['refund_id']}")
    return result
