"""ui_render — POST /v1/ui/render: JSON -> styled widget HTML.

Real logic, $0, stdlib only: generates self-contained HTML (inline CSS, no
external requests, no JS libraries) for four component types:
  - data_table       list[dict] -> sortable-looking styled <table>
  - chart            list[dict] -> real server-side-rendered SVG bar chart
  - form             dict/list of field specs -> accessible HTML <form>
  - confirmation_card dict -> summary card with confirm/cancel buttons

All user strings are HTML-escaped (html.escape). The rendered HTML is stored
via ctx.memory under "aul:ui_render:{render_id}" so the embed URL resolves to
a real artifact. The CDN URL is a labeled placeholder until deploy.
"""
from __future__ import annotations

import hashlib
import html
import json

EXEC_PRICE_USD = 0.001
COMPONENTS = {"data_table", "chart", "form", "confirmation_card"}
EMBED_URL_BASE = "https://cdn.agent-utility-layer.io/v1/render"
RECORD_PREFIX = "aul:ui_render:"
MAX_ROWS = 500
MAX_DATA_CHARS = 100_000


class ModuleError(Exception):
    pass


class AuthMissing(ModuleError):
    pass


class ApprovalDenied(ModuleError):
    pass


_CSS = """
.aul{font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,s-serif;
color:#1a1a2e;max-width:720px;margin:0 auto}
.aul h2{font-size:18px;margin:0 0 12px}
.aul table{width:100%;border-collapse:collapse;font-size:14px}
.aul th{background:#16213e;color:#fff;text-align:left;padding:10px 12px}
.aul td{border-bottom:1px solid #e0e0e0;padding:9px 12px}
.aul tr:nth-child(even) td{background:#f7f9fc}
.aul .card{border:1px solid #e0e0e0;border-radius:12px;padding:20px;
box-shadow:0 2px 8px rgba(0,0,0,.06)}
.aul .row{display:flex;justify-content:space-between;padding:6px 0;
border-bottom:1px dashed #eee;font-size:14px}
.aul .btn{display:inline-block;padding:10px 22px;border-radius:8px;border:0;
font-size:14px;cursor:pointer;margin:6px 8px 0 0}
.aul .confirm{background:#16213e;color:#fff}
.aul .cancel{background:#f0f0f0;color:#333}
.aul input,.aul select{width:100%;padding:9px 10px;margin:4px 0 12px;
border:1px solid #ccc;border-radius:6px;font-size:14px;box-sizing:border-box}
.aul label{font-size:13px;font-weight:600}
.aul svg{display:block}
"""


def _esc(value) -> str:
    return html.escape(str(value), quote=True)


def _page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>%s</title><style>%s</style></head>"
        "<body><div class=\"aul\">%s</div></body></html>"
        % (_esc(title), _CSS, body)
    )


def _render_table(title: str, data: list) -> str:
    if not isinstance(data, list) or not data or not all(
        isinstance(r, dict) for r in data
    ):
        raise ModuleError("data_table requires data as a non-empty list of objects")
    cols = []
    for row in data:
        for k in row:
            if k not in cols:
                cols.append(k)
    thead = "".join("<th>%s</th>" % _esc(c) for c in cols)
    rows = "".join(
        "<tr>" + "".join("<td>%s</td>" % _esc(r.get(c, "")) for c in cols) + "</tr>"
        for r in data
    )
    return "<h2>%s</h2><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (
        _esc(title), thead, rows)


def _render_chart(title: str, data: list) -> str:
    if not isinstance(data, list) or not data or not all(
        isinstance(r, dict) for r in data
    ):
        raise ModuleError("chart requires data as a non-empty list of objects")
    label_key = value_key = None
    for k, v in data[0].items():
        if value_key is None and isinstance(v, (int, float)) and not isinstance(v, bool):
            value_key = k
        elif label_key is None and isinstance(v, str):
            label_key = k
    if value_key is None:
        raise ModuleError("chart needs at least one numeric field in the data")
    label_key = label_key or value_key
    values = [r.get(value_key) for r in data]
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        raise ModuleError("chart value field %r must be numeric in every row"
                          % value_key)
    labels = [str(r.get(label_key, "")) for r in data]
    vmax = max(values) if max(values) > 0 else 1
    n = len(data)
    bar_h = 26
    gap = 10
    plot_w = 420
    label_w = 140
    height = n * (bar_h + gap) + 10
    bars = []
    for i, (lab, val) in enumerate(zip(labels, values)):
        y = 5 + i * (bar_h + gap)
        w = max(2.0, (val / vmax) * plot_w)
        bars.append(
            "<text x=\"0\" y=\"%d\" font-size=\"12\" fill=\"#1a1a2e\">%s</text>"
            "<rect x=\"%d\" y=\"%d\" width=\"%.1f\" height=\"%d\" rx=\"4\" "
            "fill=\"#16213e\"/>"
            "<text x=\"%d\" y=\"%d\" font-size=\"11\" fill=\"#555\">%s</text>"
            % (y + bar_h - 8, _esc(lab[:18]), label_w, y, w, bar_h,
               label_w + w + 8, y + bar_h - 9, _esc(val))
        )
    svg = (
        "<svg width=\"%d\" height=\"%d\" role=\"img\" "
        "aria-label=\"bar chart of %s\">%s</svg>"
        % (label_w + plot_w + 90, height, _esc(value_key), "".join(bars))
    )
    return "<h2>%s</h2><p style=\"font-size:13px;color:#555\">%s by %s</p>%s" % (
        _esc(title), _esc(value_key), _esc(label_key), svg)


