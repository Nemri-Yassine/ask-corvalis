"""Realistic sample data for P9: 60 past Corvalis projects.

All names, clients and people are fictional. The data is generated with a
fixed random seed, so every install gets exactly the same 60 projects.

A handful of hand-written "showcase" projects make sure the demo questions
have good answers (e.g. four footbridges in different materials).
"""
import random
import sqlite3

SEED = 42
TOTAL = 60

PROJECT_MANAGERS = [
    "Sophie Lambert", "Thomas Dubois", "Anke Peeters", "Marc Renard",
    "Julie Fontaine", "Pieter Claes", "Nadia El Amrani", "Olivier Masson",
]

CITIES = [
    "Brussels", "Liège", "Namur", "Charleroi", "Mons", "Leuven", "Ghent", "Antwerp",
    "Hasselt", "Verviers", "Wavre", "Louvain-la-Neuve", "Huy", "Seraing", "Tournai", "Arlon",
]

CLIENTS = {
    "public": ["City of {city}", "City of {city}", "Walloon Region – Mobility Dept."],
    "school": ["City of {city}", "{city} School Board", "Federation of Catholic Schools"],
    "city": ["City of {city}"],
    "developer": ["Mosan Développement", "Brabant Living", "Meuse Invest", "Nova Real Estate",
                  "Kempen Projects"],
    "architect": ["Atelier Delvaux Architectes", "Studio Vermeulen", "Bureau Lenoir & Fils",
                  "Archipel Architecture", "De Smet Architecten"],
    "health": ["Regional Hospital Group Meuse", "Sainte-Gertrude Clinic", "Brussels University Hospital"],
}

# --- Showcase projects (hand-written) -----------------------------------------

SHOWCASE = [
    {
        "number": "2014-017", "title": "Ourthe valley timber footbridge", "type": "footbridge",
        "discipline": "Structures", "client": "Province of Liège", "city": "Liège", "year": 2014,
        "project_manager": "Marc Renard", "materials": "glulam timber, steel connections",
        "budget_eur": 780_000,
        "summary": "42 m glued-laminated timber arch footbridge for pedestrians and cyclists over the "
                   "Ourthe. Corvalis designed the arch, the timber deck and the concrete abutments on "
                   "micropiles. Vibration comfort was checked for crowd loading.",
    },
    {
        "number": "2019-042", "title": "Sambre weathering-steel footbridge", "type": "footbridge",
        "discipline": "Structures", "client": "City of Charleroi", "city": "Charleroi", "year": 2019,
        "project_manager": "Sophie Lambert", "materials": "weathering steel, concrete",
        "budget_eur": 1_450_000,
        "summary": "60 m weathering-steel truss footbridge crossing the Sambre next to the old industrial "
                   "quays. The bridge was prefabricated in two halves and lifted in one night. "
                   "Includes a tuned mass damper to control lateral vibrations.",
    },
    {
        "number": "2022-008", "title": "Leuven ring road UHPC footbridge", "type": "footbridge",
        "discipline": "Structures", "client": "City of Leuven", "city": "Leuven", "year": 2022,
        "project_manager": "Anke Peeters", "materials": "ultra-high-performance concrete (UHPC), steel",
        "budget_eur": 2_100_000,
        "summary": "35 m single-span footbridge over the ring road built from precast UHPC segments only "
                   "12 cm thick. Post-tensioned on site in a weekend road closure. "
                   "Designed for a 100-year service life with minimal maintenance.",
    },
    {
        "number": "2024-031", "title": "RAVeL cycle route timber-steel footbridge", "type": "footbridge",
        "discipline": "Structures", "client": "Walloon Region – Mobility Dept.", "city": "Namur",
        "year": 2024, "project_manager": "Marc Renard", "materials": "timber, steel",
        "budget_eur": 960_000,
        "summary": "Hybrid footbridge with an oak timber deck on two steel girders, 28 m span, on the "
                   "RAVeL cycle network along the Meuse. Designed for cyclists, maintenance vehicles "
                   "up to 3.5 t and flood loads.",
    },
    {
        "number": "2021-019", "title": "Tour Canal CLT office building", "type": "office",
        "discipline": "Both", "client": "Nova Real Estate", "city": "Brussels", "year": 2021,
        "project_manager": "Julie Fontaine", "materials": "cross-laminated timber (CLT), glulam, concrete core",
        "budget_eur": 18_500_000,
        "summary": "7-storey office building with CLT floors on glulam columns around a concrete core, "
                   "12,000 m². Corvalis designed the structure and the heat-pump HVAC system. "
                   "Fire safety of the exposed timber was demonstrated by calculation (R90).",
    },
    {
        "number": "2017-055", "title": "Athénée deep energy renovation", "type": "school",
        "discipline": "Building services", "client": "City of Namur", "city": "Namur", "year": 2017,
        "project_manager": "Nadia El Amrani", "materials": "brick, concrete",
        "budget_eur": 4_200_000,
        "summary": "Deep energy renovation of a 1960s secondary school while it stayed in use. "
                   "New mechanical ventilation with heat recovery, gas boilers replaced by heat pumps "
                   "and 400 m² of solar panels. Energy use cut by 65%.",
    },
    {
        "number": "2016-023", "title": "Grand-Place post-tensioned car park", "type": "car park",
        "discipline": "Structures", "client": "Meuse Invest", "city": "Mons", "year": 2016,
        "project_manager": "Thomas Dubois", "materials": "post-tensioned concrete",
        "budget_eur": 9_800_000,
        "summary": "Four-level underground car park for 520 cars under a historic square. "
                   "Post-tensioned flat slabs to limit the excavation depth, with secant pile walls "
                   "close to listed buildings.",
    },
    {
        "number": "2020-012", "title": "Regional hospital east wing extension", "type": "hospital extension",
        "discipline": "Both", "client": "Regional Hospital Group Meuse", "city": "Liège", "year": 2020,
        "project_manager": "Pieter Claes", "materials": "reinforced concrete, steel",
        "budget_eur": 26_000_000,
        "summary": "5-storey extension with operating theatres and intensive care beds, connected to the "
                   "existing hospital by a steel link bridge. Corvalis designed the concrete frame and "
                   "the medical gas, cleanroom ventilation and backup power systems.",
    },
]

