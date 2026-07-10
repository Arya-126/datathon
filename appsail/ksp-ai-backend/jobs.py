"""Scheduled jobs — the targets Catalyst Cron hits nightly.

POST /jobs/refresh (main.py) runs `refresh()`:
  1. rebuild_person_alias() — cross-case entity resolution. The FIR schema
     has no canonical person entity; the same accused across FIRs is
     resolved on (normalized name, gender, age proximity) with a fuzzy
     pass for near-miss spellings. Materializes PersonAlias, which the
     network graph, repeat-offender profiling, and the LLM's cross-case
     queries all read.
  2. warm_caches() — recompute hotspots / trends / forecast into the cache
     layer so dashboards are instant.

Deterministic and idempotent — safe to run any number of times.
"""
from __future__ import annotations

import difflib
import os
import re
from collections import defaultdict

import analytics
import catalyst
from db import cursor

_NAME_CLEAN = re.compile(r"[^a-z ]")


def _normalize(name: str) -> str:
    return _NAME_CLEAN.sub("", (name or "").lower()).strip()


def rebuild_person_alias(*, fuzzy_threshold: float = 0.88) -> dict:
    """Cluster Accused rows into canonical persons → PersonAlias.

    Pass 1: exact key (normalized name, GenderID) with age tolerance ±2.
    Pass 2: fuzzy merge of clusters whose names are near-identical
            (difflib ratio >= fuzzy_threshold) with same gender and
            compatible age — catches spelling variants across stations.
    """
    with cursor() as conn:
        accused = [dict(r) for r in conn.execute(
            "SELECT AccusedMasterID, AccusedName, AgeYear, GenderID FROM Accused"
        ).fetchall()]

    # ---- Pass 1: exact-name groups, split by age proximity ----
    by_key: dict[tuple, list[dict]] = defaultdict(list)
    for a in accused:
        by_key[(_normalize(a["AccusedName"]), a["GenderID"])].append(a)

    clusters: list[dict] = []  # {name_norm, gender, ages, members: [(id, sim)]}
    for (name_norm, gender), rows in by_key.items():
        rows.sort(key=lambda r: (r["AgeYear"] is None, r["AgeYear"]))
        open_groups: list[dict] = []
        for r in rows:
            age = r["AgeYear"]
            placed = False
            for g in open_groups:
                anchor = g["ages"][0]
                if age is None or anchor is None or abs(age - anchor) <= 2:
                    g["members"].append((r["AccusedMasterID"], 1.0))
                    g["ages"].append(age)
                    placed = True
                    break
            if not placed:
                open_groups.append({
                    "name_norm": name_norm, "gender": gender,
                    "ages": [age],
                    "members": [(r["AccusedMasterID"], 1.0)],
                })
        clusters.extend(open_groups)

    # ---- Pass 2: fuzzy merge across clusters (same gender, name close) ----
    # Bucket by first letter to keep comparisons bounded.
    buckets: dict[tuple, list[int]] = defaultdict(list)
    for idx, c in enumerate(clusters):
        first = c["name_norm"][:1]
        buckets[(first, c["gender"])].append(idx)

    merged_into: dict[int, int] = {}
    fuzzy_merges = 0
    for _, idxs in buckets.items():
        for i_pos, i in enumerate(idxs):
            if i in merged_into:
                continue
            for j in idxs[i_pos + 1:]:
                if j in merged_into:
                    continue
                a, b = clusters[i], clusters[j]
                if a["name_norm"] == b["name_norm"]:
                    continue  # same-name split was intentional (age gap)
                ratio = difflib.SequenceMatcher(
                    None, a["name_norm"], b["name_norm"]).ratio()
                if ratio < fuzzy_threshold:
                    continue
                age_a = next((x for x in a["ages"] if x is not None), None)
                age_b = next((x for x in b["ages"] if x is not None), None)
                if age_a is not None and age_b is not None and abs(age_a - age_b) > 2:
                    continue
                a["members"].extend(
                    (mid, round(ratio, 3)) for mid, _ in b["members"])
                merged_into[j] = i
                fuzzy_merges += 1

    # ---- Materialize ----
    rows_out = []
    cluster_id = 0
    for idx, c in enumerate(clusters):
        if idx in merged_into:
            continue
        cluster_id += 1
        for accused_id, sim in c["members"]:
            rows_out.append((cluster_id, accused_id, sim))

    with cursor() as conn:
        conn.execute("DELETE FROM PersonAlias")
        conn.executemany(
            "INSERT INTO PersonAlias (ClusterID, AccusedMasterID, similarity) "
            "VALUES (?,?,?)", rows_out,
        )

    multi = cluster_id and sum(
        1 for c in (clusters[i] for i in range(len(clusters))
                    if i not in merged_into)
        if len(c["members"]) > 1
    )
    return {
        "accused_rows": len(accused),
        "clusters": cluster_id,
        "multi_member_clusters": multi,
        "fuzzy_merges": fuzzy_merges,
    }


