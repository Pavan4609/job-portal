import os
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()


from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory,
    abort
)

import mysql.connector

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from werkzeug.utils import secure_filename

from email_utils import send_email


# =========================================================
# FLASK CONFIGURATION
# =========================================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "SECRET_KEY",
    "change-this-secret-key"
)


# =========================================================
# BASE DIRECTORY
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


# =========================================================
# UPLOAD CONFIGURATION
# =========================================================

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads"
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {
    "pdf",
    "doc",
    "docx"
}

MAX_FILE_SIZE = 5 * 1024 * 1024

app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE


if not os.path.exists(UPLOAD_FOLDER):

    os.makedirs(UPLOAD_FOLDER)


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():

    return mysql.connector.connect(

        host=os.getenv(
            "MYSQL_HOST",
            "localhost"
        ),

        user=os.getenv(
            "MYSQL_USER",
            "root"
        ),

        password=os.getenv(
            "MYSQL_PASSWORD"
        ),

        database=os.getenv(
            "MYSQL_DATABASE",
            "jobportal"
        )
    )


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def allowed_file(filename):

    return (
        "." in filename
        and
        filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def is_logged_in():

    return "user_id" in session


def is_role(role):

    return (
        "user_id" in session
        and
        session.get("role") == role
    )


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def index():

    search = request.args.get(
        "search",
        ""
    ).strip()

    location = request.args.get(
        "location",
        ""
    ).strip()

    job_type = request.args.get(
        "job_type",
        ""
    ).strip()

    experience = request.args.get(
        "experience",
        ""
    ).strip()

    sort = request.args.get(
        "sort",
        "newest"
    ).strip()

    min_salary = request.args.get(
        "min_salary",
        ""
    ).strip()

    max_salary = request.args.get(
        "max_salary",
        ""
    ).strip()


    try:

        page = int(
            request.args.get(
                "page",
                1
            )
        )

    except ValueError:

        page = 1


    if page < 1:

        page = 1


    per_page = 10


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    conditions = []

    values = []


    # SEARCH

    if search:

        conditions.append(
            """
            (
                title LIKE %s
                OR company LIKE %s
                OR description LIKE %s
            )
            """
        )

        keyword = f"%{search}%"

        values.extend(
            [
                keyword,
                keyword,
                keyword
            ]
        )


    # LOCATION

    if location:

        conditions.append(
            "location LIKE %s"
        )

        values.append(
            f"%{location}%"
        )


    # JOB TYPE

    if job_type:

        conditions.append(
            "job_type = %s"
        )

        values.append(
            job_type
        )


    # EXPERIENCE

    if experience:

        conditions.append(
            "experience = %s"
        )

        values.append(
            experience
        )


    # MIN SALARY

    if min_salary:

        try:

            min_value = float(
                min_salary
            )

            conditions.append(
                "max_salary >= %s"
            )

            values.append(
                min_value
            )

        except ValueError:

            min_salary = ""


    # MAX SALARY

    if max_salary:

        try:

            max_value = float(
                max_salary
            )

            conditions.append(
                "min_salary <= %s"
            )

            values.append(
                max_value
            )

        except ValueError:

            max_salary = ""


    where_clause = ""


    if conditions:

        where_clause = (
            " WHERE "
            +
            " AND ".join(conditions)
        )


    # SORTING

    if sort == "oldest":

        order_clause = (
            " ORDER BY created_at ASC"
        )

    elif sort == "salary_high":

        order_clause = (
            " ORDER BY max_salary DESC"
        )

    elif sort == "salary_low":

        order_clause = (
            " ORDER BY min_salary ASC"
        )

    else:

        order_clause = (
            " ORDER BY created_at DESC"
        )


    # COUNT

    count_query = f"""
        SELECT COUNT(*) AS total
        FROM jobs
        {where_clause}
    """


    cursor.execute(
        count_query,
        values
    )


    result = cursor.fetchone()

    total_jobs = result["total"]


    total_pages = max(
        1,
        (
            total_jobs
            +
            per_page
            -
            1
        )
        // per_page
    )


    if page > total_pages:

        page = total_pages


    offset = (
        page - 1
    ) * per_page


    # JOBS

    query = f"""
        SELECT

            id,
            title,
            company,
            location,
            description,
            salary,
            min_salary,
            max_salary,
            job_type,
            experience,
            employer_id,
            created_at

        FROM jobs

        {where_clause}

        {order_clause}

        LIMIT %s OFFSET %s
    """


    query_values = (
        values
        +
        [
            per_page,
            offset
        ]
    )


    cursor.execute(
        query,
        query_values
    )


    jobs = cursor.fetchall()


    cursor.close()

    conn.close()


    return render_template(
        "index.html",
        jobs=jobs,
        search=search,
        location=location,
        job_type=job_type,
        experience=experience,
        sort=sort,
        min_salary=min_salary,
        max_salary=max_salary,
        page=page,
        total_pages=total_pages,
        total_jobs=total_jobs
    )


# =========================================================
# REGISTER
# =========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        full_name = request.form.get(
            "full_name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        role = request.form.get(
            "role",
            ""
        ).strip()


        if not full_name:

            flash(
                "Please enter your full name.",
                "danger"
            )

            return redirect(
                url_for("register")
            )


        if not email:

            flash(
                "Please enter your email.",
                "danger"
            )

            return redirect(
                url_for("register")
            )


        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "danger"
            )

            return redirect(
                url_for("register")
            )


        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return redirect(
                url_for("register")
            )


        if role not in [
            "job_seeker",
            "employer"
        ]:

            flash(
                "Please select a valid role.",
                "danger"
            )

            return redirect(
                url_for("register")
            )


        password_hash = generate_password_hash(
            password
        )


        conn = get_db_connection()

        cursor = conn.cursor()


        try:

            cursor.execute(
                """
                INSERT INTO users
                (
                    full_name,
                    email,
                    password,
                    role
                )

                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,

                (
                    full_name,
                    email,
                    password_hash,
                    role
                )
            )


            conn.commit()


            flash(
                "Registration successful. Please login.",
                "success"
            )


            return redirect(
                url_for("login")
            )


        except mysql.connector.IntegrityError:

            conn.rollback()


            flash(
                "Email already exists.",
                "danger"
            )


        finally:

            cursor.close()

            conn.close()


    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )


        conn = get_db_connection()

        cursor = conn.cursor(
            dictionary=True
        )


        cursor.execute(
            """
            SELECT *

            FROM users

            WHERE email = %s
            """,

            (
                email,
            )
        )


        user = cursor.fetchone()


        cursor.close()

        conn.close()


        if user:

            if check_password_hash(
                user["password"],
                password
            ):

                session.clear()


                session["user_id"] = (
                    user["id"]
                )

                session["user_name"] = (
                    user["full_name"]
                )

                session["email"] = (
                    user["email"]
                )

                session["role"] = (
                    user["role"]
                )


                flash(
                    "Login successful.",
                    "success"
                )


                if user["role"] == "admin":

                    return redirect(
                        url_for(
                            "admin_dashboard"
                        )
                    )


                if user["role"] == "employer":

                    return redirect(
                        url_for(
                            "employer_dashboard"
                        )
                    )


                return redirect(
                    url_for(
                        "dashboard"
                    )
                )


        flash(
            "Invalid email or password.",
            "danger"
        )


    return render_template(
        "login.html"
    )


# =========================================================
# FORGOT PASSWORD
# =========================================================

@app.route(
    "/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()


        conn = get_db_connection()

        cursor = conn.cursor(
            dictionary=True
        )


        cursor.execute(
            """
            SELECT
                id,
                full_name,
                email

            FROM users

            WHERE email = %s
            """,

            (
                email,
            )
        )


        user = cursor.fetchone()


        if not user:

            cursor.close()

            conn.close()


            flash(
                "No account found with this email.",
                "danger"
            )


            return redirect(
                url_for(
                    "forgot_password"
                )
            )


        otp = str(
            random.randint(
                100000,
                999999
            )
        )


        expires_at = (
            datetime.now()
            +
            timedelta(
                minutes=10
            )
        )


        cursor.execute(
            """
            DELETE FROM password_resets

            WHERE user_id = %s
            """,

            (
                user["id"],
            )
        )


        cursor.execute(
            """
            INSERT INTO password_resets
            (
                user_id,
                otp,
                expires_at
            )

            VALUES
            (
                %s,
                %s,
                %s
            )
            """,

            (
                user["id"],
                otp,
                expires_at
            )
        )


        conn.commit()


        cursor.close()

        conn.close()


        message = f"""

Hello {user["full_name"]},

Your JobPortal password reset OTP is:

{otp}

This OTP is valid for 10 minutes.

Regards,
JobPortal Team

"""


        email_sent = send_email(
            user["email"],
            "JobPortal Password Reset OTP",
            message
        )


        if email_sent:

            session["reset_user_id"] = (
                user["id"]
            )

            session["reset_email"] = (
                user["email"]
            )


            flash(
                "OTP sent to your email.",
                "success"
            )


            return redirect(
                url_for(
                    "verify_otp"
                )
            )


        flash(
            "Unable to send OTP email. Check email configuration.",
            "danger"
        )


    return render_template(
        "forgot_password.html"
    )


# =========================================================
# VERIFY OTP
# =========================================================

@app.route(
    "/verify-otp",
    methods=["GET", "POST"]
)
def verify_otp():

    if "reset_user_id" not in session:

        return redirect(
            url_for(
                "forgot_password"
            )
        )


    if request.method == "POST":

        otp = request.form.get(
            "otp",
            ""
        ).strip()


        if (
            len(otp) != 6
            or
            not otp.isdigit()
        ):

            flash(
                "Please enter a valid 6-digit OTP.",
                "danger"
            )

            return redirect(
                url_for(
                    "verify_otp"
                )
            )


        conn = get_db_connection()

        cursor = conn.cursor(
            dictionary=True
        )


        cursor.execute(
            """
            SELECT *

            FROM password_resets

            WHERE user_id = %s

            AND otp = %s

            ORDER BY id DESC

            LIMIT 1
            """,

            (
                session["reset_user_id"],
                otp
            )
        )


        reset_data = cursor.fetchone()


        cursor.close()

        conn.close()


        if not reset_data:

            flash(
                "Invalid OTP.",
                "danger"
            )

            return redirect(
                url_for(
                    "verify_otp"
                )
            )


        if datetime.now() > reset_data[
            "expires_at"
        ]:

            flash(
                "OTP has expired.",
                "danger"
            )

            return redirect(
                url_for(
                    "forgot_password"
                )
            )


        session["otp_verified"] = True


        return redirect(
            url_for(
                "reset_password"
            )
        )


    return render_template(
        "verify_otp.html"
    )


# =========================================================
# RESET PASSWORD
# =========================================================

@app.route(
    "/reset-password",
    methods=["GET", "POST"]
)
def reset_password():

    if (
        "reset_user_id" not in session
        or
        not session.get(
            "otp_verified"
        )
    ):

        return redirect(
            url_for(
                "forgot_password"
            )
        )


    if request.method == "POST":

        new_password = request.form.get(
            "new_password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )


        if len(new_password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "danger"
            )

            return redirect(
                url_for(
                    "reset_password"
                )
            )


        if new_password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return redirect(
                url_for(
                    "reset_password"
                )
            )


        password_hash = generate_password_hash(
            new_password
        )


        conn = get_db_connection()

        cursor = conn.cursor()


        cursor.execute(
            """
            UPDATE users

            SET password = %s

            WHERE id = %s
            """,

            (
                password_hash,
                session["reset_user_id"]
            )
        )


        cursor.execute(
            """
            DELETE FROM password_resets

            WHERE user_id = %s
            """,

            (
                session["reset_user_id"],
            )
        )


        conn.commit()


        cursor.close()

        conn.close()


        session.pop(
            "reset_user_id",
            None
        )

        session.pop(
            "reset_email",
            None
        )

        session.pop(
            "otp_verified",
            None
        )


        flash(
            "Password reset successfully. Please login.",
            "success"
        )


        return redirect(
            url_for("login")
        )


    return render_template(
        "reset_password.html"
    )


# =========================================================
# CHANGE PASSWORD
# =========================================================

@app.route(
    "/change-password",
    methods=["GET", "POST"]
)
def change_password():

    if not is_logged_in():

        return redirect(
            url_for("login")
        )


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


        conn = get_db_connection()

        cursor = conn.cursor(
            dictionary=True
        )


        cursor.execute(
            """
            SELECT password

            FROM users

            WHERE id = %s
            """,

            (
                session["user_id"],
            )
        )


        user = cursor.fetchone()


        if (
            not user
            or
            not check_password_hash(
                user["password"],
                current_password
            )
        ):

            cursor.close()

            conn.close()


            flash(
                "Current password is incorrect.",
                "danger"
            )


            return redirect(
                url_for(
                    "change_password"
                )
            )


        if len(new_password) < 6:

            cursor.close()

            conn.close()


            flash(
                "New password must contain at least 6 characters.",
                "danger"
            )


            return redirect(
                url_for(
                    "change_password"
                )
            )


        if new_password != confirm_password:

            cursor.close()

            conn.close()


            flash(
                "Passwords do not match.",
                "danger"
            )


            return redirect(
                url_for(
                    "change_password"
                )
            )


        password_hash = generate_password_hash(
            new_password
        )


        cursor.execute(
            """
            UPDATE users

            SET password = %s

            WHERE id = %s
            """,

            (
                password_hash,
                session["user_id"]
            )
        )


        conn.commit()


        cursor.close()

        conn.close()


        flash(
            "Password changed successfully.",
            "success"
        )


        return redirect(
            url_for(
                "change_password"
            )
        )


    return render_template(
        "change_password.html"
    )


# =========================================================
# JOB SEEKER DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if not is_role("job_seeker"):

        return redirect(
            url_for("login")
        )


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    cursor.execute(
        """
        SELECT COUNT(*) AS total

        FROM applications

        WHERE user_id = %s
        """,

        (
            session["user_id"],
        )
    )


    applications_count = (
        cursor.fetchone()["total"]
    )


    cursor.execute(
        """
        SELECT COUNT(*) AS total

        FROM saved_jobs

        WHERE user_id = %s
        """,

        (
            session["user_id"],
        )
    )


    saved_count = (
        cursor.fetchone()["total"]
    )


    cursor.execute(
        """
        SELECT COUNT(*) AS total

        FROM jobs
        """
    )


    total_jobs = (
        cursor.fetchone()["total"]
    )


    cursor.close()

    conn.close()


    return render_template(
        "dashboard.html",

        applications_count=applications_count,

        saved_count=saved_count,

        total_jobs=total_jobs
    )


# =========================================================
# JOB DETAILS
# =========================================================

@app.route(
    "/job/<int:job_id>"
)
def job_details(job_id):

    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    cursor.execute(
        """
        SELECT

            jobs.*,

            users.full_name AS employer_name,

            users.email AS employer_email

        FROM jobs

        JOIN users

            ON jobs.employer_id =
               users.id

        WHERE jobs.id = %s
        """,

        (
            job_id,
        )
    )


    job = cursor.fetchone()


    if not job:

        cursor.close()

        conn.close()

        abort(404)


    already_applied = False

    is_saved = False


    if is_role("job_seeker"):

        cursor.execute(
            """
            SELECT id

            FROM applications

            WHERE job_id = %s

            AND user_id = %s
            """,

            (
                job_id,
                session["user_id"]
            )
        )


        already_applied = (
            cursor.fetchone()
            is not None
        )


        cursor.execute(
            """
            SELECT id

            FROM saved_jobs

            WHERE job_id = %s

            AND user_id = %s
            """,

            (
                job_id,
                session["user_id"]
            )
        )


        is_saved = (
            cursor.fetchone()
            is not None
        )


    cursor.close()

    conn.close()


    return render_template(
        "job_details.html",

        job=job,

        already_applied=already_applied,

        is_saved=is_saved
    )


# =========================================================
# APPLY JOB
# =========================================================

@app.route(
    "/apply/<int:job_id>",
    methods=["POST"]
)
def apply_job(job_id):

    if not is_role("job_seeker"):

        return redirect(
            url_for("login")
        )


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    cursor.execute(
        """
        SELECT *

        FROM jobs

        WHERE id = %s
        """,

        (
            job_id,
        )
    )


    job = cursor.fetchone()


    if not job:

        cursor.close()

        conn.close()

        abort(404)


    cursor.execute(
        """
        SELECT id

        FROM applications

        WHERE job_id = %s

        AND user_id = %s
        """,

        (
            job_id,
            session["user_id"]
        )
    )


    existing = cursor.fetchone()


    if existing:

        cursor.close()

        conn.close()


        flash(
            "You have already applied for this job.",
            "warning"
        )


        return redirect(
            url_for(
                "job_details",
                job_id=job_id
            )
        )


    cursor.execute(
        """
        INSERT INTO applications
        (
            job_id,
            user_id,
            status
        )

        VALUES
        (
            %s,
            %s,
            'Applied'
        )
        """,

        (
            job_id,
            session["user_id"]
        )
    )


    conn.commit()


    cursor.execute(
        """
        SELECT

            email,
            full_name

        FROM users

        WHERE id = %s
        """,

        (
            session["user_id"],
        )
    )


    applicant = cursor.fetchone()


    cursor.close()

    conn.close()


    # Send confirmation email

    email_message = f"""

Hello {applicant["full_name"]},

Your application has been successfully submitted.

Job:
{job["title"]}

Company:
{job["company"]}

Status:
Applied

Thank you for using JobPortal.

Regards,
JobPortal Team

"""


    send_email(
        applicant["email"],
        "Job Application Confirmation",
        email_message
    )


    flash(
        "Application submitted successfully.",
        "success"
    )


    # Directly go to applications.
    # No application_success.html required.

    return redirect(
        url_for(
            "applications"
        )
    )


# =========================================================
# MY APPLICATIONS
# =========================================================

@app.route(
    "/applications"
)
def applications():

    if not is_role("job_seeker"):

        return redirect(
            url_for("login")
        )


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    cursor.execute(
        """
        SELECT

            applications.id,

            applications.job_id,

            applications.status,

            applications.applied_at,

            jobs.title,

            jobs.company,

            jobs.location,

            jobs.job_type,

            jobs.experience,

            jobs.salary

        FROM applications

        JOIN jobs

            ON applications.job_id =
               jobs.id

        WHERE applications.user_id = %s

        ORDER BY
            applications.applied_at DESC
        """,

        (
            session["user_id"],
        )
    )


    application_list = (
        cursor.fetchall()
    )


    cursor.close()

    conn.close()


    return render_template(
        "applications.html",

        applications=application_list
    )


# =========================================================
# SAVE JOB
# =========================================================

@app.route(
    "/save-job/<int:job_id>",
    methods=["POST"]
)
def save_job(job_id):

    if not is_role("job_seeker"):

        return redirect(
            url_for("login")
        )


    conn = get_db_connection()

    cursor = conn.cursor()


    try:

        cursor.execute(
            """
            INSERT INTO saved_jobs
            (
                user_id,
                job_id
            )

            VALUES
            (
                %s,
                %s
            )
            """,

            (
                session["user_id"],
                job_id
            )
        )


        conn.commit()


        flash(
            "Job saved successfully.",
            "success"
        )


    except mysql.connector.IntegrityError:

        conn.rollback()


        flash(
            "Job is already saved.",
            "warning"
        )


    finally:

        cursor.close()

        conn.close()


    return redirect(
        url_for(
            "job_details",
            job_id=job_id
        )
    )


# =========================================================
# REMOVE SAVED JOB
# =========================================================

@app.route(
    "/remove-saved-job/<int:job_id>",
    methods=["POST"]
)
def remove_saved_job(job_id):

    if not is_role("job_seeker"):

        return redirect(
            url_for("login")
        )


    conn = get_db_connection()

    cursor = conn.cursor()


    cursor.execute(
        """
        DELETE FROM saved_jobs

        WHERE user_id = %s

        AND job_id = %s
        """,

        (
            session["user_id"],
            job_id
        )
    )


    conn.commit()


    cursor.close()

    conn.close()


    flash(
        "Job removed from saved jobs.",
        "success"
    )


    return redirect(
        url_for(
            "job_details",
            job_id=job_id
        )
    )


# =========================================================
# SAVED JOBS
# =========================================================

@app.route(
    "/saved-jobs"
)
def saved_jobs():

    if not is_role("job_seeker"):

        return redirect(
            url_for("login")
        )


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    cursor.execute(
        """
        SELECT

            jobs.*,

            saved_jobs.saved_at

        FROM saved_jobs

        JOIN jobs

            ON saved_jobs.job_id =
               jobs.id

        WHERE saved_jobs.user_id = %s

        ORDER BY saved_jobs.saved_at DESC
        """,

        (
            session["user_id"],
        )
    )


    jobs = cursor.fetchall()


    cursor.close()

    conn.close()


    return render_template(
        "saved_jobs.html",

        jobs=jobs
    )


# =========================================================
# RECOMMENDED JOBS
# =========================================================

@app.route(
    "/recommended-jobs"
)
def recommended_jobs():

    if not is_role("job_seeker"):

        return redirect(
            url_for("login")
        )


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    cursor.execute(
        """
        SELECT skills

        FROM profiles

        WHERE user_id = %s
        """,

        (
            session["user_id"],
        )
    )


    profile_data = cursor.fetchone()


    skills = ""


    if profile_data:

        skills = (
            profile_data["skills"]
            or
            ""
        )


    cursor.execute(
        """
        SELECT *

        FROM jobs

        ORDER BY created_at DESC
        """
    )


    all_jobs = cursor.fetchall()


    recommended = []


    if skills:

        skill_list = [

            skill.strip().lower()

            for skill in skills.split(",")

            if skill.strip()

        ]


        for job in all_jobs:

            text = (

                str(
                    job.get(
                        "title",
                        ""
                    )
                )

                +

                " "

                +

                str(
                    job.get(
                        "description",
                        ""
                    )
                )

            ).lower()


            score = 0


            for skill in skill_list:

                if skill in text:

                    score += 1


            if score > 0:

                job["match_score"] = score

                recommended.append(
                    job
                )


        recommended.sort(
            key=lambda item:
            item["match_score"],
            reverse=True
        )


    else:

        recommended = all_jobs[:20]


    cursor.close()

    conn.close()


    return render_template(
        "recommended_jobs.html",

        jobs=recommended,

        skills=skills
    )


# =========================================================
# PROFILE
# =========================================================

@app.route(
    "/profile",
    methods=["GET", "POST"]
)
def profile():

    if not is_role("job_seeker"):

        return redirect(
            url_for("login")
        )


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    if request.method == "POST":

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        skills = request.form.get(
            "skills",
            ""
        ).strip()

        education = request.form.get(
            "education",
            ""
        ).strip()

        resume = request.files.get(
            "resume"
        )


        resume_filename = None


        if resume and resume.filename:

            if not allowed_file(
                resume.filename
            ):

                cursor.close()

                conn.close()


                flash(
                    "Only PDF, DOC and DOCX files are allowed.",
                    "danger"
                )


                return redirect(
                    url_for("profile")
                )


            resume.seek(
                0,
                os.SEEK_END
            )


            file_size = resume.tell()


            resume.seek(0)


            if file_size > MAX_FILE_SIZE:

                cursor.close()

                conn.close()


                flash(
                    "Resume size must be 5 MB or less.",
                    "danger"
                )


                return redirect(
                    url_for("profile")
                )


            filename = secure_filename(
                resume.filename
            )


            extension = os.path.splitext(
                filename
            )[1].lower()


            resume_filename = (
                f"user_"
                f"{session['user_id']}_"
                f"{int(datetime.now().timestamp())}"
                f"{extension}"
            )


            resume_path = os.path.join(
                UPLOAD_FOLDER,
                resume_filename
            )


            resume.save(
                resume_path
            )


        cursor.execute(
            """
            SELECT *

            FROM profiles

            WHERE user_id = %s
            """,

            (
                session["user_id"],
            )
        )


        existing = cursor.fetchone()


        if existing:

            if resume_filename:

                cursor.execute(
                    """
                    UPDATE profiles

                    SET

                        phone = %s,

                        skills = %s,

                        education = %s,

                        resume = %s

                    WHERE user_id = %s
                    """,

                    (
                        phone,
                        skills,
                        education,
                        resume_filename,
                        session["user_id"]
                    )
                )

            else:

                cursor.execute(
                    """
                    UPDATE profiles

                    SET

                        phone = %s,

                        skills = %s,

                        education = %s

                    WHERE user_id = %s
                    """,

                    (
                        phone,
                        skills,
                        education,
                        session["user_id"]
                    )
                )

        else:

            cursor.execute(
                """
                INSERT INTO profiles
                (
                    user_id,
                    phone,
                    skills,
                    education,
                    resume
                )

                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,

                (
                    session["user_id"],
                    phone,
                    skills,
                    education,
                    resume_filename
                )
            )


        conn.commit()


        flash(
            "Profile updated successfully.",
            "success"
        )


    cursor.execute(
        """
        SELECT *

        FROM profiles

        WHERE user_id = %s
        """,

        (
            session["user_id"],
        )
    )


    user_profile = cursor.fetchone()


    cursor.execute(
        """
        SELECT

            id,
            full_name,
            email,
            role

        FROM users

        WHERE id = %s
        """,

        (
            session["user_id"],
        )
    )


    user = cursor.fetchone()


    cursor.close()

    conn.close()


    return render_template(
        "profile.html",

        profile=user_profile,

        user=user
    )


