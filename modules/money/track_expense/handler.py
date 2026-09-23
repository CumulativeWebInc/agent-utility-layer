"""track_expense — record, list, and summarize business expenses.

INTERNAL BOOKKEEPING ONLY — expenses live in the module's scoped ctx.memory,
reversible, and move no money. No provider, no credential, no approval.
financial_report reads this ledger to build P&L-style summaries.
"""

import re
import time
import uuid

PRICE_PER_EXEC_USD = 0.01
ACTIONS = ("add", "list", "summary")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ModuleError(Exception):
    """Bad input."""


class AuthMissing(ModuleError):
    pass  # interface symmetry; never raised here


class ApprovalDenied(ModuleError):
    pass  # interface symmetry; never raised here


def _validate(inputs):
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    action = inputs.get("action", "add")
    if action not in ACTIONS:
        raise ModuleError(f"action must be one of {list(ACTIONS)}")
    p = {"action": action}
    if action == "add":
        amount = inputs.get("amount_cents")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ModuleError("amount_cents must be a positive integer")
        category = inputs.get("category", "uncategorized")
        if not isinstance(category, str) or not category.strip():
            raise ModuleError("category must be a non-empty string")
        for f in ("vendor", "note"):
            v = inputs.get(f, "")
            if v is not None and not isinstance(v, str):
                raise ModuleError(f"{f} must be a string")
            p[f] = (v or "").strip()
        currency = str(inputs.get("currency", "usd")).lower()
        if len(currency) != 3 or not currency.isalpha():
            raise ModuleError("currency must be a 3-letter ISO code")
        date = inputs.get("date", time.strftime("%Y-%m-%d"))
        if not isinstance(date, str) or not DATE_RE.match(date):
            raise ModuleError("date must be YYYY-MM-DD")
        p.update({"amount_cents": amount, "category": category.strip().lower(),
                  "currency": currency, "date": date})
    if action in ("list", "summary"):
        category = inputs.get("category")
        if category is not None and (not isinstance(category, str) or not category.strip()):
            raise ModuleError("category must be a non-empty string when provided")
        p["category"] = category.strip().lower() if isinstance(category, str) else None
    return p


def _ledger(ctx):
    return ctx.memory_get("expenses") or []


def execute(inputs: dict, ctx) -> dict:
    """Add/list/summarize expenses. No auth, no approval."""
    p = _validate(inputs)

    if p["action"] == "add":
        expense = {
            "expense_id": "exp_" + uuid.uuid4().hex[:12],
            "amount_cents": p["amount_cents"],
            "category": p["category"],
            "vendor": p["vendor"],
            "note": p["note"],
            "currency": p["currency"],
            "date": p["date"],
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        ledger = _ledger(ctx)
        ledger.append(expense)
        ctx.memory_set("expenses", ledger)
        ctx.log("track_expense.added", {
            "expense_id": expense["expense_id"],
            "amount_cents": expense["amount_cents"],
            "category": expense["category"],
        })
        ctx.bill(PRICE_PER_EXEC_USD, f"track_expense add {expense['expense_id']}")
        return {"status": "recorded", "action": "add", "expense": expense}

    ledger = _ledger(ctx)
    if p["category"]:
        ledger = [e for e in ledger if e["category"] == p["category"]]

    if p["action"] == "list":
        ctx.bill(PRICE_PER_EXEC_USD, f"track_expense list {len(ledger)}")
        return {"status": "ok", "action": "list", "count": len(ledger), "expenses": ledger}

    # summary
    total = sum(e["amount_cents"] for e in ledger)
    by_category = {}
    for e in ledger:
        by_category[e["category"]] = by_category.get(e["category"], 0) + e["amount_cents"]
    ctx.bill(PRICE_PER_EXEC_USD, f"track_expense summary {len(ledger)}")
    return {
        "status": "ok",
        "action": "summary",
        "count": len(ledger),
        "total_cents": total,
        "by_category": by_category,
    }
