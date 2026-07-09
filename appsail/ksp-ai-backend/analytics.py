"""Analytics against the FIR schema — hotspots, trends, network, predict,
socio-demographic insights, and behavioural profiling.

All queries stay pure aggregations; no PII column ever leaves this file.
Runs against SQLite locally, will run unchanged against Catalyst Data Store.
Nightly refresh is orchestrated by Catalyst Cron (see PLAN.md, Phase 5).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from db import cursor


# ------------------------------------------------------------------
# Scope helper — lets the API restrict a dashboard endpoint to a
# district / unit / officer for dysp / sho / io roles. Returns a SQL
# predicate on the aliased CaseMaster plus its bind params.
# ------------------------------------------------------------------
def scope_clause(scope: dict | None, alias: str = "c") -> tuple[str, list]:
    """Build an ' AND <predicate>' fragment for the given scope dict.

    scope keys (all optional): district_id, unit_id, employee_id.
    Returns ("", []) for a global scope.
    """
    if not scope:
        return "", []
    if scope.get("unit_id"):
        return f" AND {alias}.PoliceStationID = ?", [scope["unit_id"]]
    if scope.get("district_id"):
        return (
            f" AND {alias}.PoliceStationID IN "
            "(SELECT UnitID FROM Unit WHERE DistrictID = ?)",
            [scope["district_id"]],
        )
    if scope.get("employee_id"):
        return (
            f" AND ({alias}.PolicePersonID = ? OR EXISTS "
            f"(SELECT 1 FROM ArrestSurrender ars WHERE "
            f"ars.CaseMasterID = {alias}.CaseMasterID AND ars.IOID = ?))",
            [scope["employee_id"], scope["employee_id"]],
        )
    return "", []


def hotspots(*, level: str = "district", limit: int = 15,
             days: int = 180) -> list[dict]:
    """Hotspots ranked by FIR volume in the last N days, with map coords.

    level="district" → DistrictGeo coords (15 districts).
    level="station"  → per-Unit heat (real deployments care about
                       station-level heat, not just district).
    """
    since = (date(2026, 7, 1) - timedelta(days=days)).isoformat()
    if level == "station":
        with cursor() as conn:
            rows = conn.execute(
                """
                SELECT u.UnitID AS unit_id,
                       u.UnitName AS station,
                       d.DistrictID AS district_id,
                       d.DistrictName AS district,
                       u.latitude AS lat,
                       u.longitude AS lng,
                       COUNT(c.CaseMasterID) AS crimes,
                       SUM(CASE WHEN c.GravityOffenceID = 1 THEN 1 ELSE 0 END)
                           AS heinous
                FROM CaseMaster c
                JOIN Unit u ON u.UnitID = c.PoliceStationID
                JOIN District d ON d.DistrictID = u.DistrictID
                WHERE c.CrimeRegisteredDate >= ?
                GROUP BY u.UnitID
                ORDER BY crimes DESC
                LIMIT ?
                """,
                (since, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    with cursor() as conn:
        rows = conn.execute(
            """
            SELECT d.DistrictID AS district_id,
                   d.DistrictName AS district,
                   dg.latitude AS lat,
                   dg.longitude AS lng,
                   COUNT(c.CaseMasterID) AS crimes,
                   SUM(CASE WHEN c.GravityOffenceID = 1 THEN 1 ELSE 0 END) AS heinous,
                   COUNT(DISTINCT c.PoliceStationID) AS active_stations
            FROM CaseMaster c
            JOIN Unit u ON u.UnitID = c.PoliceStationID
            JOIN District d ON d.DistrictID = u.DistrictID
            LEFT JOIN DistrictGeo dg ON dg.DistrictID = d.DistrictID
            WHERE c.CrimeRegisteredDate >= ?
            GROUP BY d.DistrictID
            ORDER BY crimes DESC
            LIMIT ?
            """,
            (since, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def trends(*, months: int = 24, scope: dict | None = None) -> dict:
    """Monthly volume by CrimeHead.CrimeGroupName."""
    sc_sql, sc_params = scope_clause(scope, alias="c")
    with cursor() as conn:
        rows = conn.execute(
            f"""
            SELECT strftime('%Y-%m', c.CrimeRegisteredDate) AS month,
                   ch.CrimeGroupName AS category,
                   COUNT(*) AS crimes
            FROM CaseMaster c
            JOIN CrimeHead ch ON ch.CrimeHeadID = c.CrimeMajorHeadID
            WHERE 1=1 {sc_sql}
            GROUP BY month, category
            ORDER BY month
            """,
            sc_params,
        ).fetchall()
    by_month: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    categories: set[str] = set()
    for r in rows:
        by_month[r["month"]][r["category"]] = r["crimes"]
        categories.add(r["category"])
    labels = sorted(by_month.keys())[-months:]
    series = [
        {"label": cat, "data": [by_month[m].get(cat, 0) for m in labels]}
        for cat in sorted(categories)
    ]
    return {"labels": labels, "series": series}


def network(*, min_shared: int = 2, limit: int = 100,
            cross_case: bool = True, scope: dict | None = None) -> dict:
    """Co-accused graph.

    - Immediate edge: two Accused rows on the same CaseMaster.
    - Cross-case edge (when `cross_case`): same person appearing in multiple
      cases, resolved through PersonAlias.
    - `scope` restricts edges to cases visible to the caller's role
      (district / unit / officer) — an SHO sees their station's network,
      not the whole state's.

    Returns {nodes: [...], edges: [...]}, where node ids are canonical
    ClusterID when cross_case=True, else AccusedMasterID.
    """
    sc_sql, sc_params = scope_clause(scope, alias="cm")
    with cursor() as conn:
        if cross_case:
            # Canonical identity via PersonAlias.
            rows = conn.execute(
                f"""
                WITH accused_c AS (
                    SELECT a.AccusedMasterID,
                           a.CaseMasterID,
                           a.AccusedName,
                           COALESCE(pa.ClusterID, -a.AccusedMasterID) AS cluster
                    FROM Accused a
                    JOIN CaseMaster cm ON cm.CaseMasterID = a.CaseMasterID
                    LEFT JOIN PersonAlias pa
                           ON pa.AccusedMasterID = a.AccusedMasterID
                    WHERE 1=1 {sc_sql}
                )
                SELECT a1.cluster AS a_id,
                       MAX(a1.AccusedName) AS a_name,
                       a2.cluster AS b_id,
                       MAX(a2.AccusedName) AS b_name,
                       COUNT(DISTINCT a1.CaseMasterID) AS shared
                FROM accused_c a1
                JOIN accused_c a2
                     ON a1.CaseMasterID = a2.CaseMasterID
                    AND a1.cluster < a2.cluster
                GROUP BY a1.cluster, a2.cluster
                HAVING shared >= ?
                ORDER BY shared DESC
                LIMIT ?
                """,
                (*sc_params, min_shared, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""
                SELECT a1.AccusedMasterID AS a_id,
                       a1.AccusedName AS a_name,
                       a2.AccusedMasterID AS b_id,
                       a2.AccusedName AS b_name,
                       COUNT(DISTINCT a1.CaseMasterID) AS shared
                FROM Accused a1
                JOIN Accused a2
                     ON a1.CaseMasterID = a2.CaseMasterID
                    AND a1.AccusedMasterID < a2.AccusedMasterID
                JOIN CaseMaster cm ON cm.CaseMasterID = a1.CaseMasterID
                WHERE 1=1 {sc_sql}
                GROUP BY a1.AccusedMasterID, a2.AccusedMasterID
                HAVING shared >= ?
                ORDER BY shared DESC
                LIMIT ?
                """,
                (*sc_params, min_shared, limit),
            ).fetchall()

    node_set: dict[int, str] = {}
    edges: list[dict] = []
    for r in rows:
        node_set[r["a_id"]] = r["a_name"]
        node_set[r["b_id"]] = r["b_name"]
        edges.append({
            "source": r["a_id"], "target": r["b_id"],
            "weight": r["shared"],
        })

    # Case-count per node for sizing
    if not node_set:
        return {"nodes": [], "edges": []}

    with cursor() as conn:
        if cross_case:
            crime_counts = conn.execute(
                """
                SELECT COALESCE(pa.ClusterID, -a.AccusedMasterID) AS cluster,
                       COUNT(DISTINCT a.CaseMasterID) AS n
                FROM Accused a
                LEFT JOIN PersonAlias pa
                       ON pa.AccusedMasterID = a.AccusedMasterID
                GROUP BY cluster
                """
            ).fetchall()
            counts = {r["cluster"]: r["n"] for r in crime_counts}
        else:
            placeholders = ",".join("?" * len(node_set))
            crime_counts = conn.execute(
                f"SELECT AccusedMasterID AS id, COUNT(*) AS n FROM Accused "
                f"WHERE AccusedMasterID IN ({placeholders}) GROUP BY id",
                list(node_set.keys()),
            ).fetchall()
            counts = {r["id"]: r["n"] for r in crime_counts}

    nodes = [
        {"id": pid, "name": name, "crimes": counts.get(pid, 0)}
        for pid, name in node_set.items()
    ]
    return {"nodes": nodes, "edges": edges}