# =========================================================
# VIEW RESUME
# =========================================================

@app.route(
    "/resume/<int:user_id>"
)
def view_resume(user_id):

    if not is_logged_in():

        return redirect(
            url_for("login")
        )


    current_user_id = (
        session["user_id"]
    )

    current_role = (
        session.get("role")
    )


    allowed = False


    if current_user_id == user_id:

        allowed = True


    elif current_role == "admin":

        allowed = True


    elif current_role == "employer":

        conn = get_db_connection()

        cursor = conn.cursor()


        cursor.execute(
            """
            SELECT applications.id

            FROM applications

            JOIN jobs

                ON applications.job_id =
                   jobs.id

            WHERE applications.user_id = %s

            AND jobs.employer_id = %s

            LIMIT 1
            """,

            (
                user_id,
                current_user_id
            )
        )


        if cursor.fetchone():

            allowed = True


        cursor.close()

        conn.close()


    if not allowed:

        abort(403)


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    cursor.execute(
        """
        SELECT resume

        FROM profiles

        WHERE user_id = %s
        """,

        (
            user_id,
        )
    )


    profile_data = cursor.fetchone()


    cursor.close()

    conn.close()


    if (
        not profile_data
        or
        not profile_data["resume"]
    ):

        abort(404)


    return send_from_directory(
        UPLOAD_FOLDER,
        profile_data["resume"],
        as_attachment=False
    )


