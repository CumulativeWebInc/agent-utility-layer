# Agent Utility Layer — Module Registry (live tracker)

Generated 2026-09-23 18:20 GMT by `python3 spine/registry_report.py`. Re-run after modules land.

**Counts:** 60 live · 0 skeleton (capability only) · 13 invalid (in progress) · 0 unbuilt · **73 total tracked**

States: `live` = valid capability.json + handler.py (demo page generated, exec API serves it) ·
`skeleton` = capability.json only · `invalid` = failing validation / missing capability.json (crew still building) ·
`unbuilt` = cataloged, no code yet. Tests column quotes each crew's `manifest.json` claim.

Honesty: demo pages are labeled "DEMO — simulated providers". A live module is
not a verified provider integration — check its README for what is real.

| module | pillar | setup | per-exec | tests | state | kill rule |
|---|---|---|---|---|---|---|
| agent_analytics | agent_infra | $1 | $0.001 | pending | live | 60d no real use → kill/merge (listed 2026-09-23) |
| agent_log | agent_infra | $1 | $0.001 | pending | live | 60d no real use → kill/merge (listed 2026-09-23) |
| agent_monitor | agent_infra | $1 | $0.001 | pending | live | 60d no real use → kill/merge (listed 2026-09-23) |
| agent_trace | agent_infra | $1 | $0.001 | pending | live | 60d no real use → kill/merge (listed 2026-09-23) |
| api_call | internet | $1 | $0.001 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| apikey_vault | identity | $1 | $0.001 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| approval_request | human_loop | $1 | $0.01 | 10 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| browser_action | internet | $1 | $0.001 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| calc_tax | money | $1 | $0.01 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| charge_payment | money | $1 | $0.05 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| convo_history | memory | $1 | $0.001 | pending | live | 60d no real use → kill/merge (listed 2026-09-23) |
| cost_track | agent_infra | $1 | $0.001 | pending | live | 60d no real use → kill/merge (listed 2026-09-23) |
| create_invoice | money | $1 | $0.01 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| crm_record | business | $1 | $0.001 | 8 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| csv_parse | data | $1 | $0.001 | 9 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| data_transform | data | $1 | $0.001 | 9 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| dns_lookup | internet | $1 | $0.001 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| doc_parse | data | $1 | $0.001 | 8 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| draft_contract | business | $1 | $0.001 | 7 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| error_recovery | agent_infra | $1 | $0.001 | pending | live | 60d no real use → kill/merge (listed 2026-09-23) |
| esign_request | business | $1 | $0.001 | 8 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| excel_parse | data | $1 | $0.001 | 8 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| financial_report | money | $1 | $0.01 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| gl_entry | business | $1 | $0.001 | 8 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| helpdesk_ticket | business | $1 | $0.001 | 8 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| http_request | internet | $1 | $0.001 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| human_escalate | human | $1 | $0.001 | — | invalid | 60d no real use → kill/merge (listed 2026-09-23) |
| human_forms | human | $1 | $0.001 | — | invalid | 60d no real use → kill/merge (listed 2026-09-23) |
| human_notify | human | $1 | $0.001 | — | invalid | 60d no real use → kill/merge (listed 2026-09-23) |
| human_signature | human | $1 | $0.001 | — | invalid | 60d no real use → kill/merge (listed 2026-09-23) |
| human_takeover | human | $1 | $0.001 | — | invalid | 60d no real use → kill/merge (listed 2026-09-23) |
| identity_verify | identity | $1 | $0.001 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| inventory_check | business | $1 | $0.001 | 9 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| issue_refund | money | $1 | $0.05 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| job_schedule | agent_infra | $1 | $0.001 | pending | live | 60d no real use → kill/merge (listed 2026-09-23) |
| knowledge_base | memory | $1 | $0.001 | pending | live | 60d no real use → kill/merge (listed 2026-09-23) |
| manage_subscription | money | $1 | $0.05 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| mem_long_term | memory | $1 | $0.001 | pending | live | 60d no real use → kill/merge (listed 2026-09-23) |
| mem_short_term | memory | $1 | $0.001 | pending | live | 60d no real use → kill/merge (listed 2026-09-23) |
| memory_sync | memory | $1 | $0.001 | 9 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| nosql_query | data | $1 | $0.001 | 9 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| oauth_connect | identity | $1 | $0.001 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| ocr_image | data | $1 | $0.005 | 8 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| page_interact | internet | $1 | $0.001 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| pdf_extract | data | $1 | $0.001 | 9 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| permission_check | identity | $1 | $0.001 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| pm_task | business | $1 | $0.001 | 7 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| retry_policy | agent_infra | $1 | $0.001 | pending | live | 60d no real use → kill/merge (listed 2026-09-23) |
| role_assign | identity | $1 | $0.001 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| schedule_meeting | business | $1 | $0.001 | 7 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| secret_store | identity | $1 | $0.001 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| send_calendar_invite | communication | $1 | $0.001 | — | invalid | 60d no real use → kill/merge (listed 2026-09-23) |
| send_discord | communication | $1 | $0.001 | — | invalid | 60d no real use → kill/merge (listed 2026-09-23) |
| send_email | communication | $1 | $0.001 | — | invalid | 60d no real use → kill/merge (listed 2026-09-23) |
| send_push | communication | $1 | $0.001 | — | invalid | 60d no real use → kill/merge (listed 2026-09-23) |
| send_slack | communication | $1 | $0.001 | — | invalid | 60d no real use → kill/merge (listed 2026-09-23) |
| send_sms | communication | $1 | $0.001 | — | invalid | 60d no real use → kill/merge (listed 2026-09-23) |
| send_voice | communication | $1 | $0.001 | — | invalid | 60d no real use → kill/merge (listed 2026-09-23) |
| send_whatsapp | communication | $1 | $0.001 | — | invalid | 60d no real use → kill/merge (listed 2026-09-23) |
| site_monitor | internet | $1 | $0.001 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| sql_query | data | $1 | $0.001 | 7 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| state_store | agent_infra | $1 | $0.001 | pending | live | 60d no real use → kill/merge (listed 2026-09-23) |
| task_queue | agent_infra | $1 | $0.001 | pending | live | 60d no real use → kill/merge (listed 2026-09-23) |
| template_demo | _template | $1 | $0.001 | 9 passed | live | exempt (contract reference) |
| tool_wrap | tools | $1 | $1 | 11 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| track_expense | money | $1 | $0.01 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| ui_render | ui | $1 | $0.001 | 12 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| user_auth | identity | $1 | $0.001 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |
| user_profile | memory | $1 | $0.001 | pending | live | 60d no real use → kill/merge (listed 2026-09-23) |
| vector_search | memory | $1 | $0.001 | pending | live | 60d no real use → kill/merge (listed 2026-09-23) |
| web_scrape | data | $1 | $0.005 | 7 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| web_search | data | $1 | $0.005 | 9 passed | live | 60d no real use → kill/merge (listed 2026-09-23) |
| webhook_emit | internet | $1 | $0.001 | — | live | 60d no real use → kill/merge (listed 2026-09-23) |

© 2026 Cumulative Web Inc
