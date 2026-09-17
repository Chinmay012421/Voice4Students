import os
import sqlite3
from datetime import datetime

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# =========================================================
# DATABASE
# =========================================================

DB_NAME = "schoolfix.db"


def connect():
    conn = sqlite3.connect(
        DB_NAME,
        timeout=30
    )

    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():

    conn = connect()
    cur = conn.cursor()

    # =====================================================
    # USERS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            active INTEGER NOT NULL DEFAULT 1,
            must_change_password INTEGER NOT NULL DEFAULT 0,
            registered_at TEXT NOT NULL DEFAULT ''
        )
    """)

    user_columns = {
        row[1]
        for row in cur.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    }

    if "must_change_password" not in user_columns:
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN must_change_password
            INTEGER NOT NULL DEFAULT 0
        """)

    if "registered_at" not in user_columns:
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN registered_at
            TEXT NOT NULL DEFAULT ''
        """)

        cur.execute("""
            UPDATE users
            SET registered_at=?
            WHERE registered_at IS NULL
               OR registered_at=''
        """, (now(),))

    # =====================================================
    # ADMIN APPLICATIONS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            date TEXT NOT NULL
        )
    """)

    # =====================================================
    # REPORTS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            category TEXT NOT NULL,
            location TEXT,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            date TEXT NOT NULL,
            admin_note TEXT DEFAULT '',
            photo TEXT DEFAULT ''
        )
    """)

    report_columns = {
        row[1]
        for row in cur.execute(
            "PRAGMA table_info(reports)"
        ).fetchall()
    }

    if "photo" not in report_columns:
        cur.execute("""
            ALTER TABLE reports
            ADD COLUMN photo TEXT DEFAULT ''
        """)

    # =====================================================
    # MULTIPLE REPORT PHOTOS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS report_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY(report_id)
                REFERENCES reports(id)
                ON DELETE CASCADE
        )
    """)

    # =====================================================
    # REPORT CONVERSATIONS
    # =====================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS report_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY(report_id)
                REFERENCES reports(id)
                ON DELETE CASCADE
        )
    """)

    # =====================================================
    # MIGRATE OLD SINGLE PHOTOS
    # =====================================================

    old_photos = cur.execute("""
        SELECT id, photo
        FROM reports
        WHERE photo IS NOT NULL
          AND photo != ''
    """).fetchall()

    for report_id, filename in old_photos:

        exists = cur.execute("""
            SELECT id
            FROM report_photos
            WHERE report_id=?
              AND filename=?
        """, (
            report_id,
            filename
        )).fetchone()

        if not exists:

            cur.execute("""
                INSERT INTO report_photos
                (
                    report_id,
                    filename,
                    uploaded_at
                )
                VALUES (?, ?, ?)
            """, (
                report_id,
                filename,
                now()
            ))

    # =====================================================
    # MIGRATE ORIGINAL REPORT MESSAGE
    # =====================================================

    old_reports = cur.execute("""
        SELECT
            id,
            username,
            message,
            date
        FROM reports
    """).fetchall()

    for report_id, username, message, report_date in old_reports:

        exists = cur.execute("""
            SELECT id
            FROM report_messages
            WHERE report_id=?
              AND username=?
              AND message=?
        """, (
            report_id,
            username,
            message
        )).fetchone()

        if not exists:

            role_row = cur.execute("""
                SELECT role
                FROM users
                WHERE username=?
            """, (username,)).fetchone()

            role = (
                role_row[0]
                if role_row
                else "student"
            )

            cur.execute("""
                INSERT INTO report_messages
                (
                    report_id,
                    username,
                    role,
                    message,
                    date
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                report_id,
                username,
                role,
                message,
                report_date
            ))

    # =====================================================
    # MAIN ADMIN ACCOUNTS
    # =====================================================
    #
    # IMPORTANT:
    #
    # Existing Main Admin accounts are NEVER overwritten.
    #
    # If Main Admin accounts already exist in schoolfix.db,
    # this section does nothing to their passwords.
    #
    # If this is a brand-new database, the passwords must
    # be supplied through environment variables.
    # =====================================================

    main_admins = [
        (
            "Principal",
            os.environ.get("Principal")
        ),
        (
            "Vice Principal",
            os.environ.get("Vice_Principal")
        ),
        (
            "Harshil Bisen",
            os.environ.get("Harshil_Bisen")
        ),
        (
            "Chinmay Epili",
            os.environ.get("Chinmay_Epili")
        ),
        (
            "Arshad Khan",
            os.environ.get("Arshad_Khan")
        )
    ]

    for username, password in main_admins:

        existing = cur.execute("""
            SELECT id, role
            FROM users
            WHERE username=?
        """, (username,)).fetchone()

        # Existing account:
        # NEVER replace its password.
        if existing:
            continue

        # Brand-new account:
        # only create it when its password exists.
        if password:

            cur.execute("""
                INSERT INTO users
                (
                    username,
                    password,
                    role,
                    active,
                    must_change_password,
                    registered_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                username,
                generate_password_hash(password),
                "main_admin",
                1,
                0,
                now()
            ))

    conn.commit()
    conn.close()


# =========================================================
# USERS
# =========================================================

def save_user(
    username,
    password,
    role="student"
):

    username = username.strip()

    if not username or not password:
        return False

    conn = connect()

    try:

        conn.execute("""
            INSERT INTO users
            (
                username,
                password,
                role,
                active,
                must_change_password,
                registered_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            username,
            generate_password_hash(password),
            role,
            1,
            0,
            now()
        ))

        conn.commit()

        return True

    except sqlite3.IntegrityError:
        conn.rollback()
        return False

    finally:
        conn.close()


