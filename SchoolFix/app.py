import os
import uuid
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    abort,
)

from werkzeug.utils import secure_filename


# ============================================================
# SUPABASE CONFIGURATION
# ============================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL")

SUPABASE_SERVICE_KEY = os.environ.get(
    "SUPABASE_SERVICE_KEY"
)

if not SUPABASE_URL:
    raise RuntimeError(
        "SUPABASE_URL environment variable is required."
    )

if not SUPABASE_SERVICE_KEY:
    raise RuntimeError(
        "SUPABASE_SERVICE_KEY environment variable is required."
    )

print(
    "SUPABASE_URL configured:",
    bool(SUPABASE_URL)
)

print(
    "SUPABASE_SERVICE_KEY configured:",
    bool(SUPABASE_SERVICE_KEY)
)


# ============================================================
# DATABASE
# ============================================================

import database


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "schoolfix-change-this-secret"
)

app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024


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

MAX_PHOTOS = 5


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

try:

    database.init_db()

    print(
        "Database initialization successful."
    )

except Exception as e:

    print(
        "Database initialization failed:",
        str(e)
    )

    raise


# ============================================================
# TEMPLATE CONTEXT
# ============================================================

@app.context_processor
def inject_user_data():

    return {
        "current_user": session.get("username"),
        "role": session.get("role"),
        "user_id": session.get("user_id"),
        "logged_in": "user_id" in session,
    }


# ============================================================
# HELPER FUNCTIONS
# ============================================================

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


def login_required(view):

    @wraps(view)
    def wrapped_view(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Please log in first.",
                "error"
            )

            return redirect(
                url_for("login")
            )

        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):

    @wraps(view)
    def wrapped_view(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Please log in first.",
                "error"
            )

            return redirect(
                url_for("login")
            )

        if session.get("role") not in (
            "admin",
            "main_admin"
        ):

            flash(
                "You do not have permission to access this page.",
                "error"
            )

            return redirect(
                url_for("dashboard")
            )

        return view(*args, **kwargs)

    return wrapped_view


def main_admin_required(view):

    @wraps(view)
    def wrapped_view(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Please log in first.",
                "error"
            )

            return redirect(
                url_for("login")
            )

        if session.get("role") != "main_admin":

            flash(
                "Main Admin permission required.",
                "error"
            )

            return redirect(
                url_for("dashboard")
            )

        return view(*args, **kwargs)

    return wrapped_view


def delete_report_files(report_id):

    try:

        photos = database.get_report_photos(
            report_id
        )

    except Exception:

        photos = []

    for photo in photos or []:

        try:

            filename = photo[2]

            if not filename:
                continue

            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            if os.path.exists(filepath):

                os.remove(filepath)

        except Exception as e:

            print(
                "Could not delete uploaded file:",
                e
            )


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template(
        "home.html"
    )


