# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

Datathon project for **Challenge 01: Intelligent Conversational AI for the
KSP (Karnataka State Police) Crime Database**. FastAPI backend + vanilla-JS
frontend over the **real Karnataka FIR schema** (30 tables from
`Police_FIR_ER_Diagram.pdf`, anchored on `CaseMaster`). Deploys on **Zoho
Catalyst** (AppSail + Data Store + service map) — deployment via Catalyst is
mandatory for the submission.

## Common commands

All commands assume PowerShell in the project root.

```powershell
# One-shot launch (creates venv, installs deps, seeds DB, starts server)
.\run.ps1

# Manual
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env         # optional: add ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000

# Reset the database (next boot re-seeds deterministically)
Remove-Item backend\crime.db

# Export Data Store CSVs + schema cheat sheet (for Catalyst console import)
backend\.venv\Scripts\python.exe scripts\create-datastore-tables.py

# Sync code into the Catalyst deploy layout (appsail/ + client/)
powershell -File scripts\prepare-deploy.ps1

# End-to-end deploy (preflight → sync → optional DS bootstrap → catalyst deploy)
.\deploy.ps1
```

Open <http://localhost:8000>. Health check: <http://localhost:8000/health>
(reports which Catalyst services are live — never trust a badge you didn't
check). See `DEPLOY.md` for the full Catalyst bring-up (Data Store console
import, Cron wiring, split AppSail + Client Hosting layout).

There is no test suite yet. If you add one, use `pytest` in `backend/` and
put the command here.

## Architecture

### Request flow for `/chat`

```
frontend/app.js ── POST /chat { query, history, conversation_id } ──► main.py::chat
      │
      ▼
llm.nl_to_sql(query, history, capp)
  ├─ Catalyst QuickML (CATALYST_QUICKML_ENDPOINT_KEY + request context)
  ├─ rotating hosted-LLM chain: Gemini key pool → Groq → OpenRouter →
  │    OpenAI → Anthropic (raw HTTP, per-key 429 cooldowns — see
  │    _providers() in llm.py; keys documented in .env.example)
  └─ _fallback keyword rules (bilingual EN/KN, always works)
      │
      ▼
is_safe_sql  — single SELECT/WITH, keyword blocklist
      │
      ▼
_apply_role_policy  — the load-bearing security layer:
  ├─ analyst: refuse PII name columns anywhere; PII tables aggregate-only;
  │           caste/religion/occupation aggregate-only
  ├─ dysp/sho/io: sqlglot rewrite — scope predicate injected into EVERY
  │           SELECT reading CaseMaster (incl. CTEs/subqueries); SELECTs
  │           reading case-child tables (Accused, Victim, …) without
  │           CaseMaster get IN-(scoped case set); unparseable SQL → 403
  └─ append LIMIT if missing (\blimit\b regex)
      │
      ▼
execute on db.read_cursor()  — READ-ONLY SQLite connection
      │
      ▼
_audit → audit_log (local) + Data Store mirror (when Catalyst context)
_add_turn → conversation_turn (persistence; the PDF export unit)
      │
      ▼
JSON: { conversation_id, sql, rows, explanation_en/kn, chart_hint,
        answer_prefix_en/kn, provider, notes }
```

Things about this shape that are load-bearing:

1. **NL→SQL, not RAG.** Every AI answer is grounded in a specific SQL query
   shown to the investigator. The SQL *is* the explanation.
2. **RBAC enforced on the SQL, not the UI.** `_apply_role_policy` +
   `_inject_scope` (sqlglot) rewrite the query before execution. Never add
   an endpoint that trusts the frontend to filter — wire it through
   `Depends(current_session)` and `_session_scope`.
3. **Fallback everywhere is deliberate.** No API key → keyword SQL; no
   Catalyst context → local cache/audit/PDF paths. Fallbacks are labeled in
   the response (`provider`, `/health.services`) — never silent.
4. **Catalyst SDK is thread-local.** `catalyst.app_from_request(request)`
   must be called INSIDE the (sync) endpoint body and used in that same
   thread. Never cache a CatalystApp across requests/threads.

### Catalyst integration (`backend/catalyst.py`)

- **In production (AppSail)** the SDK initializes per-request from `X-ZC-*`
  headers — zero config. Locally, set `CATALYST_PROJECT_ID/KEY/DOMAIN` +
  `CATALYST_AUTH` (self-client OAuth JSON) to talk to the real project.
- **Data Store is the system of record; SQLite is the analytics engine.**
  Tables are created via console import of `datastore_export/*.csv`
  (there is NO create-table API). `POST /admin/datastore/sync`
  `{"direction":"push"}` seeds an empty Data Store from local;
  `{"direction":"pull"}` hydrates local from Data Store.
- Live adapters: ZCQL/Data Store rows, Authentication (`get_current_user`),
  Cache segment, Web Push, SmartBrowz `convert_to_pdf`, Zia Text Analytics,
  QuickML `predict`, Stratus `put_object`.
