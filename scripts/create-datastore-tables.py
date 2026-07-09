"""Prepare Catalyst Data Store provisioning artefacts from the FIR schema.

Catalyst Data Store tables can only be CREATED via the console (there is no
create-table REST/SDK API). This script makes that one-time step painless:

  1. Exports every table from the local seeded crime.db to
     `datastore_export/<Table>.csv` (header row + data). In the Catalyst
     console: Data Store → Import → upload a CSV → it creates the table
     with inferred column types and loads the rows in one shot.
  2. Writes `datastore_export/SCHEMA.md` — a per-table column/type cheat
     sheet (from db.py::SCHEMA) if you prefer creating tables by hand.
  3. Writes `datastore_export/import-all.ps1` — a loop of
     `catalyst ds:import <csv> --table <T>` commands for loading data via
     the CLI *after* the tables exist (alternative to console import).

Once tables exist, you can also skip CSV loading entirely: deploy the
AppSail and call  POST /admin/datastore/sync {"direction": "push"}  as
admin — the app copies its local seed rows up through the SDK.

Usage:
    python scripts/create-datastore-tables.py          # export everything
    python scripts/create-datastore-tables.py --dry-run  # just list tables
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from db import SCHEMA, DB_PATH  # noqa: E402

OUT_DIR = ROOT / "datastore_export"

# SQLite type → Catalyst Data Store column type (for the cheat sheet).
TYPE_MAP = {
    "INTEGER": "Bigint",
    "INT": "Bigint",
    "REAL": "Decimal",
    "TEXT": "Text",
    "VARCHAR": "Text",
    "CHAR": "Text",
    "DATE": "Date Time",
    "DATETIME": "Date Time",
}

# FK-safe order — matches catalyst.DATASTORE_TABLE_ORDER plus app tables.
TABLE_ORDER = [
    "State", "District", "DistrictGeo", "UnitType", "Unit",
    "Rank", "Designation", "Employee",
    "Act", "Section", "CrimeHead", "CrimeSubHead", "CrimeHeadActSection",
    "CaseCategory", "GravityOffence", "CaseStatusMaster", "Court",
    "CasteMaster", "ReligionMaster", "OccupationMaster",
    "CaseMaster", "ComplainantDetails", "Victim", "Accused",
    "ActSectionAssociation", "ArrestSurrender",
    "inv_arrestsurrenderaccused", "ChargesheetDetails", "PersonAlias",
    "audit_log", "conversation", "conversation_turn",
]


def parse_schema(ddl: str) -> dict[str, list[tuple[str, str]]]:
    """table → [(column, catalyst_type)] from db.py::SCHEMA."""
    tables: dict[str, list[tuple[str, str]]] = {}
    pattern = re.compile(
        r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)\s*\((.*?)\);",
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(ddl):
        name, body = m.group(1), m.group(2)
        cols = []
        depth = 0
        parts, buf = [], []
        for ch in body:
            depth += ch == "("
            depth -= ch == ")"
            if ch == "," and depth == 0:
                parts.append("".join(buf)); buf = []
            else:
                buf.append(ch)
        if buf:
            parts.append("".join(buf))
        for raw in parts:
            raw = raw.strip()
            if not raw or raw.split()[0].upper() in {
                "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT"}:
                continue
            col = raw.split()[0]
            ctype = next(
                (cat for sql_t, cat in TYPE_MAP.items()
                 if re.search(rf"\b{sql_t}\b", raw.upper())), "Text")
            cols.append((col, ctype))
        tables[name] = cols
    return tables


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tables = parse_schema(SCHEMA)
    print(f"Parsed {len(tables)} tables from backend/db.py::SCHEMA")
    if args.dry_run:
        for t in TABLE_ORDER:
            print(f"  {t} ({len(tables.get(t, []))} cols)")
        return

    if not DB_PATH.exists():
        sys.exit(f"{DB_PATH} not found — run backend/seed.py first")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    OUT_DIR.mkdir(exist_ok=True)

    # 1. CSVs (create-and-load via console import). App runtime tables ship
    #    header-only — their rows are produced by the live app, not the seed.
    RUNTIME_TABLES = {"audit_log", "conversation", "conversation_turn"}
    for name in TABLE_ORDER:
        rows = ([] if name in RUNTIME_TABLES else
                conn.execute(f"SELECT * FROM {name}").fetchall())
        cols = [c[0] for c in tables.get(name, [])] or (
            list(rows[0].keys()) if rows else [])
        path = OUT_DIR / f"{name}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in rows:
                w.writerow([r[c] if c in r.keys() else "" for c in cols])
        print(f"  + {path.name}: {len(rows)} rows")

    # 2. Schema cheat sheet
    lines = ["# Data Store table reference (from db.py::SCHEMA)\n",
             "Create these in Catalyst console → Data Store (or let the "
             "console Import flow create them from the CSVs).\n"]
    for name in TABLE_ORDER:
        lines.append(f"\n## {name}\n")
        lines.append("| Column | Catalyst type |\n|---|---|\n")
        for col, ctype in tables.get(name, []):
            lines.append(f"| {col} | {ctype} |\n")
    (OUT_DIR / "SCHEMA.md").write_text("".join(lines), encoding="utf-8")
    print(f"  + SCHEMA.md")

    # 3. CLI import loop (for loading into already-created tables)
    ps = ["# Load all CSVs into existing Data Store tables via Catalyst CLI.",
          "# Requires: catalyst login + linked project (catalyst init).",
          "$ErrorActionPreference = 'Continue'"]
    for name in TABLE_ORDER:
        ps.append(f"catalyst ds:import \"$PSScriptRoot\\{name}.csv\" "
                  f"--table {name}")
    (OUT_DIR / "import-all.ps1").write_text("\n".join(ps) + "\n",
                                            encoding="utf-8")
    print(f"  + import-all.ps1")
    print(f"\nAll artefacts in {OUT_DIR}\\")
    print("Console: Data Store > Import > upload each CSV (creates table + "
          "loads rows).\nOr create tables from SCHEMA.md, then run "
          "import-all.ps1.\nOr, after AppSail deploy: POST "
          "/admin/datastore/sync {\"direction\": \"push\"} as admin.")


if __name__ == "__main__":
    main()
