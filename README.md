# KSP Crime AI — Conversational Intelligence for the KSP Crime Database

An intelligent conversational AI platform for the Karnataka State Police /
State Crime Records Bureau, built for **Datathon Challenge 01**. Runs against
the **real Karnataka FIR schema** (30 normalized tables per
`Police_FIR_ER_Diagram.pdf`, anchored on `CaseMaster`) and deploys on
**Zoho Catalyst** (AppSail + Data Store + the mandated service map).

## The nine judged features

| Judged feature | Where it lives |
|---|---|
| Natural language chatbot (English + Kannada) | `backend/llm.py` — NL→SQL chain: **Catalyst QuickML → Claude → keyword fallback**; fully bilingual in every mode |
| Voice-enabled interaction | On-device Web Speech (`kn-IN` / `en-IN`) + server `/voice/asr`·`/voice/tts` endpoints (env-gated; Zia has no GA speech API — documented honestly) |
| Context-aware conversations | Last 6 turns + the executed SQL fed back to the LLM; conversations persist in `conversation`/`conversation_turn` tables and survive reloads |
| PDF export of conversation history | `POST /export/pdf` — **Catalyst SmartBrowz** server-side render (proper Kannada glyphs), archived to **Stratus**; jsPDF client fallback offline |
| Criminal network visualization | `analytics.network` — co-accused edges + cross-case identity via `PersonAlias` (nightly entity resolution in `jobs.py`) + vis-network |
| Crime trend & hotspot detection | `/trends`, `/hotspots?level=district\|station` — Leaflet map with heat circles + ranked cards |
| Predictive analytics & early warnings | `/predict` — 30-day delta warnings **+ 30-day forward forecast** (weighted-window statistical baseline; Zia AutoML upgrade path) with push alerts |
| Explainable AI with audit trails | Every answer returns the exact SQL + policy notes; every route writes `audit_log` (mirrored to Data Store); `/audit/fir/{crime_no}` reverse lookup |
| Role-based secure access | `admin` / `dysp` / `sho` / `io` / `analyst` enforced **on the SQL itself** via sqlglot rewrite — CTE-safe, child-table-safe (see below) |

## Architecture

```
frontend (vanilla JS + Tailwind + Leaflet + vis-network + Chart.js, CDN)
        │  POST /chat { query, history, conversation_id }
        ▼
FastAPI (main.py)                          ← Catalyst AppSail
        │  ① NL→SQL: QuickML → Claude → keyword fallback
        │  ② safety validator (single SELECT, keyword blocklist)
        │  ③ role-policy rewrite (sqlglot: scope every CaseMaster and
        │     case-child reference; PII/demographic DLP; LIMIT)
        │  ④ execute on a READ-ONLY connection
        │  ⑤ audit_log write (+ Data Store mirror)
        ▼
SQLite (analytics engine)  ⇄  Catalyst Data Store (system of record)
                               via POST /admin/datastore/sync push/pull
```

- **Why NL→SQL over RAG?** Answers are provably grounded in the database and
  the exact query is shown in the UI. That satisfies "Explainable AI" without
  a vector-store detour.
- **Why SQLite next to Data Store?** Data Store holds the canonical data
  (created/loaded via console import; see `DEPLOY.md`). The AppSail instance
  hydrates a local SQLite copy for SQLite-dialect analytics (`strftime`
  trends, CTE self-joins) and dual-writes the audit trail up. `/health`
  reports the sync state honestly.
- **Why vanilla JS?** No build step; the AppSail container serves the UI.

## RBAC — enforced in the query layer

| Role | Scope | PII rows | Notes |
|---|---|---|---|
| admin | global | yes | audit log + Data Store sync + cron |
| dysp | one district | yes | every `CaseMaster` *and* case-child reference in the SQL is constrained |
| sho | one police station | yes | same mechanism, unit-level |
| io | own cases only | yes | `PolicePersonID = self OR ArrestSurrender.IOID = self` |
| analyst | global aggregates | **no** | PII name columns refused outright; caste/religion/occupation aggregate-only |

The scope predicate is injected with **sqlglot** into every `SELECT` that
reads `CaseMaster` — including inside CTEs and subqueries — and any SELECT
that reads a case-child table (`Accused`, `Victim`, …) without joining
`CaseMaster` gets an `IN (scoped case set)` predicate, so a co-accused
self-join can't leak out-of-district data. Unparseable SQL is refused for
scoped roles. LLM SQL executes on a read-only connection.

