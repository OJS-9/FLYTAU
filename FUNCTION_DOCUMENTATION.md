# Function Documentation

This document provides short explanations for every function in `main.py` and `utils.py`.

## main.py

### Route Handlers

#### `invalid_route(e)`
- **Purpose**: Error handler for 404 (not found) routes
- **Behavior**: Redirects all invalid routes to the home page

#### `home()`
- **Purpose**: Main entry point for the application
- **GET**: Renders home page or redirects logged-in users to their dashboard
- **POST**: Routes to guest login, customer login, or signup based on user selection

#### `login()`
- **Purpose**: Handles user authentication
- **GET**: Renders login page or redirects if already logged in
- **POST**: Authenticates customers (by email) or managers (by numeric ID), sets session, and redirects to appropriate dashboard

#### `signup()`
- **Purpose**: Handles new customer registration
- **GET**: Renders signup form or redirects if already logged in
- **POST**: Validates form data, checks for duplicate emails, creates customer account with phone numbers, and logs them in

#### `guest_sign_in_route()`
- **Purpose**: Handles guest user sign-in (no password required)
- **Behavior**: Validates name format (English letters only), stores guest info in session, redirects to guest dashboard

#### `user_dashboard()`
- **Purpose**: Main dashboard for registered customers
- **Behavior**: Displays paginated future flights, order history, and airport list. Requires customer authentication.

#### `admin_dashboard()`
- **Purpose**: Main dashboard for managers
- **Behavior**: Displays airport list and management options. Requires manager authentication.

#### `guest_dashboard()`
- **Purpose**: Dashboard for guest users
- **Behavior**: Displays paginated future flights and airport list. Requires guest authentication.

#### `logout()`
- **Purpose**: Ends user session
- **Behavior**: Clears session data and redirects to home page

### Flight Search & Booking

#### `search_flights_route()`
- **Purpose**: Handles flight search requests
- **GET**: Renders search form if no parameters, or processes search if parameters provided
- **POST**: Validates search criteria (origin, destination, date, passengers), searches flights, returns JSON results

#### `get_future_flights_route()`
- **Purpose**: API endpoint for fetching paginated future flights
- **Behavior**: Returns JSON with paginated list of future flights with available seats

#### `select_seat()`
- **Purpose**: Displays seat selection interface for a flight
- **Behavior**: Fetches seat map for specified flight, shows available/occupied seats, limits selection based on passenger count

#### `booking_summary()`
- **Purpose**: Shows booking summary before finalization
- **Behavior**: Calculates total price based on selected seats, fetches flight details, displays summary with seat details and pricing

#### `finalize_booking()`
- **Purpose**: Completes the booking process
- **Behavior**: Creates order record, assigns seats, handles guest registration if needed, returns success page

### Order Management

#### `manage_reservations()`
- **Purpose**: Displays reservation details for viewing/cancellation
- **Behavior**: Fetches ticket details by order ID, ensures user can only view their own orders, renders appropriate template

#### `cancel_order_route()`
- **Purpose**: Handles order cancellation requests
- **Behavior**: Validates cancellation eligibility (36-hour rule), applies 5% penalty fee, frees up seats, updates order status

### Manager Functions - Flight Management

#### `manage_flights()`
- **Purpose**: Entry point for flight creation workflow
- **Behavior**: Renders flight management page with airport list. Requires manager authentication.

#### `validate_route()`
- **Purpose**: Validates origin/destination pair for flight creation
- **Behavior**: Checks if route exists in database, redirects to date/time selection or path creation accordingly

#### `create_new_path_manual()`
- **Purpose**: Renders form for manually creating a new flight path
- **Behavior**: Shows path creation form. Requires manager authentication.

#### `save_path_and_continue()`
- **Purpose**: Saves new flight path and continues to flight creation
- **Behavior**: Creates path record in database, then redirects to date/time selection

#### `step_2_select_plane()` (route: `/get_available_resources`)
- **Purpose**: Step 2 of flight creation - select available plane
- **Behavior**: Fetches available planes based on route and departure time, renders plane selection page

#### `step_2_5_set_pricing()` (route: `/set_pricing`)
- **Purpose**: Intermediate step to set ticket prices
- **Behavior**: Renders pricing form with flight details

#### `step_3_select_crew()` (route: `/get_available_crew`)
- **Purpose**: Step 3 of flight creation - assign crew members
- **Behavior**: Determines required crew count based on plane size, fetches available pilots/stewards, renders crew assignment page

