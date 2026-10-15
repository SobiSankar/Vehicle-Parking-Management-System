import os
import re
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "parking.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")

VEHICLE_RATES_PER_HOUR = {
    "Car": 50,
    "Bike": 20,
    "Truck": 80,
}


def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS parking_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_number TEXT NOT NULL UNIQUE,
            slot_type TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('available', 'occupied'))
        );

        CREATE TABLE IF NOT EXISTS parking_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_number TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            contact_number TEXT NOT NULL,
            vehicle_type TEXT NOT NULL,
            slot_id INTEGER NOT NULL,
            entry_time TEXT NOT NULL,
            exit_time TEXT,
            fee REAL,
            status TEXT NOT NULL CHECK(status IN ('parked', 'exited')),
            FOREIGN KEY (slot_id) REFERENCES parking_slots(id)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_active_slot
        ON parking_records(slot_id)
        WHERE status = 'parked';

        CREATE UNIQUE INDEX IF NOT EXISTS idx_active_vehicle
        ON parking_records(vehicle_number)
        WHERE status = 'parked';
        """
    )

    admin = db.execute("SELECT id FROM admins LIMIT 1").fetchone()
    if not admin:
        db.execute(
            "INSERT INTO admins (username, password_hash, created_at) VALUES (?, ?, ?)",
            ("admin", generate_password_hash("admin123"), datetime.utcnow().isoformat()),
        )

    slot_count = db.execute("SELECT COUNT(*) AS count FROM parking_slots").fetchone()["count"]
    if slot_count == 0:
        slots = [(f"A{i:02}", "General", "available") for i in range(1, 21)]
        db.executemany(
            "INSERT INTO parking_slots (slot_number, slot_type, status) VALUES (?, ?, ?)",
            slots,
        )

    db.commit()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def validate_vehicle_input(vehicle_number, owner_name, contact_number, vehicle_type):
    if not re.fullmatch(r"[A-Za-z0-9-]{4,15}", vehicle_number):
        return "Vehicle number must be 4-15 chars (letters, numbers, hyphen)."
    if not owner_name or len(owner_name.strip()) < 2:
        return "Owner name must be at least 2 characters."
    if not re.fullmatch(r"\d{10}", contact_number):
        return "Contact number must be exactly 10 digits."
    if vehicle_type not in VEHICLE_RATES_PER_HOUR:
        return "Invalid vehicle type."
    return None


def get_dashboard_data(search_query=None):
    db = get_db()
    stats = db.execute(
        """
        SELECT
            (SELECT COUNT(DISTINCT vehicle_number) FROM parking_records) AS total_vehicles,
            (SELECT COUNT(*) FROM parking_records WHERE status='parked') AS parked_vehicles,
            (SELECT COUNT(*) FROM parking_slots WHERE status='available') AS available_slots,
            COALESCE((SELECT SUM(fee) FROM parking_records WHERE status='exited'), 0) AS total_revenue
        """
    ).fetchone()

    query = """
        SELECT pr.id, pr.vehicle_number, pr.owner_name, pr.contact_number, pr.vehicle_type,
               pr.entry_time, ps.slot_number
        FROM parking_records pr
        JOIN parking_slots ps ON ps.id = pr.slot_id
        WHERE pr.status='parked'
    """
    params = []
    if search_query:
        query += " AND pr.vehicle_number LIKE ?"
        params.append(f"%{search_query}%")
    query += " ORDER BY pr.entry_time ASC"
    parked_rows = db.execute(query, params).fetchall()

    available_slots = db.execute(
        "SELECT id, slot_number FROM parking_slots WHERE status='available' ORDER BY slot_number"
    ).fetchall()

    return stats, parked_rows, available_slots


def allocate_slot(preferred_slot_id=None):
    db = get_db()
    if preferred_slot_id:
        slot = db.execute(
            "SELECT id, status FROM parking_slots WHERE id = ?",
            (preferred_slot_id,),
        ).fetchone()
        if not slot:
            return None, "Selected slot does not exist."
        if slot["status"] != "available":
            return None, "Selected slot is already occupied."
        return slot["id"], None

    slot = db.execute(
        "SELECT id FROM parking_slots WHERE status='available' ORDER BY slot_number LIMIT 1"
    ).fetchone()
    if not slot:
        return None, "No parking slots available."
    return slot["id"], None


def calculate_fee(entry_time_str, exit_time_str, vehicle_type):
    entry_time = datetime.fromisoformat(entry_time_str)
    exit_time = datetime.fromisoformat(exit_time_str)
    parked_minutes = max((exit_time - entry_time).total_seconds() / 60, 1)
    hours = parked_minutes / 60
    rate = VEHICLE_RATES_PER_HOUR.get(vehicle_type, 50)
    return round(rate * hours, 2)


@app.route("/")
def home():
    if session.get("admin_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        admin = db.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()

        if not admin or not check_password_hash(admin["password_hash"], password):
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        session.clear()
        session["admin_id"] = admin["id"]
        session["admin_username"] = admin["username"]
        flash("Login successful.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    search_query = request.args.get("search", "").strip()
    stats, parked_rows, available_slots = get_dashboard_data(search_query or None)
    return render_template(
        "index.html",
        stats=stats,
        parked_rows=parked_rows,
        available_slots=available_slots,
        vehicle_types=VEHICLE_RATES_PER_HOUR,
        search_query=search_query,
    )


@app.route("/vehicle/entry", methods=["POST"])
@login_required
def vehicle_entry():
    vehicle_number = request.form.get("vehicle_number", "").strip().upper()
    owner_name = request.form.get("owner_name", "").strip()
    contact_number = request.form.get("contact_number", "").strip()
    vehicle_type = request.form.get("vehicle_type", "").strip()
    slot_choice = request.form.get("slot_id", "").strip()

    validation_error = validate_vehicle_input(vehicle_number, owner_name, contact_number, vehicle_type)
    if validation_error:
        flash(validation_error, "error")
        return redirect(url_for("dashboard"))

    preferred_slot_id = int(slot_choice) if slot_choice.isdigit() else None
    slot_id, slot_error = allocate_slot(preferred_slot_id)
    if slot_error:
        flash(slot_error, "error")
        return redirect(url_for("dashboard"))

    db = get_db()
    existing = db.execute(
        "SELECT id FROM parking_records WHERE vehicle_number = ? AND status='parked'",
        (vehicle_number,),
    ).fetchone()
    if existing:
        flash("Vehicle is already parked.", "error")
        return redirect(url_for("dashboard"))

    entry_time = datetime.utcnow().isoformat()
    try:
        db.execute(
            """
            INSERT INTO parking_records
            (vehicle_number, owner_name, contact_number, vehicle_type, slot_id, entry_time, status)
            VALUES (?, ?, ?, ?, ?, ?, 'parked')
            """,
            (vehicle_number, owner_name, contact_number, vehicle_type, slot_id, entry_time),
        )
        db.execute(
            "UPDATE parking_slots SET status='occupied' WHERE id = ?",
            (slot_id,),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        flash("Slot or vehicle is already occupied.", "error")
        return redirect(url_for("dashboard"))

    flash("Vehicle entry recorded successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/vehicle/exit/<int:record_id>", methods=["POST"])
@login_required
def vehicle_exit(record_id):
    db = get_db()
    record = db.execute(
        """
        SELECT id, vehicle_type, entry_time, slot_id, status
        FROM parking_records
        WHERE id = ?
        """,
        (record_id,),
    ).fetchone()

    if not record or record["status"] != "parked":
        flash("Vehicle record not found or already exited.", "error")
        return redirect(url_for("dashboard"))

    exit_time = datetime.utcnow().isoformat()
    fee = calculate_fee(record["entry_time"], exit_time, record["vehicle_type"])

    db.execute(
        """
        UPDATE parking_records
        SET status='exited', exit_time=?, fee=?
        WHERE id=?
        """,
        (exit_time, fee, record_id),
    )
    db.execute(
        "UPDATE parking_slots SET status='available' WHERE id=?",
        (record["slot_id"],),
    )
    db.commit()

    flash(f"Vehicle exited. Fee: ₹{fee}", "success")
    return redirect(url_for("dashboard"))


@app.route("/reports")
@login_required
def reports():
    db = get_db()
    history_rows = db.execute(
        """
        SELECT pr.vehicle_number, pr.owner_name, pr.contact_number, pr.vehicle_type,
               ps.slot_number, pr.entry_time, pr.exit_time, COALESCE(pr.fee, 0) AS fee, pr.status
        FROM parking_records pr
        JOIN parking_slots ps ON ps.id = pr.slot_id
        ORDER BY pr.entry_time DESC
        """
    ).fetchall()

    daily_revenue = db.execute(
        """
        SELECT substr(exit_time, 1, 10) AS day, ROUND(COALESCE(SUM(fee), 0), 2) AS revenue,
               COUNT(*) AS exited_vehicles
        FROM parking_records
        WHERE status='exited' AND exit_time IS NOT NULL
        GROUP BY substr(exit_time, 1, 10)
        ORDER BY day DESC
        """
    ).fetchall()

    return render_template("reports.html", history_rows=history_rows, daily_revenue=daily_revenue)


@app.template_filter("fmt_dt")
def fmt_dt(value):
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


with app.app_context():
    init_db()


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode)
