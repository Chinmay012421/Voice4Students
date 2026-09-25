import os
import uuid
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, abort, send_from_directory
)
from werkzeug.utils import secure_filename

import database

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-in-render")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_PHOTOS = 5

database.init_db()


@app.context_processor
def inject_user_data():
    return {
        "current_user": session.get("username"),
        "role": session.get("role"),
        "user_id": session.get("user_id"),
        "logged_in": "user_id" in session,
    }


def allowed_file(filename):
    return bool(
        filename
        and "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        if session.get("role") not in ("admin", "main_admin"):
            flash("Admin permission required.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


def main_admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        if session.get("role") != "main_admin":
            flash("Main Admin permission required.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped


def can_access_report(report):
    if not report:
        return False

    role = session.get("role")
    uid = session.get("user_id")

    if role == "main_admin":
        return True

    if role == "student":
        return report[1] == uid

    if role == "admin":
        return report[9] == uid

    return False


def can_manage_report(report):
    if not report:
        return False

    if session.get("role") == "main_admin":
        return True

    return session.get("role") == "admin" and report[9] == session.get("user_id")


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
        elif len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif database.get_user_by_username(username):
            flash("Username already exists.", "error")
        elif not database.create_user(username, password, "student"):
            flash("Registration failed.", "error")
        else:
            flash("Account created. You can now log in.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = database.authenticate_user(username, password)
        if not user:
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user[0]
        session["username"] = user[1]
        session["role"] = user[3]
        flash("Welcome back, " + user[1] + "!", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    role = session["role"]

    if role == "main_admin":
        stats = database.get_report_stats()
        recent = database.get_all_reports()[:6]
        return render_template("dashboard.html", stats=stats, reports=recent)

    if role == "admin":
        stats = database.get_report_stats(assigned_to=session["user_id"])
        recent = database.get_assigned_reports(session["user_id"])[:6]
        return render_template("dashboard.html", stats=stats, reports=recent)

    reports = database.get_user_reports(session["user_id"])
    stats = database.get_report_stats(session["user_id"])
    return render_template("dashboard.html", stats=stats, reports=reports[:6])


@app.route("/submit-report", methods=["GET", "POST"])
@login_required
def submit_report():
    if request.method == "POST":
        category = request.form.get("category", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()

        if not category or not description:
            flash("Category and description are required.", "error")
            return render_template("submit_report.html")

        files = [f for f in request.files.getlist("photos") if f and f.filename]
        if len(files) > MAX_PHOTOS:
            flash(f"Maximum {MAX_PHOTOS} photos are allowed.", "error")
            return render_template("submit_report.html")

        for f in files:
            if not allowed_file(f.filename):
                flash("Only PNG, JPG, JPEG and WEBP images are allowed.", "error")
                return render_template("submit_report.html")

        try:
            report_id = database.save_report(
                user_id=session["user_id"],
                username=session["username"],
                category=category,
                location=location,
                message=description,
            )

            for f in files:
                safe_name = secure_filename(f.filename)
                ext = safe_name.rsplit(".", 1)[1].lower()
                filename = uuid.uuid4().hex + "." + ext
                storage_path = f"reports/{report_id}/{filename}"
                data = f.read()

                database.upload_photo(
                    report_id=report_id,
                    filename=filename,
                    storage_path=storage_path,
                    file_bytes=data,
                    content_type=f.mimetype or "application/octet-stream",
                )

            flash("Your report was submitted successfully.", "success")
            return redirect(url_for("report_detail", report_id=report_id))

        except Exception as exc:
            app.logger.exception("Report submission failed")
            flash("Unable to submit the report. Please try again.", "error")

    return render_template("submit_report.html")


@app.route("/my-reports")
@login_required
def my_reports():
    if session["role"] in ("admin", "main_admin"):
        return redirect(url_for("reports"))
    return render_template(
        "reports.html",
        reports=database.get_user_reports(session["user_id"]),
        page_title="My Reports",
    )


@app.route("/reports")
@admin_required
def reports():
    if session["role"] == "main_admin":
        visible_reports = database.get_all_reports()
        page_title = "All Reports"
    else:
        visible_reports = database.get_assigned_reports(session["user_id"])
        page_title = "Assigned Reports"

    return render_template(
        "reports.html",
        reports=visible_reports,
        page_title=page_title,
    )


@app.route("/report/<int:report_id>")
@login_required
def report_detail(report_id):
    report = database.get_report(report_id)
    if not report:
        abort(404)

    if not can_access_report(report):
        abort(403)

    photos = database.get_report_photos(report_id)
    for photo in photos:
        photo["url"] = database.create_photo_url(photo["storage_path"])

    messages = database.get_report_messages(report_id)

    return render_template(
        "report_detail.html",
        report=report,
        photos=photos,
        messages=messages,
        admins=database.get_admin_users() if session["role"] == "main_admin" else [],
    )


@app.route("/report/<int:report_id>/message", methods=["POST"])
@login_required
def report_message(report_id):
    report = database.get_report(report_id)
    if not report:
        abort(404)

    if not can_access_report(report):
        abort(403)

    message = request.form.get("message", "").strip()
    if not message:
        flash("Message cannot be empty.", "error")
    else:
        database.add_report_message(
            report_id,
            session["user_id"],
            session["username"],
            session["role"],
            message,
        )
        flash("Message sent.", "success")

    return redirect(url_for("report_detail", report_id=report_id))


@app.route("/update-report/<int:report_id>", methods=["POST"])
@admin_required
def update_report(report_id):
    report = database.get_report(report_id)
    if not report:
        abort(404)

    if not can_manage_report(report):
        abort(403)

    status = request.form.get("status", "Pending")
    note = request.form.get("admin_note", "").strip()

    if status not in {"Pending", "Reviewed", "In Progress", "Resolved", "Unreasonable"}:
        flash("Invalid status.", "error")
    else:
        database.update_report(report_id, status, note)
        flash("Report updated.", "success")

    return redirect(url_for("report_detail", report_id=report_id))


@app.route("/refer-report/<int:report_id>", methods=["POST"])
@main_admin_required
def refer_report(report_id):
    report = database.get_report(report_id)
    if not report:
        abort(404)

    admin_id = request.form.get("admin_id", "").strip()
    if not admin_id:
        flash("Please select an Admin.", "error")
        return redirect(url_for("report_detail", report_id=report_id))

    try:
        admin_id = int(admin_id)
    except ValueError:
        flash("Invalid Admin selected.", "error")
        return redirect(url_for("report_detail", report_id=report_id))

    if database.assign_report(report_id, admin_id, session["user_id"]):
        flash("Report referred to the selected Admin.", "success")
    else:
        flash("Unable to refer this report.", "error")

    return redirect(url_for("report_detail", report_id=report_id))


@app.route("/take-back-report/<int:report_id>", methods=["POST"])
@main_admin_required
def take_back_report(report_id):
    report = database.get_report(report_id)
    if not report:
        abort(404)

    if database.unassign_report(report_id):
        flash("Report is now back with Main Admin.", "success")
    else:
        flash("Unable to take back the report.", "error")

    return redirect(url_for("report_detail", report_id=report_id))


@app.route("/unreasonable/<int:report_id>", methods=["POST"])
@admin_required
def mark_unreasonable(report_id):
    report = database.get_report(report_id)
    if not report:
        abort(404)

    if not can_manage_report(report):
        abort(403)

    database.update_report(
        report_id,
        "Unreasonable",
        "Marked for Main Admin review.",
    )
    flash("Report marked as unreasonable.", "success")
    return redirect(url_for("report_detail", report_id=report_id))


@app.route("/unreasonable-reports")
@main_admin_required
def unreasonable_reports():
    return render_template(
        "reports.html",
        reports=database.get_unreasonable_reports(),
        page_title="Unreasonable Reports",
    )


@app.route("/delete-report/<int:report_id>", methods=["POST"])
@main_admin_required
def delete_report(report_id):
    if database.delete_report(report_id):
        flash("Report deleted.", "success")
    else:
        flash("Report not found.", "error")
    return redirect(url_for("reports"))


@app.route("/users")
@main_admin_required
def users():
    return render_template("users.html", users=database.get_all_users())


@app.route("/delete-user/<int:user_id>", methods=["POST"])
@main_admin_required
def delete_user(user_id):
    if user_id == session["user_id"]:
        flash("You cannot delete your own Main Admin account.", "error")
        return redirect(url_for("users"))

    result = database.delete_user(user_id)
    if result == "protected":
        flash("Main Admin accounts cannot be deleted.", "error")
    elif result == "not_found":
        flash("User not found.", "error")
    else:
        flash("User and their reports were deleted.", "success")

    return redirect(url_for("users"))


@app.route("/change-role/<int:user_id>", methods=["POST"])
@main_admin_required
def change_role(user_id):
    role = request.form.get("role", "student")
    if role not in {"student", "admin"}:
        flash("Invalid role.", "error")
    elif user_id == session["user_id"]:
        flash("You cannot change your own Main Admin role.", "error")
    elif database.change_user_role(user_id, role):
        flash("User role updated.", "success")
    else:
        flash("Unable to change role.", "error")
    return redirect(url_for("users"))


@app.route("/reset-user-password/<int:user_id>", methods=["POST"])
@main_admin_required
def reset_user_password(user_id):
    password = request.form.get("new_password", "")
    if len(password) < 6:
        flash("Password must be at least 6 characters.", "error")
    elif database.reset_user_password(user_id, password):
        flash("Password reset successfully.", "success")
    else:
        flash("Unable to reset password.", "error")
    return redirect(url_for("users"))


@app.route("/admin-applications")
@main_admin_required
def admin_applications():
    return render_template(
        "admin_applications.html",
        applications=database.get_admin_applications(),
    )


@app.route("/apply-admin", methods=["GET", "POST"])
@login_required
def apply_admin():
    if session["role"] != "student":
        flash("You already have admin access.", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        reason = request.form.get("reason", "").strip()
        if not reason:
            flash("Please provide a reason.", "error")
        elif database.create_admin_application(
            session["user_id"], session["username"], reason
        ):
            flash("Application submitted.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("You already have a pending application.", "error")

    return render_template("apply_admin.html")


@app.route("/approve-admin/<int:application_id>", methods=["POST"])
@main_admin_required
def approve_admin(application_id):
    if database.approve_admin_application(application_id):
        flash("Admin application approved.", "success")
    else:
        flash("Application not found.", "error")
    return redirect(url_for("admin_applications"))


@app.route("/reject-admin/<int:application_id>", methods=["POST"])
@main_admin_required
def reject_admin(application_id):
    if database.reject_admin_application(application_id):
        flash("Admin application rejected.", "success")
    else:
        flash("Application not found.", "error")
    return redirect(url_for("admin_applications"))


@app.route("/database")
@main_admin_required
def database_panel():
    return render_template(
        "database.html",
        users=database.get_all_users(),
        reports=database.get_all_reports(),
        applications=database.get_admin_applications(),
        stats=database.get_report_stats(),
    )


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        if not database.verify_user_password(session["user_id"], current):
            flash("Current password is incorrect.", "error")
        elif len(new) < 6:
            flash("New password must be at least 6 characters.", "error")
        elif new != confirm:
            flash("New passwords do not match.", "error")
        elif database.update_password(session["user_id"], new):
            flash("Password changed successfully.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Unable to change password.", "error")

    return render_template("change_password.html")


@app.errorhandler(403)
def forbidden(_):
    return render_template(
        "error.html",
        code=403,
        title="Access denied",
        message="You don't have permission to access this page.",
    ), 403


@app.errorhandler(404)
def not_found(_):
    return render_template(
        "error.html",
        code=404,
        title="Not found",
        message="That page or report does not exist.",
    ), 404


@app.errorhandler(413)
def too_large(_):
    return render_template(
        "error.html",
        code=413,
        title="File too large",
        message="The upload is larger than the allowed limit.",
    ), 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
