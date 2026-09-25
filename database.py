import os

from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError(
        "Set SUPABASE_URL and SUPABASE_SERVICE_KEY in Render Environment."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def _rows(response):
    return response.data or []


def _first(response):
    rows = _rows(response)
    return rows[0] if rows else None


def _user_tuple(row):
    if not row:
        return None
    return (
        row["id"],
        row["username"],
        row["password"],
        row["role"],
        row.get("created_at"),
    )


def _report_tuple(row):
    if not row:
        return None
    return (
        row["id"],
        row["user_id"],
        row["username"],
        row["category"],
        row["location"],
        row["message"],
        row["status"],
        row["date"],
        row["admin_note"],
        row.get("assigned_to"),
        row.get("assigned_to_username"),
        row.get("assigned_by"),
    )


def init_db():
    """
    Create configured Main Admin accounts.
    Credentials should be stored in Render Environment Variables.
    """

    main_admins = [
        (os.getenv("MAIN_ADMIN_USERNAME"), os.getenv("MAIN_ADMIN_PASSWORD")),
        (os.getenv("MAIN_ADMIN_2_USERNAME"), os.getenv("MAIN_ADMIN_2_PASSWORD")),
        (os.getenv("MAIN_ADMIN_3_USERNAME"), os.getenv("MAIN_ADMIN_3_PASSWORD")),
        (os.getenv("MAIN_ADMIN_4_USERNAME"), os.getenv("MAIN_ADMIN_4_PASSWORD")),
        (os.getenv("MAIN_ADMIN_5_USERNAME"), os.getenv("MAIN_ADMIN_5_PASSWORD")),
    ]

    for username, password in main_admins:
        if username and password and not get_user_by_username(username):
            create_user(username, password, "main_admin")


def create_user(username, password, role="student"):
    username = username.strip()
    if not username or not password:
        return False

    if get_user_by_username(username):
        return False

    result = supabase.table("users").insert({
        "username": username,
        "password": generate_password_hash(password),
        "role": role,
    }).execute()

    return bool(_rows(result))


def authenticate_user(username, password):
    user = get_user_by_username(username)
    if not user:
        return None

    if not check_password_hash(user[2], password):
        return None

    return user


def verify_user_password(user_id, password):
    user = get_user(user_id)
    return bool(user and check_password_hash(user[2], password))


def get_user(user_id):
    result = (
        supabase.table("users")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    return _user_tuple(_first(result))


def get_user_by_username(username):
    result = (
        supabase.table("users")
        .select("*")
        .eq("username", username)
        .limit(1)
        .execute()
    )
    return _user_tuple(_first(result))


def get_all_users():
    result = (
        supabase.table("users")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return [_user_tuple(row) for row in _rows(result)]


def get_admin_users():
    result = (
        supabase.table("users")
        .select("id, username, role")
        .eq("role", "admin")
        .order("username", desc=False)
        .execute()
    )
    return _rows(result)


def get_assigned_reports(user_id):
    result = (
        supabase.table("reports")
        .select("*")
        .eq("assigned_to", user_id)
        .order("date", desc=True)
        .execute()
    )
    return [_report_tuple(row) for row in _rows(result)]


def assign_report(report_id, admin_id, assigned_by):
    admin = get_user(admin_id)
    if not admin or admin[3] != "admin":
        return False

    result = (
        supabase.table("reports")
        .update({
            "assigned_to": admin_id,
            "assigned_to_username": admin[1],
            "assigned_by": assigned_by,
        })
        .eq("id", report_id)
        .execute()
    )
    return bool(_rows(result))


def unassign_report(report_id):
    result = (
        supabase.table("reports")
        .update({
            "assigned_to": None,
            "assigned_to_username": None,
            "assigned_by": None,
        })
        .eq("id", report_id)
        .execute()
    )
    return bool(_rows(result))


def update_password(user_id, new_password):
    result = (
        supabase.table("users")
        .update({"password": generate_password_hash(new_password)})
        .eq("id", user_id)
        .execute()
    )
    return bool(_rows(result))


def reset_user_password(user_id, new_password):
    return update_password(user_id, new_password)


def change_user_role(user_id, role):
    if role not in ("student", "admin"):
        return False
    result = (
        supabase.table("users")
        .update({"role": role})
        .eq("id", user_id)
        .execute()
    )
    return bool(_rows(result))


def create_admin_application(user_id, username, reason):
    existing = (
        supabase.table("admin_applications")
        .select("id")
        .eq("user_id", user_id)
        .eq("status", "Pending")
        .limit(1)
        .execute()
    )
    if _first(existing):
        return False

    result = supabase.table("admin_applications").insert({
        "user_id": user_id,
        "username": username,
        "reason": reason,
        "status": "Pending",
    }).execute()

    return bool(_rows(result))


def get_admin_applications():
    result = (
        supabase.table("admin_applications")
        .select("*")
        .eq("status", "Pending")
        .order("created_at", desc=True)
        .execute()
    )
    return [
        (
            row["id"],
            row["username"],
            row["reason"],
            row["status"],
            row["created_at"],
            row["user_id"],
        )
        for row in _rows(result)
    ]


def get_admin_application(application_id):
    result = (
        supabase.table("admin_applications")
        .select("*")
        .eq("id", application_id)
        .limit(1)
        .execute()
    )
    row = _first(result)
    if not row:
        return None
    return (
        row["id"],
        row["username"],
        row["reason"],
        row["status"],
        row["created_at"],
        row["user_id"],
    )


def approve_admin_application(application_id):
    app = get_admin_application(application_id)
    if not app:
        return False

    updated = (
        supabase.table("admin_applications")
        .update({"status": "Approved"})
        .eq("id", application_id)
        .execute()
    )

    user_updated = (
        supabase.table("users")
        .update({"role": "admin"})
        .eq("id", app[5])
        .execute()
    )

    return bool(_rows(updated)) and bool(_rows(user_updated))


def reject_admin_application(application_id):
    result = (
        supabase.table("admin_applications")
        .update({"status": "Rejected"})
        .eq("id", application_id)
        .execute()
    )
    return bool(_rows(result))


def save_report(user_id, username, category, location, message):
    result = supabase.table("reports").insert({
        "user_id": user_id,
        "username": username,
        "category": category,
        "location": location,
        "message": message,
        "status": "Pending",
        "admin_note": "",
    }).execute()

    row = _first(result)
    if not row:
        return None

    report_id = row["id"]

    supabase.table("report_messages").insert({
        "report_id": report_id,
        "user_id": user_id,
        "username": username,
        "role": "student",
        "message": message,
    }).execute()

    return report_id


def get_report(report_id):
    result = (
        supabase.table("reports")
        .select("*")
        .eq("id", report_id)
        .limit(1)
        .execute()
    )
    return _report_tuple(_first(result))


def get_all_reports():
    result = (
        supabase.table("reports")
        .select("*")
        .order("date", desc=True)
        .execute()
    )
    return [_report_tuple(row) for row in _rows(result)]


def get_user_reports(user_id):
    result = (
        supabase.table("reports")
        .select("*")
        .eq("user_id", user_id)
        .order("date", desc=True)
        .execute()
    )
    return [_report_tuple(row) for row in _rows(result)]


def update_report(report_id, status, admin_note=""):
    result = (
        supabase.table("reports")
        .update({
            "status": status,
            "admin_note": admin_note,
        })
        .eq("id", report_id)
        .execute()
    )
    return bool(_rows(result))


def get_unreasonable_reports():
    result = (
        supabase.table("reports")
        .select("*")
        .eq("status", "Unreasonable")
        .order("date", desc=True)
        .execute()
    )
    return [_report_tuple(row) for row in _rows(result)]


def upload_photo(report_id, filename, storage_path, file_bytes, content_type):
    supabase.storage.from_("report-photos").upload(
        storage_path,
        file_bytes,
        {"content-type": content_type, "upsert": "false"},
    )

    result = supabase.table("report_photos").insert({
        "report_id": report_id,
        "filename": filename,
        "storage_path": storage_path,
    }).execute()

    return bool(_rows(result))


def get_report_photos(report_id):
    result = (
        supabase.table("report_photos")
        .select("*")
        .eq("report_id", report_id)
        .order("uploaded_at", desc=False)
        .execute()
    )
    return [
        {
            "id": row["id"],
            "report_id": row["report_id"],
            "filename": row["filename"],
            "storage_path": row["storage_path"],
            "uploaded_at": row["uploaded_at"],
        }
        for row in _rows(result)
    ]


def create_photo_url(storage_path):
    result = supabase.storage.from_("report-photos").create_signed_url(
        storage_path, 3600
    )
    if isinstance(result, dict):
        return result.get("signedURL") or result.get("signedUrl") or ""
    return ""


def add_report_message(report_id, user_id, username, role, message):
    result = supabase.table("report_messages").insert({
        "report_id": report_id,
        "user_id": user_id,
        "username": username,
        "role": role,
        "message": message,
    }).execute()
    return bool(_rows(result))


def get_report_messages(report_id):
    result = (
        supabase.table("report_messages")
        .select("*")
        .eq("report_id", report_id)
        .order("date", desc=False)
        .execute()
    )
    return [
        (
            row["id"],
            row["report_id"],
            row["username"],
            row["role"],
            row["message"],
            row["date"],
        )
        for row in _rows(result)
    ]


def delete_report(report_id):
    photos = get_report_photos(report_id)

    for photo in photos:
        try:
            supabase.storage.from_("report-photos").remove(
                [photo["storage_path"]]
            )
        except Exception:
            pass

    supabase.table("report_photos").delete().eq(
        "report_id", report_id
    ).execute()

    supabase.table("report_messages").delete().eq(
        "report_id", report_id
    ).execute()

    result = (
        supabase.table("reports")
        .delete()
        .eq("id", report_id)
        .execute()
    )
    return bool(_rows(result))


def delete_user(user_id):
    user = get_user(user_id)
    if not user:
        return "not_found"

    if user[3] == "main_admin":
        return "protected"

    reports = get_user_reports(user_id)
    for report in reports:
        delete_report(report[0])

    supabase.table("admin_applications").delete().eq(
        "user_id", user_id
    ).execute()

    result = (
        supabase.table("users")
        .delete()
        .eq("id", user_id)
        .execute()
    )

    return bool(_rows(result))


def get_report_stats(user_id=None, assigned_to=None):
    if user_id is not None:
        reports = get_user_reports(user_id)
    elif assigned_to is not None:
        reports = get_assigned_reports(assigned_to)
    else:
        reports = get_all_reports()

    stats = {
        "total": len(reports),
        "pending": 0,
        "reviewed": 0,
        "in_progress": 0,
        "resolved": 0,
        "unreasonable": 0,
    }

    for report in reports:
        status = report[6]
        if status == "Pending":
            stats["pending"] += 1
        elif status == "Reviewed":
            stats["reviewed"] += 1
        elif status == "In Progress":
            stats["in_progress"] += 1
        elif status == "Resolved":
            stats["resolved"] += 1
        elif status == "Unreasonable":
            stats["unreasonable"] += 1

    return stats
