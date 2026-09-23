# Agent Utility Layer — Build Catalog v1.0.0

Source: Black's concept doc (`~/workspace/user/files/imagine_this__just_a_sceniro_dont_l.txt`).
69 capability modules. Spine first, then parallel batches. Provisional snake_case
names — public brand names come from the screened-names workstream.

## Crew A — SPINE (foundation; owns `spine/` and repo root)
- scaffold repo, git init
- spine/exec_api.py — POST /v1/execute {capability, inputs, agent_key} → {execution_id, result, billing}; GET /v1/capabilities
- spine/registry.py — load + validate modules/*/capability.json
- spine/permissions.py — declare + enforce per-capability permissions
- spine/auth.py — API-key auth (keys file outside repo)
- spine/billing.py — JSONL micro-ledger ($1 setup / $0.001 exec / $0.01 approval)
- spine/demo.py — auto-generate demo HTML per module from capability.json, labeled "DEMO — simulated providers"
- modules/_template/ — reference implementation of CONTRACT.md
- REGISTRY.md — live tracker of every module (name, pillar, price, tests, state, kill rule)
- Deploy the demo/registry page to GitHub Pages (provisional repo name `agent-utility-layer`); verify HTTP 200
- stdlib-only, pytest green

## Crew B — BATCH 1 (doc pillars; API spec exists in the concept doc)
- memory_sync (POST /v1/memory/sync — store/retrieve user memory)
- tool_wrap (POST /v1/tools/wrap — URL/OpenAPI → function spec)
- approval_request (POST /v1/approval/request — 1-tap human gate)
- ui_render (POST /v1/ui/render — JSON → widget/iframe HTML)

## Crew C — COMMUNICATION + HUMAN
- send_email, send_sms, send_voice, send_whatsapp, send_slack, send_discord, send_push, send_calendar_invite
- human_forms, human_notify, human_signature, human_escalate, human_takeover
  (approval gate itself is Crew B's; these are the surrounding human-loop tools)

## Crew D — MONEY
- charge_payment, create_invoice, manage_subscription, issue_refund, calc_tax, track_expense, financial_report

## Crew E — DATA
- web_search, web_scrape, pdf_extract, ocr_image, csv_parse, excel_parse, sql_query, nosql_query, data_transform, doc_parse

## Crew F — BUSINESS
- crm_record, helpdesk_ticket, pm_task, gl_entry, schedule_meeting, draft_contract, esign_request, inventory_check

## Crew G — INTERNET + IDENTITY
- http_request, api_call, webhook_emit, dns_lookup, site_monitor, page_interact, browser_action
- user_auth, oauth_connect, apikey_vault, permission_check, role_assign, secret_store, identity_verify
  (spine owns core auth/permission primitives; these are the user-facing capabilities built on them)

## Crew H — MEMORY + AGENT INFRA
- mem_short_term, mem_long_term, vector_search, user_profile, convo_history, knowledge_base
  (Crew B's memory_sync is the unified endpoint; these are the underlying stores)
- agent_log, agent_monitor, agent_trace, agent_analytics, cost_track, error_recovery, retry_policy, job_schedule, task_queue, state_store

## Done criteria (every module)
Working code · pytest green (≥5 tests incl. failure paths) · capability.json valid ·
README with honest pricing + limits + © 2026 Cumulative Web Inc · manifest.json ·
registers in spine demo page · kill rule recorded (60 days no real use → kill/merge).
