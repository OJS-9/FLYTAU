from flask import Flask, render_template, request, redirect, session, jsonify, url_for, flash
from flask_session import Session
from datetime import timedelta, datetime
from utils import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
import os

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
    """
    Error handler for 404 (not found) routes.
    Redirects all invalid routes to the home page.
    """
    return redirect("/")


@app.route('/', methods=['POST', 'GET'])
def home():
    """
    Main entry point for the application.
    GET: Renders home page or redirects logged-in users to their dashboard.
    POST: Routes to guest login, customer login, or signup based on user selection.
    """
    # Check if user is already logged in and redirect to appropriate dashboard
    if request.method == "GET":
        redirect_url = get_dashboard_redirect(session)
        if redirect_url:
            return redirect(redirect_url)
        return render_template("home.html")
    
    if request.method == "POST":
        login_type = request.form.get("login_type")
        if login_type == "guest":
            return render_template("guest.html")
        if login_type == "login":
            return redirect("/login")
        if login_type == "signup":
            return redirect("/signup")
        return render_template("login_form.html", error="Please select an option")


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user authentication.
    GET: Renders login page or redirects if already logged in.
    POST: Authenticates customers (by email) or managers (by numeric ID), sets session, and redirects to appropriate dashboard.
    """
    if request.method == "GET":
        redirect_url = get_dashboard_redirect(session)
        if redirect_url:
            return redirect(redirect_url)
        return render_template("login.html")

    if request.method == "POST":
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
                session.permanent = True  # Make session persist across browser restarts
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
            session.permanent = True  # Make session persist across browser restarts
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
    """
    Handles new customer registration.
    GET: Renders signup form or redirects if already logged in.
    POST: Validates form data, checks for duplicate emails, creates customer account with phone numbers, and logs them in.
    """
    if request.method == "GET":
        redirect_url = get_dashboard_redirect(session)
        if redirect_url:
            return redirect(redirect_url)
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
            session.permanent = True  # Make session persist across browser restarts
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
    Handles guest user sign-in (no password required).
    Validates name format (English letters only), stores guest info in session, redirects to guest dashboard.
    """
    email = request.form.get("email", "").strip()
    f_name = request.form.get("first_name", "").strip()
    l_name = request.form.get("last_name", "").strip()
    phones = request.form.getlist("phones")

    if not (f_name.isascii() and f_name.isalpha()) or not (l_name.isascii() and l_name.isalpha()):
        return render_template("guest.html",
                               error="First and Last names must contain English letters only (no spaces or numbers).",
                               last_email=email)
    session.clear()
    session.permanent = True  # Make session persist across browser restarts
    session["user_type"] = "guest"
    session["guest_email"] = email
    session["guest_first_name"] = f_name
    session["guest_last_name"] = l_name
    session["guest_phones"] = phones

    return redirect(url_for('guest_dashboard'))

@app.route("/user_dashboard")
def user_dashboard():
    """
    Main dashboard for registered customers.
    Displays paginated future flights, order history, and airport list. Requires customer authentication.
    """
    if session.get("user_type") != "customer":
        redirect_url = get_dashboard_redirect(session)
        if redirect_url:
            return redirect(redirect_url)
        return redirect("/login")
    
    # Pagination for list of all future flights with available seats
    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            page = 1
    except (TypeError, ValueError):
        page = 1

    # Fetch paginated future flights (only those with at least 1 available seat)
    # Currently configured for 5 flights per page
    active_flights = get_all_future_flights(page=page, per_page=5)

    # Update active orders to completed before fetching order history
    update_active_orders_to_completed()
    airports = get_all_airports()
    # Get order history for the logged-in user
    user_email = session.get("user_email")
    order_history = get_user_order_history(user_email) if user_email else []
    
    return render_template(
        "user_dashboard.html",
        user_name=session.get("user_name"),
        user_email=user_email,
        order_history=order_history,
        airports=airports,
        active_flights=active_flights
    )


@app.route("/admin_dashboard")
def admin_dashboard():
    """
    Main dashboard for managers.
    Displays airport list and management options. Requires manager authentication.
    """
    if session.get("user_type") != "manager":
        redirect_url = get_dashboard_redirect(session)
        if redirect_url:
            return redirect(redirect_url)
        return redirect("/login")
    
    airports = get_all_airports()
    return render_template(
        "admin_dashboard.html",
        user_name=session.get("user_name"),
        user_id=session.get("user_id"),
        airports=airports
    )


