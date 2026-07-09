"""Karnataka FIR schema — Data Store compatible SQLite implementation.

Faithful to Police_FIR_ER_Diagram.pdf: 25+ normalized tables anchored on
CaseMaster. Uses SQLite locally; the same DDL runs on Catalyst Data Store
(they share ANSI-SQL). Table + column names preserve the ER diagram's
CamelCase / snake_case exactly, so the LLM's SQL matches production naming.

Documented deviations from the ER PDF:
- `Inv_OccuranceTime`: the ER's relationship matrix names a one-to-one
  occurrence-time table that its own table-definitions section never
  defines. Its fields (IncidentFromDate/ToDate, InfoReceivedPSDate,
  latitude, longitude) appear as CaseMaster columns in the ER's CaseMaster
  definition, so we keep them on CaseMaster — no separate table.
- `Unit.latitude` / `Unit.longitude` and the `DistrictGeo` table are
  additions (not in the ER): they exist purely to power hotspot mapping.
- `PersonAlias`, `audit_log`, `conversation`, `conversation_turn` are
  application tables (cross-case entity resolution, audit trail, and chat
  persistence) — additions on top of the ER, never a redefinition of it.

Production: Catalyst Data Store is the system of record (tables created via
the console import flow — see DEPLOY.md); the AppSail instance keeps this
SQLite copy as its analytics engine and syncs from/to Data Store via
catalyst.py (POST /admin/datastore/sync).
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "crime.db"

# The full FIR schema — kept in one place so `catalyst.py` can re-emit it
# against Data Store's DDL API when Catalyst is wired up.
SCHEMA = """
-- ============================================================
-- Geography hierarchy
-- ============================================================
CREATE TABLE IF NOT EXISTS State (
    StateID INTEGER PRIMARY KEY,
    StateName VARCHAR NOT NULL,
    NationalityID INTEGER,
    Active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS District (
    DistrictID INTEGER PRIMARY KEY,
    DistrictName VARCHAR NOT NULL,
    StateID INTEGER NOT NULL,
    Active INTEGER DEFAULT 1,
    FOREIGN KEY (StateID) REFERENCES State(StateID)
);

-- Geo coords for districts (not in the ER; needed for hotspot mapping).
CREATE TABLE IF NOT EXISTS DistrictGeo (
    DistrictID INTEGER PRIMARY KEY,
    latitude REAL,
    longitude REAL,
    population INTEGER,
    FOREIGN KEY (DistrictID) REFERENCES District(DistrictID)
);

CREATE TABLE IF NOT EXISTS UnitType (
    UnitTypeID INTEGER PRIMARY KEY,
    UnitTypeName VARCHAR NOT NULL,
    CityDistState VARCHAR,
    Hierarchy INTEGER,
    Active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS Unit (
    UnitID INTEGER PRIMARY KEY,
    UnitName VARCHAR NOT NULL,
    TypeID INTEGER NOT NULL,
    ParentUnit INTEGER,
    NationalityID INTEGER,
    StateID INTEGER NOT NULL,
    DistrictID INTEGER NOT NULL,
    Active INTEGER DEFAULT 1,
    latitude REAL,
    longitude REAL,
    FOREIGN KEY (TypeID) REFERENCES UnitType(UnitTypeID),
    FOREIGN KEY (StateID) REFERENCES State(StateID),
    FOREIGN KEY (DistrictID) REFERENCES District(DistrictID),
    FOREIGN KEY (ParentUnit) REFERENCES Unit(UnitID)
);

-- ============================================================
-- HR: ranks, designations, employees
-- ============================================================
CREATE TABLE IF NOT EXISTS Rank (
    RankID INTEGER PRIMARY KEY,
    RankName VARCHAR NOT NULL,
    Hierarchy INTEGER,
    Active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS Designation (
    DesignationID INTEGER PRIMARY KEY,
    DesignationName VARCHAR NOT NULL,
    SortOrder INTEGER,
    Active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS Employee (
    EmployeeID INTEGER PRIMARY KEY,
    DistrictID INTEGER,
    UnitID INTEGER,
    RankID INTEGER,
    DesignationID INTEGER,
    KGID VARCHAR UNIQUE,
    FirstName VARCHAR NOT NULL,
    EmployeeDOB DATE,
    GenderID INTEGER,
    BloodGroupID INTEGER,
    PhysicallyChallenged INTEGER DEFAULT 0,
    AppointmentDate DATE,
    FOREIGN KEY (DistrictID) REFERENCES District(DistrictID),
    FOREIGN KEY (UnitID) REFERENCES Unit(UnitID),
    FOREIGN KEY (RankID) REFERENCES Rank(RankID),
    FOREIGN KEY (DesignationID) REFERENCES Designation(DesignationID)
);

-- ============================================================
-- Legal: acts + sections + crime heads
-- ============================================================
CREATE TABLE IF NOT EXISTS Act (
    ActCode VARCHAR PRIMARY KEY,
    ActDescription VARCHAR,
    ShortName VARCHAR,
    Active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS Section (
    ActCode VARCHAR NOT NULL,
    SectionCode VARCHAR NOT NULL,
    SectionDescription VARCHAR,
    Active INTEGER DEFAULT 1,
    PRIMARY KEY (ActCode, SectionCode),
    FOREIGN KEY (ActCode) REFERENCES Act(ActCode)
);

CREATE TABLE IF NOT EXISTS CrimeHead (
    CrimeHeadID INTEGER PRIMARY KEY,
    CrimeGroupName VARCHAR NOT NULL,
    Active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS CrimeSubHead (
    CrimeSubHeadID INTEGER PRIMARY KEY,
    CrimeHeadID INTEGER NOT NULL,
    CrimeHeadName VARCHAR NOT NULL,
    SeqID INTEGER,
    FOREIGN KEY (CrimeHeadID) REFERENCES CrimeHead(CrimeHeadID)
);

CREATE TABLE IF NOT EXISTS CrimeHeadActSection (
    CrimeHeadID INTEGER NOT NULL,
    ActCode VARCHAR NOT NULL,
    SectionCode VARCHAR NOT NULL,
    FOREIGN KEY (CrimeHeadID) REFERENCES CrimeHead(CrimeHeadID),
    FOREIGN KEY (ActCode) REFERENCES Act(ActCode)
);

-- ============================================================
-- Case reference / lookup masters
-- ============================================================
CREATE TABLE IF NOT EXISTS CaseCategory (
    CaseCategoryID INTEGER PRIMARY KEY,
    LookupValue VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS GravityOffence (
    GravityOffenceID INTEGER PRIMARY KEY,
    LookupValue VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS CaseStatusMaster (
    CaseStatusID INTEGER PRIMARY KEY,
    CaseStatusName VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS Court (
    CourtID INTEGER PRIMARY KEY,
    CourtName VARCHAR NOT NULL,
    DistrictID INTEGER,
    StateID INTEGER,
    Active INTEGER DEFAULT 1,
    FOREIGN KEY (DistrictID) REFERENCES District(DistrictID),
    FOREIGN KEY (StateID) REFERENCES State(StateID)
);

CREATE TABLE IF NOT EXISTS CasteMaster (
    caste_master_id INTEGER PRIMARY KEY,
    caste_master_name VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS ReligionMaster (
    ReligionID INTEGER PRIMARY KEY,
    ReligionName VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS OccupationMaster (
    OccupationID INTEGER PRIMARY KEY,
    OccupationName VARCHAR NOT NULL
);

-- ============================================================
-- CaseMaster — the FIR anchor
-- ============================================================
CREATE TABLE IF NOT EXISTS CaseMaster (
    CaseMasterID INTEGER PRIMARY KEY,
    CrimeNo VARCHAR UNIQUE NOT NULL,
    CaseNo VARCHAR NOT NULL,
    CrimeRegisteredDate DATE NOT NULL,
    PolicePersonID INTEGER NOT NULL,
    PoliceStationID INTEGER NOT NULL,
    CaseCategoryID INTEGER NOT NULL,
    GravityOffenceID INTEGER NOT NULL,
    CrimeMajorHeadID INTEGER NOT NULL,
    CrimeMinorHeadID INTEGER NOT NULL,
    CaseStatusID INTEGER NOT NULL,
    CourtID INTEGER,
    IncidentFromDate DATETIME,
    IncidentToDate DATETIME,
    InfoReceivedPSDate DATETIME,
    latitude REAL,
    longitude REAL,
    BriefFacts TEXT,
    FOREIGN KEY (PolicePersonID) REFERENCES Employee(EmployeeID),
    FOREIGN KEY (PoliceStationID) REFERENCES Unit(UnitID),
    FOREIGN KEY (CaseCategoryID) REFERENCES CaseCategory(CaseCategoryID),
    FOREIGN KEY (GravityOffenceID) REFERENCES GravityOffence(GravityOffenceID),
    FOREIGN KEY (CrimeMajorHeadID) REFERENCES CrimeHead(CrimeHeadID),
    FOREIGN KEY (CrimeMinorHeadID) REFERENCES CrimeSubHead(CrimeSubHeadID),
    FOREIGN KEY (CaseStatusID) REFERENCES CaseStatusMaster(CaseStatusID),
    FOREIGN KEY (CourtID) REFERENCES Court(CourtID)
);

-- ============================================================
-- People on a case: complainant / victim / accused
-- ============================================================
CREATE TABLE IF NOT EXISTS ComplainantDetails (
    ComplainantID INTEGER PRIMARY KEY,
    CaseMasterID INTEGER NOT NULL,
    ComplainantName VARCHAR NOT NULL,
    AgeYear INTEGER,
    OccupationID INTEGER,
    ReligionID INTEGER,
    CasteID INTEGER,
    GenderID INTEGER,
    FOREIGN KEY (CaseMasterID) REFERENCES CaseMaster(CaseMasterID),
    FOREIGN KEY (OccupationID) REFERENCES OccupationMaster(OccupationID),
    FOREIGN KEY (ReligionID) REFERENCES ReligionMaster(ReligionID),
    FOREIGN KEY (CasteID) REFERENCES CasteMaster(caste_master_id)
);

CREATE TABLE IF NOT EXISTS Victim (
    VictimMasterID INTEGER PRIMARY KEY,
    CaseMasterID INTEGER NOT NULL,
    VictimName VARCHAR NOT NULL,
    AgeYear INTEGER,
    GenderID INTEGER,
    VictimPolice VARCHAR DEFAULT '0',
    FOREIGN KEY (CaseMasterID) REFERENCES CaseMaster(CaseMasterID)
);

CREATE TABLE IF NOT EXISTS Accused (
    AccusedMasterID INTEGER PRIMARY KEY,
    CaseMasterID INTEGER NOT NULL,
    AccusedName VARCHAR NOT NULL,
    AgeYear INTEGER,
    GenderID INTEGER,
    PersonID VARCHAR,  -- Sorting label A1/A2/A3
    FOREIGN KEY (CaseMasterID) REFERENCES CaseMaster(CaseMasterID)
);

-- ============================================================
-- Arrest / surrender
-- ============================================================
CREATE TABLE IF NOT EXISTS ArrestSurrender (
    ArrestSurrenderID INTEGER PRIMARY KEY,
    CaseMasterID INTEGER NOT NULL,
    ArrestSurrenderTypeID INTEGER,
    ArrestSurrenderDate DATE,
    ArrestSurrenderStateId INTEGER,
    ArrestSurrenderDistrictId INTEGER,
    PoliceStationID INTEGER,
    IOID INTEGER,
    CourtID INTEGER,
    AccusedMasterID INTEGER,
    IsAccused INTEGER DEFAULT 1,
    IsComplainantAccused INTEGER DEFAULT 0,
    FOREIGN KEY (CaseMasterID) REFERENCES CaseMaster(CaseMasterID),
    FOREIGN KEY (ArrestSurrenderStateId) REFERENCES State(StateID),
    FOREIGN KEY (ArrestSurrenderDistrictId) REFERENCES District(DistrictID),
    FOREIGN KEY (PoliceStationID) REFERENCES Unit(UnitID),
    FOREIGN KEY (IOID) REFERENCES Employee(EmployeeID),
    FOREIGN KEY (CourtID) REFERENCES Court(CourtID),
    FOREIGN KEY (AccusedMasterID) REFERENCES Accused(AccusedMasterID)
);

-- Junction so one arrest event can link many accused (per ER).
CREATE TABLE IF NOT EXISTS inv_arrestsurrenderaccused (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    ArrestSurrenderID INTEGER NOT NULL,
    AccusedMasterID INTEGER NOT NULL,
    FOREIGN KEY (ArrestSurrenderID) REFERENCES ArrestSurrender(ArrestSurrenderID),
    FOREIGN KEY (AccusedMasterID) REFERENCES Accused(AccusedMasterID)
);

-- ============================================================
-- Act-Section applied to a case
-- ============================================================
CREATE TABLE IF NOT EXISTS ActSectionAssociation (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    CaseMasterID INTEGER NOT NULL,
    ActID VARCHAR NOT NULL,
    SectionID VARCHAR NOT NULL,
    ActOrderID INTEGER,
    SectionOrderID INTEGER,
    FOREIGN KEY (CaseMasterID) REFERENCES CaseMaster(CaseMasterID),
    FOREIGN KEY (ActID) REFERENCES Act(ActCode)
);

-- ============================================================
-- Chargesheet
-- ============================================================
CREATE TABLE IF NOT EXISTS ChargesheetDetails (
    CSID INTEGER PRIMARY KEY,
    CaseMasterID INTEGER NOT NULL,
    csdate DATETIME,
    cstype CHAR(1),  -- A=Chargesheet, B=False, C=Undetected
    PolicePersonID INTEGER,
    FOREIGN KEY (CaseMasterID) REFERENCES CaseMaster(CaseMasterID),
    FOREIGN KEY (PolicePersonID) REFERENCES Employee(EmployeeID)
);

-- ============================================================
-- Cross-case entity resolution (not in ER — needed for network graph
-- to link the same accused across multiple FIRs).
-- Populated nightly by a Catalyst Cron -> Function job.
-- ============================================================
CREATE TABLE IF NOT EXISTS PersonAlias (
    ClusterID INTEGER NOT NULL,       -- canonical person id
    AccusedMasterID INTEGER NOT NULL,
    similarity REAL,                  -- 0..1 match confidence
    PRIMARY KEY (ClusterID, AccusedMasterID),
    FOREIGN KEY (AccusedMasterID) REFERENCES Accused(AccusedMasterID)
);

-- ============================================================
-- Audit trail (Catalyst Data Store; also written locally)
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    query TEXT,
    sql TEXT,
    result_summary TEXT,
    timestamp TEXT NOT NULL
);

-- ============================================================
-- Conversation persistence (context-aware chat that survives
-- reloads; the unit of PDF export). Application tables.
-- ============================================================
CREATE TABLE IF NOT EXISTS conversation (
    ConversationID INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    title TEXT,
    started_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_turn (
    TurnID INTEGER PRIMARY KEY AUTOINCREMENT,
    ConversationID INTEGER NOT NULL,
    turn_role TEXT NOT NULL,           -- 'user' | 'assistant'
    content TEXT,
    sql TEXT,
    row_count INTEGER,
    language TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (ConversationID) REFERENCES conversation(ConversationID)
);
CREATE INDEX IF NOT EXISTS idx_turn_conv ON conversation_turn(ConversationID);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_case_date ON CaseMaster(CrimeRegisteredDate);
CREATE INDEX IF NOT EXISTS idx_case_station ON CaseMaster(PoliceStationID);
CREATE INDEX IF NOT EXISTS idx_case_status ON CaseMaster(CaseStatusID);
CREATE INDEX IF NOT EXISTS idx_case_head ON CaseMaster(CrimeMajorHeadID);
CREATE INDEX IF NOT EXISTS idx_case_subhead ON CaseMaster(CrimeMinorHeadID);
CREATE INDEX IF NOT EXISTS idx_case_officer ON CaseMaster(PolicePersonID);
CREATE INDEX IF NOT EXISTS idx_accused_case ON Accused(CaseMasterID);
CREATE INDEX IF NOT EXISTS idx_victim_case ON Victim(CaseMasterID);
CREATE INDEX IF NOT EXISTS idx_complainant_case ON ComplainantDetails(CaseMasterID);
CREATE INDEX IF NOT EXISTS idx_asa_case ON ActSectionAssociation(CaseMasterID);
CREATE INDEX IF NOT EXISTS idx_arrest_case ON ArrestSurrender(CaseMasterID);
CREATE INDEX IF NOT EXISTS idx_arrest_io ON ArrestSurrender(IOID);
CREATE INDEX IF NOT EXISTS idx_cs_case ON ChargesheetDetails(CaseMasterID);
CREATE INDEX IF NOT EXISTS idx_unit_district ON Unit(DistrictID);
CREATE INDEX IF NOT EXISTS idx_employee_unit ON Employee(UnitID);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def cursor():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


@contextmanager
def read_cursor():
    """Read-only connection — used to execute LLM-generated SQL so even a
    guardrail bypass cannot mutate the database (defense in depth)."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_schema() -> None:
    with cursor() as conn:
        conn.executescript(SCHEMA)


def is_seeded() -> bool:
    if not DB_PATH.exists():
        return False
    with cursor() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM sqlite_master "
            "WHERE type='table' AND name='CaseMaster'"
        ).fetchone()
        if row["n"] == 0:
            return False
        row = conn.execute("SELECT COUNT(*) AS n FROM CaseMaster").fetchone()
        return row["n"] > 0


# ----------------------------------------------------------------------------
# Schema document shown to the LLM. Kept in sync with the DDL above by hand;
# used for QuickML RAG grounding and Claude system prompt.
# ----------------------------------------------------------------------------
LLM_SCHEMA_DOC = """
Karnataka FIR schema (SQLite / Catalyst Data Store). Column names are
CamelCase as in the KP ER diagram. The anchor entity is CaseMaster.

-- CASE ANCHOR --
CaseMaster(CaseMasterID PK, CrimeNo UNIQUE, CaseNo, CrimeRegisteredDate DATE,
  PolicePersonID -> Employee.EmployeeID   -- officer who registered the FIR
  PoliceStationID -> Unit.UnitID          -- station where FIR filed
  CaseCategoryID -> CaseCategory          -- FIR / UDR / Zero FIR / PAR
  GravityOffenceID -> GravityOffence      -- Heinous / Non-Heinous
  CrimeMajorHeadID -> CrimeHead
  CrimeMinorHeadID -> CrimeSubHead
  CaseStatusID -> CaseStatusMaster        -- Under Investigation / Charge Sheeted / Closed
  CourtID -> Court
  IncidentFromDate, IncidentToDate DATETIME,
  InfoReceivedPSDate DATETIME,
  latitude, longitude, BriefFacts TEXT)

-- PEOPLE ON A CASE --
ComplainantDetails(ComplainantID PK, CaseMasterID FK, ComplainantName,
  AgeYear, OccupationID->OccupationMaster, ReligionID->ReligionMaster,
  CasteID->CasteMaster.caste_master_id, GenderID)
Victim(VictimMasterID PK, CaseMasterID FK, VictimName, AgeYear, GenderID,
  VictimPolice)   -- '1' if the victim is a police officer
Accused(AccusedMasterID PK, CaseMasterID FK, AccusedName, AgeYear, GenderID,
  PersonID)  -- PersonID is a sort label like A1, A2

-- ARREST + JUNCTION (one arrest event, many accused) --
ArrestSurrender(ArrestSurrenderID PK, CaseMasterID FK,
  ArrestSurrenderTypeID, ArrestSurrenderDate DATE,
  ArrestSurrenderStateId->State, ArrestSurrenderDistrictId->District,
  PoliceStationID->Unit, IOID->Employee.EmployeeID, CourtID->Court,
  AccusedMasterID->Accused)
inv_arrestsurrenderaccused(ArrestSurrenderID FK, AccusedMasterID FK)

-- LEGAL --
Act(ActCode PK, ActDescription, ShortName)   -- IPC, NDPS, IT Act, MV Act, CrPC
Section(ActCode FK, SectionCode, SectionDescription)  -- 302, 307, 379, 420...
ActSectionAssociation(CaseMasterID FK, ActID->Act.ActCode,
  SectionID->Section.SectionCode)
CrimeHead(CrimeHeadID PK, CrimeGroupName)          -- 'Crimes Against Body', ...
CrimeSubHead(CrimeSubHeadID PK, CrimeHeadID FK, CrimeHeadName)  -- 'Murder', ...
CrimeHeadActSection(CrimeHeadID FK, ActCode FK, SectionCode)

-- CHARGESHEET --
ChargesheetDetails(CSID PK, CaseMasterID FK, csdate DATETIME,
  cstype CHAR(1),  -- 'A'=chargesheet, 'B'=false case, 'C'=undetected
  PolicePersonID->Employee.EmployeeID)

-- GEOGRAPHY --
State(StateID PK, StateName)
District(DistrictID PK, DistrictName, StateID FK)
DistrictGeo(DistrictID PK, latitude, longitude, population)
UnitType(UnitTypeID PK, UnitTypeName, CityDistState, Hierarchy)
Unit(UnitID PK, UnitName, TypeID->UnitType, ParentUnit->Unit (self),
  StateID FK, DistrictID FK, latitude, longitude)

-- HR --
Rank(RankID PK, RankName, Hierarchy)
Designation(DesignationID PK, DesignationName)
Employee(EmployeeID PK, DistrictID FK, UnitID FK, RankID FK,
  DesignationID FK, KGID, FirstName, EmployeeDOB DATE, GenderID)

-- DEMOGRAPHICS (SENSITIVE — aggregate-only for non-admin roles) --
CasteMaster(caste_master_id PK, caste_master_name)
ReligionMaster(ReligionID PK, ReligionName)
OccupationMaster(OccupationID PK, OccupationName)

-- LOOKUPS --
CaseCategory(CaseCategoryID PK, LookupValue)          -- FIR / UDR / Zero FIR / PAR
GravityOffence(GravityOffenceID PK, LookupValue)      -- Heinous / Non-Heinous
CaseStatusMaster(CaseStatusID PK, CaseStatusName)     -- Under Investigation / ...
Court(CourtID PK, CourtName, DistrictID FK, StateID FK)

-- CROSS-CASE PERSON RESOLUTION (nightly job) --
PersonAlias(ClusterID, AccusedMasterID FK, similarity)  -- same ClusterID = same real person

Guidance for SQL generation:
- SELECT-only. Single statement. No semicolons.
- Aliases: c for CaseMaster, u for Unit, d for District, e for Employee,
  a for Accused, v for Victim, cd for ComplainantDetails,
  cs for ChargesheetDetails, asa for ActSectionAssociation.
- Trends group by strftime('%Y-%m', c.CrimeRegisteredDate) and
  CrimeHead.CrimeGroupName.
- Hotspots aggregate by d.DistrictID JOIN DistrictGeo for map coords.
- Network of co-accused: self-JOIN Accused ON same CaseMasterID with
  a1.AccusedMasterID < a2.AccusedMasterID.
- Cross-case network: join Accused -> PersonAlias to canonicalize identity.
- "Chargesheeting rate for IO X" = COUNT(cs.cstype='A') / COUNT(cases where
  PolicePersonID=X). Prefer csdate over CrimeRegisteredDate for time filters
  on chargesheet outcomes.
- Kannada synonyms:
    ಬೆಂಗಳೂರು = Bengaluru; ಮೈಸೂರು = Mysuru; ಮಂಗಳೂರು = Mangaluru;
    ಕೊಲೆ = Murder; ಕಳ್ಳತನ = Theft; ಸೈಬರ್ = Cyber.
"""
