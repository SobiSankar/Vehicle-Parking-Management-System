# Vehicle-Parking-Management-System

A smart vehicle parking management system built with **Python, Flask, SQLite, HTML, CSS, and JavaScript**.

## Features

- Admin login and logout (secure password hashing)
- Dashboard with:
  - Total vehicles
  - Currently parked vehicles
  - Available slots
  - Total revenue
- Vehicle entry form:
  - Vehicle number
  - Owner name
  - Contact number
  - Vehicle type
  - Slot (auto/manual)
- Automatic slot allocation with duplicate occupancy prevention
- Live table of currently parked vehicles
- Vehicle search by vehicle number
- Vehicle exit with automatic fee calculation using entry/exit time
- Slot status update on both entry and exit
- Parking history and daily revenue report

## Tech Stack

- Backend: Flask + SQLite
- Frontend: HTML, CSS, JavaScript

## Project Structure

```text
Vehicle-Parking-Management-System/
├── app.py
├── requirements.txt
├── instance/
│   └── parking.db
├── static/
│   ├── script.js
│   └── style.css
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   └── reports.html
└── README.md
```

## Setup and Run (VS Code Terminal)

1. Open the repository folder in VS Code.
2. Run:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

3. Open in browser:

```text
http://127.0.0.1:5000
```

## Default Admin Login

- Username: `admin`
- Password: `admin123`

> Change the default password after first login for production usage.
