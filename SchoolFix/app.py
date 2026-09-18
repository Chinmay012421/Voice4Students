import os
import secrets
import string

from flask import (
    Flask,
    request,
    redirect,
    session,
    render_template
)

from werkzeug.utils import secure_filename

from supabase import create_client

from database import (
    init_db,
    get_user,
    must_change_password,
    save_user,
    save_admin_application,
    get_pending_applications,
    approve_admin,
    reject_admin,
    save_report,
    get_all_reports,
    get_user_reports,
    get_report,
    update_report_status,
    delete_report,
    get_unreasonable_reports,
    get_report_stats,
    change_password,
    set_temporary_password,
    set_permanent_password,
    get_all_users,
    add_report_photo,
    get_report_photos,
    add_report_message,
    get_report_messages
)


# =========================================================
# APP
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "schoolvoice-development-key"
)


# =========================================================
# SUPABASE STORAGE
# =========================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL:
    raise RuntimeError(
        "SUPABASE_URL environment variable is missing."
    )

if not SUPABASE_SERVICE_KEY:
    raise RuntimeError(
        "SUPABASE_SERVICE_KEY environment variable is missing."
    )

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY
)

PHOTO_BUCKET = "report-photos"


# =========================================================
# UPLOAD SETTINGS
# =========================================================

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}

MAX_PHOTOS_PER_REPORT = 5

# Flask request size limit.
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024


# =========================================================
# DATABASE
# =========================================================

init_db()


# =========================================================
# LOGIN HELPERS
# =========================================================

def logged_in():

    return "username" in session


def is_main_admin():

    return (
        session.get("role")
        == "main_admin"
    )


def is_admin():

    return session.get("role") in (
        "admin",
        "main_admin"
    )


# =========================================================
# FILE HELPERS
# =========================================================

def allowed_file(filename):

    if not filename:
        return False

    if "." not in filename:
        return False

    extension = filename.rsplit(
        ".",
        1
    )[1].lower()

    return extension in ALLOWED_EXTENSIONS


