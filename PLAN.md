# PLAN.md — Rebuild against real FIR schema on Zoho Catalyst

This plan supersedes the working demo in the repo. It pivots the project on
two constraints introduced late:

1. **The database schema must match the real Karnataka FIR ER diagram**
   (`Police_FIR_ER_Diagram.pdf`). `CaseMaster` is the anchor; ~25 normalized
   tables around it including `Victim`, `Accused`, `ComplainantDetails`,
   `ArrestSurrender`, `ChargesheetDetails`, `ActSectionAssociation`, plus the
   full geography / HR / lookup hierarchy (`State` → `District` → `Unit`;
   `Rank` / `Designation` / `Employee`; `Act` / `Section` / `CrimeHead` /
   `CrimeSubHead`).
2. **Deployment is on Zoho Catalyst and every capability must use the
   mandated Catalyst service.** Third-party equivalents "may affect the
   validity of your submission." Deployment via Catalyst is mandatory.

## TL;DR

- Keep the product shape (9 judged features + explainability + audit + RBAC).
- Rewrite the DB layer against the FIR schema — no more ad-hoc `crimes` /
  `persons` / `suspects`.
- Move the backend from SQLite + FastAPI-anywhere → **Catalyst AppSail**
  (managed Python runtime) with **Catalyst Data Store** underneath.
- Replace browser-only voice / PDF / auth with Catalyst equivalents.
- Introduce **Catalyst QuickML** for the LLM / RAG side and **Zia AutoML**
  for the predictive layer. Keep Claude as a fallback only if QuickML can't
  meet quality.

## Catalyst service map

| Feature in current demo | Move to | Why / notes |
|---|---|---|
| FastAPI app (routes, session, RBAC) | **Catalyst AppSail (managed Python runtime)** | Cheapest port — the FastAPI app deploys as a single managed runtime. Split into Functions later only if needed. |
| Isolated LLM proxy, PDF trigger, scheduled recomputes | **Catalyst Serverless (Functions)** | Small, event-driven tasks are a better fit for Functions than the whole app. |
| Vanilla-JS `frontend/` | **Catalyst Web Client Hosting** | Static assets, CDN-served, custom domain via Domain Mappings. |
| SQLite `crime.db` (relational) | **Catalyst Data Store** | Real SQL, full-text search built in. Full schema port. |
| — (would be needed for BriefFacts search) | Catalyst Data Store full-text index | Search `BriefFacts` / `AccusedName` / `ComplainantName` from chat. |
| In-memory `SESSIONS` dict + bearer tokens | **Catalyst Authentication** | Real login / JWT; user identity for the audit trail and RBAC. |
| Anthropic Claude NL→SQL | **Catalyst QuickML (LLM Serving + RAG)** | Primary. Store the schema doc + a canonical-query examples set as a QuickML knowledge base for RAG-grounded NL→SQL. |
| Anthropic Claude (fallback path) | **Catalyst Connections** | If QuickML falls short, wrap Anthropic API in a Connection so the credential is managed by Catalyst — not the app. |
| Browser Web Speech (STT/TTS Kannada) | **Catalyst Zia Services (voice + translation)** | Server-side STT (`kn-IN`, `en-IN`), TTS, and translation. Audio stays inside our audit boundary. Keep browser TTS as a graceful degradation. |
| Web Speech English↔Kannada translation | **Catalyst Zia Services (translation)** | For NL turns that come in in Kannada and need to be translated for QuickML. |
| jsPDF export in browser | **Catalyst SmartBrowz** | Server-side PDF of conversation history + evidence bundle. Keeps a copy in Stratus for the audit trail. |
| Uploaded FIR attachments (photos, PDFs) — new | **Catalyst Stratus** | Blob storage for evidence. |
| Predictive analytics (30/30-day heuristic) | **Catalyst Zia AutoML (tabular)** | Train per-district × per-category volume forecast. The heuristic stays as the offline fallback. |
| Cross-app events (new-case → recompute network) | **Catalyst Signals + Event Functions** | Trigger network / hotspot recompute when a new case lands. |
| Nightly hotspot / trend / forecast refresh | **Catalyst Cron** | Recompute once per night; serve cached results on request. |
| Multi-step orchestration (NL→SQL→validate→execute→translate) | **Catalyst Circuits** | Formalize the pipeline as a Circuit for retries, branches, timeouts. |
| Alerting when a warning fires | **Catalyst Push Notifications** + **Catalyst Mail** | Push to the on-duty officer's device; email the SHO. |
| Ingress / auth / rate limit | **Catalyst API Gateway** | In front of AppSail + Functions. |
| — | Catalyst Cache | Cache hot dashboard queries (hotspots, trends) with a 1-hour TTL. |
| Delivery pipeline | Catalyst Pipelines | CI/CD for AppSail + Web Client Hosting deploys. |

