"""calc_tax — compute tax on an amount for a jurisdiction.

PURE COMPUTATION — no provider, no credential, no approval. Rates are a
small built-in table of point-in-time ESTIMATES (as of 2026-09), clearly
labeled as such. This is not tax advice: real filings need a tax
professional. Pass tax_rate explicitly to override any table entry.
"""

from decimal import Decimal, ROUND_HALF_UP

PRICE_PER_EXEC_USD = 0.01

# Jurisdiction -> [(label, effective rate)]. ESTIMATES, not filings-grade data.
RATES = {
    "US-NY": [("NY combined sales tax (NYC estimate)", Decimal("0.08875"))],
    "US-CA": [("CA state base sales tax (local add-ons vary)", Decimal("0.0725"))],
    "US-TX": [("TX state sales tax", Decimal("0.0625"))],
    "US-FL": [("FL state sales tax", Decimal("0.06"))],
    "US-WA": [("WA state sales tax (local add-ons vary)", Decimal("0.065"))],
    "GB": [("UK VAT", Decimal("0.20"))],
    "DE": [("Germany VAT", Decimal("0.19"))],
    "FR": [("France VAT", Decimal("0.20"))],
    "CA": [("Canada GST (provincial extra where applicable)", Decimal("0.05"))],
    "AU": [("Australia GST", Decimal("0.10"))],
}

DISCLAIMER = (
    "Estimate only, based on a built-in rate table (2026-09). Rates vary by "
    "locality, product category, and change over time. Not tax advice — "
    "confirm with a tax professional before filing or invoicing."
)


class ModuleError(Exception):
    """Bad input."""


class AuthMissing(ModuleError):
    pass  # interface symmetry; never raised here


class ApprovalDenied(ModuleError):
    pass  # interface symmetry; never raised here


def _validate(inputs):
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    amount = inputs.get("amount_cents")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        raise ModuleError("amount_cents must be a non-negative integer")
    jurisdiction = inputs.get("jurisdiction")
    if not isinstance(jurisdiction, str) or not jurisdiction.strip():
        raise ModuleError("jurisdiction is required (e.g. 'US-NY', 'GB', or 'CUSTOM')")
    jurisdiction = jurisdiction.strip().upper()
    inclusive = inputs.get("tax_inclusive", False)
    if not isinstance(inclusive, bool):
        raise ModuleError("tax_inclusive must be a boolean")
    custom_rate = inputs.get("tax_rate")
    if custom_rate is not None:
        if isinstance(custom_rate, bool) or not isinstance(custom_rate, (int, float)) \
                or custom_rate < 0 or custom_rate > 1:
            raise ModuleError("tax_rate must be a decimal fraction between 0 and 1")
    if jurisdiction == "CUSTOM":
        if custom_rate is None:
            raise ModuleError("jurisdiction 'CUSTOM' requires an explicit tax_rate")
        table = [("custom rate", Decimal(str(custom_rate)))]
    elif jurisdiction in RATES:
        table = RATES[jurisdiction] if custom_rate is None else [("custom rate", Decimal(str(custom_rate)))]
    else:
        raise ModuleError(
            f"unknown jurisdiction '{jurisdiction}'. Supported: {sorted(RATES)} or 'CUSTOM' with tax_rate."
        )
    return {"amount_cents": amount, "jurisdiction": jurisdiction,
            "inclusive": inclusive, "table": table}


def execute(inputs: dict, ctx) -> dict:
    """Compute taxes. No auth, no approval — pure math."""
    p = _validate(inputs)
    amount = Decimal(p["amount_cents"])

    if p["inclusive"]:
        # Back out the tax embedded in a tax-inclusive price.
        total_rate = sum(r for _, r in p["table"])
        divisor = Decimal("1") + total_rate
        net = (amount / divisor).to_integral_value(rounding=ROUND_HALF_UP)
        tax_total = int(amount) - int(net)
        subtotal = int(net)
        breakdown = []
        for label, rate in p["table"]:
            share = (Decimal(tax_total) * rate / total_rate).to_integral_value(rounding=ROUND_HALF_UP) \
                if total_rate else Decimal("0")
            breakdown.append({"label": label, "rate": float(rate), "amount_cents": int(share)})
        # fix rounding drift on the last line
        drift = tax_total - sum(b["amount_cents"] for b in breakdown)
        if breakdown:
            breakdown[-1]["amount_cents"] += drift
        total = int(amount)
    else:
        subtotal = int(amount)
        breakdown = []
        for label, rate in p["table"]:
            line = (amount * rate).to_integral_value(rounding=ROUND_HALF_UP)
            breakdown.append({"label": label, "rate": float(rate), "amount_cents": int(line)})
        tax_total = sum(b["amount_cents"] for b in breakdown)
        total = subtotal + tax_total

    ctx.log("calc_tax.computed", {
        "jurisdiction": p["jurisdiction"],
        "amount_cents": p["amount_cents"],
        "tax_total_cents": tax_total,
        "total_cents": total,
        "tax_inclusive": p["inclusive"],
    })
    ctx.bill(PRICE_PER_EXEC_USD, f"calc_tax {p['jurisdiction']} {p['amount_cents']}")

    return {
        "status": "computed",
        "jurisdiction": p["jurisdiction"],
        "tax_inclusive": p["inclusive"],
        "subtotal_cents": subtotal,
        "taxes": breakdown,
        "tax_total_cents": tax_total,
        "total_cents": total,
        "note": DISCLAIMER,
    }
