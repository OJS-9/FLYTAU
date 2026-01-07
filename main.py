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
    email = session.get('user_email') or session.get('guest_email')

    if not order_id or not email:
        flash("Please provide a valid Order ID.")
        return redirect(url_for('guest_dashboard'))

    # Fetch details using the updated logic from utils.py
    ticket = get_ticket_details(int(order_id), email)

    if not ticket:
        # If no ticket is found for this email, flash an alert
        flash(f"Order #{order_id} is not associated with your account.")
        return redirect(url_for('guest_dashboard'))

    # Instead of a new HTML, we return the same dashboard but with the 'ticket' data
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
            return render_template("manage_order.html", order=order_data, error_message=message)

    return "Invalid Request", 400


@app.route("/select_seat")
def select_seat():
    fid_raw = request.args.get('flight_id')
    if not fid_raw:
        return redirect('/')

    flight_id = int(fid_raw)  # המרה קריטית!
    max_seats = int(session.get('passengers', 1))

    seats_data = get_flight_seat_map(flight_id)

    return render_template("select_seat.html",
                           seats=seats_data,
                           flight_id=flight_id,
                           max_seats=max_seats)


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
    try:
        with get_db_connection() as cursor:
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

    # 4. PRE-FILL LOGIC: Fetch from 'Costumer' table to show on screen
    # This data is passed to the HTML but will NOT be saved to the 'Order' table later.
    user_data = None
    if session.get("user_type") == "customer":
        email = session.get("user_email")
        with get_db_connection() as cursor:
            cursor.execute("SELECT Passport_Num, B_Date FROM Costumer WHERE Mail = %s", (email,))
            user_data = cursor.fetchone()

    return render_template("booking_summary.html",
                           seats=seat_details,
                           flight=flight,
                           total_price=total_price,
                           user_data=user_data,
                           is_guest=(session.get("user_type") == "guest"))


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


@app.route('/manage_flights')
def manage_flights():
    return render_template('manage_flights.html')


@app.route('/manage_orders')
def manage_orders():
    return "Order Management Page - Coming Soon"

@app.route('/view_reports')
def view_reports():
    return "Management Reports - Coming Soon"

@app.route('/add_plane')
def add_plane():
    return render_template('add_plane.html')


@app.route('/add_pilot')
def add_pilot_page():
    return render_template('add_pilot.html')

@app.route('/add_steward')
def add_steward():
    return render_template('add_steward.html')

@app.route('/save_pilot', methods=['POST'])
def save_pilot_route():
    try:
        pilot_id = add_crew_member(request.form, 'pilot')
        return render_template('crew_success.html',
                               member_id=pilot_id,
                               role="Pilot",
                               name=f"{request.form.get('first_name')} {request.form.get('last_name')}",
                               has_certification=bool(request.form.get('long_flight_cer')))
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/save_steward', methods=['POST'])
def save_steward_route():
    try:
        steward_id = add_crew_member(request.form, 'steward')
        return render_template('crew_success.html',
                               member_id=steward_id,
                               role="Steward",
                               name=f"{request.form.get('first_name')} {request.form.get('last_name')}",
                               has_certification=bool(request.form.get('long_flight_cer')))
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/save_plane', methods=['POST'])
def save_plane_route():
    try:
        manufacturer = request.form.get('manufacturer')
        size = request.form.get('size')
        eco_cap = int(request.form.get('eco_cap'))
        bus_cap = int(request.form.get('bus_cap'))
        purchase_date = request.form.get('purchase_date')

        # Call the utility function
        plane_id = create_aircraft_with_seats(manufacturer, size, eco_cap, bus_cap, purchase_date)

        # Instead of redirecting to dashboard, show the summary
        return render_template('plane_success.html',
                               plane_id=plane_id,
                               manufacturer=manufacturer,
                               eco_cap=eco_cap,
                               bus_cap=bus_cap,
                               total_cap=eco_cap + bus_cap)

    except Exception as e:
        print(f"Error: {e}")
        return f"System Error: {str(e)}", 500


@app.route('/validate_route', methods=['POST'])
def validate_route():
    origin = request.form.get('origin').upper()
    dest = request.form.get('dest').upper()

    if origin == dest:
        flash("Origin and Destination cannot be the same.")
        return redirect(url_for('manage_flights'))

    path_data = get_path_info(origin, dest)

    if path_data:
        return render_template('select_date_time.html', origin=origin, dest=dest)
    else:
        return render_template('create_new_path.html', origin=origin, dest=dest)


@app.route('/save_path_and_continue', methods=['POST'])
def save_path_and_continue():
    origin = request.form.get('origin')
    dest = request.form.get('dest')
    duration = float(request.form.get('duration'))
    o_tz = int(request.form.get('origin_tz'))
    d_tz = int(request.form.get('dest_tz'))

    try:
        add_new_path(origin, dest, duration, o_tz, d_tz)
    except Exception as e:
        if "1062" in str(e):
            print(f"Path {origin}-{dest} already exists. Proceeding...")
        else:
            print(f"Database error: {e}")
            return f"Error: {str(e)}", 500

    return render_template('select_date_time.html', origin=origin, dest=dest)


