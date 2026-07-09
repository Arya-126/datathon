"""FastAPI entrypoint — FIR schema + Catalyst-wired.

Roles (rebuilt against the real HR schema):
  admin    — everything, plus audit log + Data Store sync
  dysp     — District-scoped (all units in one district), sees PII
  sho      — Unit-scoped (one police station), sees PII
  io       — self-scoped (cases where PolicePersonID = self OR
             ArrestSurrender.IOID = self), sees PII
  analyst  — aggregates only; row-level PII (Complainant/Victim/Accused)
             refused; caste/religion/occupation aggregate-only

Scope enforcement is done on the SQL itself via sqlglot (CTE-safe: the
predicate lands on every SELECT that reads CaseMaster, including inside
WITH clauses and subqueries). LLM-generated SQL executes on a read-only
connection. Every route writes to the audit trail; when a Catalyst request
context is present the audit row is mirrored to Data Store.

Deployment target: Catalyst AppSail. The same container serves the UI
(webroot/) so one AppSail URL is a complete deployment.
"""
from __future__ import annotations

import io
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).parent / ".env")

import sqlglot  # noqa: E402
from sqlglot import exp  # noqa: E402

import analytics  # noqa: E402
import catalyst  # noqa: E402
import jobs  # noqa: E402
from db import cursor, init_schema, read_cursor  # noqa: E402
from llm import ChatTurn, is_safe_sql, nl_to_sql  # noqa: E402
from seed import seed  # noqa: E402

