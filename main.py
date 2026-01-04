from flask import Flask, render_template, request, redirect, session, jsonify, url_for, flash
from flask_session import Session
from datetime import timedelta, datetime
from utils import *

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

# Update active orders to completed on app startup
update_active_orders_to_completed()


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
    
    # Update active orders to completed before fetching order history
    update_active_orders_to_completed()
    
    # Get order history for the logged-in user
    user_email = session.get("user_email")
    order_history = get_user_order_history(user_email) if user_email else []
    
    return render_template(
        "user_dashboard.html",
        user_name=session.get("user_name"),
        user_email=user_email,
        order_history=order_history,
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
    Validates user is logged in, validates inputs, and filters results
    based on the plane's remaining capacity for all requested passengers.
    """
    # 1. Check if user is logged in as customer or guest
    user_type = session.get("user_type")
    if user_type not in ["customer", "guest"]:
        return jsonify({"error": "You must be signed in (as guest or customer) to search flights."}), 401

    # 2. Extract form data
    origin_airport = request.form.get("origin_airport", "").strip().upper()
    destination_airport = request.form.get("destination_airport", "").strip().upper()
    departure_date = request.form.get("departure_date", "").strip()
    passengers = request.form.get("passengers", "1").strip()

    # 3. Server-side validation
    errors = []

    if not origin_airport or len(origin_airport) != 3:
        errors.append("Origin airport must be a valid 3-letter code.")

    if not destination_airport or len(destination_airport) != 3:
        errors.append("Destination airport must be a valid 3-letter code.")

    if origin_airport and destination_airport and origin_airport == destination_airport:
        errors.append("Origin and destination airports must be different.")

    if not departure_date:
        errors.append("Departure date is required.")
    else:
        try:
            date_obj = datetime.strptime(departure_date, "%Y-%m-%d")
            if date_obj.date() < datetime.now().date():
                errors.append("Departure date cannot be in the past.")
        except ValueError:
            errors.append("Invalid date format. Please use YYYY-MM-DD.")

    # 4. Handle passenger count and session storage
    try:
        passengers_int = int(passengers)
        if passengers_int < 1 or passengers_int > 9:
            errors.append("Number of passengers must be between 1 and 9.")
        else:
            # Store passenger count in session for the seat selection logic
            session['passengers'] = passengers_int
            session["search_passengers"] = passengers_int
    except ValueError:
        errors.append("Number of passengers must be a valid number.")

    if errors:
        return jsonify({"error": " ".join(errors)}), 400

    # 5. Execute search using the updated schema (direct Flight_ID in Order table)
    try:
        # Pass passengers_int to ensure the flight has enough free seats
        flights = search_flights(origin_airport, destination_airport, departure_date, passengers_int)

        # Return results to be rendered on the client side
        return jsonify({"flights": flights, "count": len(flights)})

    except Exception as e:
        # Log the internal error and return a generic user-friendly message
        print(f"Database Error: {e}")
        return jsonify({"error": "An error occurred while searching for flights. Please try again."}), 500

@app.route("/manage_reservations")
def manage_reservations():
    order_id = request.args.get('order_id')
    user_email = session.get('user_email')
    guest_email = session.get('guest_email')
    email = user_email or guest_email

    if not order_id or not email:
        flash("Please provide a valid Order ID.")
        # Redirect based on user type
        if user_email:
            return redirect(url_for('user_dashboard'))
        else:
            return redirect(url_for('guest_dashboard'))

    # Update active orders to completed before fetching ticket details
    update_active_orders_to_completed()

    # Fetch details using the updated logic from utils.py
    try:
        ticket = get_ticket_details(int(order_id), email)
    except Exception as e:
        ticket = None

    if not ticket:
        # If no ticket is found for this email, flash an alert and redirect
        error_msg = f"Order #{order_id} is not associated with your account or does not exist."
        flash(error_msg)
        # Redirect based on user type
        if user_email:
            return redirect(url_for('user_dashboard'))
        else:
            return redirect(url_for('guest_dashboard'))

    # Check user type and render appropriate template
    if user_email:
        # Customer: render manage_order.html
        # Add Passenger_Email to the ticket dict for the template
        order_data = ticket.copy()
        order_data['Passenger_Email'] = user_email
        return render_template("manage_order.html", order=order_data)
    else:
        # Guest: render guest.html (current behavior)
        return render_template("guest.html", ticket=ticket, show_manage=True)

@app.route("/cancel_order", methods=["POST"])
def cancel_order_route():
    order_id = request.form.get("order_id")
    user_type = session.get("user_type")
    email = session.get("guest_email") if user_type == "guest" else session.get("user_email")

    if order_id and email:
        # Receiving both values from the utility function
        success, message = delete_ticket(int(order_id), email)

        if success:
            # Redirect to see the updated "Cancelled" status and the new 5% price
            return redirect(url_for('manage_reservations', order_id=order_id))
        else:
            # If failed (e.g. < 36h), we can pass the message back to the page
            order_data = get_ticket_details(int(order_id), email)
            if order_data:
                # Add Passenger_Email to the order data for the template
                order_data = order_data.copy()
                order_data['Passenger_Email'] = email
            return render_template("manage_order.html", order=order_data, error_message=message)

    return "Invalid Request", 400


@app.route("/select_seat")
def select_seat():
    fid_raw = request.args.get('flight_id')
    if not fid_raw:
        return redirect('/')

    flight_id = int(fid_raw)  # המרה קריטית!
    max_seats = int(session.get('passengers', 1))
    user_type = session.get('user_type', 'guest')  # Default to guest if not set

    seats_data = get_flight_seat_map(flight_id)

    return render_template("select_seat.html",
                           seats=seats_data,
                           flight_id=flight_id,
                           max_seats=max_seats,
                           user_type=user_type)


@app.route("/booking_summary", methods=["POST"])
def booking_summary():
    """
    Summarizes the booking details.
    NOTE: We still fetch Passport/DOB from the 'Costumer' table to pre-fill the form
    for UI/UX purposes, even though we won't save this info in the 'Order' table.
    """
    selected_seats = request.form.getlist('selected_seats')
    flight_id = request.form.get('flight_id')
    max_seats = session.get('passengers', 1)

    # 1. Validation
    if not selected_seats or len(selected_seats) != int(max_seats):
        flash(f"Error: You must select exactly {max_seats} seats.")
        return redirect(url_for('select_seat', flight_id=flight_id))

    # 2. Get flight details
    flight = get_flight_by_id(int(flight_id))
    if not flight:
        flash("Error: Flight details could not be retrieved.")
        return redirect(url_for('search_flights_route'))

    # 3. Dynamic Price Calculation
    total_price = 0
    seat_details = []
    cursor = db_manager.get_cursor()
    try:
        format_strings = ','.join(['%s'] * len(selected_seats))
        query = f"SELECT ID, Type, Row_Num, Column_Letter, Seat_Type FROM class WHERE ID IN ({format_strings})"
        cursor.execute(query, tuple(selected_seats))
        seats_from_db = cursor.fetchall()

        for row in seats_from_db:
            seat_id, class_type, row_num, col_letter, seat_location = row
            price = float(flight['business_price']) if class_type.lower() == 'business' else float(flight['economy_price'])
            total_price += price
            seat_details.append({
                "id": seat_id, "type": class_type, "row": row_num,
                "letter": col_letter, "location": seat_location, "price": price
            })
    except Exception as e:
        print(f"Database Error: {e}")
        return redirect(url_for('select_seat', flight_id=flight_id))
    finally:
        cursor.close()

    # 4. PRE-FILL LOGIC: Fetch from 'Costumer' table to show on screen
    # This data is passed to the HTML but will NOT be saved to the 'Order' table later.
    user_data = None
    if session.get("user_type") == "customer":
        email = session.get("user_email")
        cursor = db_manager.get_cursor()
        try:
            cursor.execute("SELECT Passport_Num, B_Date FROM Costumer WHERE Mail = %s", (email,))
            user_data = cursor.fetchone()
        finally:
            cursor.close()

    return render_template("booking_summary.html",
                           seats=seat_details,
                           flight=flight,
                           total_price=total_price,
                           user_data=user_data)


@app.route("/finalize_booking", methods=["POST"])
def finalize_booking():
    """
    Finalizes the booking.
    Removed passport_num and b_date from the create_order_with_seats call
    to match the original database schema.
    """
    flight_id = request.form.get('flight_id')
    selected_seats = request.form.getlist('seats')
    total_price = request.form.get('total_price')

    user_type = session.get('user_type')
    customer_mail = session.get('user_email') if user_type == 'customer' else None
    guest_mail = session.get('guest_email') if user_type == 'guest' else None

    # Integrity check
    if not selected_seats or not flight_id:
        flash("Booking data is missing.")
        return redirect(url_for('home'))

    try:
        # NOTICE: We do NOT pass passport/dob here anymore.
        # We only pass the fields that exist in your original 'Order' table.
        new_order_id = create_order_with_seats(
            flight_id=int(flight_id),
            selected_seats=selected_seats,
            total_price=float(total_price),
            customer_mail=customer_mail,
            guest_mail=guest_mail
        )

        target_dashboard = 'user_dashboard' if user_type == 'customer' else 'guest_dashboard'
        return render_template("booking_success.html",
                               order_id=new_order_id,
                               target_dashboard=target_dashboard)

    except Exception as e:
        print(f"DATABASE TRANSACTION ERROR: {e}")
        flash("We could not process your booking. Please try again.")
        return redirect(url_for('home'))

@app.route('/manage_orders')
def manage_orders():
    return "Manage Orders Page - Coming Soon"

@app.route('/manage_flights')
def manage_flights():
    return "Manage Flights Page - Coming Soon"

@app.route('/view_reports')
def view_reports():
    return "Management Reports - Coming Soon"

if __name__ == "__main__":
    app.run(debug=True)