# --- Generated projects ---------------------------------------------------------

# For each project type: possible materials, budget range (EUR), client kind,
# and summary templates. {…} fields are filled in by make_project().
TYPES = {
    "office": {
        "materials": ["reinforced concrete", "steel, composite floors", "CLT, glulam", "precast concrete"],
        "budget": (3_000_000, 25_000_000), "client": "developer", "spans": [7.2, 8.1, 10.8, 13.5],
        "summary": ["{floors}-storey office building of {area:,} m² with a {material} frame.",
                    "Open-plan floors with {span} m spans and an underground car park."],
    },
    "housing": {
        "materials": ["reinforced concrete", "timber frame", "CLT", "masonry, concrete floors"],
        "budget": (2_000_000, 15_000_000), "client": "developer", "spans": [5.4, 6.0, 7.2],
        "summary": ["Residential block of {units} apartments in {material} over {floors} storeys.",
                    "Designed to passive-house level with collective heat pumps."],
    },
    "school": {
        "materials": ["precast concrete", "steel frame", "timber frame", "CLT"],
        "budget": (2_500_000, 12_000_000), "client": "school", "spans": [20, 24, 28],
        "summary": ["New school building for {pupils} pupils with a {material} structure.",
                    "Includes a sports hall with a {span} m clear span roof."],
    },
    "hospital extension": {
        "materials": ["reinforced concrete", "reinforced concrete, steel"],
        "budget": (8_000_000, 30_000_000), "client": "health", "spans": [7.2, 8.1],
        "summary": ["{floors}-storey hospital extension of {area:,} m² in {material}.",
                    "Vibration-sensitive floors for imaging rooms and full medical gas installation."],
    },
    "car park": {
        "materials": ["post-tensioned concrete", "steel, composite floors", "precast concrete"],
        "budget": (3_000_000, 12_000_000), "client": "public", "spans": [15, 16, 16.5],
        "disciplines": ["Structures", "Both"],
        "summary": ["Multi-storey car park for {cars} cars built in {material}.",
                    "Designed for fast construction with repetitive {span} m spans."],
    },
    "renovation": {
        "materials": ["masonry, timber floors", "reinforced concrete", "steel, masonry"],
        "budget": (800_000, 8_000_000), "client": "architect", "spans": [5, 6],
        "summary": ["Renovation and change of use of a {age}-year-old building ({material}).",
                    "Structural survey, strengthening of floors and new building services throughout."],
    },
    "warehouse": {
        "materials": ["steel portal frames", "precast concrete", "glulam portal frames"],
        "budget": (1_500_000, 9_000_000), "client": "developer", "spans": [24, 30, 36, 45],
        "disciplines": ["Structures", "Both"],
        "summary": ["Logistics warehouse of {area:,} m² with {material} and a {span} m clear span.",
                    "Industrial floor slab designed for high-bay racking."],
    },
    "sports hall": {
        "materials": ["glulam timber", "steel trusses", "precast concrete"],
        "budget": (2_000_000, 7_000_000), "client": "city", "spans": [24, 30, 36],
        "summary": ["Sports hall with a {span} m clear span roof in {material}.",
                    "Includes changing rooms, ventilation with heat recovery and solar panels."],
    },
    "road bridge": {
        "materials": ["prestressed concrete", "steel-concrete composite", "reinforced concrete"],
        "budget": (2_000_000, 14_000_000), "client": "public", "spans": [25, 32, 40, 55, 70],
        "disciplines": ["Structures"],
        "summary": ["Road bridge in {material} with a main span of {span} m.",
                    "Built under traffic with a phased construction sequence."],
    },
}