app = FastAPI(title="KSP Crime AI", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Role policy
# ============================================================
ROLE_POLICY = {
    "admin": {
        "row_limit": 500,
        "scope": "global",
        "pii_row_visible": True,
        "demographics_aggregate_only": False,
        "audit_visible": True,
        "network_visible": True,
    },
    "dysp": {
        "row_limit": 400,
        "scope": "district",
        "pii_row_visible": True,
        "demographics_aggregate_only": False,
        "audit_visible": False,
        "network_visible": True,
    },
    "sho": {
        "row_limit": 300,
        "scope": "unit",
        "pii_row_visible": True,
        "demographics_aggregate_only": False,
        "audit_visible": False,
        "network_visible": True,
    },
    "io": {
        "row_limit": 200,
        "scope": "self",
        "pii_row_visible": True,
        "demographics_aggregate_only": False,
        "audit_visible": False,
        "network_visible": True,
    },
    "analyst": {
        "row_limit": 500,
        "scope": "global",
        "pii_row_visible": False,       # row-level PII refused
        "demographics_aggregate_only": True,
        "audit_visible": False,
        "network_visible": False,       # co-accused names are PII
    },
}


# In-memory sessions. In production the *identity* comes from Catalyst
# Authentication (X-ZC user context on the request); the app session binds
# that identity to a role scope (district/unit/officer). Locally the app
# session is the whole story.
SESSIONS: dict[str, dict] = {}

CRON_SECRET = os.environ.get("CRON_SECRET", "")


class LoginBody(BaseModel):
    user_id: str = Field(min_length=2, max_length=80)
    role: str
    district: str | None = None
    unit: str | None = None
    employee_id: int | None = None  # for io scope


@app.post("/login")
def login(body: LoginBody, request: Request) -> dict:
    if body.role not in ROLE_POLICY:
        raise HTTPException(400, f"unknown role {body.role!r}")
    policy = ROLE_POLICY[body.role]
    session: dict = {"user_id": body.user_id, "role": body.role}

    # Catalyst Authentication: when the request carries a Catalyst end-user,
    # that identity overrides the free-text user id (audit-grade identity).
    capp = catalyst.app_from_request(request)
    zc_user = catalyst.current_catalyst_user(capp)
    if zc_user and zc_user.get("email"):
        session["user_id"] = zc_user["email"]
        session["catalyst_user"] = True

    if policy["scope"] == "district":
        if not body.district:
            raise HTTPException(400, "dysp requires a district")
        with cursor() as conn:
            r = conn.execute(
                "SELECT DistrictID FROM District WHERE DistrictName = ?",
                (body.district,),
            ).fetchone()
        if not r:
            raise HTTPException(400, f"unknown district {body.district!r}")
        session["district_id"] = r["DistrictID"]
        session["district"] = body.district

    elif policy["scope"] == "unit":
        if not body.unit:
            raise HTTPException(400, "sho requires a unit (police station)")
        with cursor() as conn:
            r = conn.execute(
                "SELECT UnitID, DistrictID FROM Unit WHERE UnitName = ?",
                (body.unit,),
            ).fetchone()
        if not r:
            raise HTTPException(400, f"unknown unit {body.unit!r}")
        session["unit_id"] = r["UnitID"]
        session["district_id"] = r["DistrictID"]
        session["unit"] = body.unit

    elif policy["scope"] == "self":
        if not body.employee_id:
            raise HTTPException(400, "io requires an employee_id")
        with cursor() as conn:
            r = conn.execute(
                "SELECT UnitID, DistrictID, FirstName FROM Employee "
                "WHERE EmployeeID = ?", (body.employee_id,),
            ).fetchone()
        if not r:
            raise HTTPException(400, f"unknown employee {body.employee_id!r}")
        session["employee_id"] = body.employee_id
        session["employee_name"] = r["FirstName"]
        session["unit_id"] = r["UnitID"]
        session["district_id"] = r["DistrictID"]

    token = secrets.token_urlsafe(24)
    SESSIONS[token] = session
    scope_desc = (session.get("district") or session.get("unit")
                  or session.get("employee_name") or "global")
    _audit(session, "login", body.role, "",
           f"session opened, scope={scope_desc}", capp=capp)
    return {"token": token, **session}


def current_session(request: Request,
                    authorization: str | None = Header(None)) -> dict:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        sess = SESSIONS.get(token)
        if sess:
            return sess

    # No app session — a Catalyst-authenticated user with a *global* role
    # (admin / analyst, created as Catalyst Auth roles in the console) can
    # proceed on identity alone; scoped roles need the /login binding.
    capp = catalyst.app_from_request(request)
    zc_user = catalyst.current_catalyst_user(capp)
    if zc_user:
        role = (zc_user.get("role_name") or "").lower()
        if role in ROLE_POLICY and ROLE_POLICY[role]["scope"] == "global":
            return {
                "user_id": zc_user.get("email") or zc_user.get("user_id"),
                "role": role,
                "catalyst_user": True,
            }
        raise HTTPException(
            401,
            "Catalyst identity verified, but this role needs a scope "
            "binding — POST /login with your district/unit/officer.",
        )
    raise HTTPException(401, "missing or invalid bearer token")


@app.get("/me")
def me(session: dict = Depends(current_session)) -> dict:
    """Session echo — lets the frontend restore state after a reload."""
    return session


# ============================================================
# Audit
# ============================================================
def _audit(session: dict, action: str, query: str,
           sql: str, summary: str, capp=None) -> None:
    ts = datetime.now(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")
    with cursor() as conn:
        conn.execute(
            "INSERT INTO audit_log (user_id, role, action, query, sql, "
            "result_summary, timestamp) VALUES (?,?,?,?,?,?,?)",
            (session["user_id"], session["role"], action, query, sql,
             summary, ts),
        )
    # Mirror to Catalyst Data Store (system of record) — best-effort,
    # same-thread (SDK credentials are thread-local).
    if capp is not None:
        catalyst.audit_to_datastore(capp, {
            "user_id": session["user_id"], "role": session["role"],
            "action": action, "query": query, "sql": sql,
            "result_summary": summary, "timestamp": ts,
        })


# ============================================================
# SQL guardrails — role-aware rewrites & refusals
# ============================================================
PII_TABLES_ROW_LEVEL = ("ComplainantDetails", "Victim", "Accused")
PII_NAME_COLUMNS = ("AccusedName", "VictimName", "ComplainantName")
DEMOGRAPHIC_TABLES = ("CasteMaster", "ReligionMaster", "OccupationMaster")
DEMOGRAPHIC_NAME_COLUMNS = ("caste_master_name", "ReligionName", "OccupationName")
AGGREGATE_RE = re.compile(
    r"\b(count|sum|avg|min|max)\s*\(", re.IGNORECASE,
)
LIMIT_RE = re.compile(r"\blimit\b", re.IGNORECASE)


def _touches(sql: str, table: str) -> bool:
    return re.search(rf"\b{table}\b", sql, re.IGNORECASE) is not None


def _is_aggregate(sql: str) -> bool:
    return bool(AGGREGATE_RE.search(sql))


def _projects_pii(sql: str, columns: tuple[str, ...]) -> bool:
    """True if any PII column appears anywhere in the SQL (projection,
    filter, or aggregate) — DLP-style enforcement for the analyst role."""
    for col in columns:
        if re.search(rf"\b{col}\b", sql, re.IGNORECASE):
            return True
    return False


# Case-child tables: rows belong to a case via CaseMasterID. When a SELECT
# reads one of these WITHOUT joining CaseMaster (e.g. a co-accused self-join
# on Accused), the scope must still apply — via an IN (scoped case set).
CASE_CHILD_TABLES = {
    "accused", "victim", "complainantdetails", "arrestsurrender",
    "chargesheetdetails", "actsectionassociation",
}


def _inject_scope(sql: str, predicate_template: str) -> tuple[str, int]:
    """Add a scope predicate to EVERY SELECT that reads case data.

    sqlglot-based, so CTEs, subqueries, and multiple references are all
    scoped — a `WITH x AS (SELECT ... FROM CaseMaster ...)` gets the
    predicate inside the CTE where it belongs. SELECTs that read a
    case-child table (Accused, Victim, ...) without CaseMaster get an
    `IN (SELECT CaseMasterID FROM CaseMaster WHERE <scope>)` predicate so
    nothing case-linked escapes the caller's scope. Raises when the SQL
    cannot be parsed; callers refuse the query for scoped roles then.
    """
    tree = sqlglot.parse_one(sql, read="sqlite")
    case_set = ("SELECT CaseMasterID FROM CaseMaster WHERE "
                + predicate_template.format(alias="CaseMaster"))
    # CTE names must not be mistaken for real tables.
    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}

    # Plan first, mutate after: the injected predicates contain their own
    # SELECTs (the scoped case set / EXISTS on ArrestSurrender), so mutating
    # while walking find_all() lazily would keep discovering the SELECTs we
    # just added and never terminate.
    plan: list[tuple[exp.Select, str]] = []
    for select in list(tree.find_all(exp.Select)):
        my_tables = [
            t for t in select.find_all(exp.Table)
            if t.name and t.find_ancestor(exp.Select) is select
            and t.name.lower() not in cte_names
        ]
        has_case_master = any(
            t.name.lower() == "casemaster" for t in my_tables)
        for t in my_tables:
            name = t.name.lower()
            alias = t.alias_or_name
            if name == "casemaster":
                plan.append((select, predicate_template.format(alias=alias)))
            elif name in CASE_CHILD_TABLES and not has_case_master:
                plan.append(
                    (select, f"{alias}.CaseMasterID IN ({case_set})"))
            elif name == "inv_arrestsurrenderaccused" and not has_case_master:
                plan.append((
                    select,
                    f"{alias}.AccusedMasterID IN (SELECT AccusedMasterID "
                    f"FROM Accused WHERE CaseMasterID IN ({case_set}))"))

    for select, condition in plan:
        select.where(condition, dialect="sqlite", copy=False)
    if not plan:
        return sql, 0
    return tree.sql(dialect="sqlite"), len(plan)


def _scope_predicate(session: dict) -> str | None:
    """The CaseMaster scope predicate template for this session, or None."""
    scope = ROLE_POLICY[session["role"]]["scope"]
    if scope == "district":
        return ("{alias}.PoliceStationID IN (SELECT UnitID FROM Unit "
                f"WHERE DistrictID = {int(session['district_id'])})")
    if scope == "unit":
        return f"{{alias}}.PoliceStationID = {int(session['unit_id'])}"
    if scope == "self":
        emp = int(session["employee_id"])
        return (f"({{alias}}.PolicePersonID = {emp} OR EXISTS "
                f"(SELECT 1 FROM ArrestSurrender ars_scope WHERE "
                f"ars_scope.CaseMasterID = {{alias}}.CaseMasterID "
                f"AND ars_scope.IOID = {emp}))")
    return None


def _apply_role_policy(sql: str, session: dict) -> tuple[str, list[str]]:
    """Return (rewritten_sql, notes). Raises HTTPException(403) on refusal."""
    policy = ROLE_POLICY[session["role"]]
    notes: list[str] = []

    # --- PII refusal for analyst on row-level projections ---
    if not policy["pii_row_visible"]:
        # (a) Refuse any query that mentions a PII name column, aggregate or
        #     not — DLP-style enforcement.
        if _projects_pii(sql, PII_NAME_COLUMNS):
            raise HTTPException(
                403,
                "analyst role: query projects PII columns "
                f"({', '.join(PII_NAME_COLUMNS)}). Rewrite as COUNT/GROUP BY "
                "without name columns.",
            )
        # (b) Non-aggregate touches of PII tables are also refused.
        for tbl in PII_TABLES_ROW_LEVEL:
            if _touches(sql, tbl) and not _is_aggregate(sql):
                raise HTTPException(
                    403,
                    f"analyst role: {tbl} row-level access refused. "
                    "Use an aggregate query (COUNT/GROUP BY).",
                )

    # --- Demographics aggregate-only enforcement ---
    if policy["demographics_aggregate_only"]:
        for tbl in DEMOGRAPHIC_TABLES:
            if _touches(sql, tbl) and not _is_aggregate(sql):
                raise HTTPException(
                    403,
                    f"{tbl} is aggregate-only. Wrap in COUNT / GROUP BY.",
                )
        if _projects_pii(sql, DEMOGRAPHIC_NAME_COLUMNS) and not _is_aggregate(sql):
            raise HTTPException(
                403,
                "demographic name columns can only appear in aggregates.",
            )

    # --- Scope injection (CTE-safe via sqlglot) ---
    predicate = _scope_predicate(session)
    touches_case_data = _touches(sql, "CaseMaster") or any(
        _touches(sql, t) for t in (
            "Accused", "Victim", "ComplainantDetails", "ArrestSurrender",
            "ChargesheetDetails", "ActSectionAssociation",
            "inv_arrestsurrenderaccused",
        )
    )
    if predicate and touches_case_data:
        try:
            sql, injected = _inject_scope(sql, predicate)
        except Exception:  # noqa: BLE001 — parse failure = unsafe to scope
            raise HTTPException(
                403,
                "query too complex to scope safely for your role — "
                "please rephrase it more simply.",
            )
        if injected:
            scope_desc = (session.get("district") or session.get("unit")
                          or f"officer #{session.get('employee_id')}")
            notes.append(
                f"scoped to {scope_desc} ({session['role']}) — "
                f"{injected} CaseMaster reference(s) constrained")

    # --- Enforce LIMIT ---
    if not LIMIT_RE.search(sql):
        sql = f"{sql.rstrip()} LIMIT {policy['row_limit']}"
        notes.append(f"appended LIMIT {policy['row_limit']}")

    return sql, notes


def _session_scope(session: dict) -> dict | None:
    """Translate a session into an analytics scope dict (or None = global).

    admin / analyst → global (analyst is aggregate-only so unscoped is fine).
    dysp → district, sho → unit, io → self.
    """
    scope = ROLE_POLICY[session["role"]]["scope"]
    if scope == "district":
        return {"district_id": session.get("district_id")}
    if scope == "unit":
        return {"unit_id": session.get("unit_id")}
    if scope == "self":
        return {"employee_id": session.get("employee_id")}
    return None


def _case_in_scope(session: dict, police_station_id: int,
                   police_person_id: int, case_master_id: int) -> bool:
    """Return True if a case is visible to this session's scope."""
    policy = ROLE_POLICY[session["role"]]
    scope = policy["scope"]
    if scope == "global":
        return True
    if scope == "district":
        with cursor() as conn:
            row = conn.execute(
                "SELECT DistrictID FROM Unit WHERE UnitID = ?",
                (police_station_id,),
            ).fetchone()
        return bool(row and row["DistrictID"] == session.get("district_id"))
    if scope == "unit":
        return police_station_id == session.get("unit_id")
    if scope == "self":
        emp = session.get("employee_id")
        if police_person_id == emp:
            return True
        with cursor() as conn:
            row = conn.execute(
                "SELECT 1 FROM ArrestSurrender WHERE CaseMasterID = ? "
                "AND IOID = ? LIMIT 1", (case_master_id, emp),
            ).fetchone()
        return bool(row)
    return False


# ============================================================
# Conversations — persistence for context-aware chat + PDF export
# ============================================================
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds").replace("+00:00", "Z")


def _create_conversation(session: dict, title: str) -> int:
    with cursor() as conn:
        cur = conn.execute(
            "INSERT INTO conversation (user_id, role, title, started_at) "
            "VALUES (?,?,?,?)",
            (session["user_id"], session["role"], title[:80], _now_iso()),
        )
        return cur.lastrowid


def _conversation_owned(conv_id: int, session: dict) -> dict:
    with cursor() as conn:
        row = conn.execute(
            "SELECT * FROM conversation WHERE ConversationID = ?",
            (conv_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "conversation not found")
    if row["user_id"] != session["user_id"] and session["role"] != "admin":
        raise HTTPException(403, "not your conversation")
    return dict(row)


def _add_turn(conv_id: int, turn_role: str, content: str,
              sql: str = "", row_count: int | None = None,
              language: str = "en") -> None:
    with cursor() as conn:
        conn.execute(
            "INSERT INTO conversation_turn (ConversationID, turn_role, "
            "content, sql, row_count, language, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (conv_id, turn_role, content, sql, row_count, language,
             _now_iso()),
        )


@app.get("/conversations")
def list_conversations(session: dict = Depends(current_session)) -> dict:
    with cursor() as conn:
        rows = conn.execute(
            "SELECT c.ConversationID AS id, c.title, c.started_at, "
            "       COUNT(t.TurnID) AS turns "
            "FROM conversation c "
            "LEFT JOIN conversation_turn t "
            "       ON t.ConversationID = c.ConversationID "
            "WHERE c.user_id = ? "
            "GROUP BY c.ConversationID ORDER BY c.ConversationID DESC "
            "LIMIT 20",
            (session["user_id"],),
        ).fetchall()
    return {"conversations": [dict(r) for r in rows]}


@app.get("/conversations/{conv_id}")
def get_conversation(conv_id: int,
                     session: dict = Depends(current_session)) -> dict:
    conv = _conversation_owned(conv_id, session)
    with cursor() as conn:
        turns = conn.execute(
            "SELECT turn_role, content, sql, row_count, language, created_at "
            "FROM conversation_turn WHERE ConversationID = ? ORDER BY TurnID",
            (conv_id,),
        ).fetchall()
    return {"conversation": conv, "turns": [dict(t) for t in turns]}


# ============================================================
# /chat
# ============================================================
class ChatBody(BaseModel):
    query: str
    history: list[dict] = []
    conversation_id: int | None = None


@app.post("/chat")
def chat(body: ChatBody, request: Request,
         session: dict = Depends(current_session)) -> dict:
    capp = catalyst.app_from_request(request)
    history = [
        ChatTurn(role=t.get("role", "user"), content=t.get("content", ""))
        for t in body.history if t.get("content")
    ]

    conv_id = body.conversation_id
    if conv_id:
        _conversation_owned(conv_id, session)
    else:
        conv_id = _create_conversation(session, body.query)
    _add_turn(conv_id, "user", body.query)

    result = nl_to_sql(body.query, history=history, capp=capp)

    if not result.sql:
        _audit(session, "chat", body.query, "", "no sql produced", capp=capp)
        _add_turn(conv_id, "assistant",
                  result.answer_prefix_en or result.explanation_en,
                  language=result.language)
        return {
            "conversation_id": conv_id,
            "language": result.language,
            "sql": "", "rows": [], "columns": [],
            "explanation_en": result.explanation_en,
            "explanation_kn": result.explanation_kn,
            "chart_hint": "table",
            "answer_prefix_en": result.answer_prefix_en or (
                "I couldn't map that to the crime database."),
            "answer_prefix_kn": result.answer_prefix_kn,
            "used_fallback": result.used_fallback,
            "provider": result.provider,
            "notes": [],
        }

    ok, why = is_safe_sql(result.sql)
    if not ok:
        _audit(session, "chat", body.query, result.sql,
               f"blocked: {why}", capp=capp)
        raise HTTPException(400, f"unsafe SQL rejected: {why}")

    try:
        safe_sql, notes = _apply_role_policy(result.sql, session)
    except HTTPException as e:
        _audit(session, "chat", body.query, result.sql,
               f"forbidden: {e.detail}", capp=capp)
        raise

    # Execute on a READ-ONLY connection — defense in depth under the
    # keyword guardrail: even if something slipped through, it can't write.
    with read_cursor() as conn:
        try:
            rows = conn.execute(safe_sql).fetchall()
        except Exception as e:  # noqa: BLE001
            _audit(session, "chat", body.query, safe_sql,
                   f"sql error: {e}", capp=capp)
            raise HTTPException(400, f"SQL execution error: {e}")

    columns = list(rows[0].keys()) if rows else []
    row_dicts = [dict(r) for r in rows]

    summary = f"{len(row_dicts)} row(s) via {result.provider}"
    _audit(session, "chat", body.query, safe_sql, summary, capp=capp)

    prefix_en = result.answer_prefix_en or f"Found {len(row_dicts)} result(s)."
    _add_turn(conv_id, "assistant", prefix_en, sql=safe_sql,
              row_count=len(row_dicts), language=result.language)

    return {
        "conversation_id": conv_id,
        "language": result.language,
        "sql": safe_sql,
        "rows": row_dicts,
        "columns": columns,
        "explanation_en": result.explanation_en,
        "explanation_kn": result.explanation_kn,
        "chart_hint": result.chart_hint,
        "answer_prefix_en": prefix_en,
        "answer_prefix_kn": result.answer_prefix_kn,
        "used_fallback": result.used_fallback,
        "provider": result.provider,
        "notes": notes,
    }


# ============================================================
# Analytics endpoints
# ============================================================
@app.get("/hotspots")
def get_hotspots(request: Request, level: str = "district",
                 session: dict = Depends(current_session)) -> dict:
    if level not in ("district", "station"):
        raise HTTPException(400, "level must be 'district' or 'station'")
    capp = catalyst.app_from_request(request)
    cache_key = f"hotspots:{level}"
    data = catalyst.cache_get(cache_key, capp=capp)
    if data is None:
        # Station level fetches every unit so role filters (an SHO's own
        # station) still find their row; the UI shows the top slice.
        data = analytics.hotspots(
            level=level, limit=15 if level == "district" else 200)
        catalyst.cache_set(cache_key, data, ttl_seconds=3600, capp=capp)

    policy = ROLE_POLICY[session["role"]]
    if policy["scope"] == "district" or policy["scope"] == "self":
        data = [r for r in data
                if r["district_id"] == session.get("district_id")]
    elif policy["scope"] == "unit":
        if level == "station":
            data = [r for r in data if r["unit_id"] == session.get("unit_id")]
        else:
            data = [r for r in data
                    if r["district_id"] == session.get("district_id")]
    _audit(session, "hotspots", level, "", f"{len(data)} rows", capp=capp)
    return {"level": level, "hotspots": data}


@app.get("/trends")
def get_trends(request: Request,
               session: dict = Depends(current_session)) -> dict:
    data = analytics.trends(scope=_session_scope(session))
    _audit(session, "trends", "", "", f"{len(data['labels'])} months",
           capp=catalyst.app_from_request(request))
    return data


@app.get("/network")
def get_network(
    request: Request,
    min_shared: int = 2, limit: int = 100, cross_case: bool = True,
    session: dict = Depends(current_session),
) -> dict:
    if not ROLE_POLICY[session["role"]]["network_visible"]:
        raise HTTPException(403, "this role cannot see criminal networks")
    data = analytics.network(
        min_shared=min_shared, limit=limit, cross_case=cross_case,
        scope=_session_scope(session),
    )
    _audit(session, "network", "", "",
           f"{len(data['nodes'])} nodes / {len(data['edges'])} edges",
           capp=catalyst.app_from_request(request))
    return data


@app.get("/predict")
def get_predict(request: Request,
                session: dict = Depends(current_session)) -> dict:
    capp = catalyst.app_from_request(request)
    scope = _session_scope(session)
    data = analytics.predict(scope=scope)
    data["forecast"] = analytics.forecast(scope=scope)

    # Proactive crime-prevention loop: dispatch a push alert for each
    # spike-severity warning — Catalyst Push Notifications when live,
    # stdout locally.
    dispatched = 0
    for w in data["warnings"]:
        if w.get("severity") == "spike":
            if catalyst.push_notify(
                user_id=session["user_id"],
                title=f"Crime spike: {w['category']} in {w['district']}",
                body=w["message"],
                data={"district": w["district"], "category": w["category"],
                      "severity": w["severity"]},
                capp=capp,
            ):
                dispatched += 1
    data["alerts_dispatched"] = dispatched
    _audit(session, "predict", "", "",
           f"{len(data['warnings'])} warnings, {dispatched} alerts",
           capp=capp)
    return data


@app.get("/chargesheet-rate")
def get_chargesheet_rate(
    request: Request,
    session: dict = Depends(current_session),
) -> dict:
    data = analytics.chargesheet_rate_by_officer(
        scope=_session_scope(session))
    _audit(session, "chargesheet_rate", "", "",
           f"{len(data['officers'])} officers",
           capp=catalyst.app_from_request(request))
    return data


@app.get("/demographics")
def get_demographics(
    request: Request,
    dimension: str = "accused_age",
    session: dict = Depends(current_session),
) -> dict:
    """Socio-demographic insight — aggregate-only, safe for every role."""
    data = analytics.demographics(
        dimension=dimension, scope=_session_scope(session),
    )
    _audit(session, "demographics", dimension, "",
           f"{len(data['labels'])} buckets",
           capp=catalyst.app_from_request(request))
    return data


@app.get("/demographics/overview")
def get_demographics_overview(
    request: Request,
    session: dict = Depends(current_session),
) -> dict:
    data = analytics.demographics_overview(scope=_session_scope(session))
    _audit(session, "demographics_overview", "", "",
           f"{len(data['panels'])} panels",
           capp=catalyst.app_from_request(request))
    return data


@app.get("/profiling/repeat-offenders")
def get_repeat_offenders(
    request: Request,
    min_cases: int = 2, limit: int = 25,
    session: dict = Depends(current_session),
) -> dict:
    """Behavioural profiling — repeat offenders + recidivism.

    Offender names are PII: analyst gets them redacted (aggregate metrics
    only). Everyone else with network visibility sees the representative
    name for each cross-case cluster.
    """
    policy = ROLE_POLICY[session["role"]]
    include_names = policy["pii_row_visible"]
    data = analytics.repeat_offenders(
        min_cases=min_cases, limit=limit,
        scope=_session_scope(session), include_names=include_names,
    )
    _audit(session, "repeat_offenders", "", "",
           f"{len(data['offenders'])} offenders, "
           f"{data['recidivism']['recidivism_pct']}% recidivism",
           capp=catalyst.app_from_request(request))
    return data


# ============================================================
# Audit endpoints
# ============================================================
@app.get("/audit")
def get_audit(session: dict = Depends(current_session)) -> dict:
    if not ROLE_POLICY[session["role"]]["audit_visible"]:
        raise HTTPException(403, "admin only")
    with cursor() as conn:
        rows = conn.execute(
            "SELECT id, user_id, role, action, query, sql, "
            "result_summary, timestamp FROM audit_log "
            "ORDER BY id DESC LIMIT 200"
        ).fetchall()
    return {"entries": [dict(r) for r in rows]}


@app.get("/audit/fir/{crime_no}")
def get_audit_for_fir(crime_no: str,
                      session: dict = Depends(current_session)) -> dict:
    """Reverse lookup: which queries have touched this FIR? (supervision)"""
    if not ROLE_POLICY[session["role"]]["audit_visible"]:
        raise HTTPException(403, "admin only")
    like = f"%{crime_no}%"
    with cursor() as conn:
        rows = conn.execute(
            "SELECT id, user_id, role, action, query, sql, "
            "result_summary, timestamp FROM audit_log "
            "WHERE query LIKE ? OR sql LIKE ? OR result_summary LIKE ? "
            "ORDER BY id DESC LIMIT 100",
            (like, like, like),
        ).fetchall()
    return {"crime_no": crime_no, "entries": [dict(r) for r in rows]}


# ============================================================
# Voice — Zia-gated server path; browser Web Speech is the fallback
# ============================================================
@app.post("/voice/asr")
async def voice_asr(request: Request, audio: UploadFile,
                    lang: str = "en-IN") -> dict:
    """Server-side speech-to-text. Catalyst Zia has no GA speech API —
    when CATALYST_ZIA_STT_URL is unset the frontend transparently uses
    on-device Web Speech (kn-IN / en-IN) instead."""
    data = await audio.read()
    try:
        out = catalyst.zia_stt(data, lang=lang)
        return {"available": True, **out}
    except Exception as e:  # noqa: BLE001
        return JSONResponse(
            status_code=200,
            content={"available": False, "reason": str(e)},
        )


class TTSBody(BaseModel):
    text: str
    lang: str = "en-IN"


@app.post("/voice/tts")
def voice_tts(body: TTSBody) -> Response:
    audio = catalyst.zia_tts(body.text, lang=body.lang)
    if audio is None:
        return JSONResponse(
            status_code=200,
            content={"available": False,
                     "reason": "server TTS not configured — "
                               "use browser speechSynthesis"},
        )
    return Response(content=audio, media_type="audio/mpeg")


# ============================================================
# PDF export — SmartBrowz server-side; jsPDF client fallback
# ============================================================
class ExportBody(BaseModel):
    conversation_id: int


_PDF_CSS = """
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Kannada&family=Inter:wght@400;600&display=swap');
  body { font-family: Inter, 'Noto Sans Kannada', sans-serif; color: #111;
         margin: 32px; font-size: 12px; }
  h1 { font-size: 18px; margin-bottom: 2px; }
  .meta { color: #666; margin-bottom: 18px; }
  .turn { margin-bottom: 14px; }
  .who { font-weight: 600; }
  .sql { font-family: monospace; font-size: 10px; background: #f4f4f4;
         padding: 8px; border-radius: 4px; white-space: pre-wrap;
         word-break: break-all; }
  .rows { color: #666; font-size: 10px; }
"""


def _conversation_html(conv: dict, turns: list[dict], session: dict) -> str:
    import html as _html
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<style>{_PDF_CSS}</style></head><body>",
        "<h1>KSP Crime AI — Conversation Transcript</h1>",
        f"<div class='meta'>Session: {_html.escape(session['user_id'])} · "
        f"Role: {session['role']} · Started: {conv['started_at']} · "
        f"Exported: {_now_iso()}</div>",
    ]
    for t in turns:
        who = "Investigator" if t["turn_role"] == "user" else "AI"
        parts.append("<div class='turn'>")
        parts.append(f"<div class='who'>{who}</div>")
        if t["content"]:
            parts.append(f"<div>{_html.escape(t['content'])}</div>")
        if t["sql"]:
            parts.append(f"<div class='sql'>{_html.escape(t['sql'])}</div>")
        if t["row_count"] is not None:
            parts.append(f"<div class='rows'>({t['row_count']} rows)</div>")
        parts.append("</div>")
    parts.append("</body></html>")
    return "".join(parts)


