"""Auto-generate demo HTML pages from registered modules' capability.json.

Usage:  python3 spine/demo.py [--out docs]

Writes <out>/index.html and <out>/<module>.html. Every page carries a
visible "DEMO — simulated providers" banner. Forms are built from each
module's inputs_schema and POST to an exec API (default http://127.0.0.1:8741)
in demo mode. The API base is editable on the page because GitHub Pages is
static — a local exec API must be running for the forms to work.
"""

import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from registry import load_modules, repo_root  # noqa: E402

BANNER = ("DEMO \u2014 simulated providers. Nothing on this page touches a "
          "real provider. Results are not real.")

STYLE = """
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:960px;
margin:0 auto;padding:24px;line-height:1.5;color:#1a1a1a;background:#fafafa}
.banner{background:#fff3cd;border:2px solid #d4a017;border-radius:8px;padding:12px 16px;
font-weight:700;margin-bottom:24px}
.card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:16px;margin:12px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
a{color:#0b5fff}.meta{color:#555;font-size:.9em}
label{display:block;margin:10px 0 4px;font-weight:600}
input[type=text],input[type=number],textarea,select{width:100%;padding:8px;
border:1px solid #bbb;border-radius:4px;font-size:1em}
button{background:#0b5fff;color:#fff;border:0;border-radius:6px;padding:10px 18px;
font-size:1em;cursor:pointer;margin-top:14px}
pre{background:#111;color:#d7ffd7;padding:12px;border-radius:6px;overflow:auto;
max-height:420px}
footer{margin-top:40px;color:#777;font-size:.85em}
code{background:#eee;padding:1px 5px;border-radius:4px}
"""

FORM_JS = """
async function runDemo(capability, schema, apiBase, key) {
  const inputs = {};
  const props = schema.properties || {};
  for (const [name, spec] of Object.entries(props)) {
    const el = document.getElementById('f_' + name);
    if (!el) continue;
    let v;
    const t = spec.type;
    if (t === 'boolean') v = el.checked;
    else if (t === 'integer') v = el.value === '' ? null : parseInt(el.value, 10);
    else if (t === 'number') v = el.value === '' ? null : parseFloat(el.value);
    else if (t === 'array' || t === 'object') {
      v = el.value.trim() === '' ? null : JSON.parse(el.value);
    } else v = el.value;
    if (v !== null && v !== '' ) inputs[name] = v;
  }
  const out = document.getElementById('out');
  out.textContent = 'running (demo mode, simulated providers)...';
  try {
    const resp = await fetch(apiBase + '/v1/execute', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({capability, inputs, agent_key: key, demo: true})
    });
    const data = await resp.json();
    out.textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    out.textContent = 'ERROR: ' + e + '\\nIs the exec API running? Start it with:\\n  AUL_DEMO=1 python3 spine/exec_api.py --port 8741';
  }
}
"""


def _field(name: str, spec: dict, required: bool) -> str:
    t = spec.get("type", "string")
    req = " required" if required else ""
    label = f"<label for='f_{html.escape(name)}'>{html.escape(name)}" \
            f"{' *' if required else ''} <span class='meta'>({html.escape(t)})</span></label>"
    desc = f"<div class='meta'>{html.escape(spec.get('description', ''))}</div>" \
        if spec.get("description") else ""
    if "enum" in spec:
        opts = "".join(f"<option>{html.escape(str(o))}</option>" for o in spec["enum"])
        return f"{label}{desc}<select id='f_{html.escape(name)}'{req}>{opts}</select>"
    if t == "boolean":
        return f"{label}{desc}<input type='checkbox' id='f_{html.escape(name)}'>"
    if t in ("integer", "number"):
        return f"{label}{desc}<input type='number' id='f_{html.escape(name)}'{req}>"
    if t in ("array", "object"):
        return (f"{label}{desc}<textarea id='f_{html.escape(name)}' rows='3' "
                f"placeholder='JSON'{req}></textarea>")
    rows = 4 if len(spec.get("description", "")) > 60 or name in ("body", "message", "text") else 1
    if rows > 1:
        return f"{label}{desc}<textarea id='f_{html.escape(name)}' rows='{rows}'{req}></textarea>"
    return f"{label}{desc}<input type='text' id='f_{html.escape(name)}'{req}>"


