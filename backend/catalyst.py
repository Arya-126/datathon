"""Catalyst service adapters — zcatalyst-sdk first, graceful local fallbacks.

Two ways the SDK comes alive:

1. **In production (AppSail):** every request that reaches the app through
   Catalyst's router carries `X-ZC-*` headers (project id/key/domain plus
   admin/user credential tokens). `app_from_request()` initializes the SDK
   from those headers. This needs zero configuration.

2. **Locally against a real project:** set env vars —
       CATALYST_PROJECT_ID / CATALYST_PROJECT_KEY / CATALYST_PROJECT_DOMAIN
       CATALYST_AUTH='{"client_id":"..","client_secret":"..","refresh_token":".."}'
   (a Zoho self-client OAuth credential) and `app_from_env()` is used.

Every adapter degrades to a local implementation when neither is available,
so the demo never blanks. `/health` reports exactly which backend each
capability is running on — no pretending.

IMPORTANT (thread-locality): the SDK stores credentials in thread-locals.
Always call `app_from_request()` inside the endpoint function body (FastAPI
runs sync endpoints in a worker thread) and use the returned app in that
same thread. Never stash a CatalystApp for use on another thread.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

try:
    import zcatalyst_sdk
    from zcatalyst_sdk import get_app as _sdk_get_app
    _SDK = True
except ImportError:  # pragma: no cover
    _SDK = False

import requests as _requests

# Exact header names the SDK expects (see zcatalyst_sdk._constants).
_ZC_HEADERS = (
    "X-ZC-ProjectId", "X-ZC-Project-Domain", "X-ZC-Project-Key",
    "X-ZC-Environment", "X-ZC-PROJECT-SECRET-KEY",
    "X-ZC-Admin-Cred-Type", "X-ZC-User-Cred-Type",
    "X-ZC-Admin-Cred-Token", "X-ZC-User-Cred-Token",
    "x-zc-cookie", "X-ZCSRF-TOKEN", "X-ZC-User-Type",
)


class _ReqShim:
    """Minimal request stand-in: the SDK only reads `.headers` (a dict) and
    is case-sensitive about names, while Starlette lower-cases them. We remap
    onto the SDK's exact expected casing."""

    def __init__(self, headers: dict):
        self.headers = headers


def is_catalyst_request(request) -> bool:
    try:
        return bool(request.headers.get("x-zc-projectid"))
    except Exception:  # noqa: BLE001
        return False


def app_from_request(request):
    """CatalystApp from an in-flight request's X-ZC headers, else None.

    Must be called in the same thread that will use the returned app.
    """
    if not _SDK or request is None:
        return None
    try:
        picked = {}
        for name in _ZC_HEADERS:
            val = request.headers.get(name)  # case-insensitive lookup
            if val is not None:
                picked[name] = val
        if "X-ZC-ProjectId" not in picked:
            return None
        return zcatalyst_sdk.initialize(req=_ReqShim(picked))
    except Exception:  # noqa: BLE001
        return None


def app_from_env():
    """CatalystApp from env credentials (local dev / scripts), else None."""
    if not _SDK:
        return None
    pid = os.environ.get("CATALYST_PROJECT_ID")
    pkey = os.environ.get("CATALYST_PROJECT_KEY")
    pdom = os.environ.get("CATALYST_PROJECT_DOMAIN")
    if not (pid and pkey and pdom and os.environ.get("CATALYST_AUTH")):
        return None
    try:
        return _sdk_get_app("env-app")
    except Exception:  # noqa: BLE001
        pass
    try:
        return zcatalyst_sdk.initialize_app(
            options={
                "project_id": pid,
                "project_key": pkey,
                "project_domain": pdom,
                "environment": os.environ.get(
                    "CATALYST_ENVIRONMENT", "Development"),
            },
            name="env-app",
        )
    except Exception:  # noqa: BLE001
        return None


def any_app(request=None):
    """Best available CatalystApp for the current thread, or None."""
    return app_from_request(request) or app_from_env()


# ============================================================
# Authentication — Catalyst end-user identity on the request
# ============================================================
def current_catalyst_user(capp) -> dict | None:
    """The Catalyst-authenticated end user on this request, if any.

    Returns {"email", "user_id", "role_name"} or None (anonymous / local).
    """
    if capp is None:
        return None
    try:
        u = capp.authentication().get_current_user()
        if not u:
            return None
        return {
            "email": u.get("email_id"),
            "user_id": str(u.get("user_id", "")),
            "role_name": (u.get("role_details") or {}).get("role_name", ""),
        }
    except Exception:  # noqa: BLE001
        return None


