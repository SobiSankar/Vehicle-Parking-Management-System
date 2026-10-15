from pathlib import Path
import sqlite3
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def init_db(default_username: str = "admin", default_password: str = "admin123"):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(schema_sql)

        existing_admin = conn.execute("SELECT id FROM admin WHERE username = ?", (default_username,)).fetchone()
        if not existing_admin:
            conn.execute(
                "INSERT INTO admin (username, password_hash) VALUES (?, ?)",
                (default_username, generate_password_hash(default_password)),
            )

        existing_slots = conn.execute("SELECT COUNT(*) FROM slots").fetchone()[0]
        if existing_slots == 0:
            slots = [(f"S{index:02d}", "Available", None) for index in range(1, 21)]
            conn.executemany(
                "INSERT INTO slots (slot_number, status, supported_vehicle_type) VALUES (?, ?, ?)",
                slots,
            )

        conn.commit()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