@app.route("/guest_dashboard")
def guest_dashboard():
    """
    Simple guest dashboard after email-only sign-in.
    Uses the same guest.html template but passes the guest email.
    """
    if session.get("user_type") != "guest":
        redirect_url = get_dashboard_redirect(session)
        if redirect_url:
            return redirect(redirect_url)
        return redirect("/login")
    
    # Pagination for list of all future flights with available seats
    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            page = 1
    except (TypeError, ValueError):
        page = 1

    # Fetch paginated future flights (only those with at least 1 available seat)
    active_flights = get_all_future_flights(page=page, per_page=5)
    
    airports = get_all_airports()
    return render_template(
        "guest.html",
        guest_email=session.get("guest_email"),
        airports=airports,
        active_flights=active_flights
    )


@app.route("/logout")
def logout():
    """
    Ends user session.
    Clears session data and redirects to home page.
    """
    session.clear()
    return redirect("/")


@app.route("/search_flights", methods=["POST", "GET"])
def search_flights_route():
    """
    Handles flight search requests for customers and guests.
    Supports both GET (query parameters) and POST (form data).
    """

    if request.method == "GET" and not request.args.get("origin_airport"):
        airports = get_all_airports()
        return render_template("customer_search.html", airports=airports)

    data = request.args if request.method == "GET" else request.form

    user_type = session.get("user_type")
    if user_type not in ["customer", "guest"]:
        redirect_url = get_dashboard_redirect(session)
        if redirect_url:
            return redirect(redirect_url)
        return redirect("/login")

    origin_airport = data.get("origin_airport", "").strip().upper()
    destination_airport = data.get("destination_airport", "").strip().upper()
    departure_date = data.get("departure_date", "").strip()
    passengers = data.get("passengers", "1").strip()

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
            # Validate date is not in the past
            date_obj = datetime.strptime(departure_date, "%Y-%m-%d")
            if date_obj.date() < datetime.now().date():
                errors.append("Departure date cannot be in the past.")
        except ValueError:
            errors.append("Invalid date format. Please use YYYY-MM-DD.")

    try:
        passengers_int = int(passengers)
        if passengers_int < 1 or passengers_int > 9:
            errors.append("Number of passengers must be between 1 and 9.")
        else:
            # Store in session for future booking steps
            session['passengers'] = passengers_int
            session["search_passengers"] = passengers_int
    except ValueError:
        errors.append("Number of passengers must be a valid number.")

    if errors:
        return jsonify({"error": " ".join(errors)}), 400

    try:
        # Note: Ensure search_flights in utils.py uses DATE(Departure_DateTime)
        flights = search_flights(origin_airport, destination_airport, departure_date, passengers_int)

        # Return JSON response for AJAX-based frontends
        return jsonify({
            "flights": flights,
            "count": len(flights),
            "search_params": {
                "origin": origin_airport,
                "dest": destination_airport,
                "date": departure_date
            }
        })

    except Exception as e:
        # Log error for debugging
        print(f"Database Error during search: {e}")
        return jsonify({"error": "An internal error occurred. Please try again later."}), 500

@app.route("/get_future_flights", methods=["GET"])
def get_future_flights_route():
    """
    Handle requests for all future flights with pagination.
    Returns paginated list of future flights with at least 1 available seat.
    """
    # Check if user is logged in as customer or guest
    user_type = session.get("user_type")
    if user_type not in ["customer", "guest"]:
            redirect_url = get_dashboard_redirect(session)
            if redirect_url:
                return redirect(redirect_url)
            return redirect("/login")

    # Get page parameter, default to 1
    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    try:
        result = get_all_future_flights(page=page, per_page=10)
        return jsonify(result)
    except Exception as e:
        # Log the internal error and return a generic user-friendly message
        print(f"Database Error: {e}")
        return jsonify({"error": "An error occurred while fetching future flights. Please try again."}), 500