## Target architecture

```
             ┌───────────────────────────────────────────────────┐
             │ Catalyst Web Client Hosting                       │
             │   frontend/  (vanilla JS + Tailwind CDN)          │
             └────────────────────┬──────────────────────────────┘
                                  │  HTTPS
                                  ▼
             ┌───────────────────────────────────────────────────┐
             │ Catalyst API Gateway                              │
             │   route + throttle + Auth check                   │
             └────────────────────┬──────────────────────────────┘
                                  │
       ┌──────────────────────────┼─────────────────────────────┐
       ▼                          ▼                             ▼
 Catalyst Authentication   Catalyst AppSail                Catalyst Functions
 (login, JWT, user/role)   (FastAPI app;                   (LLM proxy, PDF trigger,
                            RBAC policy;                    nightly cron targets)
                            /chat /hotspots ...)
                                  │
       ┌──────────────────────────┼─────────────────────────────┐
       ▼                          ▼                             ▼
 Catalyst Data Store    Catalyst QuickML                   Catalyst Zia Services
 (FIR schema:            (LLM serving +                     (STT / TTS / translate
  CaseMaster,             RAG on schema doc                  — English + Kannada)
  Victim, Accused,        + canonical queries)
  ArrestSurrender,               │
  Court, Unit, ...)              ▼
       │                   Catalyst Connections
       │                    (Anthropic Claude —
       │                     fallback path only)
       ▼
 Catalyst Cache
 (hot dashboards)

 Catalyst Signals ─► Event Functions ─► recompute network / warnings
 Catalyst Cron    ─► nightly Zia AutoML re-forecast + Cache warm
 Catalyst Push    ─► on-duty officer on spike
 Catalyst Stratus ─► evidence uploads + generated PDFs
 Catalyst SmartBrowz ─► render conversation-history PDFs
 Catalyst Circuits ─► NL→SQL→validate→execute→translate pipeline
 Catalyst Pipelines ─► CI/CD
```

## Schema migration

The current schema is not the real one; it's replaced wholesale. Table-by-table:

