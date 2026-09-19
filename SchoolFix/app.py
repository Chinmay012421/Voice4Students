import os
import uuid

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    flash
)
from werkzeug.utils import secure_filename

from database import (
    init_db,
    create_user,
    authenticate_user,
    get_user,
    get_user_by_username,
    get_all_users,
    update_password,

    create_admin_application,
    get_admin_applications,
    get_admin_application,
    approve_admin_application,
    reject_admin_application,

    save_report,
    get_report,
    get_all_reports,
    get_user_reports,
    update_report_status,
    mark_report_unreasonable,
    get_unreasonable_reports,

    add_report_photo,
    get_report_photos,

    add_report_message,
    get_report_messages,

    delete_report,
    delete_user,

    get_report_stats
)


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "schoolvoice-development-secret-key"
)


# ============================================================
# UPLOAD SETTINGS
# ============================================================

UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "uploads"
)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}

app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

try:
    init_db()
except Exception as e:
    print("Database initialization warning:", e)


# ============================================================
# HELPERS
# ============================================================

def allowed_file(filename):
    if not filename:
        return False

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def current_username():
    return session.get("username")


def current_role():
    return session.get("role")


def is_logged_in():
    return "username" in session


def is_admin():
    return session.get("role") in [
        "admin",
        "main_admin"
    ]


def is_main_admin():
    return session.get("role") == "main_admin"


def delete_report_files(report_id):
    """
    Delete physical photo files belonging to a report.
    """

    photos = get_report_photos(report_id)

    for photo in photos:
        filename = photo[2]

        if not filename:
            continue

        path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            filename
        )

        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    if is_logged_in():
        return redirect("/dashboard")

    return render_template("home.html")


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
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

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not username or not password:
            flash(
                "Username and password are required.",
                "error"
            )
            return redirect("/register")

        if password != confirm_password:
            flash(
                "Passwords do not match.",
                "error"
            )
            return redirect("/register")

        success = create_user(
            username,
            password,
            "student"
        )

        if not success:
            flash(
                "That username already exists.",
                "error"
            )
            return redirect("/register")

        flash(
            "Account created successfully. You can now log in.",
            "success"
        )

        return redirect("/login")

    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        user = authenticate_user(
            username,
            password
        )

        if not user:
            flash(
                "Invalid username or password.",
                "error"
            )
            return redirect("/login")

        session.clear()

        session["user_id"] = user[0]
        session["username"] = user[1]
        session["role"] = user[3]

        return redirect("/dashboard")

    return render_template("login.html")


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if not is_logged_in():
        return redirect("/login")

    username = current_username()

    if is_admin():

        reports = get_all_reports()

        stats = get_report_stats()

        return render_template(
            "dashboard.html",
            reports=reports,
            stats=stats
        )

    reports = get_user_reports(username)

    stats = get_report_stats(username)

    return render_template(
        "dashboard.html",
        reports=reports,
        stats=stats
    )


# ============================================================
# SUBMIT REPORT
# ============================================================

@app.route("/submit-report", methods=["GET", "POST"])
def submit_report():

    if not is_logged_in():
        return redirect("/login")

    if is_admin():
        return redirect("/dashboard")

    if request.method == "POST":

        category = request.form.get(
            "category",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        message = request.form.get(
            "message",
            ""
        ).strip()

        if not category or not message:
            flash(
                "Please fill in all required fields.",
                "error"
            )
            return redirect("/submit-report")

        photos = request.files.getlist(
            "photos"
        )

        valid_photos = []

        for photo in photos:

            if not photo or not photo.filename:
                continue

            if not allowed_file(photo.filename):
                flash(
                    "Only PNG, JPG, JPEG and WEBP images are allowed.",
                    "error"
                )
                return redirect("/submit-report")

            valid_photos.append(photo)

        if len(valid_photos) > 5:
            flash(
                "You can upload a maximum of 5 photos.",
                "error"
            )
            return redirect("/submit-report")

        # ----------------------------------------------------
        # Create report
        # ----------------------------------------------------

        report_id = save_report(
            current_username(),
            category,
            location,
            message
        )

        if not report_id:
            flash(
                "Unable to submit the report.",
                "error"
            )
            return redirect("/submit-report")

        # ----------------------------------------------------
        # Save uploaded photos
        # ----------------------------------------------------

        for photo in valid_photos:

            original_name = secure_filename(
                photo.filename
            )

            extension = ""

            if "." in original_name:
                extension = "." + original_name.rsplit(
                    ".",
                    1
                )[1].lower()

            unique_filename = (
                uuid.uuid4().hex
                + extension
            )

            file_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                unique_filename
            )

            photo.save(file_path)

            add_report_photo(
                report_id,
                unique_filename
            )

        flash(
            "Your report has been submitted successfully.",
            "success"
        )

        return redirect(
            f"/report/{report_id}"
        )

    return render_template(
        "submit_report.html"
    )


# ============================================================
# MY REPORTS
# ============================================================

@app.route("/my-reports")
def my_reports():

    if not is_logged_in():
        return redirect("/login")

    if is_admin():
        return redirect("/reports")

    reports = get_user_reports(
        current_username()
    )

    return render_template(
        "my_reports.html",
        reports=reports
    )


# ============================================================
# ALL REPORTS
# ============================================================

@app.route("/reports")
def reports():

    if not is_admin():
        return redirect("/dashboard")

    reports = get_all_reports()

    return render_template(
        "reports.html",
        reports=reports
    )


# ============================================================
# VIEW REPORT
# ============================================================

@app.route("/report/<int:report_id>")
def report_detail(report_id):

    if not is_logged_in():
        return redirect("/login")

    report = get_report(report_id)

    if not report:
        flash(
            "Report not found.",
            "error"
        )
        return redirect("/dashboard")

    # --------------------------------------------------------
    # Students can ONLY open their own reports
    # --------------------------------------------------------

    if not is_admin():

        if report[1] != current_username():
            flash(
                "You do not have permission to view this report.",
                "error"
            )
            return redirect("/my-reports")

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
        messages=messages
    )


# ============================================================
# REPORT MESSAGE / CONVERSATION
# ============================================================

@app.route(
    "/report/<int:report_id>/message",
    methods=["POST"]
)
def report_message(report_id):

    if not is_logged_in():
        return redirect("/login")

    report = get_report(report_id)

    if not report:
        return redirect("/dashboard")

    # --------------------------------------------------------
    # Students can only message on their own reports
    # --------------------------------------------------------

    if not is_admin():

        if report[1] != current_username():
            return redirect("/dashboard")

    message = request.form.get(
        "message",
        ""
    ).strip()

    if message:

        add_report_message(
            report_id,
            current_username(),
            current_role(),
            message
        )

    return redirect(
        f"/report/{report_id}"
    )


# ============================================================
# UPDATE REPORT
# ============================================================

@app.route(
    "/update-report/<int:report_id>",
    methods=["POST"]
)
def update_report(report_id):

    if not is_admin():
        return redirect("/dashboard")

    report = get_report(report_id)

    if not report:
        return redirect("/reports")

    status = request.form.get(
        "status",
        "Pending"
    )

    admin_note = request.form.get(
        "admin_note",
        ""
    ).strip()

    success = update_report_status(
        report_id,
        status,
        admin_note
    )

    if success:
        flash(
            "Report updated successfully.",
            "success"
        )
    else:
        flash(
            "Unable to update report.",
            "error"
        )

    return redirect(
        f"/report/{report_id}"
    )


# ============================================================
# MARK UNREASONABLE
# ============================================================

@app.route(
    "/unreasonable/<int:report_id>",
    methods=["POST"]
)
def unreasonable(report_id):

    if not is_admin():
        return redirect("/dashboard")

    report = get_report(report_id)

    if not report:
        return redirect("/reports")

    mark_report_unreasonable(
        report_id
    )

    flash(
        "Report marked as unreasonable and sent to Main Admin review.",
        "success"
    )

    return redirect(
        f"/report/{report_id}"
    )


# ============================================================
# UNREASONABLE REPORTS
# ============================================================

@app.route("/unreasonable-reports")
def unreasonable_reports():

    if not is_main_admin():
        return redirect("/dashboard")

    reports = get_unreasonable_reports()

    return render_template(
        "unreasonable_reports.html",
        reports=reports
    )


# ============================================================
# DELETE REPORT
# ============================================================

@app.route(
    "/delete-report/<int:report_id>",
    methods=["POST"]
)
def delete_report_route(report_id):

    if not is_main_admin():
        return redirect("/dashboard")

    report = get_report(report_id)

    if not report:
        flash(
            "Report not found.",
            "error"
        )
        return redirect("/unreasonable-reports")

    # Delete physical images first
    delete_report_files(
        report_id
    )

    # Delete Supabase records
    success = delete_report(
        report_id
    )

    if success:
        flash(
            "Report deleted successfully.",
            "success"
        )
    else:
        flash(
            "Unable to delete report.",
            "error"
        )

    return redirect(
        "/unreasonable-reports"
    )


# ============================================================
# USERS
# ============================================================

@app.route("/users")
def users():

    if not is_main_admin():
        return redirect("/dashboard")

    all_users = get_all_users()

    return render_template(
        "users.html",
        users=all_users
    )