@app.post("/export/pdf")
def export_pdf(body: ExportBody, request: Request,
               session: dict = Depends(current_session)):
    """Server-side conversation PDF via Catalyst SmartBrowz. A copy lands
    in Stratus for the audit trail. Falls back to 501 → the frontend
    renders with jsPDF instead (works offline, no Kannada glyphs)."""
    capp = catalyst.app_from_request(request)
    conv = _conversation_owned(body.conversation_id, session)
    with cursor() as conn:
        turns = [dict(t) for t in conn.execute(
            "SELECT turn_role, content, sql, row_count FROM conversation_turn "
            "WHERE ConversationID = ? ORDER BY TurnID",
            (body.conversation_id,),
        ).fetchall()]

    html_doc = _conversation_html(conv, turns, session)
    try:
        pdf = catalyst.smartbrowz_pdf(html_doc, capp=capp)
    except RuntimeError as e:
        _audit(session, "export_pdf", str(body.conversation_id), "",
               f"smartbrowz unavailable ({e}) — client jsPDF fallback",
               capp=capp)
        return JSONResponse(status_code=501, content={
            "available": False,
            "reason": str(e),
        })

    uri = catalyst.stratus_put(
        f"exports/conversation-{body.conversation_id}-"
        f"{_now_iso().replace(':', '')}.pdf",
        pdf, content_type="application/pdf", capp=capp)
    _audit(session, "export_pdf", str(body.conversation_id), "",
           f"pdf {len(pdf)} bytes → {uri}", capp=capp)
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition":
                 f"attachment; filename=ksp-conversation-"
                 f"{body.conversation_id}.pdf"},
    )