| Current (drop) | Replaced by (from FIR ER) | Notes |
|---|---|---|
| `districts` | `District` (+ `State`) | `District` FK → `State`. Keep lat/lng in a separate `DistrictGeo` table (not in the ER, needed for hotspots). |
| `police_stations` | `Unit` (+ `UnitType`) | `Unit.ParentUnit` is self-referential for hierarchy (circle → station). |
| `crime_types` | Split into `CaseCategory` (FIR/UDR/Zero FIR/PAR), `GravityOffence` (Heinous/Non-Heinous), `CrimeHead`/`CrimeSubHead` (Crimes Against Body → Murder) | Chart categories now derive from `CrimeHead.CrimeGroupName`. |
| `crimes` | `CaseMaster` | Fields: `CrimeNo` (structured 18-char code), `CaseNo`, `CrimeRegisteredDate`, `IncidentFromDate`/`ToDate`, `InfoReceivedPSDate`, `latitude`/`longitude`, `BriefFacts`, `CaseStatusID`, `CourtID`, `GravityOffenceID`, `CrimeMajorHeadID`, `CrimeMinorHeadID`, `PolicePersonID` (registering IO), `PoliceStationID`. |
| `persons` | Split by role: `ComplainantDetails`, `Victim`, `Accused`, `Employee` | No single "person" table; each role has its own schema. Cross-case entity resolution is a separate concern (see below). |
| `suspects` | `Accused` + `ArrestSurrender` + `inv_arrestsurrenderaccused` (junction) | An `Accused` is per-case (`CaseMasterID` FK). `ArrestSurrender` records arrests with IO + court + date. Junction table connects one arrest event to multiple accused. |
| — (new) | `ActSectionAssociation` + `Act` + `Section` + `CrimeHeadActSection` | Every case is charged under one or more Act-Section pairs (e.g. IPC 302). Powers "which cases invoked NDPS 20b in Mysuru." |
| — (new) | `ChargesheetDetails` | `CSID`, `csdate`, `cstype` (A/B/C = chargesheet / false case / undetected). Powers "chargesheeting rate per IO" queries. |
| — (new) | `CasteMaster`, `ReligionMaster`, `OccupationMaster` | Complainant demographics. **Sensitive** — restrict to aggregate use per RBAC. |
| — (new) | `Employee`, `Rank`, `Designation` | Ties every case + arrest back to a specific officer. Enables IO-level performance queries. |
| `audit_log` | `audit_log` (unchanged shape) | Move to Data Store. |

### Criminal network — updated definition

- **Immediate co-accused:** two rows in `Accused` sharing the same
  `CaseMasterID` → an edge. Direct read from the schema.
- **Cross-case network:** the schema has no canonical person entity. Same
  accused across cases has to be resolved on `(AccusedName, AgeYear,
  GenderID)` — fuzzy match. Do this once nightly via a Function → materialize
  a `PersonAlias` table in Data Store; the network endpoint reads from that.
- **Charged-together clusters:** two accused co-appear on the same
  `ArrestSurrender` (via the junction) — stronger signal than co-case, since
  it's a real arrest event.

### Legal / act-section queries (new capability)

The FIR schema gives us Acts and Sections. New question shapes the demo
should now handle:

- "All Heinous cases under IPC 302 in Bengaluru Urban still under
  investigation."
- "Chargesheeting rate for IO XYZ in the last 12 months."
- "All cases invoked under NDPS Act 20b closed as B-report."

The QuickML system prompt / RAG examples must include these join patterns.

## Feature-by-feature rebuild

For each of the 9 judged features — what stays, what moves, what changes.

### 1. Natural language chatbot (English + Kannada)

- **Stays:** the NL→SQL pattern. `SYSTEM_PROMPT` and `LLM_SCHEMA_DOC` are
  rewritten against the new schema.
- **Moves:** LLM call goes to **Catalyst QuickML**. Prompt + few-shot examples
  live as a QuickML knowledge base for RAG grounding on the schema and
  canonical join patterns.
- **Fallback:** the keyword rules in `llm._fallback` are rewritten for the
  new tables (`CaseMaster` / `District` / `CrimeSubHead` etc.). Kept for
  offline demo continuity.
- **Kannada:** Zia Services translation call inserted before the LLM step
  when the request language is `kn`; response translated back after
  execution.

### 2. Voice-enabled interaction

- **Move to** Catalyst Zia Services STT + TTS with `kn-IN` + `en-IN`.
- **Keep** browser `speechSynthesis` as a graceful fallback if Zia is
  degraded — flagged in the UI.
- **New flow:** frontend records audio → uploads to a Function → Function
  calls Zia STT → text goes through the chat pipeline → Zia TTS on the
  response → audio returned. All audio is logged (URL + duration only) in
  `audit_log`.

### 3. Context-aware conversations

