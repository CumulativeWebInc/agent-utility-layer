"""charge_payment — charge a customer via a configured payment provider.

HIGH-STAKES MODULE: a human approval (ctx.approval_request) is REQUIRED before
any charge is attempted — no exceptions. Without provider credentials this
raises AuthMissing; it NEVER fabricates a charge, settlement, or receipt.

Real provider path: Stripe PaymentIntents via stdlib urllib (no third-party
deps). Credential comes from ctx.auth_get('stripe') — never hardcoded, never
logged, never in errors.
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
    """The human denied the charge."""


def _validate(inputs):
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    amount = inputs.get("amount_cents")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise ModuleError("amount_cents must be a positive integer (minor currency units)")
    if amount > 99_999_999:
        raise ModuleError("amount_cents exceeds the single-charge cap (999999.99)")
    customer = inputs.get("customer")
    if not isinstance(customer, str) or not customer.strip():
        raise ModuleError("customer is required (provider customer id or email)")
    currency = str(inputs.get("currency", "usd")).lower()
    if len(currency) != 3 or not currency.isalpha():
        raise ModuleError("currency must be a 3-letter ISO code")
    provider = str(inputs.get("provider", "stripe"))
    if provider not in SUPPORTED_PROVIDERS:
        raise ModuleError(f"provider must be one of {list(SUPPORTED_PROVIDERS)}")
    description = inputs.get("description", "")
    if description is not None and not isinstance(description, str):
        raise ModuleError("description must be a string")
    metadata = inputs.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ModuleError("metadata must be an object")
    return {
        "amount_cents": amount,
        "customer": customer.strip(),
        "currency": currency,
        "provider": provider,
        "description": (description or "").strip(),
        "metadata": metadata,
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
        # Never include the credential or full raw payload in the error.
        raise ModuleError(f"Stripe error {e.code}: {str(msg)[:300]}")
    except urllib.error.URLError as e:
        raise ModuleError(f"Stripe request failed: {getattr(e, 'reason', e)}")


def _stripe_charge(api_key, p):
    params = {
        "amount": str(p["amount_cents"]),
        "currency": p["currency"],
        "description": p["description"] or "Charge via CWI Agent Utility Layer",
    }
    cust = p["customer"]
    if cust.startswith("cus_"):
        params["customer"] = cust
    else:
        params["receipt_email"] = cust
    for k, v in p["metadata"].items():
        params[f"metadata[{k}]"] = str(v)
    intent = _stripe_request(api_key, "POST", "/v1/payment_intents", params)
    return {
        "status": "succeeded" if intent.get("status") in ("succeeded", "requires_capture") else "pending",
        "charge_id": intent.get("id"),
        "amount_cents": p["amount_cents"],
        "currency": p["currency"],
        "provider_status": intent.get("status"),
        "simulated": False,
    }


def execute(inputs: dict, ctx) -> dict:
    """Charge a customer. Approval is ALWAYS requested before any charge."""
    p = _validate(inputs)

    # HIGH-STAKES GATE — fires before any credential use, before any charge.
    approval_id = ctx.approval_request(
        f"Charge {p['amount_cents'] / 100:.2f} {p['currency'].upper()} "
        f"to {p['customer']} via {p['provider']}"
        + (f" — {p['description']}" if p["description"] else "")
    )

    if p["provider"] == "test":
        # Labeled simulator for tests/demo only. Never presented as a live charge.
        result = {
            "status": "succeeded",
            "charge_id": "ch_test_" + uuid.uuid4().hex[:16],
            "amount_cents": p["amount_cents"],
            "currency": p["currency"],
            "provider_status": "succeeded",
            "simulated": True,
        }
    else:
        api_key = ctx.auth_get(p["provider"])  # raises AuthMissing when unconfigured
        result = _stripe_charge(api_key, p)

    if not result.get("charge_id"):
        raise ModuleError("Provider returned no charge id — treating as failure, no charge confirmed.")

    result.update({
        "approved": True,
        "approval_id": approval_id,
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    # Audit log carries no secrets — only ids and amounts.
    ctx.log("charge_payment.executed", {
        "charge_id": result["charge_id"],
        "amount_cents": p["amount_cents"],
        "currency": p["currency"],
        "provider": p["provider"],
        "approval_id": approval_id,
        "simulated": result["simulated"],
    })
    ctx.bill(PRICE_PER_EXEC_USD, f"charge_payment {result['charge_id']}")
    return result
