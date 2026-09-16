import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DB_NAME = "schoolfix.db"


def connect():
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_db():
    conn = connect()
    cur = conn.cursor()

    # USERS TABLE
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'student',
        active INTEGER NOT NULL DEFAULT 1,
        must_change_password INTEGER NOT NULL DEFAULT 0,
        registered_at TEXT NOT NULL DEFAULT ''
    )""")

    # Safe migrations for older databases
    user_columns = [
        row[1]
        for row in cur.execute("PRAGMA table_info(users)").fetchall()
    ]

    if "must_change_password" not in user_columns:
        cur.execute(
            "ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0"
        )

    if "registered_at" not in user_columns:
        cur.execute(
            "ALTER TABLE users ADD COLUMN registered_at TEXT NOT NULL DEFAULT ''"
        )
        cur.execute(
            "UPDATE users SET registered_at=? WHERE registered_at=''",
            (datetime.now().strftime("%Y-%m-%d %H:%M"),)
        )

    # ADMIN APPLICATIONS TABLE
    cur.execute("""CREATE TABLE IF NOT EXISTS admin_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        date TEXT NOT NULL
    )""")

    # REPORTS TABLE
    cur.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        category TEXT NOT NULL,
        location TEXT,
        message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        date TEXT NOT NULL,
        admin_note TEXT DEFAULT '',
        photo TEXT DEFAULT ''
    )""")

    # Safe migration for photo column
    report_columns = [
        row[1]
        for row in cur.execute("PRAGMA table_info(reports)").fetchall()
    ]

    if "photo" not in report_columns:
        cur.execute(
            "ALTER TABLE reports ADD COLUMN photo TEXT DEFAULT ''"
        )

    # CREATE MAIN ADMIN ACCOUNTS IF NONE EXIST
    cur.execute("SELECT COUNT(*) FROM users WHERE role='main_admin'")

    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT OR IGNORE INTO users "
            "(username,password,role,active) VALUES (?,?,?,1)",
            (
                "Principal",
                generate_password_hash("KVAG1404P"),
                "main_admin"
            )
        )

        cur.execute(
            "INSERT OR IGNORE INTO users "
            "(username,password,role,active) VALUES (?,?,?,1)",
            (
                "Vice Principal",
                generate_password_hash("KVAG1404VP"),
                "main_admin"
            )
        )

        cur.execute(
            "INSERT OR IGNORE INTO users "
            "(username,password,role,active) VALUES (?,?,?,1)",
            (
                "Harshil Bisen",
                generate_password_hash("Backend_Dev"),
                "main_admin"
            )
        )

        cur.execute(
            "INSERT OR IGNORE INTO users "
            "(username,password,role,active) VALUES (?,?,?,1)",
            (
                "Chinmay Epili",
                generate_password_hash("Frontend_Dev"),
                "main_admin"
            )
        )

    conn.commit()
    conn.close()


def save_user(username, password, role="student"):
    conn = connect()

    conn.execute(
        "INSERT INTO users "
        "(username,password,role,must_change_password,registered_at) "
        "VALUES (?,?,?,?,?)",
        (
            username,
            generate_password_hash(password),
            role,
            0,
            datetime.now().strftime("%Y-%m-%d %H:%M")
        )
    )

    conn.commit()
    conn.close()


def get_user(username, password):
    conn = connect()

    row = conn.execute(
        "SELECT * FROM users WHERE username=? AND active=1",
        (username,)
    ).fetchone()

    conn.close()

    if row and check_password_hash(row[2], password):
        return row

    return None


def save_admin_application(username, reason):
    conn = connect()

    conn.execute(
        "INSERT INTO admin_applications (username,reason,date) "
        "VALUES (?,?,?)",
        (
            username,
            reason,
            datetime.now().strftime("%Y-%m-%d %H:%M")
        )
    )

    conn.commit()
    conn.close()


