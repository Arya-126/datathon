"""NL→SQL over the FIR schema — provider chain per PLAN.md:

  1. Catalyst QuickML (LLM serving) — primary once an endpoint is deployed
     (set CATALYST_QUICKML_ENDPOINT_KEY; requires a Catalyst request context).
  2. Anthropic Claude — fallback; in production the credential is managed
     as a Catalyst Connection, surfaced to the app as ANTHROPIC_API_KEY.
  3. Local keyword rules — deterministic offline demo (fully bilingual).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import catalyst
from db import LLM_SCHEMA_DOC

try:
    from anthropic import Anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-fable-5")

FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|"
    r"replace|truncate|vacuum)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------- prompt
SYSTEM_PROMPT = f"""You are the query engine for the Karnataka State Police
Crime Records conversational AI. Investigators ask questions in English or
Kannada; you translate them into a safe SQLite SELECT against this schema:

{LLM_SCHEMA_DOC}

Rules:
1. Reply ONLY with a JSON object matching this schema:
   {{
     "language": "en" | "kn",
     "sql": "SELECT ... LIMIT 200",
     "explanation_en": "one plain-English sentence describing what the SQL does",
     "explanation_kn": "same in Kannada if the question was Kannada, else empty string",
     "chart_hint": "table" | "bar" | "line" | "map" | "network",
     "answer_prefix_en": "one-sentence natural-language lead-in for the result",
     "answer_prefix_kn": "same in Kannada if the question was Kannada, else empty string"
   }}
2. SQL MUST be a single SELECT (no INSERT/UPDATE/DELETE/DDL, no ';').
3. Always add LIMIT 200 unless the question is an aggregate.
4. Never SELECT columns from ComplainantDetails, Victim, or Accused unless
   the query is an aggregate (COUNT/GROUP BY). Row-level projections of
   caste_master_name / ReligionName / OccupationName are forbidden — those
   are sensitive demographic fields.
5. For "hotspot" / "top district" style questions → chart_hint="bar", group
   by District.DistrictName.
6. For "trend over time" / "monthly" → chart_hint="line", group by
   strftime('%Y-%m', c.CrimeRegisteredDate) and CrimeHead.CrimeGroupName.
7. For "co-accused" / "network" / "gang" → chart_hint="network"; return
   columns (a_id, a_name, b_id, b_name, shared_cases). Use PersonAlias for
   cross-case identity.
8. For act/section questions ("cases under IPC 302"), join
   ActSectionAssociation → Act / Section.
9. For chargesheet-rate questions, use ChargesheetDetails.cstype = 'A'.
10. If a previous assistant turn contains "[SQL] ..." context, treat
    follow-up questions ("only Mysuru", "just last month") as refinements
    of that SQL.
11. If the question can't be answered from this schema, set sql="" and
    put the reason in explanation_en.