@app.route("/manage_reservations")
def manage_reservations():
    """
    Search and retrieve flight reservation details for both Guests and Customers.
    Redirects to specific dashboards or renders detailed views based on user type.
    """
    if session.get("user_type") not in ["customer", "guest"]:
        redirect_url = get_dashboard_redirect(session)
        if redirect_url:
            return redirect(redirect_url)
        return redirect("/login")
        
    order_id = request.args.get('order_id')
    user_email = session.get('user_email')
    guest_email = session.get('guest_email')

    # Identify the active email session
    email = user_email or guest_email

    if not order_id or not email:
        flash("Please provide a valid Order ID and ensure you are logged in.")
        return redirect(url_for('user_dashboard' if user_email else 'guest_dashboard_route'))

    update_active_orders_to_completed()

    try:
        # We use the email to ensure a user can only view THEIR own orders
        ticket = get_ticket_details(int(order_id), email)
    except Exception as e:
        print(f"Error retrieving ticket {order_id}: {e}")
        ticket = None

    if not ticket:
        error_msg = f"Order #{order_id} was not found or is not linked to your email."
        flash(error_msg)
        return redirect(url_for('user_dashboard' if user_email else 'guest_dashboard_route'))

    if user_email:
        # REGISTERED CUSTOMER: Pass data to the dedicated management page
        order_data = ticket.copy()
        order_data['Passenger_Email'] = user_email
        # Ensure 'manage_order.html' exists for customers
        return render_template("manage_order.html", order=order_data)
    else:
        # GUEST USER: Return to the guest dashboard but with the ticket details populated
        # IMPORTANT: Ensure 'guest_dashboard.html' has the logic to display the 'ticket' variable
        airports = get_all_airports()  # Guests usually need the airport list for the search bar
        return render_template("guest.html",
                               ticket=ticket,
                               show_manage=True,
                               airports=airports)
    

@app.route("/cancel_order", methods=["POST"])
def cancel_order_route():
    """
    Handles order cancellation requests.
    Validates cancellation eligibility (36-hour rule), applies 5% penalty fee, frees up seats, updates order status.
    """
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
            return render_template("cancel_summary.html", order=order_data, error_message=message)

    return "Invalid Request", 400


@app.route("/select_seat")
def select_seat():
    """
    Displays seat selection interface for a flight.
    Fetches seat map for specified flight, shows available/occupied seats, limits selection based on passenger count.
    """
    fid_raw = request.args.get('flight_id')
    if not fid_raw or not session.get("user_type") in ["customer", "guest"]:
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

    if not selected_seats or len(selected_seats) != int(max_seats):
        flash(f"Error: You must select exactly {max_seats} seats.")
        return redirect(url_for('select_seat', flight_id=flight_id))

    flight = get_flight_by_id(int(flight_id))
    if not flight:
        flash("Error: Flight details could not be retrieved.")
        return redirect(url_for('search_flights_route'))

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

    # This data is passed to the HTML but will NOT be saved to the 'Order' table later.
    user_data = None
    if session.get("user_type") == "customer":
        email = session.get("user_email")
        with get_db_connection() as cursor:
            cursor.execute("SELECT Passport_Num, B_Date FROM costumer WHERE Mail = %s", (email,))
            user_data = cursor.fetchone()

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
        if user_type == 'guest':
            from utils import guest_sign_in
            guest_sign_in(
                email=session.get("guest_email"),
                first_name=session.get("guest_first_name"),
                last_name=session.get("guest_last_name"),
                phones=session.get("guest_phones", [])
            )

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


@app.route("/manage_flights")
def manage_flights():
    """
    Entry point for flight creation workflow.
    Renders flight management page with airport list. Requires manager authentication.
    """
    if session.get("user_type") != "manager":
        return redirect("/login")


    airports_list = get_all_airports()
    print(f"DEBUG: Found airports: {airports_list}")

    return render_template("manage_flights.html", airports=airports_list)