def get_user(
    username,
    password
):

    conn = connect()

    row = conn.execute("""
        SELECT *
        FROM users
        WHERE username=?
          AND active=1
    """, (
        username,
    )).fetchone()

    conn.close()

    if not row:
        return None

    try:
        if check_password_hash(
            row[2],
            password
        ):
            return row
    except Exception:
        return None

    return None


def get_user_by_username(username):

    conn = connect()

    row = conn.execute("""
        SELECT *
        FROM users
        WHERE username=?
    """, (
        username,
    )).fetchone()

    conn.close()

    return row


def get_all_users():

    conn = connect()

    rows = conn.execute("""
        SELECT
            id,
            username,
            password,
            role,
            active,
            must_change_password,
            registered_at
        FROM users
        ORDER BY id ASC
    """).fetchall()

    conn.close()

    return rows


def deactivate_user(user_id):

    conn = connect()

    row = conn.execute("""
        SELECT role
        FROM users
        WHERE id=?
    """, (user_id,)).fetchone()

    if not row:
        conn.close()
        return False

    # Main Admin cannot be disabled here.
    if row[0] == "main_admin":
        conn.close()
        return False

    conn.execute("""
        UPDATE users
        SET active=0
        WHERE id=?
    """, (user_id,))

    conn.commit()
    conn.close()

    return True


def activate_user(user_id):

    conn = connect()

    conn.execute("""
        UPDATE users
        SET active=1
        WHERE id=?
    """, (user_id,))

    conn.commit()
    conn.close()

    return True


# =========================================================
# ADMIN APPLICATIONS
# =========================================================

def save_admin_application(
    username,
    reason
):

    conn = connect()

    conn.execute("""
        INSERT INTO admin_applications
        (
            username,
            reason,
            status,
            date
        )
        VALUES (?, ?, ?, ?)
    """, (
        username,
        reason,
        "Pending",
        now()
    ))

    conn.commit()
    conn.close()


