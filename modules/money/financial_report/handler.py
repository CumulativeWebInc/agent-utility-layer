"""financial_report — build a financial summary report (HTML) from module memory.

READ-ONLY aggregation — it reads the invoices persisted by create_invoice and
the expenses persisted by track_expense, then renders an HTML report with
totals, net position, and category breakdowns. No provider, no credential,
no approval. Zeros are zeros: an empty ledger produces an honest zero report.
"""

import html
import time

PRICE_PER_EXEC_USD = 0.01
SECTIONS = ("invoices", "expenses")


class ModuleError(Exception):
    """Bad input."""


class AuthMissing(ModuleError):
    pass  # interface symmetry; never raised here


class ApprovalDenied(ModuleError):
    pass  # interface symmetry; never raised here


def _validate(inputs):
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    title = inputs.get("title", "Financial Report")
    if not isinstance(title, str) or not title.strip():
        raise ModuleError("title must be a non-empty string")
    currency = inputs.get("currency")
    if currency is not None:
        currency = str(currency).lower()
        if len(currency) != 3 or not currency.isalpha():
            raise ModuleError("currency must be a 3-letter ISO code")
    include = inputs.get("include", list(SECTIONS))
    if not isinstance(include, list) or not include or any(s not in SECTIONS for s in include):
        raise ModuleError(f"include must be a non-empty list of {list(SECTIONS)}")
    return {"title": title.strip(), "currency": currency, "include": include}


def _money(cents, currency):
    return f"{cents / 100:,.2f} {currency.upper()}"


def _render(p, invoices, expenses, summary):
    inv_rows = "".join(
        f"<tr><td>{html.escape(i['invoice_number'])}</td>"
        f"<td>{html.escape(i['customer_name'])}</td>"
        f"<td style='text-align:right'>{_money(i['total_cents'], i['currency'])}</td>"
        f"<td>{html.escape(str(i.get('due_date') or '—'))}</td></tr>"
        for i in invoices
    )
    cat_rows = "".join(
        f"<tr><td>{html.escape(c)}</td>"
        f"<td style='text-align:right'>{_money(v, p['currency'] or 'USD')}</td></tr>"
        for c, v in sorted(summary["by_category"].items())
    )
    exp_rows = "".join(
        f"<tr><td>{html.escape(e['date'])}</td><td>{html.escape(e['category'])}</td>"
        f"<td>{html.escape(e.get('vendor') or '—')}</td>"
        f"<td style='text-align:right'>{_money(e['amount_cents'], e['currency'])}</td></tr>"
        for e in expenses
    )
    cur = (p["currency"] or "mixed").upper()
    sections = []
    if "invoices" in p["include"]:
        sections.append(
            f"<h2>Invoices ({summary['invoice_count']})</h2>"
            f"<table><thead><tr><th>Number</th><th>Customer</th>"
            f"<th style='text-align:right'>Total</th><th>Due</th></tr></thead>"
            f"<tbody>{inv_rows or '<tr><td colspan=4>No invoices recorded.</td></tr>'}</tbody></table>"
            f"<p><strong>Invoiced total:</strong> {_money(summary['invoiced_total_cents'], cur)}</p>"
        )
    if "expenses" in p["include"]:
        sections.append(
            f"<h2>Expenses ({summary['expense_count']})</h2>"
            f"<table><thead><tr><th>Date</th><th>Category</th><th>Vendor</th>"
            f"<th style='text-align:right'>Amount</th></tr></thead>"
            f"<tbody>{exp_rows or '<tr><td colspan=4>No expenses recorded.</td></tr>'}</tbody></table>"
            f"<p><strong>Expense total:</strong> {_money(summary['expense_total_cents'], cur)}</p>"
            f"<h3>By category</h3><table><tbody>"
            f"{cat_rows or '<tr><td>No expenses recorded.</td></tr>'}</tbody></table>"
        )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{html.escape(p['title'])}</title>
<style>body{{font-family:Arial,Helvetica,sans-serif;max-width:760px;margin:32px auto;color:#111}}
table{{width:100%;border-collapse:collapse;margin-top:8px}}
th,td{{border:1px solid #ccc;padding:8px}}th{{background:#f4f4f4;text-align:left}}
.foot{{margin-top:24px;font-size:12px;color:#666}}
.net{{font-size:18px;margin-top:16px}}</style></head>
<body>
<h1>{html.escape(p['title'])}</h1>
<p class="net"><strong>Net position:</strong> {_money(summary['net_cents'], cur)}
(invoiced − expenses)</p>
{''.join(sections)}
<p class="foot">Generated {html.escape(summary['generated_at'])} via CWI Agent Utility Layer.
Invoiced figures reflect issued invoices, not collected cash.</p>
</body></html>"""


def execute(inputs: dict, ctx) -> dict:
    """Aggregate the money-module ledgers into an HTML report."""
    p = _validate(inputs)

    invoices = ctx.memory_get("invoices") or []
    expenses = ctx.memory_get("expenses") or []
    if p["currency"]:
        invoices = [i for i in invoices if i.get("currency") == p["currency"]]
        expenses = [e for e in expenses if e.get("currency") == p["currency"]]

    invoiced_total = sum(i["total_cents"] for i in invoices)
    expense_total = sum(e["amount_cents"] for e in expenses)
    by_category = {}
    for e in expenses:
        by_category[e["category"]] = by_category.get(e["category"], 0) + e["amount_cents"]

    summary = {
        "invoice_count": len(invoices),
        "expense_count": len(expenses),
        "invoiced_total_cents": invoiced_total,
        "expense_total_cents": expense_total,
        "net_cents": invoiced_total - expense_total,
        "by_category": by_category,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    html_doc = _render(p, invoices, expenses, summary)

    ctx.log("financial_report.generated", {
        "title": p["title"],
        "invoice_count": summary["invoice_count"],
        "expense_count": summary["expense_count"],
        "net_cents": summary["net_cents"],
    })
    ctx.bill(PRICE_PER_EXEC_USD, f"financial_report {p['title'][:40]}")

    return {"status": "generated", "title": p["title"], "html": html_doc, "summary": summary}