def predict(*, scope: dict | None = None) -> dict:
    """Heuristic early-warning: 30-day vs prior-30-day per district × head.

    Serves as the fallback / sanity check. The productionized path routes
    through Catalyst Zia AutoML for a real forecast (see catalyst.py).
    """
    today = date(2026, 7, 1)
    cur_start = (today - timedelta(days=30)).isoformat()
    prev_start = (today - timedelta(days=60)).isoformat()
    cur_end = today.isoformat()
    sc_sql, sc_params = scope_clause(scope, alias="c")

    with cursor() as conn:
        cur = conn.execute(
            f"""
            SELECT d.DistrictName AS district,
                   ch.CrimeGroupName AS category,
                   COUNT(*) AS n
            FROM CaseMaster c
            JOIN Unit u ON u.UnitID = c.PoliceStationID
            JOIN District d ON d.DistrictID = u.DistrictID
            JOIN CrimeHead ch ON ch.CrimeHeadID = c.CrimeMajorHeadID
            WHERE c.CrimeRegisteredDate >= ? AND c.CrimeRegisteredDate < ? {sc_sql}
            GROUP BY d.DistrictName, ch.CrimeGroupName
            """,
            [cur_start, cur_end, *sc_params],
        ).fetchall()
        prev = conn.execute(
            f"""
            SELECT d.DistrictName AS district,
                   ch.CrimeGroupName AS category,
                   COUNT(*) AS n
            FROM CaseMaster c
            JOIN Unit u ON u.UnitID = c.PoliceStationID
            JOIN District d ON d.DistrictID = u.DistrictID
            JOIN CrimeHead ch ON ch.CrimeHeadID = c.CrimeMajorHeadID
            WHERE c.CrimeRegisteredDate >= ? AND c.CrimeRegisteredDate < ? {sc_sql}
            GROUP BY d.DistrictName, ch.CrimeGroupName
            """,
            [prev_start, cur_start, *sc_params],
        ).fetchall()

    cur_map = {(r["district"], r["category"]): r["n"] for r in cur}
    prev_map = {(r["district"], r["category"]): r["n"] for r in prev}

    warnings = []
    for k in set(cur_map) | set(prev_map):
        c_now = cur_map.get(k, 0)
        c_prev = prev_map.get(k, 0)
        if c_prev == 0 and c_now >= 3:
            warnings.append({
                "district": k[0], "category": k[1],
                "prev": c_prev, "current": c_now,
                "change_pct": None,
                "severity": "new-activity",
                "message": (
                    f"New {k[1]} activity in {k[0]}: {c_now} incidents in "
                    "the last 30 days with no prior baseline."
                ),
            })
            continue
        if c_prev == 0:
            continue
        change = (c_now - c_prev) / c_prev
        if change >= 0.5 and c_now >= 4:
            warnings.append({
                "district": k[0], "category": k[1],
                "prev": c_prev, "current": c_now,
                "change_pct": round(change * 100, 1),
                "severity": "spike" if change >= 1.0 else "elevated",
                "message": (
                    f"{k[1]} in {k[0]} up {int(change * 100)}% "
                    f"({c_prev} → {c_now})."
                ),
            })
    warnings.sort(
        key=lambda w: (w["severity"] != "spike", -(w["current"])),
    )
    return {
        "window_current": [cur_start, cur_end],
        "window_previous": [prev_start, cur_start],
        "warnings": warnings[:20],
    }