@app.route('/get_available_resources', methods=['POST'])
def step_2_select_plane():
    try:
        origin = request.form.get('origin')
        dest = request.form.get('dest')
        departure_time = request.form.get('departure_time')

        if not departure_time:
            flash("Please select a departure date and time.")
            return redirect(url_for('manage_flights'))

        resources = get_available_resources(origin, dest, departure_time)

        return render_template('select_plane.html',
                               origin=origin,
                               dest=dest,
                               departure_time=departure_time,
                               planes=resources.get('planes', []))
    except Exception as e:
        print(f"Error in Step 2: {e}")
        return redirect(url_for('manage_flights'))


@app.route('/set_pricing', methods=['POST'])
def step_2_5_set_pricing():
    """
    STEP 2.5: Intermediate step to set ticket prices after selecting a plane.
    """
    return render_template('set_pricing.html',
                           origin=request.form.get('origin'),
                           dest=request.form.get('dest'),
                           departure_time=request.form.get('departure_time'),
                           plane_id=request.form.get('plane_id'),
                           plane_size=request.form.get('plane_size'))


@app.route('/get_available_crew', methods=['POST'])
def step_3_select_crew():
    try:
        origin = request.form.get('origin')
        dest = request.form.get('dest')
        departure_time = request.form.get('departure_time')
        plane_id = request.form.get('plane_id')
        plane_size = request.form.get('plane_size')
        economy_price = request.form.get('economy_price')
        business_price = request.form.get('business_price')

        if plane_size == 'Large':
            req_pilots, req_stewards = 3, 6
        else:
            req_pilots, req_stewards = 2, 3

        resources = get_available_resources(origin, dest, departure_time)

        return render_template('assign_crew.html',
                               origin=origin,
                               dest=dest,
                               departure_time=departure_time,
                               plane_id=plane_id,
                               plane_size=plane_size,
                               economy_price=economy_price,
                               business_price=business_price,
                               pilots=resources.get('pilots', []),
                               attendants=resources.get('attendants', []),
                               req_pilots=req_pilots,
                               req_stewards=req_stewards)
    except Exception as e:
        print(f"Error in Step 3: {e}")
        return redirect(url_for('manage_flights'))


@app.route('/finalize_flight_creation', methods=['POST'])
def finalize_flight_creation():
    try:
        # 1. Extract data from form
        origin = request.form.get('origin')
        dest = request.form.get('dest')
        departure_time = request.form.get('departure_time')
        plane_id = request.form.get('plane_id')
        economy_price = request.form.get('economy_price')
        business_price = request.form.get('business_price')

        pilot_ids = request.form.getlist('pilot_ids')
        attendant_ids = request.form.getlist('attendant_ids')
        manager_id = session.get('user_id')

        with get_db_connection() as cursor:
            # 2. Get Plane Size and Staffing Requirements
            cursor.execute("SELECT Size FROM plane WHERE ID = %s", (plane_id,))
            plane_row = cursor.fetchone()
            plane_size = plane_row[0]
            req_p, req_s = (3, 6) if plane_size == 'Large' else (2, 3)

            # 3. Server-side Crew Validation
            if len(pilot_ids) != req_p or len(attendant_ids) != req_s:
                return f"Error: Invalid crew count.", 400

            # 4. Fetch Duration from Path table
            cursor.execute("SELECT Clock_Duration FROM path WHERE Origin_Airport = %s AND Dest_Airport = %s",
                           (origin, dest))
            path_row = cursor.fetchone()
            duration = path_row[0] if path_row else 2

            # 5. Insert Flight with USER-DEFINED prices
            sql_flight = """
                INSERT INTO flight (
                    Departure_DateTime, Path_Dest_Airport, Path_Origin_Airport, 
                    Path_Clock_Duration, Manager_ID, Plane_ID, 
                    Business_Seat_Price, Economy_Seat_Price
                ) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql_flight, (
                departure_time, dest, origin, duration,
                manager_id, plane_id, business_price, economy_price
            ))
            new_flight_id = cursor.lastrowid

            # 6. Assign Crew
            pilot_assignments = [(p_id, new_flight_id) for p_id in pilot_ids]
            cursor.executemany("INSERT INTO pilot_works_flight (Pilot_ID, Flight_ID) VALUES (%s, %s)",
                               pilot_assignments)

            steward_assignments = [(s_id, new_flight_id) for s_id in attendant_ids]
            cursor.executemany("INSERT INTO steward_works_flight (Steward_ID, Flight_ID) VALUES (%s, %s)",
                               steward_assignments)

            # 7. Fetch Crew Names for summary
            format_p = ','.join(['%s'] * len(pilot_ids))
            cursor.execute(f"SELECT First_Name, Last_Name FROM pilot WHERE ID IN ({format_p})", tuple(pilot_ids))
            pilots_names = cursor.fetchall()

            format_s = ','.join(['%s'] * len(attendant_ids))
            cursor.execute(f"SELECT First_Name, Last_Name FROM steward WHERE ID IN ({format_s})", tuple(attendant_ids))
            stewards_names = cursor.fetchall()

        # 8. Success Response including prices
        return render_template('flight_summary.html',
                               flight_id=new_flight_id,
                               origin=origin, dest=dest,
                               departure_time=departure_time,
                               duration=duration,
                               plane_id=plane_id,
                               economy_price=economy_price,
                               business_price=business_price,
                               pilots=pilots_names,
                               stewards=stewards_names)

    except Exception as e:
        print(f"Finalize Error: {e}")
        return f"System Error: {str(e)}", 500


if __name__ == "__main__":
    app.run(debug=True)