"""


@dataclass
class LLMResult:
    language: str = "en"
    sql: str = ""
    explanation_en: str = ""
    explanation_kn: str = ""
    chart_hint: str = "table"
    answer_prefix_en: str = ""
    answer_prefix_kn: str = ""
    raw: str = ""
    used_fallback: bool = False
    provider: str = "fallback"  # "quickml" | "claude" | "fallback"


@dataclass
class ChatTurn:
    role: str  # 'user' | 'assistant'
    content: str


# ---------------------------------------------------------------- SQL guardrail
def is_safe_sql(sql: str) -> tuple[bool, str]:
    s = sql.strip().rstrip(";")
    if not s:
        return False, "empty SQL"
    if ";" in s:
        return False, "multiple statements not allowed"
    if not re.match(r"^\s*select\b|^\s*with\b", s, re.IGNORECASE):
        return False, "only SELECT/WITH allowed"
    if FORBIDDEN_SQL.search(s):
        return False, "forbidden keyword"
    return True, ""


def _anthropic_client():
    if not _ANTHROPIC_AVAILABLE:
        return None
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    return Anthropic(api_key=key)


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON object found in LLM output")
    return json.loads(m.group(0))


# ---------------------------------------------------------------- fallback
def _fb(is_kannada: bool, sql: str, en: str, kn: str, chart: str,
        prefix_en: str, prefix_kn: str) -> LLMResult:
    return LLMResult(
        language="kn" if is_kannada else "en", sql=sql,
        explanation_en=en, explanation_kn=kn if is_kannada else "",
        chart_hint=chart,
        answer_prefix_en=prefix_en,
        answer_prefix_kn=prefix_kn if is_kannada else "",
        used_fallback=True,
    )


def _fallback(query: str) -> LLMResult:
    """Deterministic keyword→SQL for offline demo continuity — bilingual.

    Every query targets the real FIR tables so results stay coherent even
    when the LLM path is offline.
    """
    q = query.lower()
    is_kn = any("ಀ" <= c <= "೿" for c in query)

    if any(k in q for k in (
        "hotspot", "top district", "most crime", "highest", "which district",
        "ಹಾಟ್", "ಜಿಲ್ಲೆ", "ಜಿಲ್ಲಾ",
    )):
        sql = (
            "SELECT d.DistrictName AS district, COUNT(c.CaseMasterID) AS crimes "
            "FROM CaseMaster c "
            "JOIN Unit u ON u.UnitID = c.PoliceStationID "
            "JOIN District d ON d.DistrictID = u.DistrictID "
            "GROUP BY d.DistrictName ORDER BY crimes DESC LIMIT 10"
        )
        return _fb(is_kn, sql,
                   "Group CaseMaster by District, order by count.",
                   "ಜಿಲ್ಲಾವಾರು ಎಫ್‌ಐಆರ್ ಎಣಿಕೆ, ಹೆಚ್ಚಿನದರಿಂದ ಕಡಿಮೆಗೆ.",
                   "bar",
                   "Top districts by FIR volume:",
                   "ಎಫ್‌ಐಆರ್ ಸಂಖ್ಯೆಯ ಪ್ರಕಾರ ಅಗ್ರ ಜಿಲ್ಲೆಗಳು:")

    if any(k in q for k in (
        "trend", "over time", "monthly", "per month", "line chart", "ಟ್ರೆಂಡ್",
    )):
        sql = (
            "SELECT strftime('%Y-%m', c.CrimeRegisteredDate) AS month, "
            "ch.CrimeGroupName AS category, COUNT(*) AS crimes "
            "FROM CaseMaster c "
            "JOIN CrimeHead ch ON ch.CrimeHeadID = c.CrimeMajorHeadID "
            "GROUP BY month, category ORDER BY month LIMIT 500"
        )
        return _fb(is_kn, sql,
                   "Monthly volume by crime head category.",
                   "ಅಪರಾಧ ವರ್ಗದ ಪ್ರಕಾರ ಮಾಸಿಕ ಪ್ರಮಾಣ.",
                   "line",
                   "Monthly crime volume by category:",
                   "ವರ್ಗವಾರು ಮಾಸಿಕ ಅಪರಾಧ ಪ್ರಮಾಣ:")

    if any(k in q for k in (
        "network", "co-offend", "co-accused", "gang", "associate",
        "syndicate", "ಸಿಂಡಿಕೇಟ್",
    )):
        sql = (
            "WITH accused_c AS ( "
            "  SELECT a.AccusedMasterID, a.CaseMasterID, a.AccusedName, "
            "         COALESCE(pa.ClusterID, -a.AccusedMasterID) AS cluster "
            "  FROM Accused a "
            "  LEFT JOIN PersonAlias pa ON pa.AccusedMasterID = a.AccusedMasterID "
            ") "
            "SELECT a1.cluster AS a_id, MAX(a1.AccusedName) AS a_name, "
            "       a2.cluster AS b_id, MAX(a2.AccusedName) AS b_name, "
            "       COUNT(DISTINCT a1.CaseMasterID) AS shared_cases "
            "FROM accused_c a1 "
            "JOIN accused_c a2 ON a1.CaseMasterID = a2.CaseMasterID "
            "                  AND a1.cluster < a2.cluster "
            "GROUP BY a1.cluster, a2.cluster "
            "HAVING shared_cases >= 2 "
            "ORDER BY shared_cases DESC LIMIT 60"
        )
        return _fb(is_kn, sql,
                   "Co-accused pairs across FIRs (via PersonAlias).",
                   "ಎಫ್‌ಐಆರ್‌ಗಳಾದ್ಯಂತ ಜೊತೆ-ಆರೋಪಿ ಜೋಡಿಗಳು (PersonAlias ಮೂಲಕ).",
                   "network",
                   "Persons who repeatedly co-offend:",
                   "ಪದೇ ಪದೇ ಜೊತೆಯಾಗಿ ಅಪರಾಧ ಮಾಡುವ ವ್ಯಕ್ತಿಗಳು:")

    if any(k in q for k in (
        "cyber", "online fraud", "phishing", "ransomware", "identity theft",
        "ಸೈಬರ್",
    )):
        sql = (
            "SELECT d.DistrictName AS district, "
            "       COUNT(c.CaseMasterID) AS cyber_cases "
            "FROM CaseMaster c "
            "JOIN CrimeHead ch ON ch.CrimeHeadID = c.CrimeMajorHeadID "
            "JOIN Unit u ON u.UnitID = c.PoliceStationID "
            "JOIN District d ON d.DistrictID = u.DistrictID "
            "WHERE ch.CrimeGroupName = 'Cyber Crimes' "
            "GROUP BY d.DistrictName ORDER BY cyber_cases DESC LIMIT 10"
        )
        return _fb(is_kn, sql,
                   "Cyber crime volume by district.",
                   "ಜಿಲ್ಲಾವಾರು ಸೈಬರ್ ಅಪರಾಧ ಪ್ರಮಾಣ.",
                   "bar",
                   "Cyber cases by district:",
                   "ಜಿಲ್ಲಾವಾರು ಸೈಬರ್ ಪ್ರಕರಣಗಳು:")

    if any(k in q for k in (
        "murder", "ipc 302", "heinous", "ಕೊಲೆ",
    )):
        sql = (
            "SELECT c.CrimeNo AS crime_no, d.DistrictName AS district, "
            "       csh.CrimeHeadName AS subhead, c.CrimeRegisteredDate AS date, "
            "       csm.CaseStatusName AS status "
            "FROM CaseMaster c "
            "JOIN CrimeSubHead csh ON csh.CrimeSubHeadID = c.CrimeMinorHeadID "
            "JOIN Unit u ON u.UnitID = c.PoliceStationID "
            "JOIN District d ON d.DistrictID = u.DistrictID "
            "JOIN CaseStatusMaster csm ON csm.CaseStatusID = c.CaseStatusID "
            "JOIN ActSectionAssociation asa ON asa.CaseMasterID = c.CaseMasterID "
            "WHERE asa.ActID = 'IPC' AND asa.SectionID = '302' "
            "ORDER BY c.CrimeRegisteredDate DESC LIMIT 25"
        )
        return _fb(is_kn, sql,
                   "Cases invoked under IPC 302 (murder), most recent first.",
                   "ಐಪಿಸಿ 302 (ಕೊಲೆ) ಅಡಿಯಲ್ಲಿ ದಾಖಲಾದ ಪ್ರಕರಣಗಳು, ಇತ್ತೀಚಿನವು ಮೊದಲು.",
                   "table",
                   "Recent cases invoked under IPC 302:",
                   "ಐಪಿಸಿ 302 ಅಡಿಯಲ್ಲಿ ದಾಖಲಾದ ಇತ್ತೀಚಿನ ಪ್ರಕರಣಗಳು:")

    if any(k in q for k in (
        "chargesheet", "conviction rate", "csr", "b report", "undetected",
    )):
        sql = (
            "SELECT csm.CaseStatusName AS status, "
            "       COALESCE(cs.cstype, '-') AS final_report, "
            "       COUNT(*) AS n "
            "FROM CaseMaster c "
            "JOIN CaseStatusMaster csm ON csm.CaseStatusID = c.CaseStatusID "
            "LEFT JOIN ChargesheetDetails cs ON cs.CaseMasterID = c.CaseMasterID "
            "GROUP BY csm.CaseStatusName, cs.cstype "
            "ORDER BY n DESC LIMIT 25"
        )
        return _fb(is_kn, sql,
                   "Case status × chargesheet final-report breakdown.",
                   "ಪ್ರಕರಣ ಸ್ಥಿತಿ ಮತ್ತು ದೋಷಾರೋಪ ಪಟ್ಟಿಯ ಅಂತಿಮ ವರದಿ ವಿಭಜನೆ.",
                   "table",
                   "Status vs chargesheet outcome:",
                   "ಸ್ಥಿತಿ ಮತ್ತು ದೋಷಾರೋಪ ಪಟ್ಟಿ ಫಲಿತಾಂಶ:")

    if any(k in q for k in ("ndps", "ganja", "narcotic", "ಮಾದಕ")):
        sql = (
            "SELECT d.DistrictName AS district, "
            "       COUNT(c.CaseMasterID) AS ndps_cases "
            "FROM CaseMaster c "
            "JOIN ActSectionAssociation asa ON asa.CaseMasterID = c.CaseMasterID "
            "JOIN Unit u ON u.UnitID = c.PoliceStationID "
            "JOIN District d ON d.DistrictID = u.DistrictID "
            "WHERE asa.ActID = 'NDPS' "
            "GROUP BY d.DistrictName ORDER BY ndps_cases DESC LIMIT 10"
        )
        return _fb(is_kn, sql,
                   "NDPS cases by district.",
                   "ಜಿಲ್ಲಾವಾರು ಎನ್‌ಡಿಪಿಎಸ್ ಪ್ರಕರಣಗಳು.",
                   "bar",
                   "Narcotic cases by district:",
                   "ಜಿಲ್ಲಾವಾರು ಮಾದಕ ವಸ್ತು ಪ್ರಕರಣಗಳು:")

    # Socio-demographic insights (focus area) — aggregate-only.
    if any(k in q for k in (
        "religion", "caste", "occupation", "demographic", "socio",
        "age group", "age band", "gender", "ಧರ್ಮ", "ಜಾತಿ", "ಉದ್ಯೋಗ",
    )):
        if "religion" in q or "ಧರ್ಮ" in q:
            group, join, label, label_kn = (
                "rm.ReligionName",
                "JOIN ComplainantDetails cd ON cd.CaseMasterID = c.CaseMasterID "
                "JOIN ReligionMaster rm ON rm.ReligionID = cd.ReligionID",
                "Complainants by religion", "ಧರ್ಮದ ಪ್ರಕಾರ ದೂರುದಾರರು")
        elif "occupation" in q or "ಉದ್ಯೋಗ" in q:
            group, join, label, label_kn = (
                "om.OccupationName",
                "JOIN ComplainantDetails cd ON cd.CaseMasterID = c.CaseMasterID "
                "JOIN OccupationMaster om ON om.OccupationID = cd.OccupationID",
                "Complainants by occupation", "ಉದ್ಯೋಗದ ಪ್ರಕಾರ ದೂರುದಾರರು")
        elif "caste" in q or "ಜಾತಿ" in q:
            group, join, label, label_kn = (
                "cm.caste_master_name",
                "JOIN ComplainantDetails cd ON cd.CaseMasterID = c.CaseMasterID "
                "JOIN CasteMaster cm ON cm.caste_master_id = cd.CasteID",
                "Complainants by caste category", "ಜಾತಿ ವರ್ಗದ ಪ್ರಕಾರ ದೂರುದಾರರು")
        else:
            group, join, label, label_kn = (
                "CASE a.GenderID WHEN 1 THEN 'Male' WHEN 2 THEN 'Female' "
                "ELSE 'Other' END",
                "JOIN Accused a ON a.CaseMasterID = c.CaseMasterID",
                "Accused by gender", "ಲಿಂಗದ ಪ್ರಕಾರ ಆರೋಪಿಗಳು")
        sql = (
            f"SELECT {group} AS category, COUNT(*) AS n "
            f"FROM CaseMaster c {join} "
            f"GROUP BY category ORDER BY n DESC LIMIT 20"
        )
        return _fb(is_kn, sql,
                   f"Socio-demographic aggregate: {label}.",
                   f"ಸಾಮಾಜಿಕ-ಜನಸಂಖ್ಯಾ ಒಟ್ಟುಗೂಡಿಕೆ: {label_kn}.",
                   "bar", f"{label}:", f"{label_kn}:")

    # Behavioural profiling (focus area) — repeat offenders / recidivism.
    if any(k in q for k in (
        "repeat offender", "recidiv", "habitual", "reoffend", "most active",
        "profiling", "prolific",
    )):
        sql = (
            "WITH accused_c AS ("
            "  SELECT a.AccusedMasterID, a.CaseMasterID, a.AccusedName, "
            "         COALESCE(pa.ClusterID, -a.AccusedMasterID) AS cluster "
            "  FROM Accused a "
            "  LEFT JOIN PersonAlias pa ON pa.AccusedMasterID = a.AccusedMasterID"
            ") "
            "SELECT MAX(ac.AccusedName) AS offender, "
            "       COUNT(DISTINCT ac.CaseMasterID) AS cases, "
            "       COUNT(DISTINCT c.CrimeMajorHeadID) AS crime_types, "
            "       SUM(CASE WHEN c.GravityOffenceID=1 THEN 1 ELSE 0 END) AS heinous "
            "FROM accused_c ac "
            "JOIN CaseMaster c ON c.CaseMasterID = ac.CaseMasterID "
            "GROUP BY ac.cluster HAVING cases >= 2 "
            "ORDER BY cases DESC, heinous DESC LIMIT 25"
        )
        return _fb(is_kn, sql,
                   "Repeat offenders (>=2 FIRs) via PersonAlias clusters.",
                   "ಪುನರಾವರ್ತಿತ ಅಪರಾಧಿಗಳು (2+ ಎಫ್‌ಐಆರ್), PersonAlias ಮೂಲಕ.",
                   "table",
                   "Repeat offenders by case count:",
                   "ಪ್ರಕರಣಗಳ ಸಂಖ್ಯೆಯ ಪ್ರಕಾರ ಪುನರಾವರ್ತಿತ ಅಪರಾಧಿಗಳು:")

    # Temporal pattern — time-of-day distribution.
    if any(k in q for k in (
        "time of day", "hour", "what time", "night", "peak time", "when do",
    )):
        sql = (
            "SELECT strftime('%H', c.IncidentFromDate) AS hour, "
            "       COUNT(*) AS crimes "
            "FROM CaseMaster c "
            "WHERE c.IncidentFromDate IS NOT NULL "
            "GROUP BY hour ORDER BY hour LIMIT 24"
        )
        return _fb(is_kn, sql,
                   "Incidents grouped by hour of day.",
                   "ದಿನದ ಗಂಟೆಯ ಪ್ರಕಾರ ಘಟನೆಗಳ ಗುಂಪು.",
                   "bar",
                   "Crime distribution by hour of day:",
                   "ದಿನದ ಗಂಟೆಯ ಪ್ರಕಾರ ಅಪರಾಧ ಹಂಚಿಕೆ:")

    # Act/Section pattern discovery.
    if any(k in q for k in (
        "section", "act ", "under ipc", "ipc ", "which sections", "legal",
    )):
        sql = (
            "SELECT asa.ActID AS act, asa.SectionID AS section, "
            "       s.SectionDescription AS description, COUNT(*) AS cases "
            "FROM ActSectionAssociation asa "
            "JOIN CaseMaster c ON c.CaseMasterID = asa.CaseMasterID "
            "LEFT JOIN Section s ON s.ActCode = asa.ActID "
            "                   AND s.SectionCode = asa.SectionID "
            "GROUP BY asa.ActID, asa.SectionID "
            "ORDER BY cases DESC LIMIT 20"
        )
        return _fb(is_kn, sql,
                   "Most-invoked Act/Section combinations.",
                   "ಹೆಚ್ಚು ಅನ್ವಯಿಸಲಾದ ಕಾಯ್ದೆ/ಕಲಂ ಸಂಯೋಜನೆಗಳು.",
                   "bar",
                   "Most frequently applied sections:",
                   "ಹೆಚ್ಚು ಬಳಸಲಾದ ಕಾಯ್ದೆ/ಕಲಂಗಳು:")

    # Default: recent FIRs
    sql = (
        "SELECT c.CrimeNo AS crime_no, csh.CrimeHeadName AS crime_type, "
        "       d.DistrictName AS district, u.UnitName AS station, "
        "       c.CrimeRegisteredDate AS date, csm.CaseStatusName AS status "
        "FROM CaseMaster c "
        "JOIN CrimeSubHead csh ON csh.CrimeSubHeadID = c.CrimeMinorHeadID "
        "JOIN Unit u ON u.UnitID = c.PoliceStationID "
        "JOIN District d ON d.DistrictID = u.DistrictID "
        "JOIN CaseStatusMaster csm ON csm.CaseStatusID = c.CaseStatusID "
        "ORDER BY c.CrimeRegisteredDate DESC LIMIT 25"
    )
    return _fb(is_kn, sql,
               "Most recent FIRs across all districts.",
               "ಎಲ್ಲಾ ಜಿಲ್ಲೆಗಳ ಇತ್ತೀಚಿನ ಎಫ್‌ಐಆರ್‌ಗಳು.",
               "table",
               "Recent FIRs:",
               "ಇತ್ತೀಚಿನ ಎಫ್‌ಐಆರ್‌ಗಳು:")


# ---------------------------------------------------------------- entry point
def nl_to_sql(query: str, history: list[ChatTurn] | None = None,
              capp=None) -> LLMResult:
    """NL question → validated SQL. Chain: QuickML → Claude → fallback."""
    messages = _messages_from_history(query, history)

    # 1. Catalyst QuickML (LLM serving)
    try:
        data = catalyst.quickml_generate(SYSTEM_PROMPT, messages, capp=capp)
        r = _result_from_json(data)
        r.provider = "quickml"
        return r
    except Exception:  # noqa: BLE001
        pass  # unconfigured or errored — fall through

    # 2. Anthropic Claude (Catalyst Connection-managed credential in prod)
    client = _anthropic_client()
    if client is not None:
        try:
            resp = client.messages.create(
                model=MODEL, max_tokens=1024, system=SYSTEM_PROMPT,
                messages=messages,
            )
            text = "".join(b.text for b in resp.content if hasattr(b, "text"))
            data = _extract_json(text)
            r = _result_from_json(data)
            r.raw = text
            r.provider = "claude"
            return r
        except Exception as e:  # noqa: BLE001
            fb = _fallback(query)
            fb.explanation_en = f"LLM error, used fallback: {e}"
            return fb

    # 3. Fallback
    return _fallback(query)


def _messages_from_history(query: str,
                            history: list[ChatTurn] | None) -> list[dict]:
    msgs: list[dict] = []
    if history:
        for turn in history[-6:]:
            msgs.append({"role": turn.role, "content": turn.content})
    msgs.append({"role": "user", "content": query})
    return msgs


def _result_from_json(data: dict) -> LLMResult:
    return LLMResult(
        language=data.get("language", "en"),
        sql=data.get("sql", "").strip().rstrip(";"),
        explanation_en=data.get("explanation_en", ""),
        explanation_kn=data.get("explanation_kn", ""),
        chart_hint=data.get("chart_hint", "table"),
        answer_prefix_en=data.get("answer_prefix_en", ""),
        answer_prefix_kn=data.get("answer_prefix_kn", ""),
    )