def chargesheet_rate_by_officer(*, min_cases: int = 5, limit: int = 20,
                                scope: dict | None = None) -> dict:
    """Bonus analytic: chargesheeting rate per IO.

    Enables the "Chargesheeting rate for IO XYZ" NL question with a real
    metric definition. `scope` keeps the league table inside the caller's
    district/unit — officer performance is sensitive HR data.
    """
    sc_sql, sc_params = scope_clause(scope, alias="c")
    with cursor() as conn:
        rows = conn.execute(
            f"""
            SELECT e.EmployeeID AS io_id,
                   e.FirstName AS io_name,
                   u.UnitName AS unit,
                   d.DistrictName AS district,
                   COUNT(DISTINCT c.CaseMasterID) AS total_cases,
                   SUM(CASE WHEN cs.cstype = 'A' THEN 1 ELSE 0 END)
                       AS chargesheeted,
                   ROUND(100.0 * SUM(CASE WHEN cs.cstype = 'A' THEN 1 ELSE 0 END)
                         / COUNT(DISTINCT c.CaseMasterID), 1) AS rate_pct
            FROM CaseMaster c
            JOIN Employee e ON e.EmployeeID = c.PolicePersonID
            JOIN Unit u ON u.UnitID = e.UnitID
            JOIN District d ON d.DistrictID = u.DistrictID
            LEFT JOIN ChargesheetDetails cs
                   ON cs.CaseMasterID = c.CaseMasterID
            WHERE 1=1 {sc_sql}
            GROUP BY e.EmployeeID
            HAVING total_cases >= ?
            ORDER BY rate_pct DESC, total_cases DESC
            LIMIT ?
            """,
            (*sc_params, min_cases, limit),
        ).fetchall()
    return {"officers": [dict(r) for r in rows]}


