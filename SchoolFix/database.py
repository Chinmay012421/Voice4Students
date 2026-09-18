import os
from datetime import datetime

from supabase import create_client, Client
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# =========================================================
# SUPABASE
# =========================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL environment variable is missing.")

if not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_KEY environment variable is missing.")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY
)


# =========================================================
# TIME
# =========================================================

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# =========================================================
# HELPERS
# =========================================================

def _first(response):
    """
    Return the first Supabase row or None.
    """
    if response and response.data:
        return response.data[0]
    return None


def _rows(response):
    """
    Return Supabase rows safely.
    """
    if response and response.data:
        return response.data
    return []


def _user_tuple(row):
    """
    Keep the same tuple format used by the old SQLite database.

    Indexes:
        0 = id
        1 = username
        2 = password
        3 = role
        4 = active
        5 = must_change_password
        6 = registered_at
    """

    if not row:
        return None

    return (
        row.get("id"),
        row.get("username"),
        row.get("password"),
        row.get("role"),
        row.get("active"),
        row.get("must_change_password"),
        row.get("registered_at")
    )


def _report_tuple(row):
    """
    Keep the same report tuple format as SQLite.

    Indexes:
        0 = id
        1 = username
        2 = category
        3 = location
        4 = message
        5 = status
        6 = date
        7 = admin_note
        8 = photo
    """

    if not row:
        return None

    return (
        row.get("id"),
        row.get("username"),
        row.get("category"),
        row.get("location"),
        row.get("message"),
        row.get("status"),
        row.get("date"),
        row.get("admin_note"),
        row.get("photo")
    )


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():

    # =====================================================
    # IMPORTANT
    #
    # The tables are already created in Supabase SQL Editor.
    #
    # This function ONLY ensures that the required Main
    # Admin accounts exist.
    #
    # EXISTING MAIN ADMIN PASSWORDS ARE NEVER OVERWRITTEN.
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
        )
    ]

    for username, password in main_admins:

        try:

            # -------------------------------------------------
            # Check whether the account already exists.
            # -------------------------------------------------

            response = (
                supabase
                .table("users")
                .select("id, username, role, password")
                .eq("username", username)
                .limit(1)
                .execute()
            )

            existing = _first(response)

            # -------------------------------------------------
            # CRITICAL:
            #
            # If the Main Admin already exists, DO NOTHING.
            #
            # This means the existing password remains exactly
            # as it is.
            # -------------------------------------------------

            if existing:
                continue

            # -------------------------------------------------
            # Account doesn't exist.
            #
            # Only create it if its password exists in Render
            # environment variables.
            # -------------------------------------------------

            if not password:
                print(
                    f"WARNING: Password environment variable "
                    f"missing for Main Admin '{username}'."
                )
                continue

            supabase.table("users").insert({
                "username": username,
                "password": generate_password_hash(password),
                "role": "main_admin",
                "active": True,
                "must_change_password": False,
                "registered_at": now()
            }).execute()

            print(
                f"Main Admin created: {username}"
            )

        except Exception as e:

            print(
                f"ERROR while initializing Main Admin "
                f"'{username}': {e}"
            )


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

    try:

        existing = (
            supabase
            .table("users")
            .select("id")
            .eq("username", username)
            .limit(1)
            .execute()
        )

        if existing.data:
            return False

        supabase.table("users").insert({
            "username": username,
            "password": generate_password_hash(password),
            "role": role,
            "active": True,
            "must_change_password": False,
            "registered_at": now()
        }).execute()

        return True

    except Exception as e:

        print("save_user error:", e)
        return False


def get_user(
    username,
    password
):

    try:

        response = (
            supabase
            .table("users")
            .select(
                "id, username, password, role, active, "
                "must_change_password, registered_at"
            )
            .eq("username", username)
            .eq("active", True)
            .limit(1)
            .execute()
        )

        row = _first(response)

        if not row:
            return None

        try:

            if check_password_hash(
                row.get("password", ""),
                password
            ):
                return _user_tuple(row)

        except Exception:
            return None

    except Exception as e:

        print("get_user error:", e)

    return None


def get_user_by_username(username):

    try:

        response = (
            supabase
            .table("users")
            .select(
                "id, username, password, role, active, "
                "must_change_password, registered_at"
            )
            .eq("username", username)
            .limit(1)
            .execute()
        )

        return _user_tuple(_first(response))

    except Exception as e:

        print("get_user_by_username error:", e)
        return None