**Sensitive demographics** (caste / religion / occupation) are aggregate-only
by policy and never row-projected for the analyst role.

## Setup (Windows PowerShell)

```powershell
.\run.ps1          # venv + deps + seed + http://localhost:8000
```

or manually:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env    # optional: add ANTHROPIC_API_KEY
uvicorn main:app --reload --port 8000
```

First launch seeds `backend/crime.db` deterministically: 15 districts,
112 units, 450 officers, 1800 FIRs over 24 months with ER-exact `CrimeNo`
formats (`1 0443 0006 2026 00001`), co-offender syndicates, arrests,
chargesheets, and complainant demographics.

### Without an API key

Leave `ANTHROPIC_API_KEY` blank — `/chat` falls back to a bilingual
keyword-based query builder. The header badge shows which provider answered
(**QuickML / Claude / fallback**); the explainability drawer shows it per
answer.

## Try it

Sign in as any role and try:

- *"Which districts had the most cyber crime?"* → bar chart
- *"Show me a monthly trend of crimes against women"* → line chart
- *"Who co-offends with whom?"* → network view (scoped to your role!)
- *"Recent murders in Bengaluru Urban"* → table with FIR numbers
- *"Chargesheet rate"* → status × final-report breakdown
- *"ಜಿಲ್ಲಾವಾರು ಸೈಬರ್ ಅಪರಾಧಗಳು"* (Kannada) → same, answered in Kannada
- Follow up with *"only Mysuru"* — the previous SQL is refined

Switch roles to see enforcement:
- **analyst** — Network tab hidden; any query projecting `AccusedName` → 403
- **sho** (pick a station) — every query auto-constrained to that station;
  even a state-wide network question comes back station-scoped (see the
  policy note under the answer)
- **admin** — Audit tab shows every query; try the FIR reverse lookup

## Deploy to Catalyst

See **[DEPLOY.md](DEPLOY.md)**. Short version: `scripts/prepare-deploy.ps1`
→ `catalyst deploy` (AppSail serves API + UI at one URL) → import
`datastore_export/*.csv` in the console (creates the 30 Data Store tables) or
`POST /admin/datastore/sync {"direction":"push"}` → add a Catalyst Cron
hitting `/jobs/refresh` nightly.

## Layout

```
backend/
  main.py         FastAPI app, routes, sqlglot role policy, conversations
  db.py           FIR schema (ER-exact) + read-only cursor + LLM schema doc
  seed.py         deterministic synthetic Karnataka data
  llm.py          QuickML → Claude → bilingual fallback NL→SQL
  analytics.py    hotspots (district/station) / trends / network / predict / forecast
  jobs.py         nightly entity resolution (PersonAlias) + cache warm
  catalyst.py     zcatalyst-sdk adapters: Data Store sync, Auth, Cache,
                  Push, SmartBrowz, Zia, QuickML, Stratus — honest fallbacks
frontend/         vanilla JS UI (chat, map, network, insights, audit)
appsail/          Catalyst AppSail bundle (Dockerfile; derived by prepare-deploy)
client/           Catalyst Web Client Hosting bundle (derived)
scripts/          prepare-deploy.ps1, create-datastore-tables.py
datastore_export/ per-table CSVs + schema cheat sheet (generated)
```

## Notes for the judges

- **Audit is real.** Every `/chat`, `/hotspots`, etc. writes user, role,
  question, exact SQL, and result summary — locally and mirrored to Catalyst
  Data Store. `/audit/fir/{crime_no}` answers "who has been looking at this
  FIR?"
- **Role enforcement is server-side, on the SQL.** The frontend only picks a
  role; `_apply_role_policy` rewrites the query before execution, and the
  rewritten SQL is displayed — you can read exactly what the policy did.
- **The schema is the real one.** Tables, columns, keys, and the structured
  `CrimeNo` format match `Police_FIR_ER_Diagram.pdf`; deviations are
  documented at the top of `db.py`.
- **Degradation is explicit.** `/health` reports which Catalyst services are
  live on this deployment; the UI badges the active LLM provider; fallbacks
  are labeled, never silent.