# =========================================================
# EMPLOYER DASHBOARD
# =========================================================

@app.route(
    "/employer"
)
def employer_dashboard():

    if not is_role("employer"):

        return redirect(
            url_for("login")
        )


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    cursor.execute(
        """
        SELECT COUNT(*) AS total

        FROM jobs

        WHERE employer_id = %s
        """,

        (
            session["user_id"],
        )
    )


    total_jobs = (
        cursor.fetchone()["total"]
    )


    cursor.execute(
        """
        SELECT COUNT(*) AS total

        FROM applications

        JOIN jobs

            ON applications.job_id =
               jobs.id

        WHERE jobs.employer_id = %s
        """,

        (
            session["user_id"],
        )
    )


    total_applications = (
        cursor.fetchone()["total"]
    )


    cursor.execute(
        """
        SELECT COUNT(*) AS total

        FROM applications

        JOIN jobs

            ON applications.job_id =
               jobs.id

        WHERE jobs.employer_id = %s

        AND applications.status =
            'Shortlisted'
        """,

        (
            session["user_id"],
        )
    )


    shortlisted = (
        cursor.fetchone()["total"]
    )


    cursor.close()

    conn.close()


    return render_template(
        "employer.html",

        total_jobs=total_jobs,

        total_applications=total_applications,

        shortlisted=shortlisted
    )