def warm_caches(capp=None) -> dict:
    """Recompute the hot dashboard payloads into the cache layer."""
    warmed = {}
    for key, fn in (
        ("hotspots:district", lambda: analytics.hotspots(level="district")),
        ("hotspots:station", lambda: analytics.hotspots(level="station")),
        ("trends:global", lambda: analytics.trends()),
        ("forecast:global", lambda: analytics.forecast()),
    ):
        try:
            catalyst.cache_set(key, fn(), ttl_seconds=86400, capp=capp)
            warmed[key] = True
        except Exception as e:  # noqa: BLE001
            warmed[key] = f"failed: {e}"
    return warmed


def _alert_routes() -> dict[str, list[str]]:
    """Parse CATALYST_ALERT_ROUTES: 'District=a@x.com,b@x.com;District2=c@x.com'.
    An alert nobody owns is an alert nobody acts on — spikes route to the
    district's own DySP, with CATALYST_ALERT_RECIPIENTS as the default."""
    routes: dict[str, list[str]] = {}
    for pair in os.environ.get("CATALYST_ALERT_ROUTES", "").split(";"):
        if "=" not in pair:
            continue
        district, emails = pair.split("=", 1)
        recipients = [e.strip() for e in emails.split(",") if e.strip()]
        if district.strip() and recipients:
            routes[district.strip().lower()] = recipients
    return routes


def dispatch_alerts(capp=None) -> dict:
    """Proactive early-warning loop — evaluate spikes and PUSH alerts.

    This is what makes prevention proactive rather than pull-based: the
    nightly Cron run evaluates the 30-day deltas and pushes each spike to
    the affected district's own recipients (CATALYST_ALERT_ROUTES), falling
    back to the global CATALYST_ALERT_RECIPIENTS list. No dashboard visit
    needed. (GET /predict additionally dispatches on-demand for the viewer.)
    """
    routes = _alert_routes()
    data = analytics.predict(scope=None)
    pushed = routed = 0
    for w in data["warnings"]:
        if w.get("severity") == "spike":
            recipients = routes.get(w["district"].lower())
            if recipients:
                routed += 1
            if catalyst.push_notify(
                user_id="",
                title=f"Crime spike: {w['category']} in {w['district']}",
                body=w["message"],
                data={"district": w["district"], "category": w["category"],
                      "severity": w["severity"], "source": "cron"},
                capp=capp,
                recipients=recipients,  # None → global default list
            ):
                pushed += 1
    return {"warnings_evaluated": len(data["warnings"]),
            "spike_alerts_pushed": pushed,
            "district_routed": routed}


def refresh(capp=None) -> dict:
    """Full nightly refresh — the Catalyst Cron entrypoint."""
    return {
        "person_alias": rebuild_person_alias(),
        "caches": warm_caches(capp=capp),
        "alerts": dispatch_alerts(capp=capp),
    }
