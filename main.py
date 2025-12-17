from flask import Flask, render_template, request, redirect, session
from flask_session import Session
from datetime import timedelta
from utils import (
    get_customer_by_email_and_password,
    get_manager_by_id_and_password,
    customer_email_exists,
    create_customer_with_phones,
    guest_sign_in,
)

app = Flask(__name__)

app.config.update(
    SESSION_TYPE="filesystem",
    SESSION_FILE_DIR="sessions",
    SESSION_PERMANENT=True,
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    SESSION_REFRESH_EACH_REQUEST=True,
    SESSION_COOKIE_SECURE=True,
)
Session(app)


@app.errorhandler(404)
def invalid_route(e):
    return redirect("/")


@app.route('/', methods=['POST', 'GET'])
def home():
    if request.method == "POST":
        login_type = request.form.get("login_type")
        if login_type == "guest":
            return render_template("guest.html")
        if login_type == "login":
            return redirect("/login")
        if login_type == "signup":
            return redirect("/signup")
        return render_template("login_form.html", error="Please select an option")
    else:
         return render_template("login_form.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "GET":
        return render_template("login.html")

    # POST: handle login
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        return render_template("login.html", error="Please enter both username and password.", last_username=username)

    try:
        # If username contains '@' -> Customer (Costumer table, Mail + Password)
        if "@" in username:
            row = get_customer_by_email_and_password(username, password)
            if not row:
                return render_template(
                    "login.html",
                    error="Invalid email or password.",
                    last_username=username,
                )

            mail, first_name, last_name = row
            session.clear()
            session["user_type"] = "customer"
            session["user_email"] = mail
            session["user_name"] = f"{first_name} {last_name}"
            return redirect("/user_dashboard")

        # Otherwise -> Manager (Manager table, ID + Password)
        try:
            manager_id = int(username)
        except ValueError:
            return render_template(
                "login.html",
                error="Manager username must be a numeric employee ID.",
                last_username=username,
            )

        row = get_manager_by_id_and_password(manager_id, password)
        if not row:
            return render_template(
                "login.html",
                error="Invalid manager ID or password.",
                last_username=username,
            )

        mgr_id, first_name, last_name = row
        session.clear()
        session["user_type"] = "manager"
        session["user_id"] = mgr_id
        session["user_name"] = f"{first_name} {last_name}"
        return redirect("/admin_dashboard")
    except Exception:
        # In a real app you would log the error server-side
        return render_template(
            "login.html",
            error="An unexpected error occurred while logging in. Please try again.",
            last_username=username,
        )


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    if request.method == "POST":
        # POST: handle customer signup
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        passport_num = request.form.get("passport_num", "").strip()
        b_date = request.form.get("b_date", "").strip()
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        phones = [p.strip() for p in request.form.getlist("phones") if p.strip()]

        # Basic validation
        if not all([email, password, confirm_password, passport_num, b_date, first_name, last_name]):
            return render_template(
                "signup.html",
                error="All fields are required, including at least one phone number.",
                form_data=request.form,
            )

        if not phones:
            return render_template(
                "signup.html",
                error="Please enter at least one phone number.",
                form_data=request.form,
            )

        if "@" not in email:
            return render_template(
                "signup.html",
                error="Please enter a valid email address.",
                form_data=request.form,
            )

        if password != confirm_password:
            return render_template(
                "signup.html",
                error="Password and confirmation do not match.",
                form_data=request.form,
            )

        try:
            # Check if email already exists
            exists = customer_email_exists(email)

            if exists:
                return render_template(
                    "signup.html",
                    error="An account with this email already exists.",
                    form_data=request.form,
                )

            # Create customer and all provided phone numbers
            create_customer_with_phones(
                email=email,
                password=password,
                passport_num=passport_num,
                b_date=b_date,
                first_name=first_name,
                last_name=last_name,
                phones=phones,
            )

            session.clear()
            session["user_type"] = "customer"
            session["user_email"] = email
            session["user_name"] = f"{first_name} {last_name}"
            return redirect("/user_dashboard")
        except Exception:
            # In a real app you would log the error server-side
            return render_template(
                "signup.html",
                error="An unexpected error occurred while signing up. Please try again.",
                form_data=request.form,
            )


@app.route("/guest_sign_in", methods=["POST"])
def guest_sign_in_route():
    """
    Guest login / signup using email only.

    Flow:
    - Get email from form.
    - If invalid -> show error on guest page.
    - Call guest_sign_in(email) which:
        * checks if email exists in Guest table
        * inserts if it doesn't exist
    - Store guest info in session and redirect to guest dashboard.
    """
    email = request.form.get("email", "").strip()

    if not email or "@" not in email:
        return render_template(
            "guest.html",
            error="Please enter a valid email address.",
            last_email=email,
        )

    try:
        guest_sign_in(email)
        session.clear()
        session["user_type"] = "guest"
        session["guest_email"] = email
        return redirect("/guest_dashboard")
    except Exception:
        return render_template(
            "guest.html",
            error="An unexpected error occurred while signing in as guest. Please try again.",
            last_email=email,
        )


@app.route("/user_dashboard")
def user_dashboard():
    if session.get("user_type") != "customer":
        return redirect("/login")
    return render_template(
        "user_dashboard.html",
        user_name=session.get("user_name"),
        user_email=session.get("user_email"),
    )


@app.route("/admin_dashboard")
def admin_dashboard():
    if session.get("user_type") != "manager":
        return redirect("/login")
    return render_template(
        "admin_dashboard.html",
        user_name=session.get("user_name"),
        user_id=session.get("user_id"),
    )


@app.route("/guest_dashboard")
def guest_dashboard():
    """
    Simple guest dashboard after email-only sign-in.
    Uses the same guest.html template but passes the guest email.
    """
    if session.get("user_type") != "guest":
        return redirect("/")
    return render_template(
        "guest.html",
        guest_email=session.get("guest_email"),
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)