@app.route('/manage_orders')
def manage_orders_page():
    """
    Displays orders for manager review.
    Filters flights with orders by origin, destination, and date. Shows active flights with bookings.
    """
    if session.get("user_type") != "manager":
        return redirect("/login")

    origin_q = request.args.get('origin', '').strip()
    dest_q = request.args.get('destination', '').strip()
    date_q = request.args.get('departure_date', '').strip()

    flights_data = []

    query = """
        SELECT DISTINCT 
            f.ID AS flight_id, 
            f.Departure_DateTime AS departure, 
            f.Path_Origin_Airport AS origin, 
            f.Path_Dest_Airport AS destination
        FROM flight f
        JOIN `order` o ON f.ID = o.Flight_ID
        WHERE o.Status != 'System Cancelation'
        AND f.is_active = 1 
    """
    params = []


    if origin_q:
        query += " AND f.Path_Origin_Airport LIKE %s"
        params.append(f"%{origin_q}%")

    if dest_q:
        query += " AND f.Path_Dest_Airport LIKE %s"
        params.append(f"%{dest_q}%")

    if date_q:
        # פילטור לפי תאריך בלבד (מתעלם מהשעה ב-DB)
        query += " AND DATE(f.Departure_DateTime) = %s"
        params.append(date_q)

    # מיון לפי התאריך הקרוב ביותר
    query += " ORDER BY f.Departure_DateTime ASC"

    try:
        with get_db_connection() as cursor:
            cursor.execute(query, tuple(params))
            flights_data = cursor.fetchall()
    except Exception as e:
        print(f"Database error: {e}")

    return render_template('manager_manage_order.html', flights=flights_data)

@app.route('/view_reports')
def view_reports():
    """
    Displays reports menu.
    Shows available reports. Requires manager authentication.
    """
    if session.get("user_type") != "manager":
        return redirect("/login")

    return render_template("reports_menu.html")


@app.route('/reports/employee_hours')
def report_employee_hours():
    """
    Generates employee flight hours report.
    Fetches data, creates stacked bar chart showing short vs long flight hours per employee, displays with summary.
    """
    if session.get("user_type") != "manager":
        return redirect("/login")

    try:
        data = get_employee_hours_report()
    except Exception:
        data = []

    if not data:
        return render_template("report_display.html",
                               report_title="Employee Flight Hours",
                               chart_url=None)

    names = [row['name'] for row in data]
    short_hours = [row['short_hours'] for row in data]
    long_hours = [row['long_hours'] for row in data]

    plt.figure(figsize=(10, 6))

    plt.bar(names, short_hours, label='Short Flights (<=6h)', color='#E67E22')
    plt.bar(names, long_hours, bottom=short_hours, label='Long Flights (>6h)', color='#2C3E50')

    plt.xlabel('Employees')
    plt.ylabel('Flight Hours')
    plt.title('Accumulated Flight Hours per Employee')
    plt.legend()
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    summary_text = """
    This chart shows the total flight hours for each crew member, divided by flight length.
    **Short Flights (Orange, <= 6h)** represent standard routes, while **Long Flights (Dark Blue, > 6h)** require longer rest periods for the crew.
    This data helps managers prevent fatigue and ensure the workload is balanced fairly among all employees.
        """

    return render_template("report_display.html",
                           report_title="Employee Flight Hours",
                           chart_url=plot_url,
                           report_summary=summary_text)


@app.route('/reports/total_revenue')
def report_total_revenue():
    """
    Generates revenue analysis report.
    Aggregates revenue by plane size, manufacturer, and class type, creates bar chart with color coding.
    """
    if session.get("user_type") != "manager":
        return redirect("/login")

    try:
        data = get_total_revenue_report()
    except Exception as e:
        print(f"Error fetching total revenue report: {e}")
        data = []

    if not data:
        return render_template("report_display.html",
                               report_title="Total Revenue Analysis",
                               chart_url=None)

    labels = [
        f"{row['plane_size']} / {row['manufacturer']} / {row['class_type']}"
        for row in data
    ]
    revenues = [row['total_revenue'] for row in data]

    # Predefined colors per specific plane/manufacturer/class combination
    label_colors = {
        "Large / Boeing / Economy": "#3498DB",
        "Large / Boeing / Business": "#5DADE2",
        "Small / Boeing / Economy": "#21618C",
        "Large / Airbus / Economy": "#E74C3C",
        "Large / Airbus / Business": "#EC7063",
        "Small / Airbus / Economy": "#922B21",
        "Large / Dassault / Economy": "#27AE60",
        "Large / Dassault / Business": "#52BE80",
        "Small / Dassault / Economy": "#196F3D",
    }

    bar_colors = [label_colors.get(label, "#7F8C8D") for label in labels]

    plt.figure(figsize=(10, 6))

    bars = plt.bar(labels, revenues, color=bar_colors, label='Total Revenue')

    plt.xlabel('Plane Size / Manufacturer / Class')
    plt.ylabel('Total Revenue')
    plt.title('Total Revenue by Plane Size, Manufacturer & Class')
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()

    # Annotate bars with revenue values (rounded, thousands separated)
    for bar, value in zip(bars, revenues):
        height = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2.0,
            height,
            f"{value:,.0f}",
            ha='center',
            va='bottom',
            fontsize=8,
        )

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    return render_template("report_display.html",
                           report_title="Total Revenue Analysis",
                           chart_url=plot_url)


@app.route('/reports/flight_occupancy')
def report_flight_occupancy():
    """
    Generates flight occupancy report.
    Analyzes last 10 completed flights, calculates occupancy percentages, creates bar chart with 100% reference line.
    """
    if session.get("user_type") != "manager":
        return redirect("/login")

    try:
        data = get_flight_occupancy_report()
    except Exception as e:
        print(f"Error fetching report: {e}")
        data = []

    if not data:
        return render_template("report_display.html",
                               report_title="Average Flight Occupancy",
                               chart_url=None)

    labels = [row['flight_label'] for row in data]
    percentages = [row['percentage'] for row in data]

    plt.figure(figsize=(10, 6))

    bars = plt.bar(labels, percentages, color='#1ABC9C', label='Occupancy %')

    plt.axhline(y=100, color='r', linestyle='--', label='Full Capacity (100%)', alpha=0.7)

    plt.ylabel('Occupancy Percentage (%)')
    plt.title('Average Occupancy per Completed Flight')
    plt.ylim(0, 110)
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.5)

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2., height,
                 f'{height}%',
                 ha='center', va='bottom')

    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    summary_text = """
        This report analyzes the occupancy rates of the last 10 completed flights. 
        The goal is to identify underperforming routes. 
        A low occupancy rate (below 70%) may indicate a need to adjust pricing or flight frequency. 
        Currently, the red line represents full capacity (100%), allowing for quick visual assessment of flight efficiency.
        """

    return render_template("report_display.html",
                           report_title="Average Flight Occupancy",
                           chart_url=plot_url,
                           report_summary=summary_text)


@app.route('/reports/cancellation_rate')
def report_cancellation_rate():
    """
    Generates monthly cancellation rate report.
    Calculates customer cancellation percentages by month, creates bar chart showing trends.
    """
    if session.get("user_type") != "manager":
        return redirect("/login")

    try:
        data = get_cancellation_rate_report()
    except Exception as e:
        print(f"Error fetching cancellation report: {e}")
        data = []

    if not data:
        return render_template("report_display.html",
                               report_title="Cancellation Rate by Month",
                               chart_url=None)

    labels = [row['label'] for row in data]
    rates = [row['rate'] for row in data]

    plt.figure(figsize=(10, 6))

    bars = plt.bar(labels, rates, color='#E74C3C', label='Cancellation Rate (%)')

    plt.ylabel('Cancellation Rate (%)')
    plt.title('Customer Cancellation Rate by Month')
    plt.ylim(0, max(rates) * 1.2 if rates else 1)
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.5)
    plt.xticks(rotation=45, ha='right')

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2., height,
                 f'{height:.1f}%',
                 ha='center', va='bottom', fontsize=8)

    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    return render_template("report_display.html",
                           report_title="Cancellation Rate by Month",
                           chart_url=plot_url)


@app.route('/add_plane')
def add_plane():
    """
    Renders form for adding new aircraft.
    Shows aircraft registration form. Requires manager authentication.
    """
    if session.get("user_type") != "manager":
        return redirect("/login")

    return render_template('add_plane.html')


@app.route('/add_pilot')
def add_pilot_page():
    """
    Renders form for adding new pilot.
    Shows pilot registration form. Requires manager authentication.
    """
    if session.get("user_type") != "manager":
        return redirect("/login")

    return render_template('add_pilot.html')

@app.route('/add_steward')
def add_steward():
    """
    Renders form for adding new steward.
    Shows steward registration form. Requires manager authentication.
    """
    if session.get("user_type") != "manager":
        return redirect("/login")
        
    return render_template('add_steward.html')

@app.route('/save_pilot', methods=['POST'])
def save_pilot_route():
    """
    Saves new pilot to database.
    Creates pilot record with provided information, shows success confirmation.
    """
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
    """
    Saves new steward to database.
    Creates steward record with provided information, shows success confirmation.
    """
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
    """
    Saves new aircraft to database.
    Validates data, enforces business rule (small planes have no business class), creates plane and seat records, shows success page.
    """
    try:
        manufacturer = request.form.get('manufacturer')
        size = request.form.get('size')
        eco_cap = int(request.form.get('eco_cap', 0))
        bus_cap = int(request.form.get('bus_cap', 0))
        purchase_date = request.form.get('purchase_date')

        # Business logic: Small aircraft do not have a Business Class
        if size == 'Small':
            bus_cap = 0

        # Call the utility function to insert into 'plane' and generate 'class' records
        plane_id = create_aircraft_with_seats(
            manufacturer=manufacturer,
            size=size,
            eco_cap=eco_cap,
            bus_cap=bus_cap,
            purchase_date=purchase_date
        )

        # Render the success page with a summary of the added aircraft
        return render_template('plane_success.html',
                               plane_id=plane_id,
                               manufacturer=manufacturer,
                               size=size,
                               eco_cap=eco_cap,
                               bus_cap=bus_cap,
                               total_cap=eco_cap + bus_cap)

    except Exception as e:
        # Log the error for debugging purposes
        print(f"Error in save_plane_route: {e}")
        return f"System Error: {str(e)}", 500

@app.route('/validate_route', methods=['POST'])
def validate_route():
    """
    Validates origin/destination pair for flight creation.
    Checks if route exists in database, redirects to date/time selection or path creation accordingly.
    """
    origin = request.form.get('origin', '').upper()
    dest = request.form.get('dest', '').upper()

    if not origin or not dest:
        flash("Please select both origin and destination.")
        return redirect(url_for('manage_flights_page'))

    if origin == dest:
        flash("Origin and Destination cannot be the same.")
        return redirect(url_for('manage_flights_page'))

    # בדיקה האם הנתיב קיים
    path_data = get_path_info(origin, dest)

    if path_data:
        # אם קיים, עוברים ישר לבחירת תאריך ושעה
        return render_template('select_date_time.html', origin=origin, dest=dest)
    else:
        # אם המנהל הזין ידנית נתיב שלא קיים, עוברים להקמתו
        return render_template('create_new_path.html', origin=origin, dest=dest)

@app.route('/admin/create-new-path-manual')
def create_new_path_manual():
    """
    Renders form for manually creating a new flight path.
    Shows path creation form. Requires manager authentication.
    """
    if session.get("user_type") != "manager":
        return redirect("/login")

    return render_template('create_new_path.html', origin='', dest='')

@app.route('/save_path_and_continue', methods=['POST'])
def save_path_and_continue():
    """
    Saves new flight path and continues to flight creation.
    Creates path record in database, then redirects to date/time selection.
    """
    origin = request.form.get('origin').upper()
    dest = request.form.get('dest').upper()
    duration = float(request.form.get('duration'))
    o_tz = int(request.form.get('origin_tz'))
    d_tz = int(request.form.get('dest_tz'))

    success = create_path(origin, dest, duration, o_tz, d_tz)
    if not success:
        print(f"Notice: Path {origin}-{dest} was already in DB.")

    return render_template('select_date_time.html', origin=origin, dest=dest)

