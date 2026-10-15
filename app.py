from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.init_db import init_db
from modules.db import get_connection

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key"

PARKING_RATES = {
    "Two-wheeler": 20,
    "Car": 40,
    "Other": 30,
}


def calculate_fee(entry_time: datetime, exit_time: datetime, vehicle_type: str) -> tuple[float, float]:
    duration_hours = max((exit_time - entry_time).total_seconds() / 3600, 0.5)
    fee = round(duration_hours * PARKING_RATES.get(vehicle_type, 30), 2)
    return duration_hours, fee


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper


def get_available_slots(connection, vehicle_type=None):
    if vehicle_type:
        return connection.execute(
            """
            SELECT id, slot_number FROM slots
            WHERE status = 'Available' AND (supported_vehicle_type IS NULL OR supported_vehicle_type = ?)
            ORDER BY slot_number
            """,
            (vehicle_type,),
        ).fetchall()

    return connection.execute(
        "SELECT id, slot_number FROM slots WHERE status = 'Available' ORDER BY slot_number"
    ).fetchall()


@app.before_request
def before_request():
    g.current_year = datetime.now().year


@app.route("/")
@login_required
def dashboard():
    with get_connection() as conn:
        total_vehicles = conn.execute("SELECT COUNT(*) FROM vehicle").fetchone()[0]
        currently_parked = conn.execute("SELECT COUNT(*) FROM parking_records WHERE exit_time IS NULL").fetchone()[0]
        available_slots = conn.execute("SELECT COUNT(*) FROM slots WHERE status = 'Available'").fetchone()[0]
        total_revenue = conn.execute(
            "SELECT COALESCE(SUM(parking_fee), 0) FROM parking_records WHERE exit_time IS NOT NULL"
        ).fetchone()[0]

        recent_records = conn.execute(
            """
            SELECT pr.id, v.vehicle_number, v.owner_name, v.vehicle_type, s.slot_number, pr.entry_time
            FROM parking_records pr
            JOIN vehicle v ON v.id = pr.vehicle_id
            JOIN slots s ON s.id = pr.slot_id
            WHERE pr.exit_time IS NULL
            ORDER BY pr.entry_time DESC
            LIMIT 5
            """
        ).fetchall()

    return render_template(
        "dashboard.html",
        total_vehicles=total_vehicles,
        currently_parked=currently_parked,
        available_slots=available_slots,
        total_revenue=total_revenue,
        recent_records=recent_records,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("login.html")

        with get_connection() as conn:
            admin = conn.execute("SELECT * FROM admin WHERE username = ?", (username,)).fetchone()

        if not admin or not check_password_hash(admin["password_hash"], password):
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        session["admin_id"] = admin["id"]
        session["username"] = admin["username"]
        flash("Login successful.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))


@app.route("/vehicle-entry", methods=["GET", "POST"])
@login_required
def vehicle_entry():
    with get_connection() as conn:
        if request.method == "POST":
            vehicle_number = request.form.get("vehicle_number", "").strip().upper()
            owner_name = request.form.get("owner_name", "").strip()
            contact_number = request.form.get("contact_number", "").strip()
            vehicle_type = request.form.get("vehicle_type", "").strip()
            selected_slot = request.form.get("slot_id", "").strip()

            if not all([vehicle_number, owner_name, contact_number, vehicle_type]):
                flash("All fields are required.", "error")
            elif vehicle_type not in PARKING_RATES:
                flash("Invalid vehicle type.", "error")
            else:
                available_slots = get_available_slots(conn, vehicle_type)
                if not available_slots:
                    flash("No slots available for the selected vehicle type.", "error")
                    return render_template("vehicle_entry.html", available_slots=[], rates=PARKING_RATES)

                slot_id = int(selected_slot) if selected_slot else available_slots[0]["id"]
                slot = conn.execute(
                    "SELECT id, slot_number, status FROM slots WHERE id = ?", (slot_id,)
                ).fetchone()

                if not slot or slot["status"] != "Available":
                    flash("Selected slot is not available.", "error")
                else:
                    try:
                        conn.execute("BEGIN")

                        existing_vehicle = conn.execute(
                            "SELECT id FROM vehicle WHERE vehicle_number = ?", (vehicle_number,)
                        ).fetchone()
                        if existing_vehicle:
                            vehicle_id = existing_vehicle["id"]
                            active_record = conn.execute(
                                "SELECT id FROM parking_records WHERE vehicle_id = ? AND exit_time IS NULL",
                                (vehicle_id,),
                            ).fetchone()
                            if active_record:
                                conn.rollback()
                                flash("This vehicle is already parked and active.", "error")
                                return redirect(url_for("parked_vehicles"))

                            conn.execute(
                                """
                                UPDATE vehicle
                                SET owner_name = ?, contact_number = ?, vehicle_type = ?
                                WHERE id = ?
                                """,
                                (owner_name, contact_number, vehicle_type, vehicle_id),
                            )
                        else:
                            vehicle_id = conn.execute(
                                """
                                INSERT INTO vehicle (vehicle_number, owner_name, contact_number, vehicle_type)
                                VALUES (?, ?, ?, ?)
                                """,
                                (vehicle_number, owner_name, contact_number, vehicle_type),
                            ).lastrowid

                        conn.execute(
                            """
                            INSERT INTO parking_records (vehicle_id, slot_id, entry_time)
                            VALUES (?, ?, ?)
                            """,
                            (vehicle_id, slot_id, datetime.now().isoformat(timespec="seconds")),
                        )

                        conn.execute("UPDATE slots SET status = 'Occupied' WHERE id = ?", (slot_id,))
                        conn.commit()
                        flash(f"Vehicle parked successfully in slot {slot['slot_number']}.", "success")
                        return redirect(url_for("parked_vehicles"))
                    except Exception:
                        conn.rollback()
                        flash("Unable to park vehicle. Please try again.", "error")

        available_slots = get_available_slots(conn)
    return render_template("vehicle_entry.html", available_slots=available_slots, rates=PARKING_RATES)


@app.route("/parked-vehicles")
@login_required
def parked_vehicles():
    search = request.args.get("search", "").strip().upper()

    query = """
        SELECT pr.id, v.vehicle_number, v.owner_name, v.contact_number, v.vehicle_type,
               s.slot_number, pr.entry_time
        FROM parking_records pr
        JOIN vehicle v ON v.id = pr.vehicle_id
        JOIN slots s ON s.id = pr.slot_id
        WHERE pr.exit_time IS NULL
    """
    params = []

    if search:
        query += " AND v.vehicle_number LIKE ?"
        params.append(f"%{search}%")

    query += " ORDER BY pr.entry_time DESC"

    with get_connection() as conn:
        records = conn.execute(query, params).fetchall()

    return render_template("parked_vehicles.html", records=records, search=search)


@app.route("/vehicle/<int:record_id>")
@login_required
def vehicle_details(record_id):
    with get_connection() as conn:
        record = conn.execute(
            """
            SELECT pr.id, pr.entry_time, pr.exit_time, pr.parking_fee,
                   v.vehicle_number, v.owner_name, v.contact_number, v.vehicle_type,
                   s.slot_number
            FROM parking_records pr
            JOIN vehicle v ON v.id = pr.vehicle_id
            JOIN slots s ON s.id = pr.slot_id
            WHERE pr.id = ?
            """,
            (record_id,),
        ).fetchone()

    if not record:
        flash("Vehicle record not found.", "error")
        return redirect(url_for("parked_vehicles"))

    return render_template("vehicle_details.html", record=record)


@app.route("/exit/<int:record_id>", methods=["GET", "POST"])
@login_required
def vehicle_exit(record_id):
    with get_connection() as conn:
        record = conn.execute(
            """
            SELECT pr.id, pr.slot_id, pr.entry_time, v.vehicle_type, v.vehicle_number, s.slot_number
            FROM parking_records pr
            JOIN vehicle v ON v.id = pr.vehicle_id
            JOIN slots s ON s.id = pr.slot_id
            WHERE pr.id = ? AND pr.exit_time IS NULL
            """,
            (record_id,),
        ).fetchone()

        if not record:
            flash("Active parking record not found.", "error")
            return redirect(url_for("parked_vehicles"))

        entry_time = datetime.fromisoformat(record["entry_time"])
        exit_time = datetime.now()
        duration_hours, fee = calculate_fee(entry_time, exit_time, record["vehicle_type"])

        if request.method == "POST":
            try:
                conn.execute("BEGIN")
                conn.execute(
                    """
                    UPDATE parking_records
                    SET exit_time = ?, parking_fee = ?
                    WHERE id = ? AND exit_time IS NULL
                    """,
                    (exit_time.isoformat(timespec="seconds"), fee, record_id),
                )
                conn.execute("UPDATE slots SET status = 'Available' WHERE id = ?", (record["slot_id"],))
                conn.commit()
                flash(f"Vehicle exited. Total fee: ₹{fee}", "success")
                return redirect(url_for("parked_vehicles"))
            except Exception:
                conn.rollback()
                flash("Unable to complete exit. Please try again.", "error")

    return render_template(
        "exit_confirmation.html",
        record=record,
        duration_hours=round(duration_hours, 2),
        fee=fee,
    )


@app.route("/parking-slots")
@login_required
def parking_slots():
    with get_connection() as conn:
        slots = conn.execute(
            """
            SELECT s.id, s.slot_number, s.status, s.supported_vehicle_type,
                   v.vehicle_number
            FROM slots s
            LEFT JOIN parking_records pr ON pr.slot_id = s.id AND pr.exit_time IS NULL
            LEFT JOIN vehicle v ON v.id = pr.vehicle_id
            ORDER BY s.slot_number
            """
        ).fetchall()

    return render_template("parking_slots.html", slots=slots)


@app.route("/reports")
@login_required
def reports():
    filter_date = request.args.get("date", "").strip()
    vehicle_number = request.args.get("vehicle_number", "").strip().upper()

    query = """
        SELECT pr.id, v.vehicle_number, v.owner_name, v.vehicle_type,
               s.slot_number, pr.entry_time, pr.exit_time, pr.parking_fee
        FROM parking_records pr
        JOIN vehicle v ON v.id = pr.vehicle_id
        JOIN slots s ON s.id = pr.slot_id
        WHERE 1 = 1
    """

    params = []
    if filter_date:
        query += " AND date(pr.entry_time) = ?"
        params.append(filter_date)
    if vehicle_number:
        query += " AND v.vehicle_number LIKE ?"
        params.append(f"%{vehicle_number}%")

    query += " ORDER BY pr.entry_time DESC"

    with get_connection() as conn:
        records = conn.execute(query, params).fetchall()

        revenue_query = (
            "SELECT COALESCE(SUM(parking_fee), 0) FROM parking_records WHERE exit_time IS NOT NULL"
        )
        revenue_params = []

        if filter_date:
            revenue_query += " AND date(exit_time) = ?"
            revenue_params.append(filter_date)

        if vehicle_number:
            revenue_query += (
                " AND vehicle_id IN (SELECT id FROM vehicle WHERE vehicle_number LIKE ?)"
            )
            revenue_params.append(f"%{vehicle_number}%")

        total_revenue = conn.execute(revenue_query, revenue_params).fetchone()[0]

    return render_template(
        "reports.html",
        records=records,
        total_revenue=total_revenue,
        filter_date=filter_date,
        vehicle_number=vehicle_number,
    )


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html"), 404


def ensure_database():
    db_file = Path(__file__).resolve().parent / "database.db"
    if not db_file.exists():
        init_db()


ensure_database()


if __name__ == "__main__":
    app.run()
