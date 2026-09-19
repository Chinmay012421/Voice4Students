import os
from datetime import datetime

from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash


# ============================================================
# SUPABASE CONNECTION
# ============================================================

SUPABASE_URL = os.environ.get("https://ywiliickclswcyrneivz.supabase.co")
SUPABASE_SERVICE_KEY = os.environ.get("sb_secret_T197BTfYTcKxtfYmJIVOTw_xZB5pxUR")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables are required."
    )

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY
)


# ============================================================
# HELPERS
# ============================================================

def _first(result):
    """
    Safely return the first row from a Supabase response.
    """
    if result and getattr(result, "data", None):
        return result.data[0]
    return None


def _rows(result):
    """
    Safely return response rows.
    """
    if result and getattr(result, "data", None):
        return result.data
    return []


def _user_tuple(row):
    """
    Convert Supabase user row into the tuple format
    expected by the existing Flask templates.
    """
    if not row:
        return None

    return (
        row.get("id"),
        row.get("username"),
        row.get("password"),
        row.get("role"),
        row.get("created_at")
    )


def _report_tuple(row):
    """
    Convert Supabase report row into the tuple format
    expected by the existing Flask templates.
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


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():
    """
    Make sure the configured Main Admin accounts exist.

    IMPORTANT:
    Existing Main Admin passwords are NOT overwritten.
    """

    main_admins = [
        {
            "username": "mainadmin",
            "password": "admin123",
        }
    ]

    for admin in main_admins:
        existing = (
            supabase
            .table("users")
            .select("*")
            .eq("username", admin["username"])
            .limit(1)
            .execute()
        )

        if _first(existing):
            continue

        supabase.table("users").insert({
            "username": admin["username"],
            "password": generate_password_hash(admin["password"]),
            "role": "main_admin"
        }).execute()


# ============================================================
# USER FUNCTIONS
# ============================================================

def create_user(username, password, role="student"):
    username = username.strip()

    if not username or not password:
        return False

    existing = (
        supabase
        .table("users")
        .select("id")
        .eq("username", username)
        .limit(1)
        .execute()
    )

    if _first(existing):
        return False

    hashed_password = generate_password_hash(password)

    supabase.table("users").insert({
        "username": username,
        "password": hashed_password,
        "role": role
    }).execute()

    return True


def authenticate_user(username, password):
    username = username.strip()

    result = (
        supabase
        .table("users")
        .select("*")
        .eq("username", username)
        .limit(1)
        .execute()
    )

    user = _first(result)

    if not user:
        return None

    stored_password = user.get("password")

    if not stored_password:
        return None

    try:
        valid = check_password_hash(stored_password, password)
    except Exception:
        valid = False

    if not valid:
        return None

    return _user_tuple(user)


def get_user(user_id):
    result = (
        supabase
        .table("users")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )

    return _user_tuple(_first(result))


def get_user_by_username(username):
    result = (
        supabase
        .table("users")
        .select("*")
        .eq("username", username)
        .limit(1)
        .execute()
    )

    return _user_tuple(_first(result))


def get_all_users():
    result = (
        supabase
        .table("users")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    return [
        _user_tuple(row)
        for row in _rows(result)
    ]


def update_password(username, new_password):
    if not username or not new_password:
        return False

    hashed_password = generate_password_hash(new_password)

    result = (
        supabase
        .table("users")
        .update({
            "password": hashed_password
        })
        .eq("username", username)
        .execute()
    )

    return bool(getattr(result, "data", None))


# ============================================================
# ADMIN APPLICATIONS
# ============================================================

def create_admin_application(username, reason=""):
    username = username.strip()

    existing = (
        supabase
        .table("admin_applications")
        .select("*")
        .eq("username", username)
        .eq("status", "Pending")
        .limit(1)
        .execute()
    )

    if _first(existing):
        return False

    supabase.table("admin_applications").insert({
        "username": username,
        "reason": reason,
        "status": "Pending"
    }).execute()

    return True


def get_admin_applications():
    result = (
        supabase
        .table("admin_applications")
        .select("*")
        .eq("status", "Pending")
        .order("created_at", desc=True)
        .execute()
    )

    applications = []

    for row in _rows(result):
        applications.append((
            row.get("id"),
            row.get("username"),
            row.get("reason"),
            row.get("status"),
            row.get("created_at")
        ))

    return applications


def get_admin_application(application_id):
    result = (
        supabase
        .table("admin_applications")
        .select("*")
        .eq("id", application_id)
        .limit(1)
        .execute()
    )

    row = _first(result)

    if not row:
        return None

    return (
        row.get("id"),
        row.get("username"),
        row.get("reason"),
        row.get("status"),
        row.get("created_at")
    )


def update_admin_application(application_id, status):
    if status not in ["Approved", "Rejected"]:
        return False

    result = (
        supabase
        .table("admin_applications")
        .update({
            "status": status
        })
        .eq("id", application_id)
        .execute()
    )

    return bool(getattr(result, "data", None))


def approve_admin_application(application_id):
    application = get_admin_application(application_id)

    if not application:
        return False

    username = application[1]

    update_admin_application(application_id, "Approved")

    result = (
        supabase
        .table("users")
        .update({
            "role": "admin"
        })
        .eq("username", username)
        .execute()
    )

    return bool(getattr(result, "data", None))


def reject_admin_application(application_id):
    return update_admin_application(
        application_id,
        "Rejected"
    )


# ============================================================
# REPORT FUNCTIONS
# ============================================================

def save_report(username, category, location, message, photo=""):
    """
    Create a new report and its first conversation message.
    """

    result = (
        supabase
        .table("reports")
        .insert({
            "username": username,
            "category": category,
            "location": location,
            "message": message,
            "status": "Pending",
            "admin_note": "",
            "photo": photo or ""
        })
        .execute()
    )

    report = _first(result)

    if not report:
        return None

    report_id = report.get("id")

    # Initial report conversation message
    supabase.table("report_messages").insert({
        "report_id": report_id,
        "username": username,
        "role": "student",
        "message": message
    }).execute()

    # Save first photo if supplied
    if photo:
        add_report_photo(
            report_id,
            photo
        )

    return report_id


def get_report(report_id):
    result = (
        supabase
        .table("reports")
        .select("*")
        .eq("id", report_id)
        .limit(1)
        .execute()
    )

    return _report_tuple(_first(result))


def get_all_reports():
    result = (
        supabase
        .table("reports")
        .select("*")
        .order("date", desc=True)
        .execute()
    )

    return [
        _report_tuple(row)
        for row in _rows(result)
    ]


def get_user_reports(username):
    result = (
        supabase
        .table("reports")
        .select("*")
        .eq("username", username)
        .order("date", desc=True)
        .execute()
    )

    return [
        _report_tuple(row)
        for row in _rows(result)
    ]


def update_report_status(report_id, status, admin_note=""):
    allowed_statuses = [
        "Pending",
        "Reviewed",
        "In Progress",
        "Resolved",
        "Unreasonable"
    ]

    if status not in allowed_statuses:
        return False

    result = (
        supabase
        .table("reports")
        .update({
            "status": status,
            "admin_note": admin_note
        })
        .eq("id", report_id)
        .execute()
    )

    return bool(getattr(result, "data", None))


def mark_report_unreasonable(report_id):
    return update_report_status(
        report_id,
        "Unreasonable",
        "Sent to Main Admin for review"
    )


# ============================================================
# REPORT PHOTOS
# ============================================================

def add_report_photo(report_id, filename):
    if not filename:
        return False

    result = (
        supabase
        .table("report_photos")
        .insert({
            "report_id": report_id,
            "filename": filename
        })
        .execute()
    )

    return bool(getattr(result, "data", None))


def get_report_photos(report_id):
    result = (
        supabase
        .table("report_photos")
        .select("*")
        .eq("report_id", report_id)
        .order("uploaded_at", desc=False)
        .execute()
    )

    photos = []

    for row in _rows(result):
        photos.append((
            row.get("id"),
            row.get("report_id"),
            row.get("filename"),
            row.get("uploaded_at")
        ))

    return photos


def delete_report_photos(report_id):
    supabase.table("report_photos").delete().eq(
        "report_id",
        report_id
    ).execute()


# ============================================================
# REPORT CONVERSATION
# ============================================================

def add_report_message(report_id, username, role, message):
    if not message or not message.strip():
        return False

    result = (
        supabase
        .table("report_messages")
        .insert({
            "report_id": report_id,
            "username": username,
            "role": role,
            "message": message.strip()
        })
        .execute()
    )

    return bool(getattr(result, "data", None))


def get_report_messages(report_id):
    result = (
        supabase
        .table("report_messages")
        .select("*")
        .eq("report_id", report_id)
        .order("date", desc=False)
        .execute()
    )

    messages = []

    for row in _rows(result):
        messages.append((
            row.get("id"),
            row.get("report_id"),
            row.get("username"),
            row.get("role"),
            row.get("message"),
            row.get("date")
        ))

    return messages


def delete_report_messages(report_id):
    supabase.table("report_messages").delete().eq(
        "report_id",
        report_id
    ).execute()


# ============================================================
# DELETE REPORT
# ============================================================

def delete_report(report_id):
    """
    Delete all database records belonging to a report.

    Physical uploaded files are handled by app.py because
    database.py should not need to know the Flask upload path.
    """

    delete_report_messages(report_id)
    delete_report_photos(report_id)

    result = (
        supabase
        .table("reports")
        .delete()
        .eq("id", report_id)
        .execute()
    )

    return bool(getattr(result, "data", None))


# ============================================================
# UNREASONABLE REPORTS
# ============================================================

def get_unreasonable_reports():
    result = (
        supabase
        .table("reports")
        .select("*")
        .eq("status", "Unreasonable")
        .order("date", desc=True)
        .execute()
    )

    return [
        _report_tuple(row)
        for row in _rows(result)
    ]


# ============================================================
# DELETE USER + ALL USER REPORTS
# ============================================================

def delete_user(user_id, upload_folder=None):
    """
    Delete a user and EVERYTHING belonging to that user.

    Deletes:
        - user's reports
        - report messages
        - report photo database records
        - physical uploaded photos
        - admin applications
        - user account

    Main Admin accounts are protected.
    """

    user_result = (
        supabase
        .table("users")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )

    user = _first(user_result)

    if not user:
        return "not_found"

    username = user.get("username")
    role = user.get("role")

    # NEVER allow deletion of a Main Admin
    if role == "main_admin":
        return "protected"

    # --------------------------------------------------------
    # Find every report belonging to this user
    # --------------------------------------------------------

    reports_result = (
        supabase
        .table("reports")
        .select("id")
        .eq("username", username)
        .execute()
    )

    report_rows = _rows(reports_result)

    deleted_report_count = 0

    # --------------------------------------------------------
    # Delete every report and its related records
    # --------------------------------------------------------

    for report in report_rows:
        report_id = report.get("id")

        # Get photo filenames before deleting DB records
        photos = get_report_photos(report_id)

        if upload_folder:
            for photo in photos:
                filename = photo[2]

                if not filename:
                    continue

                file_path = os.path.join(
                    upload_folder,
                    filename
                )

                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except OSError:
                    pass

        delete_report_messages(report_id)
        delete_report_photos(report_id)

        supabase.table("reports").delete().eq(
            "id",
            report_id
        ).execute()

        deleted_report_count += 1

    # --------------------------------------------------------
    # Delete admin applications
    # --------------------------------------------------------

    supabase.table("admin_applications").delete().eq(
        "username",
        username
    ).execute()

    # --------------------------------------------------------
    # Delete user account
    # --------------------------------------------------------

    supabase.table("users").delete().eq(
        "id",
        user_id
    ).execute()

    return {
        "username": username,
        "report_count": deleted_report_count
    }


# ============================================================
# REPORT STATISTICS
# ============================================================

def get_report_stats(username=None):
    if username:
        reports = get_user_reports(username)
    else:
        reports = get_all_reports()

    total = len(reports)
    pending = 0
    reviewed = 0
    in_progress = 0
    resolved = 0
    unreasonable = 0

    for report in reports:
        status = report[5]

        if status == "Pending":
            pending += 1
        elif status == "Reviewed":
            reviewed += 1
        elif status == "In Progress":
            in_progress += 1
        elif status == "Resolved":
            resolved += 1
        elif status == "Unreasonable":
            unreasonable += 1

    return {
        "total": total,
        "pending": pending,
        "reviewed": reviewed,
        "in_progress": in_progress,
        "resolved": resolved,
        "unreasonable": unreasonable
    }