def _render_form(title: str, data) -> str:
    if isinstance(data, dict):
        fields = [
            {"name": name,
             "label": (spec.get("label") if isinstance(spec, dict) else None) or name,
             "type": (spec.get("type") if isinstance(spec, dict) else "text") or "text",
             "required": bool(spec.get("required")) if isinstance(spec, dict) else False}
            for name, spec in data.items()
        ]
    elif isinstance(data, list) and all(isinstance(f, str) for f in data):
        fields = [{"name": f, "label": f, "type": "text", "required": False}
                  for f in data]
    else:
        raise ModuleError(
            "form requires data as an object of field specs or a list of field names")
    if not fields:
        raise ModuleError("form requires at least one field")
    inputs = []
    for f in fields:
        ftype = f["type"] if f["type"] in ("text", "email", "number", "tel", "date",
                                           "password", "url") else "text"
        req = " required" if f["required"] else ""
        inputs.append(
            "<label>%s<input type=\"%s\" name=\"%s\"%s></label>"
            % (_esc(f["label"]), ftype, _esc(f["name"]), req)
        )
    return ("<h2>%s</h2><div class=\"card\"><form method=\"post\" action=\"#\">%s"
            "<br><button class=\"btn confirm\" type=\"submit\">Submit</button>"
            "</form></div>" % (_esc(title), "".join(inputs)))


def _render_confirmation(title: str, data: dict) -> str:
    if not isinstance(data, dict) or not data:
        raise ModuleError("confirmation_card requires data as a non-empty object")
    rows = "".join(
        "<div class=\"row\"><span>%s</span><strong>%s</strong></div>"
        % (_esc(k), _esc(v)) for k, v in data.items()
    )
    return ("<h2>%s</h2><div class=\"card\">%s"
            "<button class=\"btn confirm\">Confirm</button>"
            "<button class=\"btn cancel\">Cancel</button></div>"
            % (_esc(title), rows))


def execute(inputs: dict, ctx) -> dict:
    """Run the capability. Returns a dict matching outputs_schema."""
    if not isinstance(inputs, dict):
        raise ModuleError("inputs must be an object")

    component_type = inputs.get("component_type")
    if component_type not in COMPONENTS:
        raise ModuleError(
            "invalid component_type %r; must be one of %s"
            % (component_type, sorted(COMPONENTS))
        )
    title = inputs.get("title") or "Agent UI"
    if not isinstance(title, str):
        raise ModuleError("title must be a string when provided")

    data = inputs.get("data")
    if data is None:
        raise ModuleError("data is required")
    try:
        data_text = json.dumps(data, default=str)
    except (TypeError, ValueError) as e:
        raise ModuleError("data must be JSON-serializable: %s" % e)
    if len(data_text) > MAX_DATA_CHARS:
        raise ModuleError("data exceeds %d chars" % MAX_DATA_CHARS)
    if isinstance(data, list) and len(data) > MAX_ROWS:
        raise ModuleError("data limited to %d rows per render" % MAX_ROWS)

    if component_type == "data_table":
        body = _render_table(title, data)
    elif component_type == "chart":
        body = _render_chart(title, data)
    elif component_type == "form":
        body = _render_form(title, data)
    else:
        body = _render_confirmation(title, data)

    render_id = "ui_" + hashlib.sha256(
        json.dumps({"t": component_type, "d": data_text},
                   sort_keys=True).encode()
    ).hexdigest()[:10]
    embed_url = "%s/%s.html" % (EMBED_URL_BASE, render_id)
    page = _page(title, body)
    ctx.memory_set(RECORD_PREFIX + render_id, page)
    ctx.log("ui_render.rendered",
            {"render_id": render_id, "component_type": component_type,
             "html_bytes": len(page)})
    ctx.bill(EXEC_PRICE_USD, "ui_render %s" % render_id)
    return {
        "render_id": render_id,
        "embed_url": embed_url,
        "embed_url_note": (
            "Placeholder CDN URL until deploy; the rendered HTML is stored now "
            "under ctx.memory key '%s%s'." % (RECORD_PREFIX, render_id)
        ),
        "iframe_snippet": (
            "<iframe src='%s' width='100%%' height='420px' "
            "frameborder='0' title='%s'></iframe>" % (embed_url, _esc(title))
        ),
    }
