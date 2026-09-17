import os
import secrets
import string

from flask import Flask, request, redirect, session, render_template
from werkzeug.utils import secure_filename

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
    update_report_status,
    delete_report,
    get_unreasonable_reports,
    get_report_stats,
    change_password,
    set_temporary_password,
    set_permanent_password,
    get_all_users
)


app = Flask(__name__)

app.secret_key = "schoolfix-demo-secret-key"


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

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower()
        in ALLOWED_EXTENSIONS
    )


init_db()


def logged_in():

    return "username" in session


def is_main_admin():

    return session.get("role") == "main_admin"


def is_admin():

    return session.get("role") in (
        "admin",
        "main_admin"
    )


@app.route("/")
def home():

    return render_template(
        "index.html"
    )


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

        user = get_user(
            username,
            password
        )

        if user:

            session.clear()

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


@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


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

        try:

            save_user(
                username,
                password,
                "student"
            )

            return render_template(
                "login.html",
                message=(
                    "Registration successful. "
                    "Please log in as a student."
                )
            )

        except Exception as e:

            app.logger.exception(
                "Registration error"
            )

            return render_template(
                "register.html",
                error=f"Registration failed: {e}"
            )

    return render_template(
        "register.html"
    )


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

        change_password(
            session["username"],
            new_password
        )

        return redirect(
            "/dashboard"
        )

    return render_template(
        "change_password.html"
    )


# =========================================================
# MAIN ADMIN USER MANAGEMENT
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
            search="",
            selected_role="",
            error=(
                "Main Admin passwords cannot "
                "be reset from this screen."
            )
        )

    if result is None:

        return render_template(
            "users.html",
            users=get_all_users(),
            search="",
            selected_role="",
            error="User not found."
        )

    return render_template(
        "reset_password.html",
        username=result,
        temporary_password=temporary_password
    )


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
            search="",
            selected_role="",
            error=(
                "Password must be at least "
                "8 characters."
            )
        )

    if new_password != confirm_password:

        return render_template(
            "users.html",
            users=get_all_users(),
            search="",
            selected_role="",
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
            search="",
            selected_role="",
            error=(
                "Main Admin passwords cannot "
                "be changed from this screen."
            )
        )

    if result is None:

        return render_template(
            "users.html",
            users=get_all_users(),
            search="",
            selected_role="",
            error=(
                "User not found or inactive."
            )
        )

    return render_template(
        "users.html",
        users=get_all_users(),
        search="",
        selected_role="",
        message=(
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

    if session.get("role") == "main_admin":

        stats = get_report_stats()

    return render_template(
        "dashboard.html",
        username=session["username"],
        role=session["role"],
        stats=stats
    )


# =========================================================
# ADMIN APPLICATIONS
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
# REPORT SUBMISSION
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
    )

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

    photo_name = ""

    photo = request.files.get(
        "photo"
    )

    if photo and photo.filename:

        if not allowed_file(
            photo.filename
        ):

            return render_template(
                "dashboard.html",
                username=session["username"],
                role=session["role"],
                stats=None,
                error=(
                    "Please upload a PNG, JPG, "
                    "JPEG or WEBP image."
                )
            )

        original_name = secure_filename(
            photo.filename
        )

        _, extension = os.path.splitext(
            original_name
        )

        photo_name = (
            f"{secrets.token_hex(16)}"
            f"{extension.lower()}"
        )

        photo_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            photo_name
        )

        photo.save(
            photo_path
        )

    save_report(
        session["username"],
        category,
        location,
        message,
        photo_name
    )

    return redirect(
        "/my-reports"
    )


# =========================================================
# STUDENT REPORTS
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
# ADMIN REPORTS
# =========================================================

@app.route("/reports")
def reports():

    if not is_admin():

        return redirect("/dashboard")

    return render_template(
        "reports.html",
        reports=get_all_reports()
    )


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
        "/reports"
    )


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
        "/reports"
    )


# =========================================================
# MAIN ADMIN UNREASONABLE REPORTS
# =========================================================

@app.route(
    "/unreasonable-reports"
)
def unreasonable_reports():

    if not is_main_admin():

        return redirect("/dashboard")

    return render_template(
        "unreasonable_reports.html",
        reports=get_unreasonable_reports()
    )


@app.route(
    "/delete-report/<int:report_id>"
)
def delete_report_route(
    report_id
):

    if not is_main_admin():

        return redirect("/dashboard")

    delete_report(
        report_id
    )

    return redirect(
        "/unreasonable-reports"
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
