"""
=========================================================
  database.py — MySQL Database Layer
=========================================================
  This file handles ALL database operations.
  It uses PyMySQL to connect to MySQL (via XAMPP).

  Functions provided:
    get_db_connection()      → Open & return a DB connection
    create_user(...)         → Insert a new user record
    get_user_by_username(u)  → Fetch user row by username
    log_login_attempt(...)   → Insert into login_history
    get_login_history(...)   → Fetch history rows
    get_all_users()          → Admin: fetch all users

  Design pattern: Each function opens its own connection,
  performs the query, and closes the connection.
  This is fine for a college project; for production you
  would use a connection pool (e.g., Flask-SQLAlchemy).
=========================================================
"""

import pymysql
import pymysql.cursors
import hashlib
import os
from datetime import datetime

# ── Database Configuration ─────────────────────────────
# These match XAMPP's default MySQL settings.
# Change DB_PASSWORD if you set a root password in XAMPP.
DB_CONFIG = {
    "host"    : "localhost",
    "port"    : 3306,
    "user"    : "root",
    "password": "",                  # XAMPP default: empty password
    "database": "face_auth_system",
    "charset" : "utf8mb4",
    # DictCursor returns rows as Python dictionaries
    # instead of tuples — much easier to work with!
    "cursorclass": pymysql.cursors.DictCursor
}


# ══════════════════════════════════════════════════════
#  get_db_connection()
#  Opens and returns a PyMySQL connection object.
#  Always call conn.close() after you're done!
# ══════════════════════════════════════════════════════
def get_db_connection():
    """
    Create and return a new database connection.
    Raises an exception if connection fails — make sure
    XAMPP MySQL service is running before starting Flask.
    """
    try:
        conn = pymysql.connect(**DB_CONFIG)
        return conn
    except pymysql.MySQLError as e:
        print(f"[DATABASE ERROR] Could not connect: {e}")
        raise


