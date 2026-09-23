"""Regenerate REGISTRY.md — the live module tracker.

Usage: python3 spine/registry_report.py
Reads live registry data + per-module manifest.json test claims, merges with
the CATALOG.md module list, writes REGISTRY.md. Re-run whenever modules land.
"""

import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from registry import load_modules, repo_root  # noqa: E402

# Module -> pillar, from CATALOG.md (Crew A..H assignments).
CATALOG_MODULES = {
    # Crew B — batch 1
    "memory_sync": "memory", "tool_wrap": "internet",
    "approval_request": "human", "ui_render": "ui",
    # Crew C — communication + human
    "send_email": "communication", "send_sms": "communication",
    "send_voice": "communication", "send_whatsapp": "communication",
    "send_slack": "communication", "send_discord": "communication",
    "send_push": "communication", "send_calendar_invite": "communication",
    "human_forms": "human", "human_notify": "human",
    "human_signature": "human", "human_escalate": "human",
    "human_takeover": "human",
    # Crew D — money
    "charge_payment": "money", "create_invoice": "money",
    "manage_subscription": "money", "issue_refund": "money",
    "calc_tax": "money", "track_expense": "money",
    "financial_report": "money",
    # Crew E — data
    "web_search": "data", "web_scrape": "data", "pdf_extract": "data",
    "ocr_image": "data", "csv_parse": "data", "excel_parse": "data",
    "sql_query": "data", "nosql_query": "data",
    "data_transform": "data", "doc_parse": "data",
    # Crew F — business
    "crm_record": "business", "helpdesk_ticket": "business",
    "pm_task": "business", "gl_entry": "business",
    "schedule_meeting": "business", "draft_contract": "business",
    "esign_request": "business", "inventory_check": "business",
    # Crew G — internet + identity
    "http_request": "internet", "api_call": "internet",
    "webhook_emit": "internet", "dns_lookup": "internet",
    "site_monitor": "internet", "page_interact": "internet",
    "browser_action": "internet",
    "user_auth": "identity", "oauth_connect": "identity",
    "apikey_vault": "identity", "permission_check": "identity",
    "role_assign": "identity", "secret_store": "identity",
    "identity_verify": "identity",
    # Crew H — memory + agent infra
    "mem_short_term": "memory", "mem_long_term": "memory",
    "vector_search": "memory", "user_profile": "memory",
    "convo_history": "memory", "knowledge_base": "memory",
    "agent_log": "agent_infra", "agent_monitor": "agent_infra",
    "agent_trace": "agent_infra", "agent_analytics": "agent_infra",
    "cost_track": "agent_infra", "error_recovery": "agent_infra",
    "retry_policy": "agent_infra", "job_schedule": "agent_infra",
    "task_queue": "agent_infra", "state_store": "agent_infra",
}

KILL = "60d no real use \u2192 kill/merge (listed 2026-09-23)"


def main():
    root = repo_root()
    reg = load_modules(root)
    manifests = {}
    for path in glob.glob(os.path.join(root, "modules", "*", "*", "manifest.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            manifests[data.get("module")] = data
        except (json.JSONDecodeError, KeyError):
            pass

    names = sorted(set(CATALOG_MODULES) | set(reg.modules))
    rows = []
    live = skeleton = invalid = unbuilt = 0
    for name in names:
        info = reg.modules.get(name)
        manifest = manifests.get(name, {})
        tests = manifest.get("tests", "\u2014")
        if info is None:
            pillar, state = CATALOG_MODULES[name], "unbuilt"
            setup, execp = "1.00", "0.001"
            unbuilt += 1
        else:
            pillar, state = info.pillar, info.state
            cap = info.capability or {}
            setup = f"{cap.get('setup_price_usd', 1.0):.3f}".rstrip("0").rstrip(".")
            execp = f"{cap.get('price_per_execution_usd', 0.001):.6f}".rstrip("0").rstrip(".")
            if state == "live":
                live += 1
            elif state == "skeleton":
                skeleton += 1
            else:
                invalid += 1
        kill = "exempt (contract reference)" if name == "template_demo" else KILL
        rows.append(
            f"| {name} | {pillar} | ${setup} | ${execp} | {tests} | {state} | {kill} |")

    ts = time.strftime("%Y-%m-%d %H:%M %Z", time.gmtime())
    doc = f"""# Agent Utility Layer — Module Registry (live tracker)

Generated {ts} by `python3 spine/registry_report.py`. Re-run after modules land.

**Counts:** {live} live · {skeleton} skeleton (capability only) · {invalid} invalid (in progress) · {unbuilt} unbuilt · **{len(names)} total tracked**

States: `live` = valid capability.json + handler.py (demo page generated, exec API serves it) ·
`skeleton` = capability.json only · `invalid` = failing validation / missing capability.json (crew still building) ·
`unbuilt` = cataloged, no code yet. Tests column quotes each crew's `manifest.json` claim.

Honesty: demo pages are labeled "DEMO — simulated providers". A live module is
not a verified provider integration — check its README for what is real.

| module | pillar | setup | per-exec | tests | state | kill rule |
|---|---|---|---|---|---|---|
{chr(10).join(rows)}

© 2026 Cumulative Web Inc
"""
    out = os.path.join(root, "REGISTRY.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"wrote {out}: {len(names)} modules ({live} live)")


if __name__ == "__main__":
    main()