def forecast(*, scope: dict | None = None, top: int = 15) -> dict:
    """Forward-looking 30-day volume forecast per district × crime head.

    Statistical baseline: weighted mean of the last three 30-day windows
    (0.6 / 0.3 / 0.1) — a deliberately simple, explainable model. When a
    Zia AutoML model id is configured the /predict endpoint upgrades the
    projection with the trained model's output (see catalyst.py).
    """
    today = date(2026, 7, 1)
    windows = [
        ((today - timedelta(days=30)).isoformat(), today.isoformat()),
        ((today - timedelta(days=60)).isoformat(),
         (today - timedelta(days=30)).isoformat()),
        ((today - timedelta(days=90)).isoformat(),
         (today - timedelta(days=60)).isoformat()),
    ]
    sc_sql, sc_params = scope_clause(scope, alias="c")
    counts: list[dict[tuple, int]] = []
    with cursor() as conn:
        for start, end in windows:
            rows = conn.execute(
                f"""
                SELECT d.DistrictName AS district,
                       ch.CrimeGroupName AS category,
                       COUNT(*) AS n
                FROM CaseMaster c
                JOIN Unit u ON u.UnitID = c.PoliceStationID
                JOIN District d ON d.DistrictID = u.DistrictID
                JOIN CrimeHead ch ON ch.CrimeHeadID = c.CrimeMajorHeadID
                WHERE c.CrimeRegisteredDate >= ?
                  AND c.CrimeRegisteredDate < ? {sc_sql}
                GROUP BY d.DistrictName, ch.CrimeGroupName
                """,
                [start, end, *sc_params],
            ).fetchall()
            counts.append({(r["district"], r["category"]): r["n"]
                           for r in rows})

    keys = set().union(*counts) if counts else set()
    out = []
    for k in keys:
        m1, m2, m3 = (counts[0].get(k, 0), counts[1].get(k, 0),
                      counts[2].get(k, 0))
        predicted = round(0.6 * m1 + 0.3 * m2 + 0.1 * m3)
        if predicted == 0 and m1 == 0:
            continue
        delta = predicted - m1
        out.append({
            "district": k[0], "category": k[1],
            "last_30d": m1, "predicted_next_30d": predicted,
            "direction": "rising" if delta > 0
                         else "falling" if delta < 0 else "flat",
        })
    out.sort(key=lambda r: -r["predicted_next_30d"])
    return {
        "model": "weighted 30-day windows (0.6/0.3/0.1) — statistical "
                 "baseline; Zia AutoML upgrade when configured",
        "horizon_days": 30,
        "forecast": out[:top],
    }


