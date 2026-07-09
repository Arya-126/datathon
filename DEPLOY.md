# DEPLOY.md — Ship KSP Crime AI to Zoho Catalyst

Everything is prepped. What's left is the interactive Zoho work you (a
human with the account) have to do. Follow the sections in order.

**Data centre note.** Your `.catalystrc` uses the `zoho.in` domain
(datathon-60076484984.development), so everything below uses **India DC**
URLs — `console.catalyst.zoho.in`, `accounts.zoho.in`,
`api-console.zoho.in`. Swap `.in` → `.com`/`.eu` if your account is on a
different DC.

## What's already been prepared

| File / dir | Purpose |
|---|---|
| `catalyst.json` | Project descriptor — lists the AppSail app + client |
| `appsail/ksp-ai-backend/` | Catalyst AppSail bundle (Dockerfile + `webroot/` UI) |
| `appsail/ksp-ai-backend/app-config.json` | Python 3.11, port 9000, `/health` |
| `client/` | Catalyst Web Client Hosting bundle (optional separate UI) |
| `scripts/prepare-deploy.ps1` | Syncs `backend/` → `appsail/…` and `frontend/` → `client/` + `webroot/` |
| `scripts/create-datastore-tables.py` | Exports the 30-table FIR schema to `datastore_export/*.csv` for console import |
| `datastore_export/` | Generated CSVs + `SCHEMA.md` + `import-all.ps1` (gitignored) |
| `run.ps1` | Local dev launcher |

## Prerequisites

- Node.js 18+ (you have v22)
- Catalyst CLI: `npm install -g zcatalyst-cli`
- A Zoho account with Catalyst enabled on the India DC
- A Catalyst project **created in the console** — grab the Project ID + Key
  from Project Settings

## 1. Deploy in five minutes (the fast path)

The FastAPI container serves **both** the API and the UI (it mounts the
bundled `webroot/`). One AppSail URL = a complete working demo.

```powershell
# from D:\Datathon 2026 Karnataka Police\

# 1. Sync latest code into the Catalyst layout
powershell -ExecutionPolicy Bypass -File .\scripts\prepare-deploy.ps1

# 2. Log in
catalyst login          # opens a browser tab; approve the CLI
catalyst whoami         # sanity check

# 3. Deploy (project is already linked via .catalystrc)
catalyst deploy --only appsail
```

Console → AppSail → `ksp-ai-backend` → **Endpoint** gives you your live URL.
Open it: it will boot with **empty Catalyst env vars**, which means the
UI works, chat runs on the offline keyword fallback, and `/health` reports
every Catalyst service as `false`. That's fine for a first deploy — the
next sections turn each service on.

If your Catalyst project doesn't yet have an AppSail named
`ksp-ai-backend`, create it once in the console (AppSail → Create,
stack = Docker, port = 9000, name = `ksp-ai-backend`), then rerun step 3.

## 2. Fill in the .env — how to fetch every credential

Everything below drops into either `backend/.env` (for local dev) or
Catalyst Console → AppSail → **Environment Variables** (for production).
Same names in both places.

All of these are **optional** — an empty value degrades to the honest local
fallback. Add them one at a time.

### 2.1 · `GEMINI_API_KEY` — Google Gemini Flash fallback for NL→SQL

1. https://aistudio.google.com/app/apikey → **Create API Key** → copy.
2. Paste into `GEMINI_API_KEY`. Leave `GEMINI_MODEL=gemini-2.0-flash`
   (or bump to a newer Flash tier — env-configurable).
3. Production best practice: create a **Catalyst Connection** for
   Google (Console → Connections → *Create* → Custom Service → API Key)
   so the credential is Catalyst-managed rather than baked into env;
   expose it to the AppSail via the same env var name.
4. On the deployed AppSail, add `GEMINI_API_KEY` under Serverless →
   AppSail → `ksp-ai-backend` → **Configuration → Environment Variables**
   and restart. `/health.services.gemini` flips to `true` when set.

### 2.2 · Project credentials — `CATALYST_PROJECT_ID` / `_KEY` / `_DOMAIN` / `_ENVIRONMENT`