# How many generated projects of each type (8 showcase + 52 generated = 60).
TYPE_COUNTS = {
    "office": 8, "housing": 9, "school": 6, "hospital extension": 3, "car park": 4,
    "renovation": 9, "warehouse": 6, "sports hall": 4, "road bridge": 3,
}

ADJECTIVES = ["Meuse", "Parc", "Saint-Lambert", "Gare", "Canal", "Les Tilleuls", "Horizon",
              "Quai", "Citadelle", "Moulin", "Sablon", "Ravel", "Coteaux", "Europa", "Molenveld"]

TITLE_NOUN = {
    "office": "office building", "housing": "housing", "school": "school", "car park": "car park",
    "hospital extension": "hospital extension", "renovation": "renovation",
    "warehouse": "logistics warehouse", "sports hall": "sports hall", "road bridge": "road bridge",
}


def make_project(rng: random.Random, ptype: str, number: str, year: int) -> dict:
    spec = TYPES[ptype]
    city = rng.choice(CITIES)
    material = rng.choice(spec["materials"])
    client = rng.choice(CLIENTS[spec["client"]]).format(city=city)
    discipline = rng.choice(spec.get("disciplines", ["Structures", "Building services", "Both"]))

    values = {
        "material": material, "floors": rng.randint(3, 9), "area": rng.randrange(1_500, 20_000, 100),
        "span": rng.choice(spec["spans"]), "units": rng.randint(18, 90),
        "pupils": rng.choice([300, 450, 600, 800]), "cars": rng.randrange(200, 900, 20),
        "age": rng.choice([60, 80, 100, 120]),
    }
    summary = " ".join(sentence.format(**values) for sentence in spec["summary"])
    if discipline == "Building services":
        summary += " Corvalis was responsible for the HVAC, electrical and plumbing design."
    elif discipline == "Both":
        summary += " Corvalis designed both the structure and the building services."

    low, high = spec["budget"]
    return {
        "number": number,
        "title": f"{rng.choice(ADJECTIVES)} {TITLE_NOUN[ptype]}, {city}",
        "type": ptype,
        "discipline": discipline,
        "client": client,
        "city": city,
        "year": year,
        "project_manager": rng.choice(PROJECT_MANAGERS),
        "materials": material,
        "budget_eur": rng.randrange(low, high, 50_000),
        "summary": summary,
    }


def generate_projects() -> list[dict]:
    rng = random.Random(SEED)
    projects = [dict(p) for p in SHOWCASE]
    used = {p["number"] for p in projects}

    types = [t for t, n in TYPE_COUNTS.items() for _ in range(n)]
    rng.shuffle(types)
    for ptype in types:
        year = rng.randint(2012, 2026)
        number = f"{year}-{rng.randint(1, 99):03d}"
        while number in used:
            number = f"{year}-{rng.randint(1, 99):03d}"
        used.add(number)
        projects.append(make_project(rng, ptype, number, year))

    for p in projects:
        p["folder_path"] = f"\\\\fileserver\\projects\\{p['number']}"
    projects.sort(key=lambda p: p["number"])
    assert len(projects) == TOTAL
    return projects


def seed_if_empty(conn: sqlite3.Connection) -> int:
    """Insert the sample projects only if the table is empty (safe on every start)."""
    if conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] > 0:
        return 0
    projects = generate_projects()
    conn.executemany(
        "INSERT INTO projects (number, title, type, discipline, client, city, year, "
        "project_manager, materials, budget_eur, summary, folder_path) VALUES "
        "(:number, :title, :type, :discipline, :client, :city, :year, "
        ":project_manager, :materials, :budget_eur, :summary, :folder_path)",
        projects,
    )
    conn.commit()
    return len(projects)


def get_projects(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM projects ORDER BY number").fetchall()]