# ==================================================================
# SOCIO-DEMOGRAPHIC INSIGHTS  (challenge focus area #3)
# Pure aggregates — no individual name/PII ever returned. Safe for
# every role including analyst.
# ==================================================================
_AGE_BANDS = (
    "CASE "
    "WHEN AgeYear < 18 THEN '<18' "
    "WHEN AgeYear BETWEEN 18 AND 25 THEN '18-25' "
    "WHEN AgeYear BETWEEN 26 AND 35 THEN '26-35' "
    "WHEN AgeYear BETWEEN 36 AND 50 THEN '36-50' "
    "WHEN AgeYear > 50 THEN '50+' "
    "ELSE 'unknown' END"
)


def demographics(*, dimension: str = "accused_age",
                 scope: dict | None = None) -> dict:
    """Socio-demographic breakdowns across the people on a case.

    dimension ∈ {
      accused_age, accused_gender,
      complainant_religion, complainant_caste, complainant_occupation,
      victim_age, victim_gender
    }

    Returns {dimension, labels[], counts[]} — aggregate-only.
    """
    sc_sql, sc_params = scope_clause(scope, alias="c")

    # (join person table, group expression, human label)
    configs = {
        "accused_age": ("Accused a", _AGE_BANDS.replace("AgeYear", "a.AgeYear"),
                        "Accused by age band"),
        "accused_gender": ("Accused a",
                           "CASE a.GenderID WHEN 1 THEN 'Male' "
                           "WHEN 2 THEN 'Female' ELSE 'Other' END",
                           "Accused by gender"),
        "victim_age": ("Victim v", _AGE_BANDS.replace("AgeYear", "v.AgeYear"),
                       "Victims by age band"),
        "victim_gender": ("Victim v",
                          "CASE v.GenderID WHEN 1 THEN 'Male' "
                          "WHEN 2 THEN 'Female' ELSE 'Other' END",
                          "Victims by gender"),
        "complainant_religion": (
            "ComplainantDetails cd JOIN ReligionMaster rm "
            "ON rm.ReligionID = cd.ReligionID",
            "rm.ReligionName", "Complainants by religion"),
        "complainant_caste": (
            "ComplainantDetails cd JOIN CasteMaster cm "
            "ON cm.caste_master_id = cd.CasteID",
            "cm.caste_master_name", "Complainants by caste category"),
        "complainant_occupation": (
            "ComplainantDetails cd JOIN OccupationMaster om "
            "ON om.OccupationID = cd.OccupationID",
            "om.OccupationName", "Complainants by occupation"),
    }
    if dimension not in configs:
        dimension = "accused_age"
    join_expr, group_expr, label = configs[dimension]

    sql = (
        f"SELECT {group_expr} AS bucket, COUNT(*) AS n "
        f"FROM {join_expr} "
        f"JOIN CaseMaster c ON c.CaseMasterID = "
        f"{'a' if 'Accused' in join_expr else 'v' if 'Victim' in join_expr else 'cd'}"
        ".CaseMasterID "
        f"WHERE 1=1 {sc_sql} "
        f"GROUP BY bucket ORDER BY n DESC"
    )
    with cursor() as conn:
        rows = conn.execute(sql, sc_params).fetchall()
    return {
        "dimension": dimension,
        "label": label,
        "labels": [r["bucket"] for r in rows],
        "counts": [r["n"] for r in rows],
    }