# ============================================================
# DELETE USER
# ============================================================

@app.route(
    "/delete-user/<int:user_id>",
    methods=["POST"]
)
def delete_user_route(user_id):

    if not is_main_admin():
        return redirect("/dashboard")

    try:

        result = delete_user(
            user_id,
            app.config["UPLOAD_FOLDER"]
        )

        # Main Admin protection
        if result == "protected":

            flash(
                "Main Admin accounts cannot be deleted.",
                "error"
            )

            return redirect("/users")

        # User does not exist
        if result == "not_found":

            flash(
                "User not found.",
                "error"
            )

            return redirect("/users")

        # Successful deletion
        if result:

            flash(
                f"User '{result['username']}' and "
                f"{result['report_count']} report(s) were deleted.",
                "success"
            )

            return redirect("/users")

        flash(
            "Unable to delete user.",
            "error"
        )

        return redirect("/users")

    except Exception:

        app.logger.exception(
            "Error deleting user"
        )

        flash(
            "An error occurred while deleting the user.",
            "error"
        )

        return redirect("/users")


# ============================================================
# ADMIN APPLICATIONS
# ============================================================

@app.route("/admin-applications")
def admin_applications():

    if not is_main_admin():
        return redirect("/dashboard")

    applications = get_admin_applications()

    return render_template(
        "admin_applications.html",
        applications=applications
    )


# ============================================================
# APPLY FOR ADMIN
# ============================================================

@app.route(
    "/apply-admin",
    methods=["GET", "POST"]
)
def apply_admin():

    if not is_logged_in():
        return redirect("/login")

    if current_role() != "student":
        return redirect("/dashboard")

    if request.method == "POST":

        reason = request.form.get(
            "reason",
            ""
        ).strip()

        success = create_admin_application(
            current_username(),
            reason
        )

        if success:

            flash(
                "Your admin application has been submitted.",
                "success"
            )

        else:

            flash(
                "You already have a pending admin application.",
                "error"
            )

        return redirect("/dashboard")

    return render_template(
        "apply_admin.html"
    )


# ============================================================
# APPROVE ADMIN APPLICATION
# ============================================================

@app.route(
    "/approve-admin/<int:application_id>",
    methods=["POST"]
)
def approve_admin(application_id):

    if not is_main_admin():
        return redirect("/dashboard")

    success = approve_admin_application(
        application_id
    )

    if success:

        flash(
            "Admin application approved.",
            "success"
        )

    else:

        flash(
            "Unable to approve application.",
            "error"
        )

    return redirect(
        "/admin-applications"
    )


# ============================================================
# REJECT ADMIN APPLICATION
# ============================================================

@app.route(
    "/reject-admin/<int:application_id>",
    methods=["POST"]
)
def reject_admin(application_id):

    if not is_main_admin():
        return redirect("/dashboard")

    success = reject_admin_application(
        application_id
    )

    if success:

        flash(
            "Admin application rejected.",
            "success"
        )

    else:

        flash(
            "Unable to reject application.",
            "error"
        )

    return redirect(
        "/admin-applications"
    )


# ============================================================
# CHANGE PASSWORD
# ============================================================

@app.route(
    "/change-password",
    methods=["GET", "POST"]
)
def change_password():

    if not is_logged_in():
        return redirect("/login")

    if request.method == "POST":

        new_password = request.form.get(
            "new_password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not new_password:

            flash(
                "Password cannot be empty.",
                "error"
            )

            return redirect(
                "/change-password"
            )

        if new_password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return redirect(
                "/change-password"
            )

        success = update_password(
            current_username(),
            new_password
        )

        if success:

            flash(
                "Password changed successfully.",
                "success"
            )

            return redirect(
                "/dashboard"
            )

        flash(
            "Unable to change password.",
            "error"
        )

    return render_template(
        "change_password.html"
    )


# ============================================================
# 404
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    if is_logged_in():
        return redirect("/dashboard")

    return redirect("/")


# ============================================================
# FILE TOO LARGE
# ============================================================

@app.errorhandler(413)
def file_too_large(error):

    flash(
        "The uploaded files are too large. Maximum total size is 20 MB.",
        "error"
    )

    return redirect(
        "/submit-report"
    )


# ============================================================
# SERVER ERROR
# ============================================================

@app.errorhandler(500)
def server_error(error):

    app.logger.exception(
        "Internal server error"
    )

    if is_logged_in():

        return render_template(
            "error.html",
            message="Something went wrong. Please try again."
        ), 500

    return (
        "Internal server error.",
        500
    )


# ============================================================
# RUN
# ============================================================

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
