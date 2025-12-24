from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from flask_session import Session
from datetime import timedelta, datetime
from utils import (
    get_customer_by_email_and_password,
    get_manager_by_id_and_password,
    customer_email_exists,
    create_customer_with_phones,
    guest_sign_in,
    search_flights,
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


@app.route("/search_flights", methods=["POST", "GET"])
def search_flights_route():
    """
    Handle flight search requests via AJAX.
    Validates user is logged in as customer, validates inputs, and returns JSON results.
    """
    # Check if user is logged in as customer or guest
    user_type = session.get("user_type")
    if user_type not in ["customer", "guest"]:
        return jsonify({"error": "You must be signed in (as guest or customer) to search flights."}), 401
    # Extract and validate form data
    origin_airport = request.form.get("origin_airport", "").strip().upper()
    destination_airport = request.form.get("destination_airport", "").strip().upper()
    departure_date = request.form.get("departure_date", "").strip()
    passengers = request.form.get("passengers", "1").strip()

    # Python validation
    errors = []

    if not origin_airport:
        errors.append("Origin airport is required.")
    elif len(origin_airport) != 3:
        errors.append("Origin airport must be a 3-letter code.")

    if not destination_airport:
        errors.append("Destination airport is required.")
    elif len(destination_airport) != 3:
        errors.append("Destination airport must be a 3-letter code.")

    if origin_airport and destination_airport and origin_airport == destination_airport:
        errors.append("Origin and destination airports must be different.")

    if not departure_date:
        errors.append("Departure date is required.")
    else:
        try:
            # Validate date format
            date_obj = datetime.strptime(departure_date, "%Y-%m-%d")
            # Check if date is not in the past
            if date_obj.date() < datetime.now().date():
                errors.append("Departure date cannot be in the past.")
        except ValueError:
            errors.append("Invalid date format. Please use YYYY-MM-DD.")

    try:
        passengers_int = int(passengers)
        if passengers_int < 1 or passengers_int > 9:
            errors.append("Number of passengers must be between 1 and 9.")
    except ValueError:
        errors.append("Number of passengers must be a valid number.")

    if errors:
        return jsonify({"error": " ".join(errors)}), 400

    # Save passengers count (for future use, not used in search yet)
    session["search_passengers"] = passengers_int

    try:
        # Call search function
        flights = search_flights(origin_airport, destination_airport, departure_date)
        return jsonify({"flights": flights, "count": len(flights)})
    except Exception as e:
        # In a real app, log the error
        return jsonify({"error": "An error occurred while searching for flights. Please try again."}), 500


@app.route("/manage_reservations", methods=["GET"])
def manage_reservations():
    """
    Unified route to view order details.
    Converts order_id to integer to match SQL schema.
    """
    order_id_raw = request.args.get("order_id")
    user_type = session.get("user_type")

    # Get the correct email from the session based on login type
    identifier = session.get("guest_email") if user_type == "guest" else session.get("user_email")

    if not order_id_raw or not identifier:
        return redirect("/")

    try:
        from utils import get_ticket_details
        # CRITICAL: Convert to int because DB schema uses INT for Order_ID
        order_id = int(order_id_raw)

        order_details = get_ticket_details(order_id, identifier)

        if not order_details:
            # Stay on current dashboard if not found
            target = "guest.html" if user_type == "guest" else "user_dashboard.html"
            return render_template(target, error="Order not found or unauthorized for your email.")

        return render_template("manage_order.html", order=order_details)

    except (ValueError, TypeError):
        # Handles cases where order_id is not a number
        return redirect("/")


@app.route("/cancel_order", methods=["POST"])
def cancel_order_route():
    order_id = request.form.get("order_id")
    user_type = session.get("user_type")
    email = session.get("guest_email") if user_type == "guest" else session.get("user_email")

    if order_id and email:
        from utils import delete_ticket
        # Receiving both values from the utility function
        success, message = delete_ticket(int(order_id), email)

        if success:
            # Redirect to see the updated "Cancelled" status and the new 5% price
            return redirect(url_for('manage_reservations', order_id=order_id))
        else:
            # If failed (e.g. < 36h), we can pass the message back to the page
            from utils import get_ticket_details
            order_data = get_ticket_details(int(order_id), email)
            return render_template("manage_order.html", order=order_data, error_message=message)

    return "Invalid Request", 400




if __name__ == "__main__":
    app.run(debug=True)