# ============================================================
# Cache — L1 in-process dict always; Catalyst Cache as L2 when live
# ============================================================
_CACHE_LOCAL: dict[str, tuple[float, Any]] = {}


def cache_get(key: str, capp=None) -> Any | None:
    entry = _CACHE_LOCAL.get(key)
    if entry:
        expires_at, val = entry
        if expires_at >= time.time():
            return val
        _CACHE_LOCAL.pop(key, None)
    if capp is not None:
        try:
            raw = capp.cache().segment().get_value(key.replace(":", "_"))
            if raw:
                val = json.loads(raw)
                _CACHE_LOCAL[key] = (time.time() + 300, val)
                return val
        except Exception:  # noqa: BLE001
            pass
    return None


def cache_set(key: str, value: Any, ttl_seconds: int = 3600, capp=None) -> None:
    _CACHE_LOCAL[key] = (time.time() + ttl_seconds, value)
    if capp is not None:
        try:
            seg = capp.cache().segment()
            payload = json.dumps(value, default=str)
            hours = max(1, ttl_seconds // 3600)
            ckey = key.replace(":", "_")
            try:
                seg.put(ckey, payload, hours)
            except Exception:  # noqa: BLE001
                seg.update(ckey, payload, hours)
        except Exception:  # noqa: BLE001
            pass


# ============================================================
# Data Store — system of record; SQLite is the analytics engine
# ============================================================
# FK-safe order (parents before children) for both pull and push.
DATASTORE_TABLE_ORDER = [
    "State", "District", "DistrictGeo", "UnitType", "Unit",
    "Rank", "Designation", "Employee",
    "Act", "Section", "CrimeHead", "CrimeSubHead", "CrimeHeadActSection",
    "CaseCategory", "GravityOffence", "CaseStatusMaster", "Court",
    "CasteMaster", "ReligionMaster", "OccupationMaster",
    "CaseMaster", "ComplainantDetails", "Victim", "Accused",
    "ActSectionAssociation", "ArrestSurrender",
    "inv_arrestsurrenderaccused", "ChargesheetDetails", "PersonAlias",
]

# Columns Catalyst adds to every row — never mirrored into SQLite.
_SYSTEM_COLS = {"ROWID", "CREATORID", "CREATEDTIME", "MODIFIEDTIME"}

_sync_state: dict = {"mode": "local", "last_sync": None, "detail": {}}


def sync_state() -> dict:
    return dict(_sync_state)


def _local_columns(conn, table: str) -> list[str]:
    return [r["name"] for r in
            conn.execute(f"PRAGMA table_info({table})").fetchall()]


def pull_from_datastore(capp) -> dict:
    """Replace local SQLite contents with Catalyst Data Store contents.

    Data Store is the system of record; this hydrates the local analytics
    engine from it. Tables missing remotely are kept as-is locally.
    """
    from db import cursor  # late import to avoid cycles

    if capp is None:
        raise RuntimeError("no Catalyst context")
    ds = capp.datastore()
    remote_tables = {
        t.to_dict().get("table_name") if hasattr(t, "to_dict") else None
        for t in ds.get_all_tables()
    }
    detail: dict[str, Any] = {}
    _sync_state.update(mode="pulling", detail=detail)

    with cursor() as conn:
        conn.execute("PRAGMA foreign_keys = OFF;")
        for name in DATASTORE_TABLE_ORDER:
            if name not in remote_tables:
                detail[name] = "absent remotely — kept local"
                continue
            try:
                cols = set(_local_columns(conn, name))
                rows = []
                for row in ds.table(name).get_iterable_rows():
                    rows.append({k: v for k, v in row.items()
                                 if k in cols and k not in _SYSTEM_COLS})
                if not rows:
                    detail[name] = "empty remotely — kept local"
                    continue
                keys = sorted(set().union(*(r.keys() for r in rows)))
                conn.execute(f"DELETE FROM {name}")
                conn.executemany(
                    f"INSERT INTO {name} ({','.join(keys)}) "
                    f"VALUES ({','.join('?' * len(keys))})",
                    [[r.get(k) for k in keys] for r in rows],
                )
                detail[name] = len(rows)
            except Exception as e:  # noqa: BLE001
                detail[name] = f"error: {e}"

    _sync_state.update(
        mode="datastore",
        last_sync=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    return detail


def push_to_datastore(capp, *, only_empty: bool = True) -> dict:
    """Copy local SQLite rows up to Catalyst Data Store (first-boot seed).

    With only_empty=True (default) a table that already has remote rows is
    skipped — safe to call repeatedly.
    """
    from db import cursor

    if capp is None:
        raise RuntimeError("no Catalyst context")
    ds = capp.datastore()
    remote_tables = {
        t.to_dict().get("table_name") if hasattr(t, "to_dict") else None
        for t in ds.get_all_tables()
    }
    detail: dict[str, Any] = {}
    _sync_state.update(mode="pushing", detail=detail)

    with cursor() as conn:
        for name in DATASTORE_TABLE_ORDER:
            if name not in remote_tables:
                detail[name] = "table missing in Data Store (create via console)"
                continue
            try:
                table = ds.table(name)
                if only_empty:
                    probe = table.get_paged_rows(max_rows=1)
                    if probe.get("data"):
                        detail[name] = "already has rows — skipped"
                        continue
                rows = [dict(r) for r in conn.execute(f"SELECT * FROM {name}")]
                sent = 0
                for i in range(0, len(rows), 100):
                    table.insert_rows(rows[i:i + 100])
                    sent += len(rows[i:i + 100])
                detail[name] = sent
            except Exception as e:  # noqa: BLE001
                detail[name] = f"error: {e}"

    _sync_state.update(
        mode="datastore",
        last_sync=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    return detail


def audit_to_datastore(capp, entry: dict) -> bool:
    """Best-effort mirror of an audit row into Data Store (same thread)."""
    if capp is None:
        return False
    try:
        capp.datastore().table("audit_log").insert_row(entry)
        return True
    except Exception:  # noqa: BLE001
        return False


# ============================================================
# QuickML — NL→SQL LLM serving (primary provider when configured)
# ============================================================
def quickml_generate(system: str, messages: list[dict], capp=None) -> dict:
    """Schema-grounded NL→SQL via a QuickML-served endpoint.

    Needs CATALYST_QUICKML_ENDPOINT_KEY (the deployed endpoint's key) and a
    Catalyst context. Raises when unavailable — llm.py falls through to the
    Claude path (wrapped as a Catalyst Connection credential in prod).
    """
    key = os.environ.get("CATALYST_QUICKML_ENDPOINT_KEY", "")
    if not (capp and key):
        raise RuntimeError("QuickML not configured")
    prompt = system + "\n\n" + "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages
    )
    resp = capp.quick_ml().predict(key, {"prompt": prompt})
    # Endpoint response shapes vary by model wrapper — probe common keys.
    for probe in ("prediction", "output", "text", "response", "answer"):
        if isinstance(resp, dict) and probe in resp:
            text = resp[probe]
            break
    else:
        text = json.dumps(resp)
    if isinstance(text, (dict, list)):
        return text if isinstance(text, dict) else {"raw": text}
    import re
    m = re.search(r"\{.*\}", str(text), re.DOTALL)
    if not m:
        raise RuntimeError("QuickML reply had no JSON object")
    return json.loads(m.group(0))


# ============================================================
# Zia Services
# ============================================================
def zia_text_analytics(capp, text: str) -> dict | None:
    """Sentiment + keywords + NER on FIR BriefFacts via Zia Text Analytics.

    This is a live Catalyst Zia integration (no speech API is GA in Zia;
    voice STT/TTS remain env-gated below with an on-device fallback).
    """
    if capp is None or not text:
        return None
    try:
        return capp.zia().get_text_analytics([text[:2000]])
    except Exception:  # noqa: BLE001
        return None


def zia_stt(audio_bytes: bytes, lang: str = "en-IN") -> dict:
    """Speech-to-text. Catalyst Zia has no GA speech API — this posts to a
    configurable endpoint (CATALYST_ZIA_STT_URL) if the org enables one;
    otherwise callers fall back to on-device Web Speech."""
    url = os.environ.get("CATALYST_ZIA_STT_URL", "")
    key = os.environ.get("CATALYST_ZIA_KEY", "")
    if not url:
        raise RuntimeError("server STT not configured — use browser Web Speech")
    r = _requests.post(
        url, params={"language": lang}, data=audio_bytes,
        headers={"Authorization": f"Zoho-oauthtoken {key}",
                 "Content-Type": "application/octet-stream"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def zia_tts(text: str, lang: str = "en-IN") -> bytes | None:
    url = os.environ.get("CATALYST_ZIA_TTS_URL", "")
    key = os.environ.get("CATALYST_ZIA_KEY", "")
    if not url:
        return None
    try:
        r = _requests.post(
            url, json={"text": text, "language": lang},
            headers={"Authorization": f"Zoho-oauthtoken {key}"}, timeout=30,
        )
        r.raise_for_status()
        return r.content
    except Exception:  # noqa: BLE001
        return None


def zia_automl_forecast(capp, model_id: str, data: dict) -> dict | None:
    """Per-row prediction from a trained Zia AutoML tabular model."""
    if capp is None or not model_id:
        return None
    try:
        return capp.zia().auto_ml(model_id, data)
    except Exception:  # noqa: BLE001
        return None


# ============================================================
# SmartBrowz — server-side PDF (conversation export)
# ============================================================
def smartbrowz_pdf(html: str, capp=None) -> bytes:
    """Render HTML → PDF bytes via Catalyst SmartBrowz.

    Raises RuntimeError with the underlying reason when the service can't
    deliver — the caller surfaces it in the 501 payload so a live failure
    is diagnosable instead of a generic "not configured" message.
    """
    if capp is None:
        raise RuntimeError(
            "no Catalyst request context — use the deployed URL, "
            "or export via client jsPDF")
    try:
        resp = capp.smart_browz().convert_to_pdf(
            html,
            pdf_options={"format": "A4", "print_background": True},
        )
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"SmartBrowz convert failed: {e}") from e
    content = getattr(resp, "content", None)
    if not content:
        raise RuntimeError("SmartBrowz returned an empty response")
    if content[:4] != b"%PDF":
        head = content[:200]
        try:
            head = head.decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            head = repr(head)
        raise RuntimeError(f"SmartBrowz returned non-PDF content: {head}")
    return content


# ============================================================
# Push Notifications — spike alerts to on-duty officers
# ============================================================
def push_notify(user_id: str, title: str, body: str,
                data: dict | None = None, capp=None) -> bool:
    """Web push via Catalyst Push Notifications when live; recipients are
    Catalyst-authenticated user emails (CATALYST_ALERT_RECIPIENTS env or the
    session user's email). Local fallback logs to stdout."""
    message = f"{title} — {body}"
    if capp is not None:
        recipients = [
            r.strip() for r in
            os.environ.get("CATALYST_ALERT_RECIPIENTS", "").split(",")
            if r.strip()
        ]
        if not recipients and "@" in (user_id or ""):
            recipients = [user_id]
        if recipients:
            try:
                capp.push_notification().web().send_notification(
                    message, recipients)
                return True
            except Exception:  # noqa: BLE001
                pass
    # Stdout fallback — never let console encoding (Windows cp1252) kill
    # the caller.
    try:
        print(f"[push:{user_id}] {message} (data={data})".encode(
            "ascii", "replace").decode())
    except Exception:  # noqa: BLE001
        pass
    return False


# ============================================================
# Stratus — object storage (exported PDFs, evidence)
# ============================================================
STRATUS_LOCAL_DIR = Path(__file__).parent / "stratus_local"


def stratus_put(key: str, data: bytes,
                content_type: str = "application/octet-stream",
                capp=None) -> str:
    """Store a blob; returns a URI. Catalyst Stratus when live, local dir
    fallback otherwise."""
    bucket = os.environ.get("CATALYST_STRATUS_BUCKET", "")
    if capp is not None and bucket:
        try:
            b = capp.stratus().bucket(bucket)
            b.put_object(key, data)
            return f"stratus://{bucket}/{key}"
        except Exception:  # noqa: BLE001
            pass
    STRATUS_LOCAL_DIR.mkdir(exist_ok=True)
    safe = key.replace("/", "_")
    (STRATUS_LOCAL_DIR / safe).write_bytes(data)
    return f"stratus-local://{safe}"


# ============================================================
# Provisioning summary — surfaced on /health for demo transparency
# ============================================================
def service_status(request=None) -> dict:
    capp = app_from_request(request) if request is not None else None
    catalyst_ctx = capp is not None
    return {
        "sdk_installed": _SDK,
        "catalyst_request_context": catalyst_ctx,
        "datastore": sync_state(),
        "auth": bool(catalyst_ctx and current_catalyst_user(capp)),
        "cache": "catalyst+local" if catalyst_ctx else "local",
        "quickml": bool(
            catalyst_ctx and os.environ.get("CATALYST_QUICKML_ENDPOINT_KEY")),
        "smartbrowz": catalyst_ctx,
        "zia_text_analytics": catalyst_ctx,
        "zia_stt": bool(os.environ.get("CATALYST_ZIA_STT_URL")),
        "zia_tts": bool(os.environ.get("CATALYST_ZIA_TTS_URL")),
        "push": catalyst_ctx,
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }
