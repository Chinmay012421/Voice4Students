import os
import secrets
import string
import sqlite3

from flask import (
    Flask,
    request,
    redirect,
    session,
    render_template
)

from werkzeug.utils import secure_filename

from database import (
    init_db,
    get_user,
    must_change_password,
    save_user,
    delete_user,
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
# DATABASE CONNECTION
# =========================================================

DATABASE = os.path.join(
    app.root_path,
    "schoolfix.db"
)


def connect():
    """
    Create a SQLite database connection.

    This function is used by routes that need direct
    database access, such as deleting users.
    """
    conn = sqlite3.connect(DATABASE)

    return conn


# =========================================================
# UPLOAD SETTINGS
# =========================================================

UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "uploads"
)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}

MAX_PHOTOS_PER_REPORT = 5

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

app.config["MAX_CONTENT_LENGTH"] = (
    20 * 1024 * 1024
)


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

init_db()


# =========================================================
# LOGIN HELPERS
# =========================================================

def logged_in():
    return "username" in session


def is_main_admin():
    return session.get("role") == "main_admin"


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


def delete_report_files(report_id):
    """
    Delete all physical photo files belonging to a report.
    """

    try:
        photos = get_report_photos(report_id)

    except Exception:

        app.logger.exception(
            "Unable to get report photos."
        )

        return

    for photo in photos:

        try:

            # report_photos structure:
            # id, report_id, filename, uploaded_at

            filename = photo[2]

        except (IndexError, TypeError):

            continue

        if not filename:
            continue

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        try:

            if os.path.isfile(file_path):

                os.remove(file_path)

        except OSError:

            app.logger.warning(
                "Could not delete photo file: %s",
                file_path
            )


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

        return redirect(
            "/dashboard"
        )

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
                error=(
                    "Please enter both "
                    "username and password."
                )
            )

        user = get_user(
            username,
            password
        )

        if user:

            session.clear()

            # users table:
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
            error=(
                "Invalid username or password."
            )
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

    if logged_in():

        return redirect(
            "/dashboard"
        )

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
                error=(
                    "Please fill all fields."
                )
            )

        if len(username) < 3:

            return render_template(
                "register.html",
                error=(
                    "Username must be at least "
                    "3 characters."
                )
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
                error=(
                    "Passwords do not match."
                )
            )

        success = change_password(
            session["username"],
            new_password
        )

        if not success:

            return render_template(
                "change_password.html",
                error=(
                    "Unable to change password."
                )
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

        return redirect(
            "/dashboard"
        )

    all_users = get_all_users()

    search = request.args.get(
        "search",
        ""
    ).strip().lower()

    role = request.args.get(
        "role",
        ""
    ).strip()

    filtered_users = []

    for user in all_users:

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
# DELETE USER
# =========================================================

@app.route(
    "/delete-user/<int:user_id>",
    methods=["POST"]
)
def delete_user_route(user_id):

    if not is_main_admin():

        return redirect(
            "/dashboard"
        )

    conn = connect()

    try:

        user = conn.execute(
            """
            SELECT
                id,
                username,
                role
            FROM users
            WHERE id=?
            """,
            (user_id,)
        ).fetchone()

        if not user:

            return render_template(
                "users.html",
                users=get_all_users(),
                error="User not found."
            )

        username = user[1]
        role = user[2]

        # Main Admin accounts can NEVER be deleted.
        if role == "main_admin":

            return render_template(
                "users.html",
                users=get_all_users(),
                error=(
                    "Main Admin accounts "
                    "cannot be deleted."
                )
            )

        # Find all reports belonging to this user.
        report_rows = conn.execute(
            """
            SELECT id
            FROM reports
            WHERE username=?
            """,
            (username,)
        ).fetchall()

        report_ids = [
            row[0]
            for row in report_rows
        ]

        # Delete physical photo files.
        for report_id in report_ids:

            try:

                photo_rows = conn.execute(
                    """
                    SELECT filename
                    FROM report_photos
                    WHERE report_id=?
                    """,
                    (report_id,)
                ).fetchall()

                for photo_row in photo_rows:

                    filename = photo_row[0]

                    if not filename:
                        continue

                    file_path = os.path.join(
                        app.config["UPLOAD_FOLDER"],
                        filename
                    )

                    try:

                        if os.path.isfile(file_path):

                            os.remove(file_path)

                    except OSError:

                        app.logger.warning(
                            "Could not delete file: %s",
                            file_path
                        )

            except Exception:

                app.logger.exception(
                    "Error deleting report files."
                )

        # Delete report messages.
        for report_id in report_ids:

            conn.execute(
                """
                DELETE FROM report_messages
                WHERE report_id=?
                """,
                (report_id,)
            )

            conn.execute(
                """
                DELETE FROM report_photos
                WHERE report_id=?
                """,
                (report_id,)
            )

        # Delete reports.
        conn.execute(
            """
            DELETE FROM reports
            WHERE username=?
            """,
            (username,)
        )

        # Delete admin applications.
        conn.execute(
            """
            DELETE FROM admin_applications
            WHERE username=?
            """,
            (username,)
        )

        # Finally delete the account.
        conn.execute(
            """
            DELETE FROM users
            WHERE id=?
            AND role!='main_admin'
            """,
            (user_id,)
        )

        conn.commit()

        return render_template(
            "users.html",
            users=get_all_users(),
            success=(
                f"User '{username}' and "
                f"their reports were deleted."
            )
        )

    except Exception:

        conn.rollback()

        app.logger.exception(
            "Error deleting user."
        )

        return render_template(
            "users.html",
            users=get_all_users(),
            error=(
                "Unable to delete this user."
            )
        )

    finally:

        conn.close()


# =========================================================
# TEMPORARY PASSWORD
# =========================================================

@app.route(
    "/reset-password/<int:user_id>",
    methods=["POST"]
)
def reset_password(user_id):

    if not is_main_admin():

        return redirect(
            "/dashboard"
        )

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

        return redirect(
            "/dashboard"
        )

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
            error=(
                "Passwords do not match."
            )
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

        return redirect(
            "/login"
        )

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

        return redirect(
            "/login"
        )

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

        try:

            save_admin_application(
                session["username"],
                reason
            )

        except Exception:

            app.logger.exception(
                "Admin application error."
            )

            return render_template(
                "apply_admin.html",
                error=(
                    "Unable to send your application."
                )
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

        return redirect(
            "/dashboard"
        )

    return render_template(
        "admin_applications.html",
        applications=get_pending_applications()
    )


@app.route(
    "/approve-admin/<int:application_id>"
)
def approve_admin_route(application_id):

    if not is_main_admin():

        return redirect(
            "/dashboard"
        )

    approve_admin(
        application_id
    )

    return redirect(
        "/admin-applications"
    )


@app.route(
    "/reject-admin/<int:application_id>"
)
def reject_admin_route(application_id):

    if not is_main_admin():

        return redirect(
            "/dashboard"
        )

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

        return redirect(
            "/login"
        )

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

    if not category:

        category = "General"

    if not message:

        return render_template(
            "dashboard.html",
            username=session["username"],
            role=session["role"],
            stats=None,
            error=(
                "Please describe the problem "
                "before submitting."
            )
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
                stats=None,
                error=(
                    "Only PNG, JPG, JPEG "
                    "and WEBP images are allowed."
                )
            )

        valid_photos.append(
            photo
        )

    if len(valid_photos) > MAX_PHOTOS_PER_REPORT:

        return render_template(
            "dashboard.html",
            username=session["username"],
            role=session["role"],
            stats=None,
            error=(
                "You can attach a maximum "
                "of 5 photos."
            )
        )

    try:

        report_id = save_report(
            session["username"],
            category,
            location,
            message
        )

    except Exception:

        app.logger.exception(
            "Unable to create report."
        )

        return render_template(
            "dashboard.html",
            username=session["username"],
            role=session["role"],
            stats=None,
            error=(
                "Unable to create the report."
            )
        )

    if not report_id:

        return render_template(
            "dashboard.html",
            username=session["username"],
            role=session["role"],
            stats=None,
            error=(
                "Unable to create the report."
            )
        )

    # Save photos.
    for photo in valid_photos:

        try:

            original_name = secure_filename(
                photo.filename
            )

            _, extension = os.path.splitext(
                original_name
            )

            photo_name = (
                secrets.token_hex(16)
                + extension.lower()
            )

            photo_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                photo_name
            )

            photo.save(
                photo_path
            )

            add_report_photo(
                report_id,
                photo_name
            )

        except Exception:

            app.logger.exception(
                "Unable to save report photo."
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

        return redirect(
            "/login"
        )

    # Admins do NOT use Own Reports.
    if session.get("role") != "student":

        return redirect(
            "/reports"
        )

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

    if not logged_in():

        return redirect(
            "/login"
        )

    if not is_admin():

        return redirect(
            "/dashboard"
        )

    all_reports = get_all_reports()

    return render_template(
        "reports.html",
        reports=all_reports,
        role=session["role"]
    )


# =========================================================
# REPORT DETAIL
# =========================================================

@app.route(
    "/report/<int:report_id>"
)
def report_detail(report_id):

    if not logged_in():

        return redirect(
            "/login"
        )

    report = get_report(
        report_id
    )

    if not report:

        return redirect(
            "/dashboard"
        )

    # Students can ONLY view their own report.
    if session.get("role") == "student":

        if report[1] != session["username"]:

            return redirect(
                "/dashboard"
            )

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

        return redirect(
            "/login"
        )

    report = get_report(
        report_id
    )

    if not report:

        return redirect(
            "/dashboard"
        )

    # Students can only message on their own reports.
    if session.get("role") == "student":

        if report[1] != session["username"]:

            return redirect(
                "/dashboard"
            )

    message = request.form.get(
        "message",
        ""
    ).strip()

    if message:

        try:

            add_report_message(
                report_id,
                session["username"],
                session["role"],
                message
            )

        except Exception:

            app.logger.exception(
                "Unable to add report message."
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

        return redirect(
            "/dashboard"
        )

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
# MARK REPORT UNREASONABLE
# =========================================================

@app.route(
    "/unreasonable/<int:report_id>",
    methods=["POST", "GET"]
)
def unreasonable(report_id):

    if not is_admin():

        return redirect(
            "/dashboard"
        )

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

        return redirect(
            "/dashboard"
        )

    return render_template(
        "unreasonable_reports.html",
        reports=get_unreasonable_reports()
    )


# =========================================================
# DELETE REPORT
# =========================================================

@app.route(
    "/delete-report/<int:report_id>",
    methods=["POST", "GET"]
)
def delete_report_route(report_id):

    if not is_main_admin():

        return redirect(
            "/dashboard"
        )

    # Delete physical photo files first.
    delete_report_files(
        report_id
    )

    try:

        delete_report(
            report_id
        )

    except Exception:

        app.logger.exception(
            "Unable to delete report."
        )

    return redirect(
        "/unreasonable-reports"
    )


# =========================================================
# MAIN ADMIN CHECK
# =========================================================
#
# This route DOES NOT show passwords.
#
# It only confirms that Main Admin accounts exist.
#
# You can remove this route later if you don't need it.
# =========================================================

@app.route("/check-main-admins")
def check_main_admins():

    if not is_main_admin():

        return redirect(
            "/dashboard"
        )

    conn = connect()

    try:

        rows = conn.execute(
            """
            SELECT
                id,
                username,
                role,
                active,
                must_change_password
            FROM users
            WHERE role='main_admin'
            ORDER BY id ASC
            """
        ).fetchall()

    finally:

        conn.close()

    accounts = []

    for row in rows:

        accounts.append({
            "id": row[0],
            "username": row[1],
            "role": row[2],
            "active": bool(row[3]),
            "must_change_password": bool(row[4])
        })

    return {
        "main_admin_count": len(accounts),
        "accounts": accounts
    }


# =========================================================
# ERROR HANDLER - FILE TOO LARGE
# =========================================================

@app.errorhandler(413)
def file_too_large(error):

    if logged_in():

        return render_template(
            "dashboard.html",
            username=session.get(
                "username",
                ""
            ),
            role=session.get(
                "role",
                "student"
            ),
            stats=(
                get_report_stats()
                if is_main_admin()
                else None
            ),
            error=(
                "The uploaded files are too large. "
                "Maximum total size is 20 MB."
            )
        ), 413

    return redirect(
        "/login"
    )


# =========================================================
# GENERAL SERVER ERROR
# =========================================================

@app.errorhandler(500)
def internal_server_error(error):

    app.logger.exception(
        "Internal server error."
    )

    if logged_in():

        return render_template(
            "dashboard.html",
            username=session.get(
                "username",
                ""
            ),
            role=session.get(
                "role",
                "student"
            ),
            stats=(
                get_report_stats()
                if is_main_admin()
                else None
            ),
            error=(
                "Something went wrong on the server. "
                "Please try again."
            )
        ), 500

    return render_template(
        "login.html",
        error=(
            "Something went wrong on the server."
        )
    ), 500


# =========================================================
# RUN LOCALLY
# =========================================================
#
# IMPORTANT FOR RENDER:
#
# Render should use:
#
# gunicorn --bind 0.0.0.0:$PORT app:app
#
# Do NOT use "python app.py" as the Render start command.
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