- Same as today: last 6 turns passed to the LLM. Now the LLM is QuickML;
  its RAG grounding also includes the *previous SQL* so follow-ups like
  "filter to Mysuru" can reuse it.
- **New:** persist conversation threads in Data Store (`conversation`,
  `conversation_turn`) so a session survives reload and the whole thread is
  the PDF export unit.

### 4. PDF export of conversation history

- **Move to** Catalyst SmartBrowz. Frontend calls
  `POST /conversations/{id}/pdf`; a Function renders a print-view HTML,
  hands it to SmartBrowz, stores the PDF in **Catalyst Stratus**, and
  returns a signed URL.
- **Bonus:** the exported PDF can embed the SQL and cited FIR numbers so a
  supervisor can independently verify.

### 5. Criminal network visualization

- **Data change:** graph built from `Accused` self-join on `CaseMasterID`
  (immediate co-accused) and — after nightly entity resolution — cross-case
  edges from `PersonAlias`.
- **API contract stays** (`/network` returns `{nodes, edges}`). Frontend
  vis-network code is unchanged.
- **Nightly recompute** via Catalyst Cron → Function → Data Store table
  `network_snapshot`. Runtime API just reads it. Cache with Catalyst Cache.

### 6. Crime trend & hotspot detection

- **Trends:** GROUP BY month + `CrimeHead.CrimeGroupName`. Series categories
  become real ones ("Crimes Against Body", "Crimes Against Property", ...).
- **Hotspots:** GROUP BY `District.DistrictID`. Coordinates come from a
  small `DistrictGeo` table (lat/lng of district HQ) since the ER doesn't
  give them.
- **Add** hotspot at the `Unit` level too — real deployment cares about
  station-level heat, not just district.
- Cached results in **Catalyst Cache** (1 h TTL); backing Data Store queries
  behind that.

### 7. Predictive analytics & early warnings

- **Baseline stays:** the 30-day-vs-prior-30-day heuristic runs in the
  Function that populates `predict` — as an offline fallback and a sanity
  check.
- **Add** a **Catalyst Zia AutoML** model trained on the
  `(district, crime_head, month) → volume` time series. Nightly retrain via
  Cron → Function. The `/predict` endpoint blends both: heuristic finds
  today's spikes, model forecasts next week and flags predicted spikes.
- **Alerting:** any warning above severity `spike` fires a **Catalyst Push
  Notification** to the SHO's device and a **Catalyst Mail** to the district
  DySP.

### 8. Explainable AI with audit trails

- **Stays:** every AI answer returns the executed SQL + LLM explanation.
- **Adds:**
  - Cite specific `CrimeNo` values in the answer (not just row counts).
  - Show which `Act` + `Section` were invoked when the answer touches
    charges.
  - `audit_log` in Data Store. Every request writes user (from Catalyst
    Authentication JWT), role, question, SQL, row count, timestamp.
- **New endpoint:** `/audit/{fir}` — reverse-lookup: "which queries have
  touched this FIR?" (for supervisors auditing their team).

### 9. Role-based secure access

Roles rebuilt against the real HR schema:

| Role | Scope | Enforcement |
|---|---|---|
| `admin` | Everything, plus audit | Catalyst Auth role claim → policy layer. |
| `dysp` (district superintendent) | All cases in one district, sees PII | Auto-injected `District` filter. |
| `sho` (station head) | All cases in one `Unit`, sees PII | Auto-injected `Unit` filter. |
| `io` (investigating officer) | Only cases where `PolicePersonID` = self, or where they appear in `ArrestSurrender.IOID` | Auto-injected officer-level filter. |
| `analyst` | Aggregates only, no `Accused` / `Victim` / `ComplainantDetails` PII | Query-layer refusal if PII columns/tables are touched. |

**Critical demographics constraint** — caste, religion, occupation from
`ComplainantDetails`: allowed in aggregate (COUNT ... GROUP BY) but never
projected as raw rows. Enforced by inspecting the LLM's SQL before execution
(reject `SELECT ... caste_master_name ... LIMIT n` when `n > 1`).

