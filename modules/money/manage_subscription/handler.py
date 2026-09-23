"""manage_subscription — create, update, cancel, or inspect a subscription.

HIGH-STAKES MODULE: any action that changes billing state (create, update,
cancel) requires human approval FIRST — no exceptions. The read-only 'get'
action needs no approval. Without provider credentials, state-changing actions
raise AuthMissing; 'get' also needs the credential (it queries the provider).

Real provider path: Stripe Subscriptions via stdlib urllib. Credential from
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
ACTIONS = ("create", "update", "cancel", "get")
STATE_CHANGING = ("create", "update", "cancel")


class ModuleError(Exception):
    """Bad input or provider failure."""


class AuthMissing(ModuleError):
    """No credential configured for the requested provider."""


class ApprovalDenied(ModuleError):
    """The human denied the subscription change."""


def _validate(inputs):
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    action = inputs.get("action")
    if action not in ACTIONS:
        raise ModuleError(f"action must be one of {list(ACTIONS)}")
    provider = str(inputs.get("provider", "stripe"))
    if provider not in SUPPORTED_PROVIDERS:
        raise ModuleError(f"provider must be one of {list(SUPPORTED_PROVIDERS)}")
    p = {"action": action, "provider": provider}
    if action in ("cancel", "update", "get"):
        sub_id = inputs.get("subscription_id")
        if not isinstance(sub_id, str) or not sub_id.strip():
            raise ModuleError(f"subscription_id is required for action '{action}'")
        p["subscription_id"] = sub_id.strip()
    if action == "create":
        customer = inputs.get("customer")
        if not isinstance(customer, str) or not customer.strip():
            raise ModuleError("customer is required for action 'create'")
        price = inputs.get("price")
        if not isinstance(price, str) or not price.strip():
            raise ModuleError("price is required for action 'create' (provider price id)")
        p["customer"] = customer.strip()
        p["price"] = price.strip()
        trial = inputs.get("trial_days", 0)
        if isinstance(trial, bool) or not isinstance(trial, int) or trial < 0:
            raise ModuleError("trial_days must be a non-negative integer")
        p["trial_days"] = trial
    if action == "update":
        price = inputs.get("price")
        if price is not None and (not isinstance(price, str) or not price.strip()):
            raise ModuleError("price must be a non-empty string when provided")
        p["price"] = price.strip() if isinstance(price, str) else None
        cancel_at = inputs.get("cancel_at_period_end")
        if cancel_at is not None and not isinstance(cancel_at, bool):
            raise ModuleError("cancel_at_period_end must be a boolean")
        p["cancel_at_period_end"] = cancel_at
        if p["price"] is None and p["cancel_at_period_end"] is None:
            raise ModuleError("update requires 'price' and/or 'cancel_at_period_end'")
    return p


def _stripe_request(api_key, method, path, params=None):
    url = "https://api.stripe.com" + path
    body = urllib.parse.urlencode(params or {}).encode("utf-8") if method != "GET" else None
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


def _stripe_execute(api_key, p):
    if p["action"] == "create":
        params = {"customer": p["customer"], "items[0][price]": p["price"]}
        if p["trial_days"]:
            params["trial_period_days"] = str(p["trial_days"])
        sub = _stripe_request(api_key, "POST", "/v1/subscriptions", params)
    elif p["action"] == "cancel":
        sub = _stripe_request(api_key, "DELETE", f"/v1/subscriptions/{p['subscription_id']}")
    elif p["action"] == "update":
        params = {}
        if p["price"]:
            params["items[0][price]"] = p["price"]
        if p["cancel_at_period_end"] is not None:
            params["cancel_at_period_end"] = "true" if p["cancel_at_period_end"] else "false"
        sub = _stripe_request(api_key, "POST", f"/v1/subscriptions/{p['subscription_id']}", params)
    else:  # get
        sub = _stripe_request(api_key, "GET", f"/v1/subscriptions/{p['subscription_id']}")
    return {
        "status": "ok",
        "subscription_id": sub.get("id"),
        "state": sub.get("status"),
        "simulated": False,
        "raw_status": sub.get("status"),
    }


def _test_execute(p):
    # Labeled simulator. Never presented as a live provider result.
    state = {"create": "active", "update": "active", "cancel": "canceled", "get": "active"}[p["action"]]
    return {
        "status": "ok",
        "subscription_id": p.get("subscription_id") or ("sub_test_" + uuid.uuid4().hex[:12]),
        "state": state,
        "simulated": True,
    }


def execute(inputs: dict, ctx) -> dict:
    """Run the subscription action. State changes require approval first."""
    p = _validate(inputs)

    approval_id = None
    if p["action"] in STATE_CHANGING:
        # HIGH-STAKES GATE — fires before any credential use, before any change.
        approval_id = ctx.approval_request(
            f"Subscription {p['action']}: "
            + (f"customer {p['customer']}, price {p['price']}" if p["action"] == "create"
               else f"{p['subscription_id']} via {p['provider']}")
        )

    if p["provider"] == "test":
        result = _test_execute(p)
    else:
        api_key = ctx.auth_get(p["provider"])  # raises AuthMissing when unconfigured
        result = _stripe_execute(api_key, p)

    if not result.get("subscription_id"):
        raise ModuleError("Provider returned no subscription id — treating as failure.")

    result.update({
        "action": p["action"],
        "approved": approval_id is not None,
        "approval_id": approval_id,
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    # Audit log carries no secrets.
    ctx.log("manage_subscription.executed", {
        "action": p["action"],
        "subscription_id": result["subscription_id"],
        "state": result["state"],
        "provider": p["provider"],
        "approval_id": approval_id,
        "simulated": result["simulated"],
    })
    ctx.bill(PRICE_PER_EXEC_USD, f"manage_subscription {p['action']} {result['subscription_id']}")
    return result