def upload_photo_to_supabase(
    photo,
    report_id
):
    """
    Upload a report photo to Supabase Storage.

    Returns the public URL if successful.
    Returns None if upload fails.
    """

    if not photo or not photo.filename:
        return None

    original_name = secure_filename(
        photo.filename
    )

    if not original_name:
        return None

    _, extension = os.path.splitext(
        original_name
    )

    extension = extension.lower()

    photo_name = (
        secrets.token_hex(16)
        + extension
    )

    # Keep photos organized by report.
    storage_path = (
        f"reports/{report_id}/{photo_name}"
    )

    try:

        photo_bytes = photo.read()

        if not photo_bytes:
            return None

        content_type = (
            photo.mimetype
            or "application/octet-stream"
        )

        supabase.storage.from_(
            PHOTO_BUCKET
        ).upload(
            storage_path,
            photo_bytes,
            {
                "content-type": content_type,
                "upsert": False
            }
        )

        public_url = (
            supabase
            .storage
            .from_(PHOTO_BUCKET)
            .get_public_url(storage_path)
        )

        return public_url

    except Exception as e:

        app.logger.exception(
            "Supabase photo upload failed"
        )

        return None


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if logged_in():
        return redirect("/dashboard")

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if not username or not password:

            return render_template(
                "login.html",
                error="Please enter both username and password."
            )

        user = get_user(
            username,
            password
        )

        if user:

            session.clear()

            # Database layout:
            #
            # 0 = id
            # 1 = username
            # 2 = password hash
            # 3 = role
            # 4 = active
            # 5 = must_change_password
            # 6 = registered_at

            session["username"] = user[1]
            session["role"] = user[3]

            if must_change_password(
                user[1]
            ):

                return redirect(
                    "/change-password"
                )

            return redirect(
                "/dashboard"
            )

        return render_template(
            "login.html",
            error="Invalid username or password."
        )

    return render_template(
        "login.html"
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if not username or not password:

            return render_template(
                "register.html",
                error="Please fill all fields."
            )

        if len(password) < 8:

            return render_template(
                "register.html",
                error=(
                    "Password must be at least "
                    "8 characters."
                )
            )

        try:

            success = save_user(
                username,
                password,
                "student"
            )

            if not success:

                return render_template(
                    "register.html",
                    error=(
                        "Username already exists."
                    )
                )

            return render_template(
                "login.html",
                message=(
                    "Registration successful. "
                    "Please log in as a student."
                )
            )

        except Exception:

            app.logger.exception(
                "Registration error"
            )

            return render_template(
                "register.html",
                error=(
                    "Registration failed. "
                    "Username may already exist."
                )
            )

    return render_template(
        "register.html"
    )


# =========================================================
# CHANGE OWN PASSWORD
# =========================================================

@app.route(
    "/change-password",
    methods=["GET", "POST"]
)
def change_password_route():

    if not logged_in():

        return redirect("/login")

    if request.method == "POST":

        new_password = request.form.get(
            "new_password",
            ""
        )

        confirm = request.form.get(
            "confirm_password",
            ""
        )

        if len(new_password) < 8:

            return render_template(
                "change_password.html",
                error=(
                    "Password must be at least "
                    "8 characters."
                )
            )

        if new_password != confirm:

            return render_template(
                "change_password.html",
                error="Passwords do not match."
            )

        success = change_password(
            session["username"],
            new_password
        )

        if not success:

            return render_template(
                "change_password.html",
                error="Unable to change password."
            )

        return redirect(
            "/dashboard"
        )

    return render_template(
        "change_password.html"
    )


# =========================================================
# USERS
# =========================================================

@app.route("/users")
def users():

    if not is_main_admin():

        return redirect("/dashboard")

    users = get_all_users()

    search = request.args.get(
        "search",
        ""
    ).strip().lower()

    role = request.args.get(
        "role",
        ""
    ).strip()

    filtered_users = []

    for user in users:

        # 0 = id
        # 1 = username
        # 2 = password hash
        # 3 = role
        # 4 = active
        # 5 = must_change_password
        # 6 = registered_at

        username = str(
            user[1] or ""
        ).lower()

        user_role = str(
            user[3] or ""
        )

        if search and search not in username:
            continue

        if (
            role == "student"
            and user_role != "student"
        ):
            continue

        if (
            role == "admin"
            and user_role not in (
                "admin",
                "main_admin"
            )
        ):
            continue

        if (
            role == "main_admin"
            and user_role != "main_admin"
        ):
            continue

        filtered_users.append(
            user
        )

    return render_template(
        "users.html",
        users=filtered_users,
        search=request.args.get(
            "search",
            ""
        ),
        selected_role=role
    )


# =========================================================
# TEMPORARY PASSWORD
# =========================================================

@app.route(
    "/reset-password/<int:user_id>",
    methods=["POST"]
)
def reset_password(user_id):

    if not is_main_admin():

        return redirect("/dashboard")

    alphabet = (
        string.ascii_letters
        + string.digits
    )

    temporary_password = "".join(
        secrets.choice(alphabet)
        for _ in range(14)
    )

    result = set_temporary_password(
        user_id,
        temporary_password
    )

    if result == "protected":

        return render_template(
            "users.html",
            users=get_all_users(),
            error=(
                "Main Admin passwords cannot "
                "be reset from this screen."
            )
        )

    if result is None:

        return render_template(
            "users.html",
            users=get_all_users(),
            error="User not found."
        )

    return render_template(
        "reset_password.html",
        username=result,
        temporary_password=temporary_password
    )


# =========================================================
# PERMANENT USER PASSWORD
# =========================================================

@app.route(
    "/change-user-password/<int:user_id>",
    methods=["POST"]
)
def change_user_password(user_id):

    if not is_main_admin():

        return redirect("/dashboard")

    new_password = request.form.get(
        "new_password",
        ""
    )

    confirm_password = request.form.get(
        "confirm_password",
        ""
    )

    if len(new_password) < 8:

        return render_template(
            "users.html",
            users=get_all_users(),
            error=(
                "Password must be at least "
                "8 characters."
            )
        )

    if new_password != confirm_password:

        return render_template(
            "users.html",
            users=get_all_users(),
            error="Passwords do not match."
        )

    result = set_permanent_password(
        user_id,
        new_password
    )

    if result == "protected":

        return render_template(
            "users.html",
            users=get_all_users(),
            error=(
                "Main Admin passwords cannot "
                "be changed from this screen."
            )
        )

    if result is None:

        return render_template(
            "users.html",
            users=get_all_users(),
            error=(
                "User not found or inactive."
            )
        )

    return render_template(
        "users.html",
        users=get_all_users(),
        success=(
            f"Password permanently changed "
            f"for {result}."
        )
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if not logged_in():

        return redirect("/login")

    stats = None

    if is_main_admin():

        stats = get_report_stats()

    return render_template(
        "dashboard.html",
        username=session["username"],
        role=session["role"],
        stats=stats
    )


# =========================================================
# ADMIN APPLICATION
# =========================================================

@app.route(
    "/apply-admin",
    methods=["GET", "POST"]
)
def apply_admin():

    if (
        not logged_in()
        or session.get("role") != "student"
    ):

        return redirect("/login")

    if request.method == "POST":

        reason = request.form.get(
            "reason",
            ""
        ).strip()

        if not reason:

            return render_template(
                "apply_admin.html",
                error=(
                    "Please give a reason "
                    "for your application."
                )
            )

        save_admin_application(
            session["username"],
            reason
        )

        return render_template(
            "apply_admin.html",
            message=(
                "Application sent to Main Admin."
            )
        )

    return render_template(
        "apply_admin.html"
    )


# =========================================================
# ADMIN APPLICATIONS
# =========================================================

@app.route("/admin-applications")
def admin_applications():

    if not is_main_admin():

        return redirect("/dashboard")

    return render_template(
        "admin_applications.html",
        applications=get_pending_applications()
    )


@app.route(
    "/approve-admin/<int:application_id>"
)
def approve_admin_route(
    application_id
):

    if not is_main_admin():

        return redirect("/dashboard")

    approve_admin(
        application_id
    )

    return redirect(
        "/admin-applications"
    )


@app.route(
    "/reject-admin/<int:application_id>"
)
def reject_admin_route(
    application_id
):

    if not is_main_admin():

        return redirect("/dashboard")

    reject_admin(
        application_id
    )

    return redirect(
        "/admin-applications"
    )


# =========================================================
# SUBMIT REPORT + MULTIPLE PHOTOS
# =========================================================

@app.route(
    "/submit-report",
    methods=["POST"]
)
def submit_report():

    if (
        not logged_in()
        or session.get("role") != "student"
    ):

        return redirect("/login")

    category = request.form.get(
        "category",
        "General"
    ).strip()

    location = request.form.get(
        "location",
        ""
    ).strip()

    message = request.form.get(
        "message",
        ""
    ).strip()

    if not message:

        return redirect(
            "/dashboard"
        )

    photos = request.files.getlist(
        "photos"
    )

    valid_photos = []

    for photo in photos:

        if not photo or not photo.filename:
            continue

        if not allowed_file(
            photo.filename
        ):

            return render_template(
                "dashboard.html",
                username=session["username"],
                role=session["role"],
                stats=(
                    get_report_stats()
                    if is_main_admin()
                    else None
                ),
                error=(
                    "Only PNG, JPG, JPEG "
                    "and WEBP images are allowed."
                )
            )

        valid_photos.append(photo)

    if len(valid_photos) > MAX_PHOTOS_PER_REPORT:

        return render_template(
            "dashboard.html",
            username=session["username"],
            role=session["role"],
            stats=(
                get_report_stats()
                if is_main_admin()
                else None
            ),
            error=(
                "You can attach a maximum "
                "of 5 photos."
            )
        )

    # -----------------------------------------------------
    # Create report first.
    # -----------------------------------------------------

    report_id = save_report(
        session["username"],
        category,
        location,
        message
    )

    if not report_id:

        return render_template(
            "dashboard.html",
            username=session["username"],
            role=session["role"],
            stats=None,
            error="Unable to create the report."
        )

    # -----------------------------------------------------
    # Upload each photo to Supabase Storage.
    # -----------------------------------------------------

    for photo in valid_photos:

        public_url = upload_photo_to_supabase(
            photo,
            report_id
        )

        if not public_url:

            app.logger.error(
                "Photo upload failed for report %s",
                report_id
            )

            continue

        # Store the Supabase public URL in the database.
        add_report_photo(
            report_id,
            public_url
        )

    return redirect(
        f"/report/{report_id}"
    )


# =========================================================
# MY REPORTS
# =========================================================

@app.route("/my-reports")
def my_reports():

    if not logged_in():

        return redirect("/login")

    reports = get_user_reports(
        session["username"]
    )

    return render_template(
        "my_reports.html",
        reports=reports,
        role=session["role"]
    )


# =========================================================
# ALL REPORTS
# =========================================================

@app.route("/reports")
def reports():

    if not is_admin():

        return redirect("/dashboard")

    reports = get_all_reports()

    return render_template(
        "reports.html",
        reports=reports
    )


# =========================================================
# REPORT DETAIL
# =========================================================

@app.route(
    "/report/<int:report_id>"
)
def report_detail(report_id):

    if not logged_in():

        return redirect("/login")

    report = get_report(
        report_id
    )

    if not report:

        return redirect("/dashboard")

    # Students can only see their own reports.
    if (
        session.get("role") == "student"
        and report[1] != session["username"]
    ):

        return redirect("/dashboard")

    photos = get_report_photos(
        report_id
    )

    messages = get_report_messages(
        report_id
    )

    return render_template(
        "report_detail.html",
        report=report,
        photos=photos,
        messages=messages,
        username=session["username"],
        role=session["role"]
    )


# =========================================================
# REPORT CONVERSATION
# =========================================================

@app.route(
    "/report/<int:report_id>/message",
    methods=["POST"]
)
def report_message(report_id):

    if not logged_in():

        return redirect("/login")

    report = get_report(
        report_id
    )

    if not report:

        return redirect("/dashboard")

    # Students can only reply to their own reports.
    if (
        session.get("role") == "student"
        and report[1] != session["username"]
    ):

        return redirect("/dashboard")

    message = request.form.get(
        "message",
        ""
    ).strip()

    if message:

        add_report_message(
            report_id,
            session["username"],
            session["role"],
            message
        )

    return redirect(
        f"/report/{report_id}"
    )


# =========================================================
# UPDATE REPORT
# =========================================================

@app.route(
    "/update-report/<int:report_id>",
    methods=["POST"]
)
def update_report(report_id):

    if not is_admin():

        return redirect("/dashboard")

    status = request.form.get(
        "status",
        "Pending"
    )

    allowed_statuses = {
        "Pending",
        "In Progress",
        "Reviewed",
        "Resolved"
    }

    if status not in allowed_statuses:

        status = "Pending"

    note = request.form.get(
        "admin_note",
        ""
    ).strip()

    update_report_status(
        report_id,
        status,
        note
    )

    return redirect(
        f"/report/{report_id}"
    )


# =========================================================
# MARK UNREASONABLE
# =========================================================

@app.route(
    "/unreasonable/<int:report_id>"
)
def unreasonable(report_id):

    if not is_admin():

        return redirect("/dashboard")

    update_report_status(
        report_id,
        "Unreasonable",
        "Sent to Main Admin for review"
    )

    return redirect(
        f"/report/{report_id}"
    )


# =========================================================
# UNREASONABLE REPORTS
# =========================================================

@app.route("/unreasonable-reports")
def unreasonable_reports():

    if not is_main_admin():

        return redirect("/dashboard")

    return render_template(
        "unreasonable_reports.html",
        reports=get_unreasonable_reports()
    )


# =========================================================
# DELETE REPORT
# =========================================================

@app.route(
    "/delete-report/<int:report_id>"
)
def delete_report_route(report_id):

    if not is_main_admin():

        return redirect("/dashboard")

    delete_report(
        report_id
    )

    return redirect(
        "/unreasonable-reports"
    )


# =========================================================
# MAIN ADMIN CHECK
# =========================================================

@app.route("/check-main-admins")
def check_main_admins():

    if not is_main_admin():

        return redirect("/login")

    users = get_all_users()

    accounts = []

    for user in users:

        if user[3] == "main_admin":

            accounts.append({
                "id": user[0],
                "username": user[1],
                "role": user[3],
                "active": bool(user[4]),
                "must_change_password": bool(user[5])
            })

    return {
        "main_admin_count": len(accounts),
        "accounts": accounts
    }


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