- **Zia has no GA speech API** — voice endpoints (`/voice/asr`, `/voice/tts`)
  are env-gated (`CATALYST_ZIA_STT_URL`); the UI falls back to on-device
  Web Speech (`kn-IN` / `en-IN`). This is documented honestly — don't
  pretend otherwise.

### Backend layout

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI app, all routes, role policy (sqlglot scope injection), conversations, PDF export, jobs, Data Store sync |
| `backend/db.py` | FIR schema DDL (ER-exact; deviations documented at top), `LLM_SCHEMA_DOC`, and the load-bearing cursor split: `cursor()` is read/write for app tables (sessions, audit, conversations); `read_cursor()` opens a separate read-only SQLite connection and is the ONLY thing LLM-generated SQL runs on — do not merge them |
| `backend/seed.py` | Deterministic synthetic data — 15 districts, 112 units, 450 officers, 1800 FIRs/24 months, ER-exact `CrimeNo`, 6 syndicates |
| `backend/llm.py` | Rotating provider chain QuickML → Gemini/Groq/OpenRouter/OpenAI/Anthropic → bilingual keyword fallback; `is_safe_sql`; server TTS chain (Sarvam → Google → OpenAI) for Kannada audio |
| `backend/analytics.py` | hotspots (district+station), trends, network (scoped), predict, forecast, demographics, repeat offenders, chargesheet rate |
| `backend/jobs.py` | `/jobs/refresh` target: PersonAlias entity resolution (exact + fuzzy) + cache warm — wire to Catalyst Cron |
| `backend/catalyst.py` | All Catalyst service adapters with local fallbacks + honest `service_status()` |

### Frontend layout

Vanilla JS + Tailwind CDN + Leaflet + vis-network + Chart.js + jsPDF — no
build step.

| File | Purpose |
|---|---|
| `frontend/index.html` | Shell: login, sidebar, chat + explainability drawer, hotspot map, trends, network, insights, early warnings + forecast, audit + FIR lookup |
| `frontend/app.js` | Everything: session restore (sessionStorage), conversation replay, chat (SQL fed back into history for follow-ups), Leaflet map, charts, network, server-first PDF export, voice |
| `frontend/config.js` | Runtime `window.KSP_CONFIG.apiBase` — empty for same-origin (AppSail serves the UI); set to the AppSail URL when using split Web Client Hosting |
| `frontend/styles.css` | Ink/khaki police theme, Kannada font |

`appsail/` and `client/` are **derived** — run `scripts/prepare-deploy.ps1`
after backend/frontend changes; never edit them directly (except
`Dockerfile` / `app-config.json` / `client-package.json`, which are
deploy-owned and not overwritten).

## Role policy — quick reference

Defined in `ROLE_POLICY` (`backend/main.py`):

| Role | Scope | PII rows | Audit | Network |
|---|---|---|---|---|
| admin | global | yes | yes | yes |
| dysp | district (login-bound) | yes | — | scoped |
| sho | unit (login-bound) | yes | — | scoped |
| io | own cases (`PolicePersonID`/`IOID`) | yes | — | scoped |
| analyst | global, aggregates only | **no** | — | **blocked** |

Caste / religion / occupation are aggregate-only for analyst; PII name
columns (`AccusedName`, `VictimName`, `ComplainantName`) are refused for
analyst anywhere in the SQL.

## Extending

- **New crime schema field.** Update `SCHEMA` and `LLM_SCHEMA_DOC` in
  `db.py` together — the LLM only knows what's in `LLM_SCHEMA_DOC`. Then
  re-export CSVs for Data Store.
- **New chart type.** Add a `chart_hint` value in `SYSTEM_PROMPT` (`llm.py`)
  and a render branch in `addMessage` (`frontend/app.js`).
- **New scoped endpoint.** `Depends(current_session)` +
  `_session_scope(session)` passed into the analytics function; audit it.
- **New Catalyst service.** Add an adapter in `catalyst.py` with a local
  fallback and a line in `service_status()` — degradation must be visible.

## Domain constraints to keep in mind

- **Bilingual (English + Kannada) is first-class.** Voice uses `kn-IN` /
  `en-IN`; the LLM *and the keyword fallback* return paired
  `explanation_en/kn` and `answer_prefix_en/kn`.
- **Explainability & auditability.** Every AI answer surfaces the SQL. Every
  route writes to `audit_log`. Don't add code paths that answer without
  one or both.
- **Sensitive data.** `crime.db`, `.env`, `datastore_export/` stay out of
  version control (`.gitignore`). Caste/religion/occupation only ever
  appear aggregated.
- **Anchor date.** Seed + analytics use `date(2026, 7, 1)` as "today"
  (matches the 24-month seed window). If the demo moves months, re-seed or
  update both together.