# ============================================================
# Jobs — Catalyst Cron target (nightly refresh)
# ============================================================
@app.post("/jobs/refresh")
def jobs_refresh(request: Request,
                 x_cron_key: str | None = Header(None),
                 authorization: str | None = Header(None)) -> dict:
    """Nightly: rebuild PersonAlias entity resolution + warm caches.

    Auth: either the X-Cron-Key header (set CRON_SECRET env; use it in the
    Catalyst Cron URL invocation) or an admin session token.
    """
    authorized = bool(
        CRON_SECRET and x_cron_key
        and secrets.compare_digest(x_cron_key, CRON_SECRET)
    )
    session = {"user_id": "cron", "role": "admin"}
    if not authorized:
        session = current_session(request, authorization)
        if session["role"] != "admin":
            raise HTTPException(403, "admin or cron key required")
    capp = catalyst.app_from_request(request)
    summary = jobs.refresh(capp=capp)
    _audit(session, "jobs_refresh", "", "",
           f"clusters={summary['person_alias']['clusters']}", capp=capp)
    return summary


class SyncBody(BaseModel):
    direction: str = "pull"  # "pull" (Data Store → local) | "push" (seed up)


@app.post("/admin/datastore/sync")
def datastore_sync(body: SyncBody, request: Request,
                   session: dict = Depends(current_session)) -> dict:
    """Data Store ⇄ local sync. `push` seeds an empty Data Store from the
    local synthetic data (first boot); `pull` makes Data Store the source
    of truth for this instance. Admin only; needs a Catalyst context."""
    if session["role"] != "admin":
        raise HTTPException(403, "admin only")
    capp = catalyst.app_from_request(request)
    if capp is None:
        raise HTTPException(
            501, "no Catalyst request context — call this on the deployed "
                 "AppSail URL (or set CATALYST_* env vars locally)")
    if body.direction == "pull":
        detail = catalyst.pull_from_datastore(capp)
    elif body.direction == "push":
        detail = catalyst.push_to_datastore(capp)
    else:
        raise HTTPException(400, "direction must be 'pull' or 'push'")
    _audit(session, "datastore_sync", body.direction, "",
           f"{sum(1 for v in detail.values() if isinstance(v, int))} tables",
           capp=capp)
    return {"direction": body.direction, "detail": detail}


