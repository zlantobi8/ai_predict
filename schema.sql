-- Run this once in phpMyAdmin / mysql CLI against your XAMPP MySQL server,
-- or just run `python setup_db.py`, which does this for you AND upgrades a
-- database that was created from an older version of this file.
CREATE DATABASE IF NOT EXISTS predictive_maintenance_db;
USE predictive_maintenance_db;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    staff_id VARCHAR(50) NOT NULL UNIQUE,         -- the login name
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(30) NOT NULL DEFAULT 'maintenance_staff',  -- admin, maintenance_staff, technical_staff
    status VARCHAR(20) NOT NULL DEFAULT 'active',            -- active, inactive
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS equipment (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    equipment_type VARCHAR(50) NOT NULL,          -- lathe, drilling, ac, water-pump (what the ML model knows)
    category VARCHAR(50) NOT NULL,                -- Laboratory Equipment, Workshop Equipment, Computer Laboratory, Other Infrastructure
    location VARCHAR(120),
    status VARCHAR(30) NOT NULL DEFAULT 'operational',   -- operational, at_risk, faulty (updated by every prediction)
    operating_hours FLOAT NOT NULL DEFAULT 0,
    installed_date DATE,
    last_maintenance_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sensor_readings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    equipment_id INT NOT NULL,
    temperature FLOAT NOT NULL,
    vibration FLOAT NOT NULL,
    voltage FLOAT NOT NULL,
    operating_hours FLOAT NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS maintenance_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    equipment_id INT NOT NULL,
    maintenance_type VARCHAR(50) NOT NULL,        -- Preventive, Corrective, Routine Inspection
    description TEXT,
    technician VARCHAR(120),
    status VARCHAR(30) NOT NULL DEFAULT 'scheduled', -- scheduled, in_progress, completed
    scheduled_date DATE,
    completed_date DATE,
    created_by VARCHAR(100) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    equipment_id INT NOT NULL,
    temperature FLOAT NOT NULL,
    vibration FLOAT NOT NULL,
    voltage FLOAT NOT NULL,
    operating_hours FLOAT NOT NULL,
    maintenance_history VARCHAR(20) NOT NULL,     -- recent, moderate, overdue
    predicted_condition VARCHAR(50) NOT NULL,
    risk_level VARCHAR(20) NOT NULL,
    confidence FLOAT NOT NULL,
    created_by VARCHAR(100) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    equipment_id INT NOT NULL,
    message VARCHAR(255) NOT NULL,
    severity VARCHAR(20) NOT NULL,                -- low, medium, high, critical
    status VARCHAR(20) NOT NULL DEFAULT 'open',   -- open, acknowledged, resolved
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE CASCADE
);
