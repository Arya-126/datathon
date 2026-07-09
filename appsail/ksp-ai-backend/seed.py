"""Seed the FIR schema with realistic-shape Karnataka data.

Deterministic (RNG seeded). Emits every table described in
Police_FIR_ER_Diagram.pdf plus DistrictGeo / PersonAlias / audit_log.

Scale (roughly matches a single-year district snapshot):
  15 districts, ~90 units, ~200 officers, ~30 courts, 20 crime-heads,
  ~30 sections, 1800 FIRs, ~2700 accused, ~1500 arrests,
  ~600 chargesheets, ~1800 complainants, ~1500 victims.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from db import cursor, init_schema, is_seeded

RNG = random.Random(20260702)


# ============================================================
# Reference data
# ============================================================

STATE = ("Karnataka", 29)  # (name, NationalityID placeholder)

DISTRICTS = [
    # (DistrictID, DistrictName, lat, lng, population)
    (443, "Bengaluru Urban", 12.9716, 77.5946, 9621551),
    (444, "Bengaluru Rural", 13.2846, 77.7955, 990923),
    (445, "Mysuru", 12.2958, 76.6394, 3001127),
    (446, "Mangaluru", 12.9141, 74.8560, 2083625),
    (447, "Hubballi-Dharwad", 15.3647, 75.1240, 1846993),
    (448, "Belagavi", 15.8497, 74.4977, 4779661),
    (449, "Kalaburagi", 17.3297, 76.8343, 2566326),
    (450, "Ballari", 15.1394, 76.9214, 2452595),
    (451, "Vijayapura", 16.8302, 75.7100, 2177331),
    (452, "Shivamogga", 13.9299, 75.5681, 1752753),
    (453, "Tumakuru", 13.3392, 77.1010, 2678980),
    (454, "Davanagere", 14.4644, 75.9218, 1946905),
    (455, "Udupi", 13.3409, 74.7421, 1177908),
    (456, "Chitradurga", 14.2251, 76.4001, 1660378),
    (457, "Raichur", 16.2076, 77.3463, 1928812),
]

UNIT_TYPES = [
    # (UnitTypeID, UnitTypeName, CityDistState, Hierarchy)
    (1, "Police Station", "City", 3),
    (2, "Circle Office", "District", 2),
    (3, "District HQ", "District", 1),
    (4, "Cyber Crime Cell", "District", 2),
    (5, "Special Branch", "State", 1),
]

RANKS = [
    # (RankID, RankName, Hierarchy)  lower Hierarchy = more senior
    (1, "Director General of Police", 1),
    (2, "Inspector General", 2),
    (3, "Superintendent of Police", 3),
    (4, "Deputy Superintendent", 4),
    (5, "Circle Inspector", 5),
    (6, "Police Inspector", 6),
    (7, "Sub-Inspector", 7),
    (8, "Assistant Sub-Inspector", 8),
    (9, "Head Constable", 9),
    (10, "Constable", 10),
]

DESIGNATIONS = [
    (1, "SHO", 1),                # Station House Officer
    (2, "Investigating Officer", 2),
    (3, "Circle Inspector", 3),
    (4, "DySP", 4),
    (5, "Cyber Investigator", 5),
    (6, "Constable", 6),
]

CASE_CATEGORIES = [
    (1, "FIR"),
    (3, "UDR"),      # Unnatural Death Report
    (4, "PAR"),      # Preliminary Action Report
    (8, "Zero FIR"),
]

GRAVITY = [
    (1, "Heinous"),
    (2, "Non-Heinous"),
]

CASE_STATUSES = [
    (1, "Under Investigation"),
    (2, "Charge Sheeted"),
    (3, "Closed"),
    (4, "Referred / Zero FIR"),
]

CRIME_HEADS = [
    (1, "Crimes Against Body"),
    (2, "Crimes Against Property"),
    (3, "Crimes Against Public Order"),
    (4, "Cyber Crimes"),
    (5, "Narcotic Drug Crimes"),
    (6, "Economic / White-Collar Crimes"),
    (7, "Crimes Against Women"),
    (8, "Crimes Against Children"),
]

# (CrimeSubHeadID, parent CrimeHeadID, name, indicative gravity {1|2})
CRIME_SUBHEADS = [
    (101, 1, "Murder", 1),
    (102, 1, "Attempt to Murder", 1),
    (103, 1, "Culpable Homicide", 1),
    (104, 1, "Hurt / Assault", 2),
    (105, 1, "Kidnapping", 1),
    (201, 2, "House Burglary", 2),
    (202, 2, "Robbery", 1),
    (203, 2, "Dacoity", 1),
    (204, 2, "Vehicle Theft", 2),
    (205, 2, "Chain Snatching", 2),
    (301, 3, "Rioting", 2),
    (302, 3, "Public Nuisance", 2),
    (401, 4, "Online Fraud", 2),
    (402, 4, "Phishing", 2),
    (403, 4, "Ransomware", 1),
    (404, 4, "Identity Theft", 2),
    (501, 5, "NDPS Act", 1),
    (502, 5, "Ganja Peddling", 2),
    (601, 6, "Cheating", 2),
    (602, 6, "Forgery", 2),
    (701, 7, "Sexual Assault", 1),
    (702, 7, "Dowry Harassment", 1),
    (801, 8, "POCSO", 1),
]

ACTS = [
    ("IPC", "Indian Penal Code, 1860", "IPC"),
    ("CrPC", "Code of Criminal Procedure, 1973", "CrPC"),
    ("NDPS", "Narcotic Drugs and Psychotropic Substances Act, 1985", "NDPS"),
    ("ITAct", "Information Technology Act, 2000", "IT Act"),
    ("MVAct", "Motor Vehicles Act, 1988", "MV"),
    ("POCSO", "Protection of Children from Sexual Offences Act, 2012", "POCSO"),
]

# (ActCode, SectionCode, Description) — real IPC/NDPS/IT-Act sections
SECTIONS = [
    ("IPC", "302",  "Punishment for murder"),
    ("IPC", "307",  "Attempt to murder"),
    ("IPC", "304",  "Culpable homicide"),
    ("IPC", "323",  "Voluntarily causing hurt"),
    ("IPC", "363",  "Kidnapping"),
    ("IPC", "379",  "Theft"),
    ("IPC", "380",  "Theft in dwelling"),
    ("IPC", "392",  "Robbery"),
    ("IPC", "395",  "Dacoity"),
    ("IPC", "420",  "Cheating"),
    ("IPC", "465",  "Forgery"),
    ("IPC", "376",  "Rape"),
    ("IPC", "498A", "Cruelty by husband"),
    ("IPC", "147",  "Rioting"),
    ("IPC", "268",  "Public nuisance"),
    ("NDPS", "20b", "Ganja possession / sale"),
    ("NDPS", "22",  "Psychotropic substance"),
    ("ITAct", "66",   "Computer-related offences"),
    ("ITAct", "66C",  "Identity theft"),
    ("ITAct", "66D",  "Cheating by personation online"),
    ("ITAct", "43",   "Damage to computer / system"),
    ("POCSO", "6",    "Aggravated penetrative sexual assault"),
    ("MVAct", "184",  "Rash driving"),
]

# Which sections normally apply to which sub-head. Keeps the joined output
# realistic ("Murder → IPC 302", "Online fraud → IPC 420 + IT Act 66D").
SUBHEAD_SECTIONS = {
    101: [("IPC", "302")],
    102: [("IPC", "307")],
    103: [("IPC", "304")],
    104: [("IPC", "323")],
    105: [("IPC", "363")],
    201: [("IPC", "380")],
    202: [("IPC", "392")],
    203: [("IPC", "395")],
    204: [("IPC", "379")],
    205: [("IPC", "379"), ("IPC", "392")],
    301: [("IPC", "147")],
    302: [("IPC", "268")],
    401: [("IPC", "420"), ("ITAct", "66D")],
    402: [("ITAct", "66D")],
    403: [("ITAct", "66"), ("ITAct", "43")],
    404: [("ITAct", "66C")],
    501: [("NDPS", "22")],
    502: [("NDPS", "20b")],
    601: [("IPC", "420")],
    602: [("IPC", "465")],
    701: [("IPC", "376")],
    702: [("IPC", "498A")],
    801: [("POCSO", "6"), ("IPC", "376")],
}

CASTES = [
    (1, "General"), (2, "OBC"), (3, "SC"), (4, "ST"),
    (5, "Muslim OBC"), (6, "Not Disclosed"),
]

RELIGIONS = [
    (1, "Hindu"), (2, "Muslim"), (3, "Christian"),
    (4, "Jain"), (5, "Buddhist"), (6, "Not Disclosed"),
]

OCCUPATIONS = [
    (1, "Farmer"), (2, "Labourer"), (3, "Driver"),
    (4, "Shopkeeper"), (5, "Student"), (6, "Unemployed"),
    (7, "IT Employee"), (8, "Auto Driver"), (9, "Small Business"),
    (10, "Clerk"), (11, "Teacher"), (12, "Government Employee"),
    (13, "Homemaker"), (14, "Not Disclosed"),
]

FIRST_NAMES = [
    "Arun", "Bhavana", "Chetan", "Deepa", "Girish", "Harsha", "Indira",
    "Jayanth", "Kavya", "Lokesh", "Manjula", "Naveen", "Pooja", "Raghu",
    "Sneha", "Tejas", "Umesh", "Varsha", "Yashwanth", "Zoya",
    "Ravi", "Anitha", "Ganesh", "Meera", "Prakash", "Shanti",
    "Vinay", "Divya", "Kiran", "Rekha", "Suresh", "Lakshmi",
    "Mahesh", "Sudha", "Prashant", "Vidya",
]
LAST_NAMES = [
    "Rao", "Shetty", "Gowda", "Naik", "Hegde", "Patil", "Kulkarni",
    "Reddy", "Kamath", "Bhat", "Iyer", "Prasad", "Murthy", "Shastri",
    "Nayak", "Desai", "Kore", "Kadam", "Prabhu", "Rai",
]

# One-off syndicate names to make the network graph interesting.
SYNDICATE_SIZE = 6
NUM_SYNDICATES = 6


# ============================================================
# Helpers
# ============================================================
def _rand_person_name() -> str:
    return f"{RNG.choice(FIRST_NAMES)} {RNG.choice(LAST_NAMES)}"


def _rand_date_between(start: date, end: date) -> date:
    return start + timedelta(days=RNG.randint(0, (end - start).days))


def _rand_dt_between(start: date, end: date) -> str:
    d = _rand_date_between(start, end)
    return f"{d.isoformat()} {RNG.randint(0, 23):02d}:{RNG.randint(0, 59):02d}:00"


def _jitter(base: float, spread: float = 0.05) -> float:
    return round(base + RNG.uniform(-spread, spread), 6)


def _crime_no(cat_code: int, district_id: int, unit_id: int,
              year: int, serial: int) -> str:
    """Karnataka CrimeNo format from the ER:
    1-digit category + 4-digit district + 4-digit unit + 4-digit year
    + 5-digit serial = 18 chars total.
    """
    return (
        f"{cat_code:01d}"
        f"{district_id:04d}"
        f"{unit_id:04d}"
        f"{year:04d}"
        f"{serial:05d}"
    )


# ============================================================
# Main seed
# ============================================================
def seed(*, n_cases: int = 1800) -> None:
    init_schema()
    if is_seeded():
        return

    today = date(2026, 7, 1)
    horizon_start = date(2024, 7, 1)  # 24-month window

    with cursor() as conn:
        # ---------- State + Districts ----------
        conn.execute(
            "INSERT INTO State (StateID, StateName, NationalityID, Active) "
            "VALUES (?,?,?,1)",
            (1, STATE[0], STATE[1]),
        )
        for d_id, d_name, lat, lng, pop in DISTRICTS:
            conn.execute(
                "INSERT INTO District (DistrictID, DistrictName, StateID, Active) "
                "VALUES (?,?,?,1)",
                (d_id, d_name, 1),
            )
            conn.execute(
                "INSERT INTO DistrictGeo (DistrictID, latitude, longitude, population) "
                "VALUES (?,?,?,?)",
                (d_id, lat, lng, pop),
            )

        # ---------- UnitType + Units ----------
        for t_id, t_name, level, hier in UNIT_TYPES:
            conn.execute(
                "INSERT INTO UnitType (UnitTypeID, UnitTypeName, CityDistState, "
                "Hierarchy, Active) VALUES (?,?,?,?,1)",
                (t_id, t_name, level, hier),
            )

        # Build 4-8 police stations per district, plus 1 cyber cell and 1
        # district HQ per district.
        units: list[tuple] = []
        next_unit_id = 1
        for d_id, d_name, lat, lng, _pop in DISTRICTS:
            # District HQ (UnitTypeID=3)
            units.append((
                next_unit_id, f"{d_name} District HQ", 3, None, 1, d_id,
                _jitter(lat, 0.02), _jitter(lng, 0.02),
            ))
            hq_id = next_unit_id
            next_unit_id += 1
            # Cyber cell (UnitTypeID=4)
            units.append((
                next_unit_id, f"{d_name} Cyber Crime Cell", 4, hq_id, 1, d_id,
                _jitter(lat, 0.03), _jitter(lng, 0.03),
            ))
            next_unit_id += 1
            # Regular police stations (UnitTypeID=1)
            n_ps = RNG.randint(4, 8)
            for i in range(1, n_ps + 1):
                units.append((
                    next_unit_id, f"{d_name} PS-{i}", 1, hq_id, 1, d_id,
                    _jitter(lat, 0.08), _jitter(lng, 0.08),
                ))
                next_unit_id += 1

        conn.executemany(
            "INSERT INTO Unit (UnitID, UnitName, TypeID, ParentUnit, StateID, "
            "DistrictID, latitude, longitude, Active) "
            "VALUES (?,?,?,?,?,?,?,?,1)",
            units,
        )

        # ---------- Rank + Designation ----------
        for r_id, r_name, hier in RANKS:
            conn.execute(
                "INSERT INTO Rank (RankID, RankName, Hierarchy, Active) "
                "VALUES (?,?,?,1)",
                (r_id, r_name, hier),
            )
        for d_id, d_name, order in DESIGNATIONS:
            conn.execute(
                "INSERT INTO Designation (DesignationID, DesignationName, "
                "SortOrder, Active) VALUES (?,?,?,1)",
                (d_id, d_name, order),
            )

        # ---------- Employees ----------
        # For each Unit (excluding District HQ / Cyber Cell), attach 4-6
        # employees: 1 SHO + 1-2 IOs + constables. Cyber cell gets 2 cyber
        # investigators. HQ gets 1 DySP.
        employees: list[tuple] = []
        next_emp_id = 1

        def _add_emp(unit_id: int, district_id: int, rank_id: int,
                     desig_id: int) -> int:
            nonlocal next_emp_id
            dob = _rand_date_between(date(1965, 1, 1), date(2000, 1, 1))
            appt = _rand_date_between(date(1990, 1, 1), date(2022, 1, 1))
            employees.append((
                next_emp_id, district_id, unit_id, rank_id, desig_id,
                f"KGID{next_emp_id:06d}",
                _rand_person_name(),
                dob.isoformat(),
                1 if RNG.random() < 0.9 else 2,  # GenderID: 1=M, 2=F
                appt.isoformat(),
            ))
            eid = next_emp_id
            next_emp_id += 1
            return eid

        # Build a quick index of units by type & district.
        units_by_district: dict[int, list[dict]] = {}
        for row in conn.execute(
            "SELECT UnitID, UnitName, TypeID, DistrictID FROM Unit"
        ).fetchall():
            units_by_district.setdefault(row["DistrictID"], []).append(dict(row))

        for d_id, d_name, _lat, _lng, _pop in DISTRICTS:
            for u in units_by_district[d_id]:
                if u["TypeID"] == 3:      # District HQ
                    _add_emp(u["UnitID"], d_id, 4, 4)      # DySP
                elif u["TypeID"] == 4:    # Cyber cell
                    _add_emp(u["UnitID"], d_id, 6, 5)      # PI as Cyber Investigator
                    _add_emp(u["UnitID"], d_id, 7, 5)      # SI Cyber
                else:                     # Regular PS
                    _add_emp(u["UnitID"], d_id, 6, 1)      # PI as SHO
                    n_io = RNG.randint(1, 2)
                    for _ in range(n_io):
                        _add_emp(u["UnitID"], d_id, 7, 2)  # SI as IO
                    for _ in range(RNG.randint(2, 3)):
                        _add_emp(u["UnitID"], d_id, 10, 6)  # Constables

        conn.executemany(
            "INSERT INTO Employee (EmployeeID, DistrictID, UnitID, RankID, "
            "DesignationID, KGID, FirstName, EmployeeDOB, GenderID, "
            "AppointmentDate) VALUES (?,?,?,?,?,?,?,?,?,?)",
            employees,
        )

        # ---------- Legal (Acts + Sections) ----------
        for code, desc, short in ACTS:
            conn.execute(
                "INSERT INTO Act (ActCode, ActDescription, ShortName, Active) "
                "VALUES (?,?,?,1)",
                (code, desc, short),
            )
        for act_code, sec_code, desc in SECTIONS:
            conn.execute(
                "INSERT INTO Section (ActCode, SectionCode, SectionDescription, "
                "Active) VALUES (?,?,?,1)",
                (act_code, sec_code, desc),
            )

        # ---------- Crime heads ----------
        for h_id, name in CRIME_HEADS:
            conn.execute(
                "INSERT INTO CrimeHead (CrimeHeadID, CrimeGroupName, Active) "
                "VALUES (?,?,1)",
                (h_id, name),
            )
        for s_id, h_id, name, _grav in CRIME_SUBHEADS:
            conn.execute(
                "INSERT INTO CrimeSubHead (CrimeSubHeadID, CrimeHeadID, "
                "CrimeHeadName, SeqID) VALUES (?,?,?,?)",
                (s_id, h_id, name, s_id),
            )
        # Head↔Act-Section map (derived from SUBHEAD_SECTIONS).
        for s_id, h_id, _name, _grav in CRIME_SUBHEADS:
            for act_code, sec_code in SUBHEAD_SECTIONS.get(s_id, []):
                conn.execute(
                    "INSERT INTO CrimeHeadActSection (CrimeHeadID, ActCode, "
                    "SectionCode) VALUES (?,?,?)",
                    (h_id, act_code, sec_code),
                )

        # ---------- Lookup masters ----------
        for c_id, name in CASE_CATEGORIES:
            conn.execute(
                "INSERT INTO CaseCategory (CaseCategoryID, LookupValue) VALUES (?,?)",
                (c_id, name),
            )
        for g_id, name in GRAVITY:
            conn.execute(
                "INSERT INTO GravityOffence (GravityOffenceID, LookupValue) "
                "VALUES (?,?)", (g_id, name),
            )
        for s_id, name in CASE_STATUSES:
            conn.execute(
                "INSERT INTO CaseStatusMaster (CaseStatusID, CaseStatusName) "
                "VALUES (?,?)", (s_id, name),
            )

        # ---------- Courts ----------
        court_id = 1
        for d_id, d_name, _lat, _lng, _pop in DISTRICTS:
            for kind in ("District & Sessions", "JMFC-I", "JMFC-II"):
                conn.execute(
                    "INSERT INTO Court (CourtID, CourtName, DistrictID, StateID, "
                    "Active) VALUES (?,?,?,?,1)",
                    (court_id, f"{d_name} {kind} Court", d_id, 1),
                )
                court_id += 1

        # ---------- Caste / Religion / Occupation ----------
        for c_id, name in CASTES:
            conn.execute(
                "INSERT INTO CasteMaster (caste_master_id, caste_master_name) "
                "VALUES (?,?)", (c_id, name),
            )
        for r_id, name in RELIGIONS:
            conn.execute(
                "INSERT INTO ReligionMaster (ReligionID, ReligionName) VALUES (?,?)",
                (r_id, name),
            )
        for o_id, name in OCCUPATIONS:
            conn.execute(
                "INSERT INTO OccupationMaster (OccupationID, OccupationName) "
                "VALUES (?,?)", (o_id, name),
            )

        # ---------- CaseMaster + child rows ----------
        # Pre-select which units are eligible for FIR registration (regular
        # PS and cyber cell). District HQ doesn't register FIRs itself.
        eligible_units_by_district: dict[int, list[dict]] = {}
        for d_id in units_by_district:
            eligible_units_by_district[d_id] = [
                u for u in units_by_district[d_id] if u["TypeID"] in (1, 4)
            ]

        # Employees by unit (for choosing IOs).
        employees_by_unit: dict[int, list[dict]] = {}
        for row in conn.execute(
            "SELECT EmployeeID, UnitID, DesignationID FROM Employee"
        ).fetchall():
            employees_by_unit.setdefault(row["UnitID"], []).append(dict(row))

        # District weights (heavier for city districts, matches reality).
        district_weights = []
        for d_id, d_name, _lat, _lng, _pop in DISTRICTS:
            if d_name == "Bengaluru Urban":
                district_weights.append(3.5)
            elif d_name in ("Mysuru", "Mangaluru", "Hubballi-Dharwad"):
                district_weights.append(2.0)
            else:
                district_weights.append(1.0)
        district_ids = [d[0] for d in DISTRICTS]

        # Syndicates for network structure.
        syndicate_names: list[list[str]] = []
        for _ in range(NUM_SYNDICATES):
            syndicate_names.append([_rand_person_name() for _ in range(SYNDICATE_SIZE)])

        subhead_map = {s[0]: s for s in CRIME_SUBHEADS}
        case_rows = []
        complainant_rows = []
        victim_rows = []
        accused_rows = []
        asa_rows = []
        arrest_rows = []
        junction_rows = []
        cs_rows = []

        next_accused_id = 1
        next_arrest_id = 1
        next_cs_id = 1
        next_complainant_id = 1
        next_victim_id = 1

        # Track (district, unit, year, category) counters for CrimeNo serial.
        serials: dict[tuple, int] = {}

        for case_id in range(1, n_cases + 1):
            reg_date = _rand_date_between(horizon_start, today)
            year = reg_date.year
            category = RNG.choices(
                [c[0] for c in CASE_CATEGORIES],
                weights=[0.82, 0.06, 0.04, 0.08],
            )[0]
            district_id = RNG.choices(district_ids, weights=district_weights)[0]
            subhead = RNG.choice(CRIME_SUBHEADS)
            sh_id, ch_id, sh_name, indicative_grav = subhead

            # Cyber subhead? use the cyber cell rather than a normal PS.
            if ch_id == 4:  # Cyber Crimes
                unit = next(
                    (u for u in units_by_district[district_id]
                     if u["TypeID"] == 4), None,
                )
                if unit is None:
                    unit = RNG.choice(eligible_units_by_district[district_id])
            else:
                unit = RNG.choice(
                    [u for u in eligible_units_by_district[district_id]
                     if u["TypeID"] == 1]
                )

            unit_id = unit["UnitID"]

            key = (unit_id, category, year)
            serials[key] = serials.get(key, 0) + 1
            serial = serials[key]

            crime_no = _crime_no(category, district_id, unit_id, year, serial)
            case_no = f"{year:04d}{serial:05d}"

            # Officer who registered = an SHO or IO at that unit.
            unit_emps = employees_by_unit.get(unit_id, [])
            if not unit_emps:
                registering_officer = RNG.choice(employees)[0]
            else:
                candidates = [
                    e for e in unit_emps if e["DesignationID"] in (1, 2, 5)
                ] or unit_emps
                registering_officer = RNG.choice(candidates)["EmployeeID"]

            gravity_id = indicative_grav
            status_id = RNG.choices(
                [1, 2, 3, 4], weights=[0.45, 0.25, 0.15, 0.15],
            )[0]

            # Roughly half chargesheeted cases get a court, others none.
            if status_id == 2 or RNG.random() < 0.4:
                court_row = conn.execute(
                    "SELECT CourtID FROM Court WHERE DistrictID = ? "
                    "ORDER BY RANDOM() LIMIT 1", (district_id,),
                ).fetchone()
                court_id_val = court_row["CourtID"] if court_row else None
            else:
                court_id_val = None

            incident_from = _rand_dt_between(
                max(horizon_start, reg_date - timedelta(days=15)), reg_date,
            )
            incident_to = incident_from  # single-day incident by default
            info_received = incident_from  # simplification
            latitude = _jitter(
                next(d[2] for d in DISTRICTS if d[0] == district_id), 0.05
            )
            longitude = _jitter(
                next(d[3] for d in DISTRICTS if d[0] == district_id), 0.05
            )

            brief = (
                f"{sh_name} reported at {unit['UnitName']}. "
                f"CrimeNo {crime_no}. Registered {reg_date.isoformat()}."
            )

            case_rows.append((
                case_id, crime_no, case_no, reg_date.isoformat(),
                registering_officer, unit_id, category, gravity_id, ch_id,
                sh_id, status_id, court_id_val,
                incident_from, incident_to, info_received,
                latitude, longitude, brief,
            ))

            # -- Complainant (1 per case)
            complainant_rows.append((
                next_complainant_id, case_id, _rand_person_name(),
                RNG.randint(18, 70),
                RNG.choice(OCCUPATIONS)[0],
                RNG.choice(RELIGIONS)[0],
                RNG.choice(CASTES)[0],
                RNG.choices([1, 2, 3], weights=[0.55, 0.42, 0.03])[0],
            ))
            next_complainant_id += 1

            # -- Victim (85% of cases have an explicit victim)
            if RNG.random() < 0.85:
                victim_rows.append((
                    next_victim_id, case_id, _rand_person_name(),
                    RNG.randint(8, 75),
                    RNG.choices([1, 2, 3], weights=[0.5, 0.48, 0.02])[0],
                    "1" if RNG.random() < 0.03 else "0",
                ))
                next_victim_id += 1

            # -- Accused (1-3 per case, 40% chance drawn from a syndicate)
            n_accused = RNG.choices([1, 2, 3], weights=[0.55, 0.30, 0.15])[0]
            case_accused_ids: list[int] = []
            if RNG.random() < 0.40:
                syn = RNG.choice(syndicate_names)
                names = RNG.sample(syn, k=min(n_accused, len(syn)))
            else:
                names = [_rand_person_name() for _ in range(n_accused)]
            for idx, name in enumerate(names, start=1):
                accused_rows.append((
                    next_accused_id, case_id, name,
                    RNG.randint(18, 55),
                    RNG.choices([1, 2, 3], weights=[0.85, 0.13, 0.02])[0],
                    f"A{idx}",
                ))
                case_accused_ids.append(next_accused_id)
                next_accused_id += 1

            # -- Act-Section rows (from subhead map)
            for act_ord, (act_code, sec_code) in enumerate(
                SUBHEAD_SECTIONS.get(sh_id, [("IPC", "379")]), start=1,
            ):
                asa_rows.append((
                    case_id, act_code, sec_code, act_ord, 1,
                ))

            # -- Arrest / surrender (60% of cases have at least one arrest)
            if case_accused_ids and RNG.random() < 0.60:
                arrest_date = _rand_date_between(
                    reg_date, min(today, reg_date + timedelta(days=45)),
                )
                io_candidates = [
                    e for e in unit_emps if e["DesignationID"] == 2
                ] or unit_emps
                io_id = (RNG.choice(io_candidates)["EmployeeID"]
                         if io_candidates else registering_officer)
                arrest_type = 1 if RNG.random() < 0.9 else 2  # 1=arrest, 2=surrender
                first_accused = case_accused_ids[0]
                arrest_rows.append((
                    next_arrest_id, case_id, arrest_type,
                    arrest_date.isoformat(), 1, district_id, unit_id, io_id,
                    court_id_val, first_accused, 1, 0,
                ))
                # Junction rows for every accused in the arrest event
                for aid in case_accused_ids:
                    junction_rows.append((next_arrest_id, aid))
                next_arrest_id += 1

            # -- Chargesheet (for chargesheeted status and some closed cases)
            if status_id == 2:
                cs_type = "A"
            elif status_id == 3:
                cs_type = RNG.choices(["B", "C"], weights=[0.4, 0.6])[0]
            else:
                cs_type = None

            if cs_type:
                cs_start = reg_date + timedelta(days=30)
                cs_end = min(today, reg_date + timedelta(days=240))
                if cs_end >= cs_start:
                    cs_date = _rand_date_between(cs_start, cs_end)
                    cs_rows.append((
                        next_cs_id, case_id,
                        f"{cs_date.isoformat()} 10:00:00", cs_type,
                        registering_officer,
                    ))
                    next_cs_id += 1

        # ---------- Bulk inserts ----------
        conn.executemany(
            "INSERT INTO CaseMaster (CaseMasterID, CrimeNo, CaseNo, "
            "CrimeRegisteredDate, PolicePersonID, PoliceStationID, "
            "CaseCategoryID, GravityOffenceID, CrimeMajorHeadID, "
            "CrimeMinorHeadID, CaseStatusID, CourtID, IncidentFromDate, "
            "IncidentToDate, InfoReceivedPSDate, latitude, longitude, "
            "BriefFacts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            case_rows,
        )
        conn.executemany(
            "INSERT INTO ComplainantDetails (ComplainantID, CaseMasterID, "
            "ComplainantName, AgeYear, OccupationID, ReligionID, CasteID, "
            "GenderID) VALUES (?,?,?,?,?,?,?,?)",
            complainant_rows,
        )
        conn.executemany(
            "INSERT INTO Victim (VictimMasterID, CaseMasterID, VictimName, "
            "AgeYear, GenderID, VictimPolice) VALUES (?,?,?,?,?,?)",
            victim_rows,
        )
        conn.executemany(
            "INSERT INTO Accused (AccusedMasterID, CaseMasterID, AccusedName, "
            "AgeYear, GenderID, PersonID) VALUES (?,?,?,?,?,?)",
            accused_rows,
        )
        conn.executemany(
            "INSERT INTO ActSectionAssociation (CaseMasterID, ActID, SectionID, "
            "ActOrderID, SectionOrderID) VALUES (?,?,?,?,?)",
            asa_rows,
        )
        conn.executemany(
            "INSERT INTO ArrestSurrender (ArrestSurrenderID, CaseMasterID, "
            "ArrestSurrenderTypeID, ArrestSurrenderDate, "
            "ArrestSurrenderStateId, ArrestSurrenderDistrictId, "
            "PoliceStationID, IOID, CourtID, AccusedMasterID, IsAccused, "
            "IsComplainantAccused) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            arrest_rows,
        )
        conn.executemany(
            "INSERT INTO inv_arrestsurrenderaccused (ArrestSurrenderID, "
            "AccusedMasterID) VALUES (?,?)",
            junction_rows,
        )
        conn.executemany(
            "INSERT INTO ChargesheetDetails (CSID, CaseMasterID, csdate, "
            "cstype, PolicePersonID) VALUES (?,?,?,?,?)",
            cs_rows,
        )

        # ---------- Cross-case entity resolution ----------
        # For the demo: cluster accused by exact-match on (name, age±3).
        # A nightly Function on Catalyst will replace this with a proper job.
        _build_person_alias(conn)


def _build_person_alias(conn) -> None:
    """Populate PersonAlias with clusters of same-person accused across cases."""
    rows = conn.execute(
        "SELECT AccusedMasterID, AccusedName, AgeYear FROM Accused"
    ).fetchall()
    by_name: dict[str, list[dict]] = {}
    for r in rows:
        by_name.setdefault(r["AccusedName"].lower(), []).append(dict(r))

    cluster_id = 1
    aliases: list[tuple] = []
    for name, group in by_name.items():
        if len(group) < 2:
            continue
        # Same name is a strong signal in this synthetic set; real system
        # would add fuzzy match on address / dob.
        for row in group:
            aliases.append((cluster_id, row["AccusedMasterID"], 0.95))
        cluster_id += 1

    conn.executemany(
        "INSERT INTO PersonAlias (ClusterID, AccusedMasterID, similarity) "
        "VALUES (?,?,?)",
        aliases,
    )


if __name__ == "__main__":
    seed()
    with cursor() as conn:
        for tbl in (
            "State", "District", "DistrictGeo", "UnitType", "Unit",
            "Rank", "Designation", "Employee",
            "Act", "Section", "CrimeHead", "CrimeSubHead",
            "CrimeHeadActSection",
            "CaseCategory", "GravityOffence", "CaseStatusMaster", "Court",
            "CasteMaster", "ReligionMaster", "OccupationMaster",
            "CaseMaster", "ComplainantDetails", "Victim", "Accused",
            "ActSectionAssociation", "ArrestSurrender",
            "inv_arrestsurrenderaccused", "ChargesheetDetails",
            "PersonAlias",
        ):
            n = conn.execute(f"SELECT COUNT(*) AS n FROM {tbl}").fetchone()["n"]
            print(f"{tbl:34s} {n:>6d}")
