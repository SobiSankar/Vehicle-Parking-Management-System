# Vehicle Parking Management System

A beginner-friendly web-based project built with **Python, Flask, SQLite, HTML, CSS, and JavaScript** to manage vehicle parking entry, exit, slot allocation, and fee calculation.

## Features
- Admin login/logout with password hashing
- Dashboard with:
  - Total vehicles
  - Currently parked vehicles
  - Available slots
  - Total revenue
- Vehicle entry form with validation
- Duplicate active parking prevention for a vehicle
- Slot occupancy protection (same slot cannot be assigned twice)
- Parked vehicles list with search and details view
- Vehicle exit flow with automatic fee calculation
- Slot status tracking (Available/Occupied)
- Reports with date/vehicle filtering and revenue summary

## Tech Stack
- **Backend:** Flask (Python)
- **Database:** SQLite (`sqlite3`)
- **Frontend:** HTML, CSS, JavaScript

## Project Structure
```
Vehicle-Parking-Management-System/
├── app.py
├── database/
│   ├── init_db.py
│   └── schema.sql
├── modules/
│   └── db.py
├── static/
│   ├── script.js
│   └── style.css
├── templates/
│   ├── 404.html
│   ├── base.html
│   ├── dashboard.html
│   ├── exit_confirmation.html
│   ├── login.html
│   ├── parked_vehicles.html
│   ├── parking_slots.html
│   ├── reports.html
│   ├── vehicle_details.html
│   └── vehicle_entry.html
├── requirements.txt
└── README.md
```

## Database Design
### 1) `admin`
- `id` (PK)
- `username` (UNIQUE)
- `password_hash`

### 2) `slots`
- `id` (PK)
- `slot_number` (UNIQUE)
- `status` (`Available` / `Occupied`)
- `supported_vehicle_type` (optional)

### 3) `vehicle`
- `id` (PK)
- `vehicle_number` (UNIQUE)
- `owner_name`
- `contact_number`
- `vehicle_type`

### 4) `parking_records`
- `id` (PK)
- `vehicle_id` (FK -> `vehicle.id`)
- `slot_id` (FK -> `slots.id`)
- `entry_time`
- `exit_time`
- `parking_fee`

Additional active-session unique indexes prevent duplicate active occupancy by slot and by vehicle.

## Setup and Run (VS Code)
1. Open this project folder in VS Code.
2. Create and activate a virtual environment:
   - **Windows (PowerShell):**
     ```powershell
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```
   - **Linux/macOS:**
     ```bash
     python -m venv .venv
     source .venv/bin/activate
     ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Initialize database (optional; app auto-initializes if missing):
   ```bash
   python database/init_db.py
   ```
5. Run the app:
   ```bash
   python app.py
   ```
6. Open: `http://127.0.0.1:5000`
7. Login with default credentials:
   - Username: `admin`
   - Password: `admin123`

## Common Setup Errors
- **ModuleNotFoundError:** activate the same virtual environment where dependencies were installed.
- **Port already in use:** run on a new port (update `app.run(...)` in `app.py`).
- **Database locked:** close other running app instances using the same `database.db`.

## Sample Test Cases (Expected Results)
1. Valid login with `admin/admin123` -> dashboard loads.
2. Invalid login -> error message.
3. Submit vehicle entry with missing fields -> validation error.
4. Add same vehicle while still parked -> duplicate active entry blocked.
5. Assign occupied slot manually -> blocked.
6. Exit parked vehicle -> fee displayed and slot becomes available.
7. Dashboard counts/revenue update after entry/exit.
8. Empty database tables -> pages still render with zero counts/no records.

## Screenshots
Add screenshots in this section for:
- Login
- Dashboard
- Vehicle Entry
- Parked Vehicles
- Parking Slots
- Reports

## Notes
- `database.db` is generated locally and ignored by git.
- Application uses parameterized SQL queries and enables SQLite foreign keys.