def demographics_overview(*, scope: dict | None = None) -> dict:
    """A compact multi-panel snapshot for the Insights dashboard."""
    return {
        "panels": [
            demographics(dimension=d, scope=scope) for d in (
                "accused_age", "accused_gender",
                "complainant_religion", "complainant_occupation",
                "victim_gender",
            )
        ],
    }


# ==================================================================
# BEHAVIOURAL PROFILING  (challenge focus area #4)
# Repeat offenders / recidivism via PersonAlias cross-case clusters.
# Returns cluster-level aggregates; a single representative name is
# shown for investigator+ roles, gated by the caller (main.py).
# ==================================================================
def repeat_offenders(*, min_cases: int = 2, limit: int = 25,
                     scope: dict | None = None,
                     include_names: bool = True) -> dict:
    """Persons (resolved across FIRs) appearing as accused in >= min_cases.

    Metrics per offender cluster:
      - cases: distinct FIRs
      - arrests: distinct arrest events
      - heinous: cases with a heinous gravity
      - crime_heads: how many distinct crime groups they span (versatility)
    """
    sc_sql, sc_params = scope_clause(scope, alias="c")
    name_col = "MAX(ac.AccusedName)" if include_names else "'[redacted]'"
    sql = (
        "WITH accused_c AS ("
        "  SELECT a.AccusedMasterID, a.CaseMasterID, a.AccusedName,"
        "         COALESCE(pa.ClusterID, -a.AccusedMasterID) AS cluster"
        "  FROM Accused a"
        "  LEFT JOIN PersonAlias pa ON pa.AccusedMasterID = a.AccusedMasterID"
        ") "
        f"SELECT ac.cluster AS offender_id, {name_col} AS name, "
        "       COUNT(DISTINCT ac.CaseMasterID) AS cases, "
        "       COUNT(DISTINCT ars.ArrestSurrenderID) AS arrests, "
        "       SUM(CASE WHEN c.GravityOffenceID = 1 THEN 1 ELSE 0 END) AS heinous, "
        "       COUNT(DISTINCT c.CrimeMajorHeadID) AS crime_heads "
        "FROM accused_c ac "
        "JOIN CaseMaster c ON c.CaseMasterID = ac.CaseMasterID "
        "LEFT JOIN ArrestSurrender ars ON ars.CaseMasterID = ac.CaseMasterID "
        f"WHERE 1=1 {sc_sql} "
        "GROUP BY ac.cluster "
        "HAVING cases >= ? "
        "ORDER BY cases DESC, heinous DESC "
        "LIMIT ?"
    )
    params = sc_params + [min_cases, limit]
    with cursor() as conn:
        rows = conn.execute(sql, params).fetchall()
    offenders = [dict(r) for r in rows]

    # Recidivism headline: share of accused clusters with >1 case.
    with cursor() as conn:
        rec = conn.execute(
            "WITH accused_c AS ("
            "  SELECT a.AccusedMasterID, a.CaseMasterID,"
            "         COALESCE(pa.ClusterID, -a.AccusedMasterID) AS cluster"
            "  FROM Accused a"
            "  LEFT JOIN PersonAlias pa ON pa.AccusedMasterID = a.AccusedMasterID"
            "), per AS ("
            "  SELECT cluster, COUNT(DISTINCT CaseMasterID) AS n"
            "  FROM accused_c GROUP BY cluster"
            ") "
            "SELECT "
            "  SUM(CASE WHEN n > 1 THEN 1 ELSE 0 END) AS repeat_offenders, "
            "  COUNT(*) AS total_offenders "
            "FROM per"
        ).fetchone()
    total = rec["total_offenders"] or 1
    return {
        "offenders": offenders,
        "recidivism": {
            "repeat_offenders": rec["repeat_offenders"],
            "total_offenders": rec["total_offenders"],
            "recidivism_pct": round(100.0 * rec["repeat_offenders"] / total, 1),
        },
    }
