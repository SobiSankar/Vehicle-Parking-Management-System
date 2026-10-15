PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS admin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_number TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Occupied')),
    supported_vehicle_type TEXT
);

CREATE TABLE IF NOT EXISTS vehicle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_number TEXT NOT NULL UNIQUE,
    owner_name TEXT NOT NULL,
    contact_number TEXT NOT NULL,
    vehicle_type TEXT NOT NULL CHECK(vehicle_type IN ('Two-wheeler', 'Car', 'Other'))
);

CREATE TABLE IF NOT EXISTS parking_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id INTEGER NOT NULL,
    slot_id INTEGER NOT NULL,
    entry_time TEXT NOT NULL,
    exit_time TEXT,
    parking_fee REAL,
    FOREIGN KEY(vehicle_id) REFERENCES vehicle(id) ON DELETE RESTRICT,
    FOREIGN KEY(slot_id) REFERENCES slots(id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_active_slot ON parking_records(slot_id) WHERE exit_time IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_vehicle ON parking_records(vehicle_id) WHERE exit_time IS NULL;