**Only needed for local dev** (talking to the real Catalyst project from
your workstation). On the deployed AppSail every request already carries
these as `X-ZC-*` headers, and `catalyst.py::app_from_request` picks them
up automatically.

1. Console → project **DATATHON** → *Settings* (top-right cog) → **Project
   Settings** → tabs *Project Key* and *Project Details*:
   - `CATALYST_PROJECT_ID` — the numeric Project ID (yours is
     `55025000000016001` — already visible in `.catalystrc`).
   - `CATALYST_PROJECT_KEY` — the "Project Key" string on that page.
   - `CATALYST_PROJECT_DOMAIN` — your project's serverless URL,
     without the scheme, in the form
     `<project-slug>-<project-id>.development.catalystserverless.in`.
     Same page shows the API base URL — strip `https://` and any path.
2. `CATALYST_ENVIRONMENT=Development` (or `Production` after promotion).

### 2.3 · `CATALYST_AUTH` — self-client OAuth JSON (local dev only)

The SDK's `initialize_app()` reads a JSON string from this env var so it
can mint access tokens. Not needed on AppSail (thread-locals carry the
admin token per-request).

1. https://api-console.zoho.in → *Add Client* → **Self Client** → *Create*.
   Copy `Client ID` + `Client Secret`.
2. Same page → **Generate Code** tab. Paste **scopes** (comma-separated).
   The set below is verified against the Catalyst OAuth catalog (India DC,
   2026) and covers every service the app uses — Data Store rows + tables,
   ZCQL, Cache, Web Push, Stratus buckets, SmartBrowz (PDF + screenshot
   are one scope: `pdfshot.execute`), Zia Services (`mlkit.READ` covers
   Text Analytics and AutoML), and QuickML deployment predict:

   ```
   ZohoCatalyst.tables.READ,ZohoCatalyst.tables.columns.READ,
   ZohoCatalyst.tables.rows.READ,ZohoCatalyst.tables.rows.CREATE,
   ZohoCatalyst.tables.rows.UPDATE,ZohoCatalyst.tables.rows.DELETE,
   ZohoCatalyst.zcql.CREATE,
   ZohoCatalyst.cache.READ,ZohoCatalyst.cache.CREATE,ZohoCatalyst.cache.DELETE,
   ZohoCatalyst.notifications.web,
   ZohoCatalyst.buckets.READ,ZohoCatalyst.buckets.objects.READ,
   ZohoCatalyst.buckets.objects.CREATE,
   ZohoCatalyst.pdfshot.execute,
   ZohoCatalyst.mlkit.READ,
   QuickML.deployment.READ
   ```

   Notes:
   - `QuickML.deployment.READ` has **no `ZohoCatalyst.` prefix**.
   - Cache has only `READ` / `CREATE` / `DELETE` — no `UPDATE` scope
     (the SDK's `update()` uses `CREATE` under the hood).
   - `pdfshot.execute` alone covers both PDF and screenshot APIs.
   - `mlkit.READ` alone covers every Zia service (Text Analytics + AutoML).

   Time Duration = 10 minutes, Scope Description = anything. **Create**.
   Copy the 10-minute grant code — **it expires fast**.
3. Exchange the grant code for a refresh token (do this within 10 min):

   ```powershell
   $code = "<grant code from step 2>"
   $cid  = "<client id>"
   $csec = "<client secret>"
   curl.exe -X POST "https://accounts.zoho.in/oauth/v2/token" `
     -d "grant_type=authorization_code" `
     -d "client_id=$cid" -d "client_secret=$csec" `
     -d "code=$code"
   ```
   Save `refresh_token` from the JSON response (access_token is throwaway).
4. Set `CATALYST_AUTH` to the compact JSON (all on one line):

   ```
   CATALYST_AUTH={"client_id":"…","client_secret":"…","refresh_token":"…"}
   ```

### 2.4 · Data Store — provision the 30 FIR tables

**Optional for the demo.** The AppSail runs fully against a local SQLite
copy seeded at startup; `/health.services.datastore.mode` reports `"local"`
honestly. Every judged feature works without Data Store. Provision it only
if you want the durable system-of-record story.

Data Store tables can only be **created** via the console (no SDK
create-table API, no bulk-import CSV wizard in recent console versions —
the "+ New Table" modal accepts a name only, and columns must be added
one at a time). So the console-only path is realistic for 30 tables only
if you have a couple of hours and steady patience.

**Option A — console upload (recommended when console has "Import Data"):**

1. Regenerate the CSV export:
   ```powershell
   backend\.venv\Scripts\python.exe scripts\create-datastore-tables.py
   ```
   Writes `datastore_export/*.csv` + `SCHEMA.md`.
2. Console → project → **Data Store** → *Import Data* (if visible) → upload
   each CSV in the order listed in `datastore_export/SCHEMA.md`
   (`State` → `District` → … → `PersonAlias` → app tables). Catalyst infers
   column types from the header + first rows; if any column type looks
   wrong (e.g. `ID`s should be *Bigint*, `CrimeNo` must stay *Varchar*
   because leading zeros matter), edit before confirming import.
3. After the CSVs are loaded, no further Data Store work is needed — the
   AppSail sees the tables through `catalyst.py`.

If the console you're using shows only "+ New Table" with a name-only
modal (no CSV import step), option A becomes 30 tables × ~10 columns each
of manual clicking. In that case, skip Data Store and note it as deferred
in your submission — the app runs identically without it.

**Option B — CLI (`catalyst ds:import`) after tables exist:**

Once every table is present in the console (from A above, or created by
hand), you can reload row data via CLI:
```powershell
cd datastore_export
powershell -ExecutionPolicy Bypass -File .\import-all.ps1
```

**Option C — push from the running AppSail (once tables exist):**

```
POST https://<appsail>/admin/datastore/sync
Authorization: Bearer <admin session token>
Body: {"direction": "push"}
```
The app copies its local seeded rows up through the SDK.

### 2.5 · `CATALYST_QUICKML_ENDPOINT_KEY` — LLM serving (primary NL→SQL)

Catalyst QuickML is available on the **India DC** and offers both classical
ML pipelines and LLM Serving (Qwen 2.5 family). The app's provider chain
prefers QuickML when this key is set and a Catalyst request context is
present.

1. Console → project → **AI/ML** → **QuickML** → left nav *Generative AI*
   → **LLM Serving** → pick a model (Qwen 2.5-14B Instruct is the strongest
   general model) → **Create Endpoint** → name it (e.g. `nl-to-sql`) →
   *Create*.
2. Open the endpoint's **Details** page → API Details popup → copy:
   - The **endpoint key / unique ID** → `CATALYST_QUICKML_ENDPOINT_KEY`.
   - Note the **Deployment URL** (informational — the SDK constructs the
     URL from the endpoint key automatically).
3. Free tier: 500 prediction calls/mo + 1000 free invocations per
   Development endpoint. Click **Publish** to move to Production once you
   verify it works.

If you're only using the classical/tabular API (unlikely for NL→SQL), the
same page still shows an endpoint key; the SDK call is identical.

### 2.6 · `CRON_SECRET` — nightly refresh

A shared secret for `POST /jobs/refresh` (rebuild `PersonAlias` + warm
caches). Generate a random string:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set `CRON_SECRET` to that value in both `backend/.env` and the AppSail env.

Then in the console: **Cron** → *Create Cron* → *Schedule Cron with URL
Invocation* → Every day at (e.g.) 02:30 → **Method: POST** → **URL:**
`https://<your-appsail>/jobs/refresh` → *Add Header*
`X-Cron-Key: <the secret you just generated>` → *Create*.

(If your Catalyst tier's URL cron doesn't allow custom headers, use a
query string instead: `?key=<CRON_SECRET>` and change
`main.jobs_refresh` to accept it from `request.query_params`. Ping me and
I'll add the alternative in a minute.)

### 2.7 · `CATALYST_ALERT_RECIPIENTS` — Push Notifications recipients

Web push messages go to **Catalyst end users** by email.

1. Console → **Authentication** → *Add User* → invite yourself/teammates
   with an email; they accept the invite and set a password.
2. Console → **Push Notifications** → *Enable Web Push* if not already on
   (creates VAPID keys; nothing to copy).
3. Set `CATALYST_ALERT_RECIPIENTS` to a comma-separated list of those
   Catalyst users' emails. `/predict` will send a web push per crime spike.
4. Recipients open the AppSail URL once and grant browser notification
   permission (the frontend registers the service worker); after that the
   next `/predict` spike fires a real push.

### 2.8 · `CATALYST_STRATUS_BUCKET` — exported-PDF archive

Console → **Stratus** → *Create Bucket* → name (lowercase, hyphens),
region *(same as project)*, private → Create. Set
`CATALYST_STRATUS_BUCKET` to the bucket name (not URL).

The `/export/pdf` endpoint stores a copy of every generated conversation
PDF here for the audit trail.

### 2.9 · Zia — Text Analytics (yes), Speech (no GA)

`zia_text_analytics` (BriefFacts sentiment / NER / keywords) works
out-of-the-box once the SDK has a Catalyst context — **no env var**.

Catalyst Zia does **not** offer a GA speech-to-text or text-to-speech API
as of this writing. The `.env.example` exposes `CATALYST_ZIA_STT_URL` /
`CATALYST_ZIA_TTS_URL` / `CATALYST_ZIA_KEY` as pass-through hooks in case
Zoho promotes one to your account (or you plug in a private endpoint) —
otherwise leave empty and the UI uses on-device Web Speech for `kn-IN` /
`en-IN`, which works well.

### 2.10 · SmartBrowz — PDF rendering

Nothing to configure. The `/export/pdf` endpoint calls SmartBrowz through
the SDK; the first call may trigger a "First Use" prompt in the console
that just needs one click to accept. If the request context can't reach
SmartBrowz, the frontend transparently falls back to client-side jsPDF.

## 3. Verify it all works

```powershell
# Sanity
curl.exe https://<your-appsail>/health
# → { ok: true, cases: 1800, services: { … } }

# Every "true" in the services block is a Catalyst path that's live.
# The frontend's LLM badge upgrades to "QuickML" or "Gemini" the
# moment either shows true.
```

Then click through the app: **Chat → Hotspots (map!) → Trends →
Network → Insights → Early Warnings → Audit**. Each view writes to
`audit_log`; the Audit tab (admin only) shows the trail plus the FIR
reverse-lookup box.

## 4. Custom domain (optional)

Console → **Domain Mappings** → *Add* → e.g. `crime-ai.kar.gov.in` →
verify DNS TXT → SSL auto-issued.

## 5. Redeploying after code changes

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare-deploy.ps1
catalyst deploy --only appsail
```

The container re-seeds SQLite on cold start (idempotent), then serves.
Only Data Store CSVs and env vars persist across redeploys.

## What can't be automated from a coding-agent session

- `catalyst login` — browser OAuth on your machine
- Creating the Catalyst project + AppSail app in the console
- Reading Project ID / Key / Domain from Project Settings
- Uploading the Data Store CSVs / clicking *Import*
- Creating the QuickML endpoint + copying the endpoint key
- Creating the Cron job in the console
- Adding Catalyst Auth users + granting them push permission

Everything else — schema, seed, Docker image, FastAPI routes, client
build, deploy scripts — is prepped in this repo and syncs with
`prepare-deploy.ps1`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `catalyst deploy` errors "no project linked" | `catalyst init --force` |
| `/health.services.quickml` stays `false` after setting the key | The key needs a Catalyst request context — QuickML only fires on requests hitting the deployed AppSail, not local `uvicorn` (unless you also set `CATALYST_PROJECT_*` + `CATALYST_AUTH` locally) |
| `/chat` returns `SQL execution error: attempt to write a readonly database` | Expected only if guardrails somehow allowed a write — file an issue; the read-only cursor caught it |
| Cron says "invalid X-Cron-Key" | The env var on the AppSail differs from the header you set in the cron; make sure they match exactly |
| PDF export downloads but says "SmartBrowz not configured" | You're calling the endpoint from local dev (no request context). Deploy first, then export from the AppSail URL |
| Data Store CSV upload rejected on `caste_master_name` | Catalyst is case-sensitive on column names; the schema uses `caste_master_id` / `caste_master_name` in snake_case per the ER. Confirm the header row matches SCHEMA.md exactly |