# ══════════════════════════════════════════════════════
#  hash_password(password)
#  SHA-256 hash a plaintext password before storing.
#  In a real app, use bcrypt or argon2 instead!
# ══════════════════════════════════════════════════════
def hash_password(password: str) -> str:
    """
    Returns the SHA-256 hex digest of the password string.
    Example: hash_password("hello") → "2cf24dba5fb..."
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ══════════════════════════════════════════════════════
#  create_user(username, email, full_name, password)
#  Inserts a new user into the `users` table.
#  Returns the new user's auto-increment ID, or None.
# ══════════════════════════════════════════════════════
def create_user(username: str, email: str,
                full_name: str, password: str):
    """
    Insert a new user record.
    Password is hashed before storage.
    Default role is 'user' (not admin).
    """
    conn   = None
    cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()

        hashed_pw = hash_password(password)

        sql = """
            INSERT INTO users
                (username, email, full_name, password_hash,
                 role, created_at, is_active)
            VALUES
                (%s, %s, %s, %s, 'user', NOW(), 1)
        """
        cursor.execute(sql, (username, email, full_name, hashed_pw))
        conn.commit()

        new_id = cursor.lastrowid    # MySQL auto-generated ID
        print(f"[DB] User created: {username} (ID={new_id})")
        return new_id

    except pymysql.MySQLError as e:
        print(f"[DB ERROR] create_user: {e}")
        if conn:
            conn.rollback()
        return None
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


# ══════════════════════════════════════════════════════
#  get_user_by_username(username)
#  Returns a dict with user info, or None if not found.
# ══════════════════════════════════════════════════════
def get_user_by_username(username: str):
    """
    SELECT a user row by username.
    Returns a dictionary like:
      {
        "id": 1, "username": "ali",
        "email": "ali@test.com", "full_name": "Ali Raza",
        "role": "user", "is_active": 1, ...
      }
    Returns None if username doesn't exist.
    """
    conn   = None
    cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()

        sql = "SELECT * FROM users WHERE username = %s LIMIT 1"
        cursor.execute(sql, (username,))
        return cursor.fetchone()   # dict or None

    except pymysql.MySQLError as e:
        print(f"[DB ERROR] get_user_by_username: {e}")
        return None
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


# ══════════════════════════════════════════════════════
#  log_login_attempt(user_id, ip, status, notes)
#  Inserts a row into login_history table.
#  Call this on EVERY login attempt — success or failure.
# ══════════════════════════════════════════════════════
def log_login_attempt(user_id, ip_address: str,
                      status: str, notes: str = ""):
    """
    Record a login attempt.
    Parameters:
      user_id    : int or None (None = unknown user)
      ip_address : string (request.remote_addr)
      status     : "success" or "failed"
      notes      : extra info (e.g., confidence score)
    """
    conn   = None
    cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()

        sql = """
            INSERT INTO login_history
                (user_id, ip_address, status, notes, attempted_at)
            VALUES
                (%s, %s, %s, %s, NOW())
        """
        cursor.execute(sql, (user_id, ip_address, status, notes))
        conn.commit()
        print(f"[DB] Login logged: status={status}, ip={ip_address}")

    except pymysql.MySQLError as e:
        print(f"[DB ERROR] log_login_attempt: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


# ══════════════════════════════════════════════════════
#  get_login_history(user_id=None, limit=20)
#  Returns a list of login history rows (dicts).
#  If user_id is provided, filter by that user.
#  If user_id is None, return history for ALL users.
# ══════════════════════════════════════════════════════
def get_login_history(user_id=None, limit: int = 20):
    """
    Fetch login history records.
    Joins with users table to also get the username.
    Most recent attempts shown first (ORDER BY DESC).
    """
    conn   = None
    cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()

        if user_id:
            sql = """
                SELECT
                    lh.id,
                    u.username,
                    u.full_name,
                    lh.ip_address,
                    lh.status,
                    lh.notes,
                    lh.attempted_at
                FROM login_history lh
                LEFT JOIN users u ON lh.user_id = u.id
                WHERE lh.user_id = %s
                ORDER BY lh.attempted_at DESC
                LIMIT %s
            """
            cursor.execute(sql, (user_id, limit))
        else:
            sql = """
                SELECT
                    lh.id,
                    u.username,
                    u.full_name,
                    lh.ip_address,
                    lh.status,
                    lh.notes,
                    lh.attempted_at
                FROM login_history lh
                LEFT JOIN users u ON lh.user_id = u.id
                ORDER BY lh.attempted_at DESC
                LIMIT %s
            """
            cursor.execute(sql, (limit,))

        return cursor.fetchall()   # list of dicts

    except pymysql.MySQLError as e:
        print(f"[DB ERROR] get_login_history: {e}")
        return []
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


# ══════════════════════════════════════════════════════
#  get_all_users()
#  Admin function — returns all users from the DB.
# ══════════════════════════════════════════════════════
def get_all_users():
    """
    Returns all users (excluding sensitive password hash).
    Used on the admin panel to show the user list.
    """
    conn   = None
    cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()

        sql = """
            SELECT id, username, email, full_name,
                   role, is_active, created_at
            FROM users
            ORDER BY created_at DESC
        """
        cursor.execute(sql)
        return cursor.fetchall()

    except pymysql.MySQLError as e:
        print(f"[DB ERROR] get_all_users: {e}")
        return []
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()


# ══════════════════════════════════════════════════════
#  get_login_stats()
#  Returns summary statistics for admin dashboard
# ══════════════════════════════════════════════════════
def get_login_stats():
    """
    Returns a dict with:
      - total_users      : int
      - total_logins     : int
      - successful_logins: int
      - failed_logins    : int
    """
    conn   = None
    cursor = None
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()

        stats = {}

        cursor.execute("SELECT COUNT(*) AS cnt FROM users")
        stats["total_users"] = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) AS cnt FROM login_history")
        stats["total_logins"] = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) AS cnt FROM login_history WHERE status='success'")
        stats["successful_logins"] = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) AS cnt FROM login_history WHERE status='failed'")
        stats["failed_logins"] = cursor.fetchone()["cnt"]

        return stats

    except pymysql.MySQLError as e:
        print(f"[DB ERROR] get_login_stats: {e}")
        return {}
    finally:
        if cursor: cursor.close()
        if conn:   conn.close()
