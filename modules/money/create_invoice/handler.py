"""create_invoice — generate a real invoice document (HTML) for a customer.

This module CREATES A DOCUMENT — it moves no money. It therefore requires no
human approval and no provider credential. Totals are computed in minor units
with Decimal to avoid float rounding errors. Issued invoices are persisted in
ctx.memory ("invoices") so financial_report can aggregate them.
"""

import html
import time
from decimal import Decimal, ROUND_HALF_UP

PRICE_PER_EXEC_USD = 0.01


class ModuleError(Exception):
    """Bad input."""


class AuthMissing(ModuleError):
    pass  # kept for ctx-interface symmetry; not raised by this module


class ApprovalDenied(ModuleError):
    pass  # kept for ctx-interface symmetry; not raised by this module


def _validate(inputs):
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")
    customer_name = inputs.get("customer_name")
    if not isinstance(customer_name, str) or not customer_name.strip():
        raise ModuleError("customer_name is required")
    customer_email = inputs.get("customer_email", "")
    if customer_email is not None and not isinstance(customer_email, str):
        raise ModuleError("customer_email must be a string")
    items = inputs.get("items")
    if not isinstance(items, list) or not items:
        raise ModuleError("items must be a non-empty list")
    clean_items = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            raise ModuleError(f"items[{i}] must be an object")
        desc = it.get("description")
        if not isinstance(desc, str) or not desc.strip():
            raise ModuleError(f"items[{i}].description is required")
        qty = it.get("qty", 1)
        if isinstance(qty, bool) or not isinstance(qty, (int, float)) or qty <= 0:
            raise ModuleError(f"items[{i}].qty must be a positive number")
        unit = it.get("unit_cents")
        if isinstance(unit, bool) or not isinstance(unit, int) or unit < 0:
            raise ModuleError(f"items[{i}].unit_cents must be a non-negative integer")
        clean_items.append({"description": desc.strip(), "qty": qty, "unit_cents": unit})
    currency = str(inputs.get("currency", "usd")).lower()
    if len(currency) != 3 or not currency.isalpha():
        raise ModuleError("currency must be a 3-letter ISO code")
    tax_rate = inputs.get("tax_rate", 0)
    if isinstance(tax_rate, bool) or not isinstance(tax_rate, (int, float)) or tax_rate < 0 or tax_rate > 1:
        raise ModuleError("tax_rate must be a decimal fraction between 0 and 1")
    due_date = inputs.get("due_date", "")
    if due_date is not None and not isinstance(due_date, str):
        raise ModuleError("due_date must be a string (YYYY-MM-DD)")
    invoice_number = inputs.get("invoice_number", "")
    if invoice_number is not None and not isinstance(invoice_number, str):
        raise ModuleError("invoice_number must be a string")
    issuer = inputs.get("issuer", {})
    if not isinstance(issuer, dict):
        raise ModuleError("issuer must be an object")
    notes = inputs.get("notes", "")
    if notes is not None and not isinstance(notes, str):
        raise ModuleError("notes must be a string")
    return {
        "customer_name": customer_name.strip(),
        "customer_email": (customer_email or "").strip(),
        "items": clean_items,
        "currency": currency,
        "tax_rate": Decimal(str(tax_rate)),
        "due_date": (due_date or "").strip(),
        "invoice_number": (invoice_number or "").strip(),
        "issuer": issuer,
        "notes": (notes or "").strip(),
    }


def _money(cents, currency):
    return f"{cents / 100:,.2f} {currency.upper()}"