def get_all_users():

    try:

        response = (
            supabase
            .table("users")
            .select(
                "id, username, password, role, active, "
                "must_change_password, registered_at"
            )
            .order("id")
            .execute()
        )

        return [
            _user_tuple(row)
            for row in _rows(response)
        ]

    except Exception as e:

        print("get_all_users error:", e)
        return []


def deactivate_user(user_id):

    try:

        response = (
            supabase
            .table("users")
            .select("role")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

        row = _first(response)

        if not row:
            return False

        # Main Admin cannot be disabled.
        if row.get("role") == "main_admin":
            return False

        result = (
            supabase
            .table("users")
            .update({"active": False})
            .eq("id", user_id)
            .execute()
        )

        return bool(result.data)

    except Exception as e:

        print("deactivate_user error:", e)
        return False


def activate_user(user_id):

    try:

        result = (
            supabase
            .table("users")
            .update({"active": True})
            .eq("id", user_id)
            .execute()
        )

        return bool(result.data)

    except Exception as e:

        print("activate_user error:", e)
        return False


# =========================================================
# ADMIN APPLICATIONS
# =========================================================

def save_admin_application(
    username,
    reason
):

    try:

        supabase.table("admin_applications").insert({
            "username": username,
            "reason": reason,
            "status": "Pending",
            "date": now()
        }).execute()

        return True

    except Exception as e:

        print("save_admin_application error:", e)
        return False


def get_pending_applications():

    try:

        response = (
            supabase
            .table("admin_applications")
            .select("*")
            .eq("status", "Pending")
            .order("id", desc=True)
            .execute()
        )

        rows = []

        for row in _rows(response):

            rows.append((
                row.get("id"),
                row.get("username"),
                row.get("reason"),
                row.get("status"),
                row.get("date")
            ))

        return rows

    except Exception as e:

        print("get_pending_applications error:", e)
        return []


def get_all_applications():

    try:

        response = (
            supabase
            .table("admin_applications")
            .select("*")
            .order("id", desc=True)
            .execute()
        )

        rows = []

        for row in _rows(response):

            rows.append((
                row.get("id"),
                row.get("username"),
                row.get("reason"),
                row.get("status"),
                row.get("date")
            ))

        return rows

    except Exception as e:

        print("get_all_applications error:", e)
        return []


def approve_admin(
    application_id
):

    try:

        response = (
            supabase
            .table("admin_applications")
            .select("username")
            .eq("id", application_id)
            .limit(1)
            .execute()
        )

        row = _first(response)

        if not row:
            return False

        username = row.get("username")

        # Promote only a student.
        supabase.table("users").update({
            "role": "admin"
        }).eq(
            "username", username
        ).eq(
            "role", "student"
        ).execute()

        supabase.table("admin_applications").update({
            "status": "Approved"
        }).eq(
            "id", application_id
        ).execute()

        return True

    except Exception as e:

        print("approve_admin error:", e)
        return False


def reject_admin(
    application_id
):

    try:

        result = (
            supabase
            .table("admin_applications")
            .update({
                "status": "Rejected"
            })
            .eq("id", application_id)
            .execute()
        )

        return bool(result.data)

    except Exception as e:

        print("reject_admin error:", e)
        return False


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

    try:

        report_date = now()

        response = supabase.table("reports").insert({
            "username": username,
            "category": category,
            "location": location,
            "message": message,
            "status": "Pending",
            "date": report_date,
            "admin_note": "",
            "photo": photo
        }).execute()

        row = _first(response)

        if not row:
            return None

        report_id = row.get("id")

        # -------------------------------------------------
        # Find reporter role
        # -------------------------------------------------

        role_response = (
            supabase
            .table("users")
            .select("role")
            .eq("username", username)
            .limit(1)
            .execute()
        )

        role_row = _first(role_response)

        role = (
            role_row.get("role")
            if role_row
            else "student"
        )

        # -------------------------------------------------
        # Original report message
        # -------------------------------------------------

        supabase.table("report_messages").insert({
            "report_id": report_id,
            "username": username,
            "role": role,
            "message": message,
            "date": report_date
        }).execute()

        # -------------------------------------------------
        # First photo
        # -------------------------------------------------

        if photo:

            supabase.table("report_photos").insert({
                "report_id": report_id,
                "filename": photo,
                "uploaded_at": report_date
            }).execute()

        return report_id

    except Exception as e:

        print("save_report error:", e)
        return None


def get_report(report_id):

    try:

        response = (
            supabase
            .table("reports")
            .select("*")
            .eq("id", report_id)
            .limit(1)
            .execute()
        )

        return _report_tuple(_first(response))

    except Exception as e:

        print("get_report error:", e)
        return None


def get_all_reports():

    try:

        response = (
            supabase
            .table("reports")
            .select("*")
            .order("id", desc=True)
            .execute()
        )

        return [
            _report_tuple(row)
            for row in _rows(response)
        ]

    except Exception as e:

        print("get_all_reports error:", e)
        return []


def get_user_reports(username):

    try:

        response = (
            supabase
            .table("reports")
            .select("*")
            .eq("username", username)
            .order("id", desc=True)
            .execute()
        )

        return [
            _report_tuple(row)
            for row in _rows(response)
        ]

    except Exception as e:

        print("get_user_reports error:", e)
        return []


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

    try:

        response = (
            supabase
            .table("reports")
            .update({
                "status": status,
                "admin_note": admin_note
            })
            .eq("id", report_id)
            .execute()
        )

        return bool(response.data)

    except Exception as e:

        print("update_report_status error:", e)
        return False


def mark_report_unreasonable(report_id):

    try:

        response = (
            supabase
            .table("reports")
            .update({
                "status": "Unreasonable"
            })
            .eq("id", report_id)
            .execute()
        )

        return bool(response.data)

    except Exception as e:

        print("mark_report_unreasonable error:", e)
        return False


def get_unreasonable_reports():

    try:

        response = (
            supabase
            .table("reports")
            .select("*")
            .eq("status", "Unreasonable")
            .order("id", desc=True)
            .execute()
        )

        return [
            _report_tuple(row)
            for row in _rows(response)
        ]

    except Exception as e:

        print("get_unreasonable_reports error:", e)
        return []


def delete_report(report_id):

    try:

        # Delete messages first.
        supabase.table("report_messages").delete().eq(
            "report_id", report_id
        ).execute()

        # Delete photo records.
        supabase.table("report_photos").delete().eq(
            "report_id", report_id
        ).execute()

        # Delete report.
        response = (
            supabase
            .table("reports")
            .delete()
            .eq("id", report_id)
            .execute()
        )

        return bool(response.data)

    except Exception as e:

        print("delete_report error:", e)
        return False


# =========================================================
# REPORT PHOTOS
# =========================================================

def add_report_photo(
    report_id,
    filename
):

    if not filename:
        return False

    try:

        # Make sure report exists.
        report_response = (
            supabase
            .table("reports")
            .select("id")
            .eq("id", report_id)
            .limit(1)
            .execute()
        )

        if not _first(report_response):
            return False

        supabase.table("report_photos").insert({
            "report_id": report_id,
            "filename": filename,
            "uploaded_at": now()
        }).execute()

        return True

    except Exception as e:

        print("add_report_photo error:", e)
        return False


def get_report_photos(report_id):

    try:

        response = (
            supabase
            .table("report_photos")
            .select(
                "id, report_id, filename, uploaded_at"
            )
            .eq("report_id", report_id)
            .order("id")
            .execute()
        )

        return [
            (
                row.get("id"),
                row.get("report_id"),
                row.get("filename"),
                row.get("uploaded_at")
            )
            for row in _rows(response)
        ]

    except Exception as e:

        print("get_report_photos error:", e)
        return []


def delete_report_photo(photo_id):

    try:

        response = (
            supabase
            .table("report_photos")
            .select("report_id, filename")
            .eq("id", photo_id)
            .limit(1)
            .execute()
        )

        row = _first(response)

        if not row:
            return None

        supabase.table("report_photos").delete().eq(
            "id", photo_id
        ).execute()

        return (
            row.get("report_id"),
            row.get("filename")
        )

    except Exception as e:

        print("delete_report_photo error:", e)
        return None


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

    try:

        report_response = (
            supabase
            .table("reports")
            .select("id")
            .eq("id", report_id)
            .limit(1)
            .execute()
        )

        if not _first(report_response):
            return False

        supabase.table("report_messages").insert({
            "report_id": report_id,
            "username": username,
            "role": role,
            "message": message,
            "date": now()
        }).execute()

        return True

    except Exception as e:

        print("add_report_message error:", e)
        return False


def get_report_messages(report_id):

    try:

        response = (
            supabase
            .table("report_messages")
            .select(
                "id, report_id, username, role, message, date"
            )
            .eq("report_id", report_id)
            .order("id")
            .execute()
        )

        return [
            (
                row.get("id"),
                row.get("report_id"),
                row.get("username"),
                row.get("role"),
                row.get("message"),
                row.get("date")
            )
            for row in _rows(response)
        ]

    except Exception as e:

        print("get_report_messages error:", e)
        return []


# =========================================================
# PASSWORD MANAGEMENT
# =========================================================

def set_temporary_password(
    user_id,
    temporary_password
):

    if not temporary_password:
        return None

    try:

        response = (
            supabase
            .table("users")
            .select("id, username, role")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )

        row = _first(response)

        if not row:
            return None

        # -------------------------------------------------
        # MAIN ADMIN PROTECTION
        # -------------------------------------------------

        if row.get("role") == "main_admin":
            return "protected"

        supabase.table("users").update({
            "password": generate_password_hash(
                temporary_password
            ),
            "must_change_password": True
        }).eq(
            "id", user_id
        ).execute()

        return row.get("username")

    except Exception as e:

        print("set_temporary_password error:", e)
        return None


def set_permanent_password(
    user_id,
    new_password
):

    if not new_password:
        return None

    try:

        response = (
            supabase
            .table("users")
            .select("id, username, role")
            .eq("id", user_id)
            .eq("active", True)
            .limit(1)
            .execute()
        )

        row = _first(response)

        if not row:
            return None

        # -------------------------------------------------
        # MAIN ADMIN PROTECTION
        # -------------------------------------------------

        if row.get("role") == "main_admin":
            return "protected"

        supabase.table("users").update({
            "password": generate_password_hash(
                new_password
            ),
            "must_change_password": False
        }).eq(
            "id", user_id
        ).execute()

        return row.get("username")

    except Exception as e:

        print("set_permanent_password error:", e)
        return None


def change_password(
    username,
    new_password
):

    if not new_password:
        return False

    try:

        response = (
            supabase
            .table("users")
            .select("role")
            .eq("username", username)
            .eq("active", True)
            .limit(1)
            .execute()
        )

        row = _first(response)

        if not row:
            return False

        # -------------------------------------------------
        # MAIN ADMINS CANNOT BE CHANGED THROUGH THIS ROUTE.
        # -------------------------------------------------

        if row.get("role") == "main_admin":
            return False

        supabase.table("users").update({
            "password": generate_password_hash(
                new_password
            ),
            "must_change_password": False
        }).eq(
            "username", username
        ).execute()

        return True

    except Exception as e:

        print("change_password error:", e)
        return False


def must_change_password(username):

    try:

        response = (
            supabase
            .table("users")
            .select("must_change_password")
            .eq("username", username)
            .eq("active", True)
            .limit(1)
            .execute()
        )

        row = _first(response)

        return bool(
            row and row.get("must_change_password")
        )

    except Exception as e:

        print("must_change_password error:", e)
        return False


# =========================================================
# REPORT STATISTICS
# =========================================================

def get_report_stats():

    try:

        response = (
            supabase
            .table("reports")
            .select("status")
            .execute()
        )

        rows = _rows(response)

        total = len(rows)

        pending = sum(
            1 for row in rows
            if row.get("status") == "Pending"
        )

        reviewed = sum(
            1 for row in rows
            if row.get("status") == "Reviewed"
        )

        in_progress = sum(
            1 for row in rows
            if row.get("status") == "In Progress"
        )

        resolved = sum(
            1 for row in rows
            if row.get("status") == "Resolved"
        )

        unreasonable = sum(
            1 for row in rows
            if row.get("status") == "Unreasonable"
        )

        return {
            "total": total,
            "pending": pending,
            "reviewed": reviewed,
            "in_progress": in_progress,
            "resolved": resolved,
            "unreasonable": unreasonable
        }

    except Exception as e:

        print("get_report_stats error:", e)

        return {
            "total": 0,
            "pending": 0,
            "reviewed": 0,
            "in_progress": 0,
            "resolved": 0,
            "unreasonable": 0
        }
