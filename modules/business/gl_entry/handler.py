"""gl_entry — real double-entry bookkeeping on a JSON-backed ledger.

Actions: post / get / list / void / trial_balance.
Every posted entry must balance: sum(debits) == sum(credits), enforced
before write. Voiding keeps the audit trail (entries are never deleted).
Store key: "aul:gl_journal_v1". This is bookkeeping, not a certified
accounting system and not a bank.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

EXEC_PRICE_USD = 0.001
STORE_KEY = "aul:gl_journal_v1"
ACTIONS = {"post", "get", "list", "void", "trial_balance"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(ctx) -> list:
    journal = ctx.memory_get(STORE_KEY)
    return list(journal) if isinstance(journal, list) else []


def _save(ctx, journal: list) -> None:
    ctx.memory_set(STORE_KEY, journal)


def _dec(value, what: str) -> Decimal:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ModuleError("%s must be numeric, got %r" % (what, value))
    if d < 0:
        raise ModuleError("%s must be >= 0, got %r" % (what, value))
    return d


def execute(inputs: dict, ctx) -> dict:
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    action = inputs.get("action")
    if action not in ACTIONS:
        raise ModuleError("invalid action %r; must be one of %s" % (action, sorted(ACTIONS)))

    journal = _load(ctx)
    ctx.log("gl_entry.action", {"action": action})

    def _entry_or_raise(eid):
        if not eid:
            raise ModuleError("entry_id is required")
        for e in journal:
            if e["id"] == eid:
                return e
        raise ModuleError("no journal entry found with id %r" % eid)

    if action == "post":
        lines = inputs.get("lines")
        if not isinstance(lines, list) or len(lines) < 2:
            raise ModuleError("lines must be a list of at least 2 line items")
        date = inputs.get("date", datetime.now(timezone.utc).date().isoformat())
        if not isinstance(date, str) or not DATE_RE.match(date):
            raise ModuleError("date must be YYYY-MM-DD, got %r" % (date,))
        memo = inputs.get("memo", "")
        if not isinstance(memo, str):
            raise ModuleError("memo must be a string")

        clean_lines = []
        total_debit = Decimal("0")
        total_credit = Decimal("0")
        has_debit = has_credit = False
        for i, line in enumerate(lines):
            if not isinstance(line, dict):
                raise ModuleError("lines[%d] must be an object" % i)
            account = line.get("account")
            if not isinstance(account, str) or not account.strip():
                raise ModuleError("lines[%d].account is required (non-empty string)" % i)
            debit = _dec(line.get("debit", 0), "lines[%d].debit" % i)
            credit = _dec(line.get("credit", 0), "lines[%d].credit" % i)
            if debit > 0 and credit > 0:
                raise ModuleError("lines[%d]: a line may not have both debit and credit > 0" % i)
            if debit == 0 and credit == 0:
                raise ModuleError("lines[%d]: debit or credit must be > 0" % i)
            if debit > 0:
                has_debit = True
            if credit > 0:
                has_credit = True
            total_debit += debit
            total_credit += credit
            clean_lines.append({
                "account": account.strip(),
                "debit": str(debit),
                "credit": str(credit),
            })
        if not (has_debit and has_credit):
            raise ModuleError("entry must contain at least one debit line and one credit line")
        if total_debit != total_credit:
            raise ModuleError(
                "entry does not balance: total debits %s != total credits %s"
                % (total_debit, total_credit)
            )

        entry = {
            "id": "je_" + uuid.uuid4().hex[:12],
            "date": date,
            "memo": memo,
            "lines": clean_lines,
            "total": str(total_debit),
            "voided": False,
            "posted_at": _now(),
        }
        journal.append(entry)
        _save(ctx, journal)
        ctx.bill(EXEC_PRICE_USD, "gl_entry post")
        return {"status": "posted", "entry": entry, "entries": [], "balances": [], "count": 1}

    if action == "get":
        entry = _entry_or_raise(inputs.get("entry_id"))
        ctx.bill(EXEC_PRICE_USD, "gl_entry get")
        return {"status": "ok", "entry": entry, "entries": [], "balances": [], "count": 1}

    if action == "list":
        limit = inputs.get("limit", 50)
        if not isinstance(limit, int) or limit < 1 or limit > 500:
            raise ModuleError("limit must be an integer between 1 and 500")
        entries = sorted(journal, key=lambda e: (e.get("date", ""), e.get("posted_at", "")))[:limit]
        ctx.bill(EXEC_PRICE_USD, "gl_entry list")
        return {"status": "ok", "entry": {}, "entries": entries,
                "balances": [], "count": len(entries)}

    if action == "void":
        entry = _entry_or_raise(inputs.get("entry_id"))
        if entry["voided"]:
            raise ModuleError("entry %r is already voided" % entry["id"])
        entry["voided"] = True
        entry["voided_at"] = _now()
        _save(ctx, journal)
        ctx.bill(EXEC_PRICE_USD, "gl_entry void")
        return {"status": "voided", "entry": entry, "entries": [], "balances": [], "count": 1}

    # trial_balance
    balances: dict = {}
    for e in journal:
        if e.get("voided"):
            continue
        for line in e["lines"]:
            acct = line["account"]
            b = balances.setdefault(acct, {"debit": Decimal("0"), "credit": Decimal("0")})
            b["debit"] += Decimal(line["debit"])
            b["credit"] += Decimal(line["credit"])
    rows = [
        {
            "account": acct,
            "debit": str(v["debit"]),
            "credit": str(v["credit"]),
            "balance": str(v["debit"] - v["credit"]),
        }
        for acct, v in sorted(balances.items())
    ]
    ctx.bill(EXEC_PRICE_USD, "gl_entry trial_balance")
    return {"status": "ok", "entry": {}, "entries": [],
            "balances": rows, "count": len(rows)}