## Workstreams / phases

Order matters. Each phase closes on a working demo — no half-migrations.

### Phase 0 · Catalyst environment (day 1)

- Create Catalyst project.
- Enable: Data Store, AppSail, Web Client Hosting, Authentication, Zia
  Services, QuickML, SmartBrowz, Stratus, Cache, Cron, Push Notifications,
  API Gateway, Circuits, Pipelines.
- Configure Catalyst Connections for Anthropic (fallback path).
- Deploy an empty FastAPI "hello world" to AppSail; deploy current
  `frontend/` to Web Client Hosting; confirm end-to-end 200 OK.

### Phase 1 · Schema + seed against real FIR (day 1–2)

- Model every FIR table in Data Store.
- Rewrite `backend/db.py` to use the Catalyst Data Store client (drops
  sqlite3 dependency).
- Rewrite `backend/seed.py` to emit real-shape rows: `CaseMaster` with
  proper `CrimeNo` format, `Act`/`Section` combinations for each case,
  demographics for complainants, arrest events for a fraction of cases.
- Keep the ~1800 cases / 15 districts scale for a fast demo; the shape is
  what changed.
- Verify: read a `CaseMaster` row and follow every FK.

### Phase 2 · Auth + RBAC on real roles (day 2)

- Integrate Catalyst Authentication in the frontend (drop the demo login
  overlay in favour of Catalyst-hosted login, or use the Auth SDK on our
  page).
- Reshape `ROLE_POLICY` to the five new roles.
- Rewrite `_apply_role_policy` for the FIR schema:
  - `sho` filter → `CaseMaster.PoliceStationID = :unit_id`.
  - `io` filter → `CaseMaster.PolicePersonID = :employee_id OR EXISTS(SELECT 1 FROM ArrestSurrender a WHERE a.CaseMasterID = CaseMaster.CaseMasterID AND a.IOID = :employee_id)`.
  - `analyst` refusal if `Accused` / `Victim` / `ComplainantDetails` are
    touched (unless aggregate).
- Verify: same three-way test we ran on the old schema (allow / restrict /
  refuse).

### Phase 3 · NL→SQL on QuickML (day 3)

- Build the RAG knowledge base: (a) `LLM_SCHEMA_DOC` for the FIR schema,
  (b) 15–20 canonical NL↔SQL examples covering: hotspots, act/section
  queries, chargesheet-rate queries, network queries, gravity/status
  filters, Kannada variants.
- Wire the QuickML client into `llm.py`; keep the Anthropic path behind a
  feature flag as fallback.
- Rewrite `_fallback` for the new tables.
- Verify: end-to-end EN and KN questions return correct rows against seed
  data.

### Phase 4 · Voice on Zia (day 3–4)

- Frontend: record audio → POST to `/voice/asr` → text.
- Backend: Function calls Zia STT (`en-IN` / `kn-IN`).
- Response: text → Zia TTS → audio blob → play.
- Fallback path (Web Speech) stays for offline dev.
- Verify: a Kannada spoken question returns spoken Kannada answer.

### Phase 5 · Analytics + prediction on Data Store + Zia AutoML (day 4)

- Rewrite `analytics.py` against the FIR schema (hotspots, trends, network).
- Cache hot endpoints in Catalyst Cache.
- Set up Cron nightly to (a) recompute `PersonAlias` entity resolution,
  (b) refresh `network_snapshot`, (c) retrain Zia AutoML volume forecast.
- Wire `/predict` to blend heuristic + AutoML.
- Verify: nightly cron produces artefacts; endpoints read them.

### Phase 6 · PDF, alerts, evidence (day 5)

- Move PDF export to SmartBrowz + Stratus.
- Wire spike-detected Signals → Push Notifications + Mail.
- Add evidence-upload endpoint (Stratus) — bonus feature, tie to `CaseMaster`.
- Verify: end-to-end export produces a stored PDF URL that a fresh browser
  session can open.