def _render_html(p, subtotal, tax, total):
    rows = "".join(
        f"<tr><td>{html.escape(it['description'])}</td>"
        f"<td style='text-align:right'>{it['qty']}</td>"
        f"<td style='text-align:right'>{_money(it['unit_cents'], p['currency'])}</td>"
        f"<td style='text-align:right'>{_money(int(Decimal(it['unit_cents']) * Decimal(str(it['qty']))), p['currency'])}</td></tr>"
        for it in p["items"]
    )
    issuer = p["issuer"] or {}
    issuer_name = html.escape(str(issuer.get("name", "Cumulative Web Inc")))
    issuer_addr = "<br>".join(html.escape(str(x)) for x in issuer.get("address_lines", []))
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Invoice {html.escape(p['invoice_number'])}</title>
<style>body{{font-family:Arial,Helvetica,sans-serif;max-width:720px;margin:32px auto;color:#111}}
table{{width:100%;border-collapse:collapse;margin-top:16px}}
th,td{{border:1px solid #ccc;padding:8px}}th{{background:#f4f4f4;text-align:left}}
.totals td{{border:none;text-align:right}}.foot{{margin-top:24px;font-size:12px;color:#666}}</style></head>
<body>
<h1>Invoice {html.escape(p['invoice_number'])}</h1>
<p><strong>From:</strong> {issuer_name}{('<br>' + issuer_addr) if issuer_addr else ''}</p>
<p><strong>Bill to:</strong> {html.escape(p['customer_name'])}
{('<br>' + html.escape(p['customer_email'])) if p['customer_email'] else ''}
{('<br><strong>Due:</strong> ' + html.escape(p['due_date'])) if p['due_date'] else ''}</p>
<table><thead><tr><th>Description</th><th style="text-align:right">Qty</th>
<th style="text-align:right">Unit</th><th style="text-align:right">Line total</th></tr></thead>
<tbody>{rows}</tbody></table>
<table class="totals">
<tr><td>Subtotal:</td><td><strong>{_money(subtotal, p['currency'])}</strong></td></tr>
<tr><td>Tax ({float(p['tax_rate']) * 100:.2f}%):</td><td><strong>{_money(tax, p['currency'])}</strong></td></tr>
<tr><td>Total due:</td><td><strong>{_money(total, p['currency'])}</strong></td></tr>
</table>
{'<p><strong>Notes:</strong> ' + html.escape(p['notes']) + '</p>' if p['notes'] else ''}
<p class="foot">Issued {html.escape(p['issued_at'])} via CWI Agent Utility Layer.</p>
</body></html>"""


def execute(inputs: dict, ctx) -> dict:
    """Build the invoice, persist it, return it. No approval/auth needed."""
    p = _validate(inputs)

    if not p["invoice_number"]:
        seq = int(ctx.memory_get("invoice_seq") or 0) + 1
        ctx.memory_set("invoice_seq", seq)
        p["invoice_number"] = f"INV-{time.strftime('%Y%m%d')}-{seq:04d}"

    subtotal = sum(int(Decimal(it["unit_cents"]) * Decimal(str(it["qty"]))) for it in p["items"])
    tax = int((Decimal(subtotal) * p["tax_rate"]).to_integral_value(rounding=ROUND_HALF_UP))
    total = subtotal + tax

    p["issued_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    html_doc = _render_html(p, subtotal, tax, total)

    invoice = {
        "invoice_id": f"inv_{p['invoice_number']}",
        "invoice_number": p["invoice_number"],
        "customer_name": p["customer_name"],
        "currency": p["currency"],
        "subtotal_cents": subtotal,
        "tax_cents": tax,
        "total_cents": total,
        "issued_at": p["issued_at"],
        "due_date": p["due_date"] or None,
    }
    invoices = ctx.memory_get("invoices") or []
    invoices.append(invoice)
    ctx.memory_set("invoices", invoices)

    ctx.log("create_invoice.issued", {
        "invoice_number": p["invoice_number"],
        "customer_name": p["customer_name"],
        "total_cents": total,
        "currency": p["currency"],
    })
    ctx.bill(PRICE_PER_EXEC_USD, f"create_invoice {p['invoice_number']}")

    return {
        "status": "issued",
        "invoice_id": invoice["invoice_id"],
        "invoice_number": p["invoice_number"],
        "customer_name": p["customer_name"],
        "subtotal_cents": subtotal,
        "tax_cents": tax,
        "total_cents": total,
        "currency": p["currency"],
        "html": html_doc,
    }
