import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DB_NAME = "schoolfix.db"


def connect():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = connect()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'student',
        active INTEGER NOT NULL DEFAULT 1
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS admin_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        date TEXT NOT NULL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        category TEXT NOT NULL,
        location TEXT,
        message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending',
        date TEXT NOT NULL,
        admin_note TEXT DEFAULT ''
    )""")

    cur.execute("SELECT COUNT(*) FROM users WHERE role='main_admin'")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT OR IGNORE INTO users (username,password,role,active) VALUES (?,?,?,1)",
                    ("mainadmin1", generate_password_hash("ChangeMe123"), "main_admin"))
        cur.execute("INSERT OR IGNORE INTO users (username,password,role,active) VALUES (?,?,?,1)",
                    ("mainadmin2", generate_password_hash("ChangeMe456"), "main_admin"))
    conn.commit()
    conn.close()


def save_user(username, password, role="student"):
    conn = connect()
    conn.execute("INSERT INTO users (username,password,role) VALUES (?,?,?)",
                 (username, generate_password_hash(password), role))
    conn.commit()
    conn.close()


def get_user(username, password):
    conn = connect()
    row = conn.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
    conn.close()
    if row and check_password_hash(row[2], password):
        return row
    return None


def save_admin_application(username, reason):
    conn = connect()
    conn.execute("INSERT INTO admin_applications (username,reason,date) VALUES (?,?,?)",
                 (username, reason, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()


def get_pending_applications():
    conn = connect()
    rows = conn.execute("SELECT * FROM admin_applications WHERE status='Pending' ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def approve_admin(application_id):
    conn = connect()
    row = conn.execute("SELECT username FROM admin_applications WHERE id=?", (application_id,)).fetchone()
    if row:
        conn.execute("UPDATE users SET role='admin' WHERE username=?", (row[0],))
        conn.execute("UPDATE admin_applications SET status='Approved' WHERE id=?", (application_id,))
    conn.commit()
    conn.close()


def reject_admin(application_id):
    conn = connect()
    conn.execute("UPDATE admin_applications SET status='Rejected' WHERE id=?", (application_id,))
    conn.commit()
    conn.close()


def save_report(username, category, location, message):
    conn = connect()
    conn.execute("INSERT INTO reports (username,category,location,message,date) VALUES (?,?,?,?,?)",
                 (username, category, location, message, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()


def get_all_reports():
    conn = connect()
    rows = conn.execute("SELECT * FROM reports ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def get_user_reports(username):
    conn = connect()
    rows = conn.execute("SELECT * FROM reports WHERE username=? ORDER BY id DESC", (username,)).fetchall()
    conn.close()
    return rows


def update_report_status(report_id, status, admin_note=""):
    conn = connect()
    conn.execute("UPDATE reports SET status=?, admin_note=? WHERE id=?", (status, admin_note, report_id))
    conn.commit()
    conn.close()


def get_unreasonable_reports():
    conn = connect()
    rows = conn.execute("SELECT * FROM reports WHERE status='Unreasonable' ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def delete_report(report_id):
    conn = connect()
    conn.execute("DELETE FROM reports WHERE id=?", (report_id,))
    conn.commit()
    conn.close()