def get_pending_applications():
    conn = connect()

    rows = conn.execute(
        "SELECT * FROM admin_applications "
        "WHERE status='Pending' ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return rows


def approve_admin(application_id):
    conn = connect()

    row = conn.execute(
        "SELECT username FROM admin_applications WHERE id=?",
        (application_id,)
    ).fetchone()

    if row:
        conn.execute(
            "UPDATE users SET role='admin' WHERE username=?",
            (row[0],)
        )

        conn.execute(
            "UPDATE admin_applications SET status='Approved' WHERE id=?",
            (application_id,)
        )

    conn.commit()
    conn.close()


def reject_admin(application_id):
    conn = connect()

    conn.execute(
        "UPDATE admin_applications SET status='Rejected' WHERE id=?",
        (application_id,)
    )

    conn.commit()
    conn.close()


def save_report(username, category, location, message, photo=""):
    conn = connect()

    conn.execute(
        """INSERT INTO reports
        (username, category, location, message, date, photo)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (
            username,
            category,
            location,
            message,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            photo
        )
    )

    conn.commit()
    conn.close()


def get_all_reports():
    conn = connect()

    rows = conn.execute(
        "SELECT * FROM reports ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return rows


def get_user_reports(username):
    conn = connect()

    rows = conn.execute(
        "SELECT * FROM reports "
        "WHERE username=? ORDER BY id DESC",
        (username,)
    ).fetchall()

    conn.close()

    return rows


def update_report_status(report_id, status, admin_note=""):
    conn = connect()

    conn.execute(
        "UPDATE reports SET status=?, admin_note=? WHERE id=?",
        (status, admin_note, report_id)
    )

    conn.commit()
    conn.close()


def get_unreasonable_reports():
    conn = connect()

    rows = conn.execute(
        "SELECT * FROM reports "
        "WHERE status='Unreasonable' ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return rows


def delete_report(report_id):
    conn = connect()

    conn.execute(
        "DELETE FROM reports WHERE id=?",
        (report_id,)
    )

    conn.commit()
    conn.close()


def get_all_users():
    conn = connect()

    rows = conn.execute(
        "SELECT id, username, role, active, "
        "must_change_password, registered_at "
        "FROM users ORDER BY id ASC"
    ).fetchall()

    conn.close()

    return rows


def set_temporary_password(user_id, temporary_password):
    conn = connect()
    cur = conn.cursor()

    row = cur.execute(
        "SELECT id, username, role FROM users WHERE id=?",
        (user_id,)
    ).fetchone()

    if not row:
        conn.close()
        return None

    if row[2] == "main_admin":
        conn.close()
        return "protected"

    cur.execute(
        "UPDATE users SET password=?, must_change_password=1 "
        "WHERE id=?",
        (
            generate_password_hash(temporary_password),
            user_id
        )
    )

    conn.commit()
    conn.close()

    return row[1]


def change_password(username, new_password):
    conn = connect()

    conn.execute(
        "UPDATE users SET password=?, must_change_password=0 "
        "WHERE username=?",
        (
            generate_password_hash(new_password),
            username
        )
    )

    conn.commit()
    conn.close()


def must_change_password(username):
    conn = connect()

    row = conn.execute(
        "SELECT must_change_password "
        "FROM users WHERE username=? AND active=1",
        (username,)
    ).fetchone()

    conn.close()

    return bool(row and row[0])


def get_report_stats():
    conn = connect()

    total = conn.execute(
        "SELECT COUNT(*) FROM reports"
    ).fetchone()[0]

    pending = conn.execute(
        "SELECT COUNT(*) FROM reports WHERE status='Pending'"
    ).fetchone()[0]

    reviewed = conn.execute(
        "SELECT COUNT(*) FROM reports WHERE status='Reviewed'"
    ).fetchone()[0]

    resolved = conn.execute(
        "SELECT COUNT(*) FROM reports WHERE status='Resolved'"
    ).fetchone()[0]

    unreasonable = conn.execute(
        "SELECT COUNT(*) FROM reports WHERE status='Unreasonable'"
    ).fetchone()[0]

    conn.close()

    return {
        "total": total,
        "pending": pending,
        "reviewed": reviewed,
        "resolved": resolved,
        "unreasonable": unreasonable
    }