#### `finalize_flight_creation()`
- **Purpose**: Final step - creates the flight record
- **Behavior**: Validates crew count, creates flight record, assigns pilots and stewards, returns flight summary

#### `confirm_cancelation_route()`
- **Purpose**: Handles system/manager flight cancellation
- **Behavior**: Cancels flight, updates all related orders to "System Cancelation", removes crew assignments, shows cancellation summary

### Manager Functions - Resource Management

#### `add_plane()`
- **Purpose**: Renders form for adding new aircraft
- **Behavior**: Shows aircraft registration form. Requires manager authentication.

#### `save_plane_route()`
- **Purpose**: Saves new aircraft to database
- **Behavior**: Validates data, enforces business rule (small planes have no business class), creates plane and seat records, shows success page

#### `add_pilot_page()`
- **Purpose**: Renders form for adding new pilot
- **Behavior**: Shows pilot registration form. Requires manager authentication.

#### `add_steward()`
- **Purpose**: Renders form for adding new steward
- **Behavior**: Shows steward registration form. Requires manager authentication.

#### `save_pilot_route()`
- **Purpose**: Saves new pilot to database
- **Behavior**: Creates pilot record with provided information, shows success confirmation

#### `save_steward_route()`
- **Purpose**: Saves new steward to database
- **Behavior**: Creates steward record with provided information, shows success confirmation

### Manager Functions - Order Management

#### `manage_orders_page()`
- **Purpose**: Displays orders for manager review
- **Behavior**: Filters flights with orders by origin, destination, and date. Shows active flights with bookings.

### Manager Functions - Reports

#### `view_reports()`
- **Purpose**: Displays reports menu
- **Behavior**: Shows available reports. Requires manager authentication.

#### `report_employee_hours()`
- **Purpose**: Generates employee flight hours report
- **Behavior**: Fetches data, creates stacked bar chart showing short vs long flight hours per employee, displays with summary

#### `report_total_revenue()`
- **Purpose**: Generates revenue analysis report
- **Behavior**: Aggregates revenue by plane size, manufacturer, and class type, creates bar chart with color coding

#### `report_flight_occupancy()`
- **Purpose**: Generates flight occupancy report
- **Behavior**: Analyzes last 10 completed flights, calculates occupancy percentages, creates bar chart with 100% reference line

#### `report_cancellation_rate()`
- **Purpose**: Generates monthly cancellation rate report
- **Behavior**: Calculates customer cancellation percentages by month, creates bar chart showing trends

#### `report_aircraft_activity()`
- **Purpose**: Generates aircraft activity and utilization report
- **Behavior**: Shows flights performed and utilization rate per aircraft over last 30 days, displays dominant routes, creates dual-axis chart

---

## utils.py

### Database Connection

#### `get_db_connection()`
- **Purpose**: Context manager for database connections
- **Behavior**: Creates MySQL connection using environment variables, yields cursor, automatically closes connection and cursor on exit

### Authentication & User Management

#### `get_dashboard_redirect(session_obj)`
- **Purpose**: Determines appropriate dashboard URL based on user type
- **Returns**: Dashboard URL string or None if not logged in

#### `get_customer_by_email_and_password(email, password)`
- **Purpose**: Authenticates customer credentials
- **Returns**: Tuple of (Mail, First_Name, Last_Name) if valid, None otherwise

#### `get_manager_by_id_and_password(manager_id, password)`
- **Purpose**: Authenticates manager credentials
- **Returns**: Tuple of (ID, First_Name, Last_Name) if valid, None otherwise

#### `customer_email_exists(email)`
- **Purpose**: Checks if customer email is already registered
- **Returns**: Boolean indicating if email exists

#### `create_customer_with_phones(...)`
- **Purpose**: Creates new customer account with associated phone numbers
- **Behavior**: Inserts customer record, then inserts all provided phone numbers into customer_phone table

#### `guest_sign_in(email, first_name, last_name, phones)`
- **Purpose**: Creates or updates guest record in database
- **Behavior**: Inserts new guest or updates existing one, adds/updates phone numbers

### Flight Search & Retrieval

#### `search_flights(origin_airport, destination_airport, departure_date, passengers)`
- **Purpose**: Searches for available flights matching criteria
- **Behavior**: Finds flights with sufficient available seats, returns list of flight dictionaries with details

#### `get_all_future_flights(page, per_page)`
- **Purpose**: Retrieves paginated list of future flights with available seats
- **Returns**: Dictionary with flights list, pagination metadata (total, page, per_page, total_pages)

#### `get_flight_by_id(flight_id)`
- **Purpose**: Fetches detailed information for a specific flight
- **Returns**: Dictionary with flight details or None if not found