# ============================================================
# Reference data (for the frontend login form)
# ============================================================
@app.get("/reference/districts")
def get_districts() -> dict:
    with cursor() as conn:
        rows = conn.execute(
            "SELECT DistrictID AS id, DistrictName AS name FROM District "
            "ORDER BY DistrictName"
        ).fetchall()
    return {"districts": [dict(r) for r in rows]}


@app.get("/reference/units")
def get_units(district_id: int | None = None) -> dict:
    with cursor() as conn:
        if district_id:
            rows = conn.execute(
                "SELECT UnitID AS id, UnitName AS name FROM Unit "
                "WHERE DistrictID = ? AND TypeID IN (1,4) ORDER BY UnitName",
                (district_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT UnitID AS id, UnitName AS name FROM Unit "
                "WHERE TypeID IN (1,4) ORDER BY UnitName LIMIT 200"
            ).fetchall()
    return {"units": [dict(r) for r in rows]}


@app.get("/reference/employees")
def get_employees(unit_id: int | None = None) -> dict:
    """Officers a user can log in as, filtered by unit if given."""
    with cursor() as conn:
        if unit_id:
            rows = conn.execute(
                "SELECT e.EmployeeID AS id, e.FirstName AS name, "
                "       r.RankName AS rank, ds.DesignationName AS designation "
                "FROM Employee e "
                "JOIN Rank r ON r.RankID = e.RankID "
                "JOIN Designation ds ON ds.DesignationID = e.DesignationID "
                "WHERE e.UnitID = ? ORDER BY r.Hierarchy",
                (unit_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT e.EmployeeID AS id, e.FirstName AS name, "
                "       r.RankName AS rank, ds.DesignationName AS designation "
                "FROM Employee e "
                "JOIN Rank r ON r.RankID = e.RankID "
                "JOIN Designation ds ON ds.DesignationID = e.DesignationID "
                "WHERE ds.DesignationName IN ('SHO','Investigating Officer',"
                "'Cyber Investigator') "
                "ORDER BY r.Hierarchy LIMIT 100"
            ).fetchall()
    return {"employees": [dict(r) for r in rows]}


# ============================================================
# Case detail (for follow-up drill-down)
# ============================================================
@app.get("/case/{crime_no}")
def get_case(crime_no: str, request: Request,
             session: dict = Depends(current_session)) -> dict:
    capp = catalyst.app_from_request(request)
    policy = ROLE_POLICY[session["role"]]
    with cursor() as conn:
        case = conn.execute(
            """
            SELECT c.CaseMasterID, c.PoliceStationID, c.PolicePersonID,
                   c.CrimeNo, c.CaseNo, c.CrimeRegisteredDate,
                   c.IncidentFromDate, c.BriefFacts, c.latitude, c.longitude,
                   u.UnitName AS station, d.DistrictName AS district,
                   ch.CrimeGroupName AS major_head,
                   csh.CrimeHeadName AS minor_head,
                   cc.LookupValue AS category,
                   g.LookupValue AS gravity,
                   csm.CaseStatusName AS status
            FROM CaseMaster c
            JOIN Unit u ON u.UnitID = c.PoliceStationID
            JOIN District d ON d.DistrictID = u.DistrictID
            JOIN CrimeHead ch ON ch.CrimeHeadID = c.CrimeMajorHeadID
            JOIN CrimeSubHead csh ON csh.CrimeSubHeadID = c.CrimeMinorHeadID
            JOIN CaseCategory cc ON cc.CaseCategoryID = c.CaseCategoryID
            JOIN GravityOffence g ON g.GravityOffenceID = c.GravityOffenceID
            JOIN CaseStatusMaster csm ON csm.CaseStatusID = c.CaseStatusID
            WHERE c.CrimeNo = ?
            """,
            (crime_no,),
        ).fetchone()
    if not case:
        raise HTTPException(404, "not found")

    # RBAC: dysp/sho/io may only open a case inside their scope.
    if not _case_in_scope(session, case["PoliceStationID"],
                          case["PolicePersonID"], case["CaseMasterID"]):
        _audit(session, "case", crime_no, "", "forbidden: out of scope",
               capp=capp)
        raise HTTPException(403, "case is outside your assigned scope")

    with cursor() as conn:
        sections = conn.execute(
            "SELECT asa.ActID AS act, asa.SectionID AS section, "
            "       s.SectionDescription AS description "
            "FROM ActSectionAssociation asa "
            "LEFT JOIN Section s ON s.ActCode = asa.ActID "
            "                   AND s.SectionCode = asa.SectionID "
            "WHERE asa.CaseMasterID = (SELECT CaseMasterID FROM CaseMaster "
            "                           WHERE CrimeNo = ?) "
            "ORDER BY asa.ActOrderID",
            (crime_no,),
        ).fetchall()

    resp = {"case": dict(case), "sections": [dict(s) for s in sections]}

    # Zia Text Analytics enrichment on BriefFacts (live Catalyst Zia use).
    insights = catalyst.zia_text_analytics(capp, case["BriefFacts"])
    if insights:
        resp["ai_insights"] = insights

    if policy["pii_row_visible"]:
        with cursor() as conn:
            resp["accused"] = [dict(r) for r in conn.execute(
                "SELECT AccusedName, AgeYear, GenderID, PersonID "
                "FROM Accused WHERE CaseMasterID = "
                "(SELECT CaseMasterID FROM CaseMaster WHERE CrimeNo = ?)",
                (crime_no,),
            ).fetchall()]
            resp["victims"] = [dict(r) for r in conn.execute(
                "SELECT VictimName, AgeYear, GenderID FROM Victim WHERE "
                "CaseMasterID = (SELECT CaseMasterID FROM CaseMaster "
                "                 WHERE CrimeNo = ?)",
                (crime_no,),
            ).fetchall()]
    _audit(session, "case", crime_no, "", "detail", capp=capp)
    return resp


# ============================================================
# Health
# ============================================================
@app.get("/health")
def health(request: Request) -> dict:
    with cursor() as conn:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM CaseMaster"
        ).fetchone()["n"]
    return {
        "ok": True,
        "cases": n,
        "services": catalyst.service_status(request),
    }


# ============================================================
# Frontend
# ============================================================
# A single AppSail container can serve both the API and the UI. The
# deploy sync (scripts/prepare-deploy.ps1) drops the frontend into a
# local ./webroot; locally we fall back to ../frontend. First existing
# wins, so one AppSail URL serves the whole app.
_FRONTEND_CANDIDATES = [
    Path(__file__).parent / "webroot",       # bundled inside AppSail image
    Path(__file__).parent.parent / "frontend",  # local dev checkout
]
FRONTEND_DIR = next((p for p in _FRONTEND_CANDIDATES if p.exists()), None)
if FRONTEND_DIR:
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")


# ============================================================
# Startup
# ============================================================
@app.on_event("startup")
def _startup() -> None:
    init_schema()
    seed()