@app.route('/get_available_resources', methods=['POST'])
def step_2_select_plane():
    """
    Step 2 of flight creation - select available plane.
    Fetches available planes based on route and departure time, renders plane selection page.
    """
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
    """
    Step 3 of flight creation - assign crew members.
    Determines required crew count based on plane size, fetches available pilots/stewards, renders crew assignment page.
    """
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
    """
    Final step - creates the flight record.
    Validates crew count, creates flight record, assigns pilots and stewards, returns flight summary.
    """
    try:
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
            cursor.execute("SELECT Size FROM plane WHERE ID = %s", (plane_id,))
            plane_row = cursor.fetchone()
            plane_size = plane_row[0]
            req_p, req_s = (3, 6) if plane_size == 'Large' else (2, 3)

            if len(pilot_ids) != req_p or len(attendant_ids) != req_s:
                return f"Error: Invalid crew count.", 400

            cursor.execute("SELECT Clock_Duration FROM path WHERE Origin_Airport = %s AND Dest_Airport = %s",
                           (origin, dest))
            path_row = cursor.fetchone()
            duration = path_row[0] if path_row else 2

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

            pilot_assignments = [(p_id, new_flight_id) for p_id in pilot_ids]
            cursor.executemany("INSERT INTO pilot_works_flight (Pilot_ID, Flight_ID) VALUES (%s, %s)",
                               pilot_assignments)

            steward_assignments = [(s_id, new_flight_id) for s_id in attendant_ids]
            cursor.executemany("INSERT INTO steward_works_flight (Steward_ID, Flight_ID) VALUES (%s, %s)",
                               steward_assignments)

            format_p = ','.join(['%s'] * len(pilot_ids))
            cursor.execute(f"SELECT First_Name, Last_Name FROM pilot WHERE ID IN ({format_p})", tuple(pilot_ids))
            pilots_names = cursor.fetchall()

            format_s = ','.join(['%s'] * len(attendant_ids))
            cursor.execute(f"SELECT First_Name, Last_Name FROM steward WHERE ID IN ({format_s})", tuple(attendant_ids))
            stewards_names = cursor.fetchall()

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

@app.route('/reports/aircraft_activity')
def report_aircraft_activity():
    """
    Generates aircraft activity and utilization report.
    Shows flights performed and utilization rate per aircraft over last 30 days, displays dominant routes, creates dual-axis chart.
    """
    if session.get("user_type") != "manager":
        return redirect("/login")

    try:
        data = get_aircraft_activity_report()
    except Exception:
        data = []

    if not data:
        return render_template("report_display.html", report_title="Aircraft Activity", chart_url=None)

    planes = [d['plane_id'] for d in data]
    flights = [d['flights'] for d in data]
    utilization = [d['utilization'] for d in data]
    routes = [d['route'] for d in data]

    fig, ax1 = plt.subplots(figsize=(12, 6))

    bars = ax1.bar(planes, flights, color='#95a5a6', alpha=0.6, label='Flights Performed')
    ax1.set_ylabel('Number of Flights', color='#7f8c8d')
    ax1.tick_params(axis='y', labelcolor='#7f8c8d')

    ax2 = ax1.twinx()
    ax2.plot(planes, utilization, color='#e74c3c', marker='o', linewidth=2, label='Utilization %')
    ax2.set_ylabel('Utilization (%)', color='#e74c3c')
    ax2.tick_params(axis='y', labelcolor='#e74c3c')
    ax2.set_ylim(0, 100)

    plt.title('Aircraft Activity: Flights vs. Utilization (Last 30 Days)')

    for i, bar in enumerate(bars):
        height = bar.get_height()
        if height > 0:
            ax1.text(bar.get_x() + bar.get_width() / 2., height / 2,
                     routes[i],
                     ha='center', va='center', rotation=90, color='black', fontsize=8, fontweight='bold')

    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    summary_text = """
    This report summarizes fleet efficiency over the last 30 days. 
    The **Grey Bars** show the total completed flights, while the **Red Line** tracks the aircraft utilization rate (percentage of time spent in the air). 
    The dominant route for each aircraft is listed inside the bar. Low utilization may indicate maintenance issues or inefficient scheduling.
    """

    return render_template("report_display.html",
                           report_title="Aircraft Activity Summary",
                           chart_url=plot_url,
                           report_summary=summary_text)


@app.route('/confirm_cancelation', methods=['POST'])
def confirm_cancelation_route():
    """
    Handles system/manager flight cancellation.
    Cancels flight, updates all related orders to "System Cancelation", removes crew assignments, shows cancellation summary.
    """
    f_id = request.form.get('flight_id')

    with get_db_connection() as cursor:
        cursor.execute("SELECT COUNT(*) FROM `order` WHERE Flight_ID = %s", (f_id,))
        orders_count = cursor.fetchone()[0]

        cursor.execute("SELECT Path_Origin_Airport, Path_Dest_Airport FROM flight WHERE ID = %s", (f_id,))
        flight_data = cursor.fetchone()
        origin, dest = flight_data[0], flight_data[1]

    if process_system_cancellation(f_id):
        return render_template('cancel_summary.html',
                               flight_id=f_id,
                               orders_count=orders_count,
                               origin=origin,
                               dest=dest)

    return redirect('/manage_orders?status=error')

if __name__ == "__main__":
    app.run(debug=True)