def get_pending_applications():

    conn = connect()

    rows = conn.execute("""
        SELECT *
        FROM admin_applications
        WHERE status='Pending'
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return rows


def get_all_applications():

    conn = connect()

    rows = conn.execute("""
        SELECT *
        FROM admin_applications
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return rows


def approve_admin(
    application_id
):

    conn = connect()

    row = conn.execute("""
        SELECT username
        FROM admin_applications
        WHERE id=?
    """, (
        application_id,
    )).fetchone()

    if not row:
        conn.close()
        return False

    conn.execute("""
        UPDATE users
        SET role='admin'
        WHERE username=?
          AND role='student'
    """, (
        row[0],
    ))

    conn.execute("""
        UPDATE admin_applications
        SET status='Approved'
        WHERE id=?
    """, (
        application_id,
    ))

    conn.commit()
    conn.close()

    return True


def reject_admin(
    application_id
):

    conn = connect()

    conn.execute("""
        UPDATE admin_applications
        SET status='Rejected'
        WHERE id=?
    """, (
        application_id,
    ))

    conn.commit()
    conn.close()

    return True


# =========================================================
# REPORTS
# =========================================================

def save_report(
    username,
    category,
    location,
    message,
    photo=""
):

    message = message.strip()

    if not message:
        return None

    conn = connect()
    cur = conn.cursor()

    report_date = now()

    cur.execute("""
        INSERT INTO reports
        (
            username,
            category,
            location,
            message,
            status,
            date,
            admin_note,
            photo
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        username,
        category,
        location,
        message,
        "Pending",
        report_date,
        "",
        photo
    ))

    report_id = cur.lastrowid

    # Find reporter role
    role_row = cur.execute("""
        SELECT role
        FROM users
        WHERE username=?
    """, (
        username,
    )).fetchone()

    role = (
        role_row[0]
        if role_row
        else "student"
    )

    # Add original report message
    cur.execute("""
        INSERT INTO report_messages
        (
            report_id,
            username,
            role,
            message,
            date
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        report_id,
        username,
        role,
        message,
        report_date
    ))

    # Save first photo into multiple-photo table
    if photo:

        cur.execute("""
            INSERT INTO report_photos
            (
                report_id,
                filename,
                uploaded_at
            )
            VALUES (?, ?, ?)
        """, (
            report_id,
            photo,
            report_date
        ))

    conn.commit()
    conn.close()

    return report_id


def get_report(report_id):

    conn = connect()

    row = conn.execute("""
        SELECT *
        FROM reports
        WHERE id=?
    """, (
        report_id,
    )).fetchone()

    conn.close()

    return row


def get_all_reports():

    conn = connect()

    rows = conn.execute("""
        SELECT *
        FROM reports
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return rows


def get_user_reports(username):

    conn = connect()

    rows = conn.execute("""
        SELECT *
        FROM reports
        WHERE username=?
        ORDER BY id DESC
    """, (
        username,
    )).fetchall()

    conn.close()

    return rows


def update_report_status(
    report_id,
    status,
    admin_note=""
):

    allowed_statuses = {
        "Pending",
        "Reviewed",
        "In Progress",
        "Resolved",
        "Unreasonable"
    }

    if status not in allowed_statuses:
        return False

    conn = connect()

    conn.execute("""
        UPDATE reports
        SET
            status=?,
            admin_note=?
        WHERE id=?
    """, (
        status,
        admin_note,
        report_id
    ))

    changed = conn.total_changes > 0

    conn.commit()
    conn.close()

    return changed


def mark_report_unreasonable(report_id):

    conn = connect()

    conn.execute("""
        UPDATE reports
        SET status='Unreasonable'
        WHERE id=?
    """, (
        report_id,
    ))

    changed = conn.total_changes > 0

    conn.commit()
    conn.close()

    return changed


def get_unreasonable_reports():

    conn = connect()

    rows = conn.execute("""
        SELECT *
        FROM reports
        WHERE status='Unreasonable'
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return rows


def delete_report(report_id):

    conn = connect()

    # Explicit deletes keep this safe even if foreign keys
    # were not enabled by an older connection.

    conn.execute("""
        DELETE FROM report_messages
        WHERE report_id=?
    """, (
        report_id,
    ))

    conn.execute("""
        DELETE FROM report_photos
        WHERE report_id=?
    """, (
        report_id,
    ))

    conn.execute("""
        DELETE FROM reports
        WHERE id=?
    """, (
        report_id,
    ))

    changed = conn.total_changes > 0

    conn.commit()
    conn.close()

    return changed


# =========================================================
# REPORT PHOTOS
# =========================================================

def add_report_photo(
    report_id,
    filename
):

    if not filename:
        return False

    conn = connect()

    # Make sure report exists
    report = conn.execute("""
        SELECT id
        FROM reports
        WHERE id=?
    """, (
        report_id,
    )).fetchone()

    if not report:
        conn.close()
        return False

    conn.execute("""
        INSERT INTO report_photos
        (
            report_id,
            filename,
            uploaded_at
        )
        VALUES (?, ?, ?)
    """, (
        report_id,
        filename,
        now()
    ))

    conn.commit()
    conn.close()

    return True


def get_report_photos(report_id):

    conn = connect()

    rows = conn.execute("""
        SELECT
            id,
            report_id,
            filename,
            uploaded_at
        FROM report_photos
        WHERE report_id=?
        ORDER BY id ASC
    """, (
        report_id,
    )).fetchall()

    conn.close()

    return rows


def delete_report_photo(photo_id):

    conn = connect()

    row = conn.execute("""
        SELECT report_id, filename
        FROM report_photos
        WHERE id=?
    """, (
        photo_id,
    )).fetchone()

    if not row:
        conn.close()
        return None

    conn.execute("""
        DELETE FROM report_photos
        WHERE id=?
    """, (
        photo_id,
    ))

    conn.commit()
    conn.close()

    return row


# =========================================================
# REPORT CONVERSATION
# =========================================================

def add_report_message(
    report_id,
    username,
    role,
    message
):

    message = message.strip()

    if not message:
        return False

    conn = connect()

    report = conn.execute("""
        SELECT id
        FROM reports
        WHERE id=?
    """, (
        report_id,
    )).fetchone()

    if not report:
        conn.close()
        return False

    conn.execute("""
        INSERT INTO report_messages
        (
            report_id,
            username,
            role,
            message,
            date
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        report_id,
        username,
        role,
        message,
        now()
    ))

    conn.commit()
    conn.close()

    return True


def get_report_messages(report_id):

    conn = connect()

    rows = conn.execute("""
        SELECT
            id,
            report_id,
            username,
            role,
            message,
            date
        FROM report_messages
        WHERE report_id=?
        ORDER BY id ASC
    """, (
        report_id,
    )).fetchall()

    conn.close()

    return rows


# =========================================================
# PASSWORD MANAGEMENT
# =========================================================

def set_temporary_password(
    user_id,
    temporary_password
):

    if not temporary_password:
        return None

    conn = connect()

    row = conn.execute("""
        SELECT
            id,
            username,
            role
        FROM users
        WHERE id=?
    """, (
        user_id,
    )).fetchone()

    if not row:
        conn.close()
        return None

    # Main Admin accounts are protected.
    if row[2] == "main_admin":
        conn.close()
        return "protected"

    conn.execute("""
        UPDATE users
        SET
            password=?,
            must_change_password=1
        WHERE id=?
    """, (
        generate_password_hash(
            temporary_password
        ),
        user_id
    ))

    conn.commit()
    conn.close()

    return row[1]


def set_permanent_password(
    user_id,
    new_password
):

    if not new_password:
        return None

    conn = connect()

    row = conn.execute("""
        SELECT
            id,
            username,
            role
        FROM users
        WHERE id=?
          AND active=1
    """, (
        user_id,
    )).fetchone()

    if not row:
        conn.close()
        return None

    # Main Admin passwords cannot be changed through
    # ordinary user management.
    if row[2] == "main_admin":
        conn.close()
        return "protected"

    conn.execute("""
        UPDATE users
        SET
            password=?,
            must_change_password=0
        WHERE id=?
    """, (
        generate_password_hash(
            new_password
        ),
        user_id
    ))

    conn.commit()
    conn.close()

    return row[1]


def change_password(
    username,
    new_password
):

    if not new_password:
        return False

    conn = connect()

    row = conn.execute("""
        SELECT role
        FROM users
        WHERE username=?
          AND active=1
    """, (
        username,
    )).fetchone()

    if not row:
        conn.close()
        return False

    conn.execute("""
        UPDATE users
        SET
            password=?,
            must_change_password=0
        WHERE username=?
    """, (
        generate_password_hash(
            new_password
        ),
        username
    ))

    conn.commit()
    conn.close()

    return True


def must_change_password(username):

    conn = connect()

    row = conn.execute("""
        SELECT must_change_password
        FROM users
        WHERE username=?
          AND active=1
    """, (
        username,
    )).fetchone()

    conn.close()

    return bool(
        row and row[0]
    )


# =========================================================
# REPORT STATISTICS
# =========================================================

def get_report_stats():

    conn = connect()

    total = conn.execute("""
        SELECT COUNT(*)
        FROM reports
    """).fetchone()[0]

    pending = conn.execute("""
        SELECT COUNT(*)
        FROM reports
        WHERE status='Pending'
    """).fetchone()[0]

    reviewed = conn.execute("""
        SELECT COUNT(*)
        FROM reports
        WHERE status='Reviewed'
    """).fetchone()[0]

    in_progress = conn.execute("""
        SELECT COUNT(*)
        FROM reports
        WHERE status='In Progress'
    """).fetchone()[0]

    resolved = conn.execute("""
        SELECT COUNT(*)
        FROM reports
        WHERE status='Resolved'
    """).fetchone()[0]

    unreasonable = conn.execute("""
        SELECT COUNT(*)
        FROM reports
        WHERE status='Unreasonable'
    """).fetchone()[0]

    conn.close()

    return {
        "total": total,
        "pending": pending,
        "reviewed": reviewed,
        "in_progress": in_progress,
        "resolved": resolved,
        "unreasonable": unreasonable
    }
