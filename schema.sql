-- =========================================================
--  AI-Based Face Authentication System
--  schema.sql — MySQL Database Schema
-- =========================================================
--  HOW TO USE:
--    1. Open phpMyAdmin at http://localhost/phpmyadmin
--    2. Click "SQL" tab at the top
--    3. Paste this entire file and click "Go"
--
--  OR from MySQL command line:
--    mysql -u root -p < schema.sql
-- =========================================================


-- ── Step 1: Create the database ──────────────────────────
CREATE DATABASE IF NOT EXISTS face_auth_system
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE face_auth_system;


-- ── Step 2: Drop tables if they exist (clean start) ──────
DROP TABLE IF EXISTS login_history;
DROP TABLE IF EXISTS admin_logs;
DROP TABLE IF EXISTS users;


-- ═══════════════════════════════════════════════════════
--  TABLE: users
--  Stores one row per registered user.
--  face_data_path: folder path where face images live
--  password_hash:  SHA-256 of their password (fallback)
--  role:           'user' or 'admin'
--  is_active:      1=active, 0=suspended by admin
-- ═══════════════════════════════════════════════════════
CREATE TABLE users (
    id              INT UNSIGNED    AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(50)     NOT NULL UNIQUE,
    email           VARCHAR(120)    NOT NULL UNIQUE,
    full_name       VARCHAR(100)    NOT NULL,
    password_hash   VARCHAR(64)     NOT NULL,          -- SHA-256 = 64 hex chars
    face_data_path  VARCHAR(255)    DEFAULT NULL,      -- e.g. dataset/user_faces/alice
    role            ENUM('user','admin') NOT NULL DEFAULT 'user',
    is_active       TINYINT(1)      NOT NULL DEFAULT 1,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_username  (username),
    INDEX idx_email     (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ═══════════════════════════════════════════════════════
--  TABLE: login_history
--  Records EVERY login attempt (success or failure).
--  user_id is NULL when the face was not recognized
--  (i.e., an unknown intruder tried to log in).
-- ═══════════════════════════════════════════════════════
CREATE TABLE login_history (
    id              INT UNSIGNED    AUTO_INCREMENT PRIMARY KEY,
    user_id         INT UNSIGNED    DEFAULT NULL,      -- NULL = unknown face
    ip_address      VARCHAR(45)     NOT NULL,          -- IPv4 or IPv6
    status          ENUM('success','failed') NOT NULL,
    notes           VARCHAR(255)    DEFAULT NULL,      -- e.g. "Confidence: 94.3%"
    attempted_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key: if the user is deleted, keep history but set user_id to NULL
    CONSTRAINT fk_history_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    INDEX idx_user_id       (user_id),
    INDEX idx_status        (status),
    INDEX idx_attempted_at  (attempted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ═══════════════════════════════════════════════════════
--  TABLE: admin_logs
--  Audit trail for admin actions (optional / bonus).
--  e.g. "admin deactivated user X"
-- ═══════════════════════════════════════════════════════
CREATE TABLE admin_logs (
    id              INT UNSIGNED    AUTO_INCREMENT PRIMARY KEY,
    admin_id        INT UNSIGNED    NOT NULL,
    action          VARCHAR(200)    NOT NULL,
    target_user_id  INT UNSIGNED    DEFAULT NULL,
    logged_at       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_log_admin
        FOREIGN KEY (admin_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    INDEX idx_admin_id  (admin_id),
    INDEX idx_logged_at (logged_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ═══════════════════════════════════════════════════════
--  Seed Data: Create a default admin account
--  Password: "admin123"  → SHA-256 hash below
--  CHANGE THIS IN PRODUCTION!
-- ═══════════════════════════════════════════════════════
INSERT INTO users
    (username, email, full_name, password_hash, role, is_active, created_at)
VALUES (
    'admin',
    'admin@faceauth.local',
    'System Administrator',
    '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9',  -- "admin123"
    'admin',
    1,
    NOW()
);


-- ═══════════════════════════════════════════════════════
--  Quick verification: check tables were created
-- ═══════════════════════════════════════════════════════
SHOW TABLES;
SELECT 'Database setup complete!' AS status;
