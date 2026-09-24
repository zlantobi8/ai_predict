"""Sample data. Normally run for you by `python setup_db.py`; safe to run again."""
import bcrypt
from database import run_query

EQUIPMENT = [
    # name, equipment_type (what the ML model knows), category, location, installed
    ("Lathe Machine A", "lathe", "Workshop Equipment", "Mechanical Workshop", "2023-01-10"),
    ("Drilling Machine B", "drilling", "Workshop Equipment", "Mechanical Workshop", "2022-11-05"),
    ("Computer Lab AC Unit 1", "ac", "Computer Laboratory", "Computer Laboratory", "2021-06-15"),
    ("Main Water Pump", "water-pump", "Other Infrastructure", "Pump House", "2020-03-20"),
    ("Electrical Lab AC", "ac", "Laboratory Equipment", "Electrical Laboratory", "2022-02-01"),
]


def seed():
    admin_exists = run_query(
        "SELECT id FROM users WHERE staff_id = %s", ("admin",), fetch_one=True
    )
    if not admin_exists:
        password_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
        run_query(
            """INSERT INTO users (staff_id, full_name, email, password_hash, role, status)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            ("admin", "System Administrator", "admin@campus.edu", password_hash, "admin", "active"),
            commit=True,
        )
        print("Created default admin user -> staff ID: admin / password: admin123  (change this!)")
    else:
        print("Admin user already exists — skipping")

    existing_count = run_query("SELECT COUNT(*) AS c FROM equipment", fetch_one=True)["c"]
    if existing_count == 0:
        for name, eq_type, category, location, installed in EQUIPMENT:
            run_query(
                """INSERT INTO equipment (name, equipment_type, category, location,
                   status, installed_date) VALUES (%s,%s,%s,%s,%s,%s)""",
                (name, eq_type, category, location, "operational", installed),
                commit=True,
            )
        print(f"Inserted {len(EQUIPMENT)} sample equipment records")
    else:
        print("Equipment table already has data — skipping seed")


if __name__ == "__main__":
    seed()