def module_page(info) -> str:
    cap = info.capability
    schema = cap.get("inputs_schema", {}) or {}
    props = schema.get("properties", {}) or {}
    required = set(schema.get("required", []) or [])
    fields = "".join(_field(n, s if isinstance(s, dict) else {}, n in required)
                     for n, s in props.items())
    schema_json = html.escape(json.dumps(schema))
    perms = ", ".join(f"<code>{html.escape(p)}</code>" for p in cap.get("permissions", []))
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(info.name)} — demo</title><style>{STYLE}</style></head>
<body>
<div class="banner">\u26a0\ufe0f {html.escape(BANNER)}</div>
<p><a href="index.html">&larr; all modules</a></p>
<h1>{html.escape(info.name)}</h1>
<p>{html.escape(cap.get('description', ''))}</p>
<div class="card meta">
pillar: <b>{html.escape(info.pillar)}</b> &middot; version {html.escape(cap.get('version',''))}
&middot; setup ${cap.get('setup_price_usd')} &middot; per execution ${cap.get('price_per_execution_usd')}<br>
permissions: {perms or '<i>none</i>'} &middot; provisional: {cap.get('provisional')}
</div>
<h2>Try it (demo)</h2>
<div class="card">
<label>exec API base <span class="meta">(must be running with demo enabled)</span></label>
<input type="text" id="apiBase" value="http://127.0.0.1:8741">
<label>agent_key</label>
<input type="text" id="agentKey" placeholder="paste a dev API key">
{fields}
<button onclick='runDemo({json.dumps(info.name)}, JSON.parse(document.getElementById("schema").textContent), document.getElementById("apiBase").value, document.getElementById("agentKey").value)'>Run demo</button>
</div>
<h2>Response</h2>
<pre id="out">response appears here</pre>
<script id="schema" type="application/json">{schema_json}</script>
<script>{FORM_JS}</script>
<footer>\u00a9 2026 Cumulative Web Inc &middot; provisional module name &middot; demo results are not real</footer>
</body></html>"""


def index_page(registry) -> str:
    live = registry.live_modules()
    cards = []
    for name in sorted(live):
        info = live[name]
        cap = info.capability
        cards.append(
            f"<div class='card'><h3><a href='{html.escape(name)}.html'>{html.escape(name)}</a></h3>"
            f"<p>{html.escape(cap.get('description', ''))}</p>"
            f"<div class='meta'>{html.escape(info.pillar)} &middot; v{html.escape(cap.get('version',''))}"
            f" &middot; ${cap.get('price_per_execution_usd')}/exec</div></div>")
    total = len(registry.modules)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Utility Layer — module demos</title><style>{STYLE}</style></head>
<body>
<div class="banner">\u26a0\ufe0f {html.escape(BANNER)}</div>
<h1>Agent Utility Layer <span class="meta">(provisional name &mdash; under construction)</span></h1>
<p>{len(live)} of {total} modules live with runnable demos. Each demo page builds
its form from the module's <code>capability.json</code> and calls the exec API
in demo mode.</p>
<div class="grid">{''.join(cards) if cards else '<p>No live modules yet.</p>'}</div>
<footer>\u00a9 2026 Cumulative Web Inc &middot; demo results are not real provider results</footer>
</body></html>"""


def generate(root: str | None = None, out_dir: str = "docs") -> dict:
    root = root or repo_root()
    registry = load_modules(root)
    out = os.path.join(root, out_dir)
    os.makedirs(out, exist_ok=True)
    live = registry.live_modules()
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(index_page(registry))
    for name, info in live.items():
        with open(os.path.join(out, f"{name}.html"), "w", encoding="utf-8") as fh:
            fh.write(module_page(info))
    return {"pages": len(live) + 1, "live": len(live), "total": len(registry.modules)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs")
    parser.add_argument("--root", default=None)
    args = parser.parse_args()
    stats = generate(args.root, args.out)
    print(json.dumps(stats))