# ============================================================
# REGISTER
# ============================================================

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

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not username or not password:

            flash(
                "Username and password are required.",
                "error"
            )

            return render_template(
                "register.html"
            )

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return render_template(
                "register.html"
            )

        if len(password) < 6:

            flash(
                "Password must be at least 6 characters.",
                "error"
            )

            return render_template(
                "register.html"
            )

        try:

            existing = database.get_user_by_username(
                username
            )

            if existing:

                flash(
                    "Username already exists.",
                    "error"
                )

                return render_template(
                    "register.html"
                )

            success = database.create_user(
                username=username,
                password=password,
                role="student"
            )

            if not success:

                flash(
                    "Unable to create account.",
                    "error"
                )

                return render_template(
                    "register.html"
                )

            flash(
                "Registration successful. You can now log in.",
                "success"
            )

            return redirect(
                url_for("login")
            )

        except Exception as e:

            print(
                "Registration error:",
                e
            )

            flash(
                "Registration failed. Please try again.",
                "error"
            )

    return render_template(
        "register.html"
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
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

        if not username or not password:

            flash(
                "Please enter your username and password.",
                "error"
            )

            return render_template(
                "login.html"
            )

        try:

            user = database.authenticate_user(
                username,
                password
            )

            if not user:

                flash(
                    "Invalid username or password.",
                    "error"
                )

                return render_template(
                    "login.html"
                )

            session.clear()

            session["user_id"] = user[0]
            session["username"] = user[1]
            session["role"] = user[3]

            flash(
                "Login successful.",
                "success"
            )

            return redirect(
                url_for("dashboard")
            )

        except Exception as e:

            print(
                "Login error:",
                e
            )

            flash(
                "Login failed. Please try again.",
                "error"
            )

    return render_template(
        "login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("home")
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():

    role = session.get("role")
    username = session.get("username")

    try:

        if role in (
            "admin",
            "main_admin"
        ):

            stats = database.get_stats()

            return render_template(
                "dashboard.html",
                stats=stats,
                reports=[]
            )

        reports = database.get_user_reports(
            username
        )

        return render_template(
            "dashboard.html",
            reports=reports,
            stats={}
        )

    except Exception as e:

        print(
            "Dashboard error:",
            e
        )

        flash(
            "Unable to load dashboard.",
            "error"
        )

        return render_template(
            "dashboard.html",
            reports=[],
            stats={}
        )


# ============================================================
# SUBMIT REPORT
# ============================================================

@app.route(
    "/submit-report",
    methods=["GET", "POST"]
)
@login_required
def submit_report():

    if request.method == "POST":

        category = request.form.get(
            "category",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        if not category:

            flash(
                "Please select a category.",
                "error"
            )

            return render_template(
                "submit_report.html"
            )

        if not description:

            flash(
                "Please describe the issue.",
                "error"
            )

            return render_template(
                "submit_report.html"
            )

        files = request.files.getlist(
            "photos"
        )

        selected_files = [
            file
            for file in files
            if file and file.filename
        ]

        if len(selected_files) > MAX_PHOTOS:

            flash(
                f"You can upload a maximum of {MAX_PHOTOS} photos.",
                "error"
            )

            return render_template(
                "submit_report.html"
            )

        for file in selected_files:

            if not allowed_file(
                file.filename
            ):

                flash(
                    "Only PNG, JPG, JPEG and WEBP images are allowed.",
                    "error"
                )

                return render_template(
                    "submit_report.html"
                )

        saved_files = []

        try:

            # Save report first.
            report_id = database.save_report(
                username=session["username"],
                category=category,
                location=location,
                message=description,
                photo=""
            )

            if not report_id:

                raise RuntimeError(
                    "Report could not be created."
                )

            # Save uploaded photos.
            for file in selected_files:

                original_name = secure_filename(
                    file.filename
                )

                if not original_name:
                    continue

                extension = ""

                if "." in original_name:

                    extension = original_name.rsplit(
                        ".",
                        1
                    )[1].lower()

                filename = (
                    uuid.uuid4().hex
                    + "."
                    + extension
                )

                filepath = os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )

                file.save(filepath)

                saved_files.append(
                    filepath
                )

                success = database.add_report_photo(
                    report_id=report_id,
                    filename=filename
                )

                if not success:

                    raise RuntimeError(
                        "Photo could not be saved."
                    )

            flash(
                "Your report has been submitted successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "report_detail",
                    report_id=report_id
                )
            )

        except Exception as e:

            print(
                "Submit report error:",
                e
            )

            # Clean up physical files if database operation fails.
            for filepath in saved_files:

                try:

                    if os.path.exists(filepath):
                        os.remove(filepath)

                except OSError:
                    pass

            flash(
                "Unable to submit your report.",
                "error"
            )

    return render_template(
        "submit_report.html"
    )


# ============================================================
# MY REPORTS
# ============================================================

@app.route("/my-reports")
@login_required
def my_reports():

    if session.get("role") in (
        "admin",
        "main_admin"
    ):

        return redirect(
            url_for("reports")
        )

    try:

        reports = database.get_user_reports(
            session["username"]
        )

        return render_template(
            "reports.html",
            reports=reports,
            page_title="My Reports"
        )

    except Exception as e:

        print(
            "My reports error:",
            e
        )

        flash(
            "Unable to load your reports.",
            "error"
        )

        return render_template(
            "reports.html",
            reports=[],
            page_title="My Reports"
        )


# ============================================================
# ALL REPORTS
# ADMIN + MAIN ADMIN
# ============================================================

@app.route("/reports")
@admin_required
def reports():

    try:

        all_reports = database.get_all_reports()

        return render_template(
            "reports.html",
            reports=all_reports,
            page_title="All Reports"
        )

    except Exception as e:

        print(
            "Reports error:",
            e
        )

        flash(
            "Unable to load reports.",
            "error"
        )

        return render_template(
            "reports.html",
            reports=[],
            page_title="All Reports"
        )


# ============================================================
# REPORT DETAIL
# ============================================================

@app.route(
    "/report/<int:report_id>"
)
@login_required
def report_detail(report_id):

    report = database.get_report(
        report_id
    )

    if not report:
        abort(404)

    role = session.get("role")

    # Students can ONLY see their own reports.
    if role not in (
        "admin",
        "main_admin"
    ):

        if report[1] != session.get(
            "username"
        ):

            abort(403)

    try:

        photos = database.get_report_photos(
            report_id
        )

        messages = database.get_report_messages(
            report_id
        )

        return render_template(
            "report_detail.html",
            report=report,
            photos=photos,
            messages=messages,
            role=role
        )

    except Exception as e:

        print(
            "Report detail error:",
            e
        )

        flash(
            "Unable to load the report.",
            "error"
        )

        return redirect(
            url_for("dashboard")
        )


# ============================================================
# REPORT MESSAGE
# ============================================================

@app.route(
    "/report/<int:report_id>/message",
    methods=["POST"]
)
@login_required
def report_message(report_id):

    message = request.form.get(
        "message",
        ""
    ).strip()

    if not message:

        flash(
            "Message cannot be empty.",
            "error"
        )

        return redirect(
            url_for(
                "report_detail",
                report_id=report_id
            )
        )

    report = database.get_report(
        report_id
    )

    if not report:
        abort(404)

    role = session.get("role")

    # Students can only message their own reports.
    if role not in (
        "admin",
        "main_admin"
    ):

        if report[1] != session.get(
            "username"
        ):

            abort(403)

    try:

        success = database.add_report_message(
            report_id=report_id,
            username=session["username"],
            role=role,
            message=message
        )

        if not success:

            raise RuntimeError(
                "Message could not be saved."
            )

        flash(
            "Message sent.",
            "success"
        )

    except Exception as e:

        print(
            "Message error:",
            e
        )

        flash(
            "Unable to send message.",
            "error"
        )

    return redirect(
        url_for(
            "report_detail",
            report_id=report_id
        )
    )


# ============================================================
# UPDATE REPORT
# ADMIN + MAIN ADMIN
# ============================================================

@app.route(
    "/update-report/<int:report_id>",
    methods=["POST"]
)
@admin_required
def update_report(report_id):

    status = request.form.get(
        "status",
        "Pending"
    ).strip()

    admin_note = request.form.get(
        "admin_note",
        ""
    ).strip()

    allowed_statuses = {
        "Pending",
        "Reviewed",
        "In Progress",
        "Resolved",
        "Unreasonable"
    }

    if status not in allowed_statuses:

        flash(
            "Invalid report status.",
            "error"
        )

        return redirect(
            url_for(
                "report_detail",
                report_id=report_id
            )
        )

    try:

        success = database.update_report(
            report_id=report_id,
            status=status,
            admin_note=admin_note
        )

        if not success:

            raise RuntimeError(
                "Report was not updated."
            )

        flash(
            "Report updated successfully.",
            "success"
        )

    except Exception as e:

        print(
            "Update report error:",
            e
        )

        flash(
            "Unable to update report.",
            "error"
        )

    return redirect(
        url_for(
            "report_detail",
            report_id=report_id
        )
    )


# ============================================================
# MARK UNREASONABLE
# ADMIN + MAIN ADMIN
# ============================================================

@app.route(
    "/unreasonable/<int:report_id>",
    methods=["POST"]
)
@admin_required
def mark_unreasonable(report_id):

    try:

        success = database.mark_report_unreasonable(
            report_id
        )

        if not success:

            raise RuntimeError(
                "Report was not updated."
            )

        flash(
            "Report marked as unreasonable.",
            "success"
        )

    except Exception as e:

        print(
            "Mark unreasonable error:",
            e
        )

        flash(
            "Unable to mark the report.",
            "error"
        )

    return redirect(
        url_for(
            "report_detail",
            report_id=report_id
        )
    )


# ============================================================
# UNREASONABLE REPORTS
# MAIN ADMIN ONLY
# ============================================================

@app.route("/unreasonable-reports")
@main_admin_required
def unreasonable_reports():

    try:

        reports = database.get_unreasonable_reports()

        return render_template(
            "reports.html",
            reports=reports,
            page_title="Unreasonable Reports"
        )

    except Exception as e:

        print(
            "Unreasonable reports error:",
            e
        )

        flash(
            "Unable to load unreasonable reports.",
            "error"
        )

        return render_template(
            "reports.html",
            reports=[],
            page_title="Unreasonable Reports"
        )


# ============================================================
# DELETE REPORT
# MAIN ADMIN ONLY
# ============================================================

@app.route(
    "/delete-report/<int:report_id>",
    methods=["POST"]
)
@main_admin_required
def delete_report(report_id):

    try:

        report = database.get_report(
            report_id
        )

        if not report:
            abort(404)

        delete_report_files(
            report_id
        )

        success = database.delete_report(
            report_id
        )

        if not success:

            raise RuntimeError(
                "Report could not be deleted."
            )

        flash(
            "Report permanently deleted.",
            "success"
        )

        return redirect(
            url_for("reports")
        )

    except Exception as e:

        print(
            "Delete report error:",
            e
        )

        if getattr(e, "code", None) == 404:
            raise

        flash(
            "Unable to delete report.",
            "error"
        )

        return redirect(
            url_for(
                "report_detail",
                report_id=report_id
            )
        )


# ============================================================
# USERS
# MAIN ADMIN ONLY
# ============================================================

@app.route("/users")
@main_admin_required
def users():

    try:

        all_users = database.get_all_users()

        return render_template(
            "users.html",
            users=all_users
        )

    except Exception as e:

        print(
            "Users error:",
            e
        )

        flash(
            "Unable to load users.",
            "error"
        )

        return render_template(
            "users.html",
            users=[]
        )


# ============================================================
# DELETE USER
# MAIN ADMIN ONLY
# ============================================================

@app.route(
    "/delete-user/<int:user_id>",
    methods=["POST"]
)
@main_admin_required
def delete_user(user_id):

    if user_id == session.get(
        "user_id"
    ):

        flash(
            "You cannot delete your own Main Admin account.",
            "error"
        )

        return redirect(
            url_for("users")
        )

    try:

        user = database.get_user(
            user_id
        )

        if not user:

            flash(
                "User not found.",
                "error"
            )

            return redirect(
                url_for("users")
            )

        if user[3] == "main_admin":

            flash(
                "Main Admin accounts cannot be deleted.",
                "error"
            )

            return redirect(
                url_for("users")
            )

        result = database.delete_user(
            user_id,
            upload_folder=app.config[
                "UPLOAD_FOLDER"
            ]
        )

        if result == "protected":

            flash(
                "Main Admin accounts cannot be deleted.",
                "error"
            )

        elif result == "not_found":

            flash(
                "User not found.",
                "error"
            )

        else:

            flash(
                "User and associated reports deleted successfully.",
                "success"
            )

    except Exception as e:

        print(
            "Delete user error:",
            e
        )

        flash(
            "Unable to delete user.",
            "error"
        )

    return redirect(
        url_for("users")
    )


# ============================================================
# ADMIN APPLICATIONS
# MAIN ADMIN ONLY
# ============================================================

@app.route("/admin-applications")
@main_admin_required
def admin_applications():

    try:

        applications = database.get_admin_applications()

        return render_template(
            "admin_applications.html",
            applications=applications
        )

    except Exception as e:

        print(
            "Admin applications error:",
            e
        )

        flash(
            "Unable to load admin applications.",
            "error"
        )

        return render_template(
            "admin_applications.html",
            applications=[]
        )


# ============================================================
# APPLY FOR ADMIN
# ============================================================

@app.route(
    "/apply-admin",
    methods=["GET", "POST"]
)
@login_required
def apply_admin():

    if session.get("role") in (
        "admin",
        "main_admin"
    ):

        flash(
            "You already have admin access.",
            "error"
        )

        return redirect(
            url_for("dashboard")
        )

    if request.method == "POST":

        reason = request.form.get(
            "reason",
            ""
        ).strip()

        if not reason:

            flash(
                "Please provide a reason.",
                "error"
            )

            return render_template(
                "apply_admin.html"
            )

        try:

            success = database.create_admin_application(
                username=session["username"],
                reason=reason
            )

            if not success:

                flash(
                    "You already have a pending admin application.",
                    "error"
                )

                return redirect(
                    url_for("dashboard")
                )

            flash(
                "Your admin application has been submitted.",
                "success"
            )

            return redirect(
                url_for("dashboard")
            )

        except Exception as e:

            print(
                "Admin application error:",
                e
            )

            flash(
                "Unable to submit application.",
                "error"
            )

    return render_template(
        "apply_admin.html"
    )


# ============================================================
# APPROVE ADMIN
# MAIN ADMIN ONLY
# ============================================================

@app.route(
    "/approve-admin/<int:application_id>",
    methods=["POST"]
)
@main_admin_required
def approve_admin(application_id):

    try:

        application = database.get_admin_application(
            application_id
        )

        if not application:

            flash(
                "Application not found.",
                "error"
            )

            return redirect(
                url_for("admin_applications")
            )

        success = database.approve_admin_application(
            application_id
        )

        if not success:

            raise RuntimeError(
                "Application could not be approved."
            )

        flash(
            "Admin application approved.",
            "success"
        )

    except Exception as e:

        print(
            "Approve admin error:",
            e
        )

        flash(
            "Unable to approve application.",
            "error"
        )

    return redirect(
        url_for("admin_applications")
    )


# ============================================================
# REJECT ADMIN
# MAIN ADMIN ONLY
# ============================================================

@app.route(
    "/reject-admin/<int:application_id>",
    methods=["POST"]
)
@main_admin_required
def reject_admin(application_id):

    try:

        success = database.reject_admin_application(
            application_id
        )

        if not success:

            raise RuntimeError(
                "Application could not be rejected."
            )

        flash(
            "Admin application rejected.",
            "success"
        )

    except Exception as e:

        print(
            "Reject admin error:",
            e
        )

        flash(
            "Unable to reject application.",
            "error"
        )

    return redirect(
        url_for("admin_applications")
    )


# ============================================================
# CHANGE PASSWORD
# ============================================================

@app.route(
    "/change-password",
    methods=["GET", "POST"]
)
@login_required
def change_password():

    if request.method == "POST":

        current_password = request.form.get(
            "current_password",
            ""
        )

        new_password = request.form.get(
            "new_password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not current_password or not new_password:

            flash(
                "All password fields are required.",
                "error"
            )

            return render_template(
                "change_password.html"
            )

        if new_password != confirm_password:

            flash(
                "New passwords do not match.",
                "error"
            )

            return render_template(
                "change_password.html"
            )

        if len(new_password) < 6:

            flash(
                "New password must be at least 6 characters.",
                "error"
            )

            return render_template(
                "change_password.html"
            )

        try:

            user = database.authenticate_user(
                session["username"],
                current_password
            )

            if not user:

                flash(
                    "Current password is incorrect.",
                    "error"
                )

                return render_template(
                    "change_password.html"
                )

            success = database.update_password(
                session["username"],
                new_password
            )

            if not success:

                raise RuntimeError(
                    "Password could not be updated."
                )

            flash(
                "Password changed successfully.",
                "success"
            )

            return redirect(
                url_for("dashboard")
            )

        except Exception as e:

            print(
                "Change password error:",
                e
            )

            flash(
                "Unable to change password.",
                "error"
            )

    return render_template(
        "change_password.html"
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(403)
def forbidden(error):

    return render_template(
        "error.html",
        error_code=403,
        message="You do not have permission to access this page."
    ), 403


@app.errorhandler(404)
def not_found(error):

    return render_template(
        "error.html",
        error_code=404,
        message="The page you are looking for could not be found."
    ), 404


@app.errorhandler(413)
def file_too_large(error):

    flash(
        "Uploaded files are too large. Maximum total size is 20 MB.",
        "error"
    )

    return redirect(
        url_for("submit_report")
    )


@app.errorhandler(500)
def internal_error(error):

    print(
        "ERROR in app: Internal server error"
    )

    return render_template(
        "error.html",
        error_code=500,
        message="Something went wrong on the server."
    ), 500


# ============================================================
# LOCAL SERVER
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