#### `get_flight_seat_map(flight_id)`
- **Purpose**: Retrieves seat map for a flight showing availability
- **Returns**: List of seat dictionaries with position, class type, and occupied status

### Order & Ticket Management

#### `get_ticket_details(order_id, email)`
- **Purpose**: Fetches complete ticket information for an order
- **Behavior**: Ensures user can only access their own tickets, returns ticket details including seats and status

#### `get_user_order_history(email)`
- **Purpose**: Retrieves all orders for a user (customer or guest)
- **Returns**: List of order dictionaries sorted by order date (newest first)

#### `create_order_with_seats(flight_id, selected_seats, total_price, customer_mail, guest_mail)`
- **Purpose**: Creates new order and assigns selected seats
- **Behavior**: Creates order record, inserts seat assignments into assigned table, returns new order ID

#### `delete_ticket(order_id, email)`
- **Purpose**: Cancels a customer order
- **Behavior**: Validates 36-hour cancellation rule, applies 5% penalty fee, updates order status, frees up seats
- **Returns**: Tuple of (success: bool, message: str)

#### `update_active_orders_to_completed()`
- **Purpose**: Updates order status from Active to Completed after flight departure
- **Behavior**: Checks all active orders, updates those where departure time has passed
- **Returns**: Number of orders updated (though return value not currently used)

### Reports

#### `get_employee_hours_report()`
- **Purpose**: Generates flight hours data for all employees
- **Returns**: List of dictionaries with employee names, roles, and hours split by short (≤6h) and long (>6h) flights

#### `get_flight_occupancy_report()`
- **Purpose**: Calculates occupancy rates for completed flights
- **Returns**: List of dictionaries with flight labels, passenger counts, capacity, and occupancy percentages for last 10 completed flights

#### `get_total_revenue_report()`
- **Purpose**: Aggregates revenue by plane characteristics and class type
- **Returns**: List of dictionaries with plane size, manufacturer, class type, total revenue, and ticket count

#### `get_cancellation_rate_report()`
- **Purpose**: Calculates monthly customer cancellation statistics
- **Returns**: List of dictionaries with year, month, cancellation counts, and percentage rates

#### `get_aircraft_activity_report()`
- **Purpose**: Analyzes aircraft utilization and activity over last 30 days
- **Returns**: List of dictionaries with plane info, flight counts, cancellation counts, utilization percentage, and dominant route

### Resource Management

#### `get_available_resources(origin, dest, departure_time)`
- **Purpose**: Finds available planes, pilots, and stewards for a flight
- **Logic**: Uses three-tier system: NEW (no history), IDLE (no flights in 72h), ACTIVE (at origin airport)
- **Special Rules**: For flights >6h, only shows Large planes
- **Returns**: Dictionary with 'planes', 'pilots', and 'attendants' lists

#### `create_path(origin, dest, duration, origin_tz, dest_tz)`
- **Purpose**: Creates new flight path in database
- **Behavior**: Checks if path exists first, inserts if new, returns True if created, False if already exists

#### `get_path_info(origin, dest)`
- **Purpose**: Retrieves path information (duration and clock duration)
- **Returns**: Tuple of (Duration, Clock_Duration) or None if path doesn't exist

#### `add_new_path(origin, dest, duration, o_tz, d_tz)`
- **Purpose**: Inserts new path without checking for duplicates
- **Note**: Similar to `create_path` but doesn't check for existing paths first

#### `create_aircraft_with_seats(manufacturer, size, eco_cap, bus_cap, purchase_date)`
- **Purpose**: Creates new aircraft and generates all seat records
- **Behavior**: Inserts plane record, generates Business seats (4 per row: A-D), then Economy seats (6 per row: A-F)
- **Returns**: New plane ID

#### `add_crew_member(data, role)`
- **Purpose**: Generic function to add pilot or steward
- **Behavior**: Validates ID format, handles optional fields (converts empty strings to NULL), sets certification flag, inserts into specified role table
- **Returns**: Member ID

### System Operations

#### `process_system_cancellation(flight_id)`
- **Purpose**: Handles system-initiated flight cancellation
- **Behavior**: Sets flight to inactive, updates all orders to "System Cancelation" with $0 price, removes all crew assignments
- **Returns**: True if successful, False on error

#### `get_all_airports()`
- **Purpose**: Retrieves list of all airports from path table
- **Behavior**: Extracts unique origin and destination airports, returns sorted list
- **Note**: Uses positional indexing to handle column names with spaces