### Phase 7 · Circuits + Gateway + Pipelines (day 5)

- Formalize the NL→SQL→validate→execute→translate flow as a Circuit.
- Move ingress behind Catalyst API Gateway with per-role rate limits.
- Wire CI to Catalyst Pipelines for automatic redeploys on push.

### Phase 8 · Demo polish (day 6)

- Seed a scripted demo path that hits every judged feature in 4 minutes:
  EN chat → KN voice → hotspots → trends → network → predict → PDF export.
- Record a fallback video in case live Wi-Fi bites us.

## What survives from the current repo

Not everything is thrown away. Keep:

- `frontend/index.html`, `frontend/app.js`, `frontend/styles.css` — the UI
  shell survives. Contract with backend is minimally different.
- `backend/analytics.py` shape — the aggregation *patterns* transfer; only
  table/column names change.
- `backend/llm.py::is_safe_sql` + the `_apply_role_policy` skeleton — same
  guard-rail approach, new column names.
- The role-based-in-the-query-layer principle. This was the right design.

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| QuickML's LLM isn't strong enough for NL→SQL over 25 tables | Keep Claude via Catalyst Connections as feature-flagged fallback; document why we needed it in the submission. |
| Zia STT accuracy for Kannada in noisy demo room | Fall back to Web Speech on client; show the transcript on screen before executing so investigator can correct. |
| Real-schema seed is too complex to hand-write | Use the current seed's *distributions* (crime volume per district, syndicate clusters) and re-shape into the FIR tables via a translator script. |
| Officer-level RBAC is much harder than district-level | Ship district-level (`sho`, `dysp`) first; add `io` if time. Don't block the demo on it. |
| Entity resolution across cases is fuzzy — false-positive edges in the network | Show similarity score per edge; only render edges above threshold; label as "probable" so investigators know. |
| Catalyst service availability gaps in trial account | Check every service in the plan is enabled on day 1; escalate anything gated. |
| Judges want to poke at raw SQL | Keep the explainability drawer showing every SQL; add a "run in read-only console" button that opens a Data Store SQL query editor pre-filled. |

## Sensitive-data handling (constitutional / policy)

- **Caste, religion, occupation** (`CasteMaster`, `ReligionMaster`,
  `OccupationMaster`) are constitutionally sensitive. Policy:
  - Never returned in row-level projections. Only aggregate (COUNT / GROUP
    BY) allowed.
  - `analyst` role can query these aggregates. Other roles get a redacted
    view.
  - The LLM system prompt must warn against building analytics that could
    stereotype or target a caste / religion group. Log any such query as
    high-severity in audit for supervisor review.

## Immediate next steps

1. Enable the Catalyst services listed under Phase 0. **Blocker for
   everything else.**
2. Model the FIR schema in Data Store — copy from `Police_FIR_ER_Diagram.pdf`
   verbatim, tables + FKs + indexes.
3. Rewrite `backend/db.py` to use the Data Store client + the new schema.
4. Rewrite `backend/seed.py` to emit real-shape rows at the same scale.
5. Rewrite `backend/llm.py::LLM_SCHEMA_DOC` and `_fallback` against the new
   tables.
6. Rewrite `backend/analytics.py` — `hotspots`, `trends`, `network`,
   `predict` — using `CaseMaster` / `Accused` / `District` / etc.
7. Rewire `main.py::_apply_role_policy` for the five new roles.
8. Rest of the pieces (Zia voice, SmartBrowz PDF, QuickML swap, Push
   notifications) come after the schema pivot lands.

## Cross-reference

- ER diagram: `Police_FIR_ER_Diagram.pdf` (project root).
- Catalyst service list: attached table in the previous turn's message.
- Current demo (superseded by this plan): `README.md`, `CLAUDE.md`.
