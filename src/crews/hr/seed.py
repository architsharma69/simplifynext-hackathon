"""
crews/hr/seed.py
Seed a believable 8-person startup into crews/hr/workload.db.

Demo data is a design task, not filler. Priya is deliberately at ~130% for
three consecutive weeks so the burnout catch happens live on stage rather
than in theory.

Run before every rehearsal / whenever the checked-in workload.db needs
regenerating:

    python -m crews.hr.seed        # from src/, with src on PYTHONPATH

Ported from plan/workload_manager/seed.py — only the imports changed
(`from db import ...` / `from ledger import ...` -> `crews.hr.*`). The
resulting workload.db is checked into the repo so the HR crew has working
demo data out of the box, the same way crews/document ships its
knowledge/documents/*.json fixtures.
"""

from datetime import date, timedelta

from crews.hr.db import connect, init_db, week_of, previous_week
from crews.hr.ledger import recompute_workload

PEOPLE = [
    ("Priya Menon",   "Senior Engineer",  "backend,python,infra",       40, "@priya"),
    ("Rahul Iyer",    "Engineer",         "backend,python,onboarding",  40, "@rahul"),
    ("Wei Ling Tan",  "Designer",         "design,ux,research",         40, "@weiling"),
    ("Daniel Osei",   "Engineer",         "frontend,react,design",      40, "@daniel"),
    ("Sofia Marchi",  "Product",          "product,research,writing",   32, "@sofia"),
    ("Ken Nakamura",  "Engineer",         "backend,data,python",        40, "@ken"),
    ("Amara Nwosu",   "Ops",              "ops,finance,writing",        24, "@amara"),
    ("Tom Bradley",   "Founder",          "sales,product",              40, "@tom"),
]

# (assignee, title, est_hours, days_from_monday_this_week, status)
TASKS = [
    ("Priya Menon",  "Migrate billing service to new queue", 18, 3,  "in_progress"),
    ("Priya Menon",  "Fix payment webhook retries",          14, 4,  "in_progress"),
    ("Priya Menon",  "On-call handover doc",                  8, 2,  "in_progress"),
    ("Priya Menon",  "Rework rate limiter",                  16, 10, "in_progress"),
    ("Priya Menon",  "Postgres upgrade dry run",             14, 11, "in_progress"),
    ("Rahul Iyer",   "Onboarding email sequence",             8, 3,  "in_progress"),
    ("Rahul Iyer",   "Fix signup validation bug",             6, 4,  "in_progress"),
    ("Wei Ling Tan", "Dashboard redesign — first pass",      20, 4,  "in_progress"),
    ("Daniel Osei",  "Settings page rebuild",                12, 3,  "in_progress"),
    ("Sofia Marchi", "Q4 roadmap draft",                     10, 4,  "in_progress"),
    ("Ken Nakamura", "Analytics pipeline cleanup",           16, 3,  "in_progress"),
    ("Ken Nakamura", "Data retention policy",                 6, 10, "in_progress"),
    ("Amara Nwosu",  "Vendor invoices",                       6, 2,  "in_progress"),
    (None,           "Investor update deck",                  6, 4,  "unassigned"),
]


def seed() -> None:
    init_db(reset=True)
    this_monday = date.today() - timedelta(days=date.today().weekday())

    with connect() as conn:
        conn.executemany(
            "INSERT INTO people (name, role, skills, weekly_capacity_hrs, contact_handle) "
            "VALUES (?, ?, ?, ?, ?)",
            PEOPLE,
        )

        ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM people")}

        for assignee, title, hours, offset, status in TASKS:
            conn.execute(
                "INSERT INTO tasks (title, assignee_id, est_hours, due_date, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (title, ids.get(assignee), hours,
                 (this_monday + timedelta(days=offset)).isoformat(), status),
            )

        # Wei Ling is away Thursday and Friday this week.
        conn.execute(
            "INSERT INTO wellbeing_events (person_id, type, note, start_date, end_date) "
            "VALUES (?, 'leave', 'Family trip', ?, ?)",
            (ids["Wei Ling Tan"],
             (this_monday + timedelta(days=3)).isoformat(),
             (this_monday + timedelta(days=4)).isoformat()),
        )

        # The history that makes Priya's case a BLOCK rather than a WARN:
        # two prior weeks already flagged as overloaded.
        this_week = week_of(this_monday)
        w1 = previous_week(this_week)
        w2 = previous_week(w1)
        for wk, hrs in ((w1, 46), (w2, 44)):
            conn.execute(
                "INSERT INTO workload_log (person_id, week, assigned_hours, overload_flag) "
                "VALUES (?, ?, ?, 1)",
                (ids["Priya Menon"], wk, hrs),
            )
            conn.execute(
                "INSERT INTO wellbeing_events (person_id, type, note) VALUES (?, 'overloaded', ?)",
                (ids["Priya Menon"], f"Over capacity in {wk}"),
            )

    # Bring workload_log up to date for the weeks we just populated.
    for name in [p[0] for p in PEOPLE]:
        person_id = get_id(name)
        for wk in (week_of(this_monday), week_of(this_monday + timedelta(weeks=1))):
            recompute_workload(person_id, wk)

    print("Seeded 8 people, 14 tasks.")
    print(f"This week is {week_of(this_monday)}.")
    print("Priya Menon is deliberately overloaded, with two prior flagged weeks.")


def get_id(name: str) -> int:
    with connect() as conn:
        return conn.execute("SELECT id FROM people WHERE name = ?", (name,)).fetchone()["id"]


if __name__ == "__main__":
    seed()