# =========================================================
# POST JOB
# =========================================================

@app.route(
    "/employer/post-job",
    methods=["GET", "POST"]
)
def post_job():

    if not is_role("employer"):

        return redirect(
            url_for("login")
        )


    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        company = request.form.get(
            "company",
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

        salary = request.form.get(
            "salary",
            ""
        ).strip()

        min_salary = request.form.get(
            "min_salary",
            0
        )

        max_salary = request.form.get(
            "max_salary",
            0
        )

        job_type = request.form.get(
            "job_type",
            "Full Time"
        ).strip()

        experience = request.form.get(
            "experience",
            "Fresher"
        ).strip()


        if not title:

            flash(
                "Job title is required.",
                "danger"
            )

            return redirect(
                url_for("post_job")
            )


        if not company:

            flash(
                "Company name is required.",
                "danger"
            )

            return redirect(
                url_for("post_job")
            )


        if not location:

            flash(
                "Location is required.",
                "danger"
            )

            return redirect(
                url_for("post_job")
            )


        if not description:

            flash(
                "Job description is required.",
                "danger"
            )

            return redirect(
                url_for("post_job")
            )


        conn = get_db_connection()

        cursor = conn.cursor()


        cursor.execute(
            """
            INSERT INTO jobs
            (
                title,
                company,
                location,
                description,
                salary,
                employer_id,
                job_type,
                experience,
                min_salary,
                max_salary
            )

            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,

            (
                title,
                company,
                location,
                description,
                salary,
                session["user_id"],
                job_type,
                experience,
                min_salary,
                max_salary
            )
        )


        conn.commit()


        cursor.close()

        conn.close()


        flash(
            "Job posted successfully.",
            "success"
        )


        return redirect(
            url_for("my_jobs")
        )


    return render_template(
        "post_job.html"
    )


# =========================================================
# EMPLOYER APPLICATIONS
# =========================================================

@app.route(
    "/employer/applications"
)
def employer_applications():

    if not is_role("employer"):

        return redirect(
            url_for("login")
        )


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    cursor.execute(
        """
        SELECT

            applications.id,

            applications.job_id,

            applications.user_id,

            applications.status,

            applications.applied_at,

            jobs.title,

            jobs.company,

            jobs.location,

            jobs.job_type,

            jobs.experience,

            jobs.salary,

            users.full_name,

            users.email,

            profiles.phone,

            profiles.skills,

            profiles.education,

            profiles.resume

        FROM applications

        JOIN jobs

            ON applications.job_id =
               jobs.id

        JOIN users

            ON applications.user_id =
               users.id

        LEFT JOIN profiles

            ON applications.user_id =
               profiles.user_id

        WHERE jobs.employer_id = %s

        ORDER BY
            applications.applied_at DESC
        """,

        (
            session["user_id"],
        )
    )


    application_list = (
        cursor.fetchall()
    )


    cursor.close()

    conn.close()


    return render_template(
        "employer_applications.html",

        applications=application_list
    )


# =========================================================
# UPDATE APPLICATION STATUS
# =========================================================

@app.route(
    "/employer/application/<int:application_id>/status",
    methods=["POST"]
)
def update_application_status(
    application_id
):

    if not is_role("employer"):

        return redirect(
            url_for("login")
        )


    status = request.form.get(
        "status",
        ""
    ).strip()


    allowed_statuses = [

        "Applied",
        "Under Review",
        "Shortlisted",
        "Interview",
        "Selected",
        "Rejected"

    ]


    if status not in allowed_statuses:

        flash(
            "Invalid application status.",
            "danger"
        )

        return redirect(
            url_for(
                "employer_applications"
            )
        )


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    cursor.execute(
        """
        SELECT

            applications.user_id,

            jobs.title,

            jobs.company,

            users.email,

            users.full_name

        FROM applications

        JOIN jobs

            ON applications.job_id =
               jobs.id

        JOIN users

            ON applications.user_id =
               users.id

        WHERE applications.id = %s

        AND jobs.employer_id = %s
        """,

        (
            application_id,
            session["user_id"]
        )
    )


    application = cursor.fetchone()


    if not application:

        cursor.close()

        conn.close()

        abort(404)


    cursor.execute(
        """
        UPDATE applications

        SET status = %s

        WHERE id = %s
        """,

        (
            status,
            application_id
        )
    )


    conn.commit()


    cursor.close()

    conn.close()


    email_message = f"""

Hello {application["full_name"]},

Your application status has been updated.

Job:
{application["title"]}

Company:
{application["company"]}

New Status:
{status}

Please login to JobPortal to view your application.

Regards,
JobPortal Team

"""


    send_email(
        application["email"],
        "Application Status Updated",
        email_message
    )


    flash(
        "Application status updated.",
        "success"
    )


    return redirect(
        url_for(
            "employer_applications"
        )
    )


# =========================================================
# MY JOBS
# =========================================================

@app.route(
    "/employer/my-jobs"
)
def my_jobs():

    if not is_role("employer"):

        return redirect(
            url_for("login")
        )


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    cursor.execute(
        """
        SELECT

            jobs.*,

            COUNT(
                applications.id
            ) AS applicant_count

        FROM jobs

        LEFT JOIN applications

            ON jobs.id =
               applications.job_id

        WHERE jobs.employer_id = %s

        GROUP BY jobs.id

        ORDER BY
            jobs.created_at DESC
        """,

        (
            session["user_id"],
        )
    )


    jobs = cursor.fetchall()


    cursor.close()

    conn.close()


    return render_template(
        "my_jobs.html",

        jobs=jobs
    )


# =========================================================
# EDIT JOB
# =========================================================

@app.route(
    "/employer/edit-job/<int:job_id>",
    methods=["GET", "POST"]
)
def edit_job(job_id):

    if not is_role("employer"):

        return redirect(
            url_for("login")
        )


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    cursor.execute(
        """
        SELECT *

        FROM jobs

        WHERE id = %s

        AND employer_id = %s
        """,

        (
            job_id,
            session["user_id"]
        )
    )


    job = cursor.fetchone()


    if not job:

        cursor.close()

        conn.close()

        abort(404)


    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        company = request.form.get(
            "company",
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

        salary = request.form.get(
            "salary",
            ""
        ).strip()

        min_salary = request.form.get(
            "min_salary",
            0
        )

        max_salary = request.form.get(
            "max_salary",
            0
        )

        job_type = request.form.get(
            "job_type",
            "Full Time"
        ).strip()

        experience = request.form.get(
            "experience",
            "Fresher"
        ).strip()


        cursor.execute(
            """
            UPDATE jobs

            SET

                title = %s,

                company = %s,

                location = %s,

                description = %s,

                salary = %s,

                min_salary = %s,

                max_salary = %s,

                job_type = %s,

                experience = %s

            WHERE id = %s

            AND employer_id = %s
            """,

            (
                title,
                company,
                location,
                description,
                salary,
                min_salary,
                max_salary,
                job_type,
                experience,
                job_id,
                session["user_id"]
            )
        )


        conn.commit()


        cursor.close()

        conn.close()


        flash(
            "Job updated successfully.",
            "success"
        )


        return redirect(
            url_for("my_jobs")
        )


    cursor.close()

    conn.close()


    return render_template(
        "edit_job.html",

        job=job
    )


# =========================================================
# EMPLOYER DELETE JOB
# =========================================================

@app.route(
    "/employer/delete-job/<int:job_id>"
)
def employer_delete_job(job_id):

    if not is_role("employer"):

        return redirect(
            url_for("login")
        )


    conn = get_db_connection()

    cursor = conn.cursor()


    try:

        cursor.execute(
            """
            DELETE FROM applications

            WHERE job_id = %s
            """,

            (
                job_id,
            )
        )


        cursor.execute(
            """
            DELETE FROM saved_jobs

            WHERE job_id = %s
            """,

            (
                job_id,
            )
        )


        cursor.execute(
            """
            DELETE FROM jobs

            WHERE id = %s

            AND employer_id = %s
            """,

            (
                job_id,
                session["user_id"]
            )
        )


        conn.commit()


        flash(
            "Job deleted successfully.",
            "success"
        )


    except Exception as error:

        conn.rollback()

        print(
            "EMPLOYER DELETE JOB ERROR:",
            error
        )


        flash(
            "Unable to delete job.",
            "danger"
        )


    finally:

        cursor.close()

        conn.close()


    return redirect(
        url_for("my_jobs")
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route(
    "/admin"
)
def admin_dashboard():

    if not is_role("admin"):

        return redirect(
            url_for("login")
        )


    conn = get_db_connection()

    cursor = conn.cursor(
        dictionary=True
    )


    cursor.execute(
        """
        SELECT

            id,

            full_name,

            email,

            role,

            created_at

        FROM users

        ORDER BY id DESC
        """
    )


    users = cursor.fetchall()


    cursor.execute(
        """
        SELECT

            id,

            title,

            company,

            location,

            salary,

            job_type,

            experience,

            created_at

        FROM jobs

        ORDER BY id DESC
        """
    )


    jobs = cursor.fetchall()


    cursor.close()

    conn.close()


    return render_template(
        "admin.html",

        users=users,

        jobs=jobs
    )


# =========================================================
# ADMIN DELETE USER
# =========================================================

@app.route(
    "/admin/delete-user/<int:user_id>"
)
def admin_delete_user(user_id):

    if not is_role("admin"):

        return redirect(
            url_for("login")
        )


    if user_id == session.get(
        "user_id"
    ):

        flash(
            "You cannot delete your own admin account.",
            "danger"
        )


        return redirect(
            url_for("admin_dashboard")
        )


    conn = get_db_connection()

    cursor = conn.cursor()


    try:

        # User applications

        cursor.execute(
            """
            DELETE FROM applications

            WHERE user_id = %s
            """,

            (
                user_id,
            )
        )


        # User saved jobs

        cursor.execute(
            """
            DELETE FROM saved_jobs

            WHERE user_id = %s
            """,

            (
                user_id,
            )
        )


        # Password reset records

        cursor.execute(
            """
            DELETE FROM password_resets

            WHERE user_id = %s
            """,

            (
                user_id,
            )
        )


        # Profile

        cursor.execute(
            """
            DELETE FROM profiles

            WHERE user_id = %s
            """,

            (
                user_id,
            )
        )


        # Applications for employer jobs

        cursor.execute(
            """
            DELETE applications

            FROM applications

            INNER JOIN jobs

                ON applications.job_id =
                   jobs.id

            WHERE jobs.employer_id = %s
            """,

            (
                user_id,
            )
        )


        # Saved jobs for employer jobs

        cursor.execute(
            """
            DELETE saved_jobs

            FROM saved_jobs

            INNER JOIN jobs

                ON saved_jobs.job_id =
                   jobs.id

            WHERE jobs.employer_id = %s
            """,

            (
                user_id,
            )
        )


        # Employer jobs

        cursor.execute(
            """
            DELETE FROM jobs

            WHERE employer_id = %s
            """,

            (
                user_id,
            )
        )


        # User

        cursor.execute(
            """
            DELETE FROM users

            WHERE id = %s
            """,

            (
                user_id,
            )
        )


        conn.commit()


        flash(
            "User deleted successfully.",
            "success"
        )


    except Exception as error:

        conn.rollback()

        print(
            "ADMIN DELETE USER ERROR:",
            error
        )


        flash(
            "Unable to delete user.",
            "danger"
        )


    finally:

        cursor.close()

        conn.close()


    return redirect(
        url_for("admin_dashboard")
    )


# =========================================================
# ADMIN DELETE JOB
# =========================================================

@app.route(
    "/admin/delete-job/<int:job_id>"
)
def admin_delete_job(job_id):

    if not is_role("admin"):

        return redirect(
            url_for("login")
        )


    conn = get_db_connection()

    cursor = conn.cursor()


    try:

        cursor.execute(
            """
            DELETE FROM applications

            WHERE job_id = %s
            """,

            (
                job_id,
            )
        )


        cursor.execute(
            """
            DELETE FROM saved_jobs

            WHERE job_id = %s
            """,

            (
                job_id,
            )
        )


        cursor.execute(
            """
            DELETE FROM jobs

            WHERE id = %s
            """,

            (
                job_id,
            )
        )


        conn.commit()


        flash(
            "Job deleted successfully.",
            "success"
        )


    except Exception as error:

        conn.rollback()

        print(
            "ADMIN DELETE JOB ERROR:",
            error
        )


        flash(
            "Unable to delete job.",
            "danger"
        )


    finally:

        cursor.close()

        conn.close()


    return redirect(
        url_for("admin_dashboard")
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route(
    "/logout"
)
def logout():

    session.clear()


    flash(
        "You have been logged out.",
        "success"
    )


    return redirect(
        url_for("login")
    )


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "404.html"
    ), 404


@app.errorhandler(403)
def access_denied(error):

    return render_template(
        "404.html"
    ), 403


@app.errorhandler(413)
def file_too_large(error):

    flash(
        "File is too large. Maximum size is 5 MB.",
        "danger"
    )


    return redirect(
        url_for("profile")
    )


@app.errorhandler(500)
def internal_server_error(error):

    return render_template(
        "500.html"
    ), 500


# =========================================================
# COMPATIBILITY ENDPOINTS
# =========================================================
#
# Some older HTML files may still contain:
#
#     url_for('home')
#
# or:
#
#     url_for('employer')
#
# The following aliases prevent BuildError.
# =========================================================

# =========================================================
# COMPATIBILITY ENDPOINTS
# =========================================================

# Old template -> Homepage
app.add_url_rule(
    "/",
    endpoint="home",
    view_func=index
)

# Old template -> Employer Dashboard
app.add_url_rule(
    "/employer",
    endpoint="employer",
    view_func=employer_dashboard
)

# Old template -> Delete Employer Job
app.add_url_rule(
    "/employer/delete-job/<int:job_id>",
    endpoint="delete_job",
    view_func=employer_delete_job
)


# =========================================================
# START APPLICATION
# =========================================================
# =========================================================
# COMPATIBILITY ENDPOINTS FOR OLD TEMPLATES
# =========================================================

# Home
app.add_url_rule(
    "/",
    endpoint="home",
    view_func=index
)

# Employer dashboard
app.add_url_rule(
    "/employer",
    endpoint="employer",
    view_func=employer_dashboard
)

# Old delete_job endpoint
app.add_url_rule(
    "/employer/delete-job/<int:job_id>",
    endpoint="delete_job",
    view_func=employer_delete_job
)

# Old apply endpoint
app.add_url_rule(
    "/apply/<int:job_id>",
    endpoint="apply",
    view_func=apply_job
)

# Old job details endpoint
app.add_url_rule(
    "/job/<int:job_id>",
    endpoint="job",
    view_func=job_details
)

# Old my applications endpoint
app.add_url_rule(
    "/my-applications",
    endpoint="my_applications",
    view_func=applications
)

# Old saved jobs endpoint
app.add_url_rule(
    "/saved",
    endpoint="saved",
    view_func=saved_jobs
)

# Old remove saved job endpoint
app.add_url_rule(
    "/remove-saved/<int:job_id>",
    endpoint="remove_saved",
    view_func=remove_saved_job
)

# Old recommended jobs endpoint
app.add_url_rule(
    "/recommendations",
    endpoint="recommendations",
    view_func=recommended_jobs
)

# Old employer applications endpoint
app.add_url_rule(
    "/employer/applications",
    endpoint="applications_employer",
    view_func=employer_applications
)

# Old change application status endpoint
app.add_url_rule(
    "/employer/application/<int:application_id>/status",
    endpoint="change_status",
    view_func=update_application_status
)

# Old employer delete endpoint
app.add_url_rule(
    "/employer/delete/<int:job_id>",
    endpoint="remove_job",
    view_func=employer_delete_job
)
if __name__ == "__main__":

    app.run(
        debug=True,
        port=5000
    )