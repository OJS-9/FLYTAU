import mysql.connector
from contextlib import contextmanager
import os
from typing import Optional, Tuple, List, Dict
from dotenv import load_dotenv
from datetime import datetime, timedelta
load_dotenv()


@contextmanager
def get_db_connection():
    mydb = None
    cursor = None
    try:
        mydb = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            autocommit=True,
        )
        cursor = mydb.cursor()
        yield cursor
    finally:
        if cursor:
            cursor.close()
        if mydb:
            mydb.close()


def get_customer_by_email_and_password(email: str, password: str) -> Optional[Tuple[str, str, str]]:
    """
    Return (Mail, First_Name, Last_Name) for a matching customer, or None.
    """
    with get_db_connection() as cursor:
        cursor.execute(
            "SELECT Mail, First_Name, Last_Name FROM Costumer WHERE Mail = %s AND Password = %s",
            (email, password),
        )
        return cursor.fetchone()


def get_manager_by_id_and_password(manager_id: int, password: str) -> Optional[Tuple[int, str, str]]:
    """
    Return (ID, First_Name, Last_Name) for a matching manager, or None.
    """
    with get_db_connection() as cursor:
        cursor.execute(
            "SELECT ID, First_Name, Last_Name FROM Manager WHERE ID = %s AND Password = %s",
            (manager_id, password),
        )
        return cursor.fetchone()


def customer_email_exists(email: str) -> bool:
    """
    Check if a customer with the given email already exists.
    """
    with get_db_connection() as cursor:
        cursor.execute("SELECT Mail FROM Costumer WHERE Mail = %s", (email,))
        return cursor.fetchone() is not None


def create_customer_with_phones(
    email: str,
    password: str,
    passport_num: str,
    b_date: str,
    first_name: str,
    last_name: str,
    phones,
) -> None:
    """
    Create a new customer and one or more phone records.
    """
    with get_db_connection() as cursor:
        cursor.execute(
            """
            INSERT INTO Costumer (Mail, Passport_Num, B_Date, Password, Signup_date, First_Name, Last_Name)
            VALUES (%s, %s, %s, %s, CURDATE(), %s, %s)
            """,
            (email, passport_num, b_date, password, first_name, last_name),
        )

        if not phones:
            return

        phone_rows = [(phone, email) for phone in phones]
        cursor.executemany(
            "INSERT INTO Costumer_Phone (Phone, Costumer_Mail) VALUES (%s, %s)",
            phone_rows,
        )


def guest_sign_in(email: str) -> None:
    """
    Ensure a guest with the given email exists in the Guest table.

    Flow:
    - If the email already exists in Guest -> do nothing.
    - If it does not exist -> insert a new row with this email.

    Assumes a table similar to:
        Guest(Mail VARCHAR PRIMARY KEY, Signup_date DATE, ...)
    """
    with get_db_connection() as cursor:
        # Check if guest already exists
        cursor.execute("SELECT Mail FROM Guest WHERE Mail = %s", (email,))
        if cursor.fetchone():
            return

        # Insert new guest
        cursor.execute(
            "INSERT INTO Guest (Mail) VALUES (%s)",
            (email,),
        )


def search_flights(origin_airport: str, destination_airport: str, departure_date: str, passengers: int) -> List[Dict]:
    """
    Search for flights based on origin, destination, date, and required capacity.
    Uses Class_ID for seat identification in the Assigned table as per the schema.
    """
    with get_db_connection() as cursor:
        cursor.execute(
            """
            SELECT 
                f.ID, f.Departure_DateTime, f.Arrival_DateTime,
                f.Path_Origin_Airport, f.Path_Dest_Airport,
                f.Business_Seat_Price, f.Economy_Seat_Price, f.Plane_ID
            FROM Flight f
            JOIN Plane p ON f.Plane_ID = p.ID
            LEFT JOIN (
                SELECT 
                    o.Flight_ID,
                    COUNT(a.Class_ID) AS booked_seats
                FROM Assigned a
                JOIN `Order` o ON a.Order_ID = o.Order_ID
                WHERE o.Status = 'Active'
                GROUP BY o.Flight_ID
            ) seat_counts ON f.ID = seat_counts.Flight_ID
            WHERE f.Path_Origin_Airport = %s
              AND f.Path_Dest_Airport = %s
              AND DATE(f.Departure_DateTime) = %s
              AND (p.Total_Capacity - COALESCE(seat_counts.booked_seats, 0)) >= %s
            ORDER BY f.Departure_DateTime ASC
            """,
            (origin_airport.upper(), destination_airport.upper(), departure_date, passengers),
        )

        results = cursor.fetchall()

        flights = []
        for row in results:
            flights.append({
                "flight_id": row[0],
                "departure_datetime": row[1].strftime("%Y-%m-%d %H:%M:%S") if row[1] else None,
                "arrival_datetime": row[2].strftime("%Y-%m-%d %H:%M:%S") if row[2] else None,
                "origin_airport": row[3],
                "destination_airport": row[4],
                "business_seat_price": row[5],
                "economy_seat_price": row[6],
                "plane_id": row[7],
            })

        return flights

def get_ticket_details(order_id: int, email: str):
    """
    Fetches ticket details without passenger identity fields (Passport/DOB)
    as per the requirement to keep the Order table structure original.
    """
    with get_db_connection() as cursor:
        query = """
            SELECT 
                o.Order_ID, f.Path_Origin_Airport, f.Path_Dest_Airport, f.Departure_DateTime,
                GROUP_CONCAT(CONCAT(c.Row_Num, c.Column_Letter) SEPARATOR ', ') as Seats,
                o.Status, o.Total_Price
            FROM `Order` o
            JOIN Flight f ON o.Flight_ID = f.ID
            LEFT JOIN Assigned a ON o.Order_ID = a.Order_ID
            LEFT JOIN CLASS c ON a.Class_ID = c.ID 
            WHERE o.Order_ID = %s AND (o.Guest_Mail = %s OR o.Costumer_Mail = %s)
            GROUP BY o.Order_ID
        """
        try:
            cursor.execute(query, (order_id, email, email))
            row = cursor.fetchone()
            if row:
                return {
                    "Ticket_ID": row[0],
                    "Origin": row[1],
                    "Destination": row[2],
                    "Departure_Time": row[3].strftime("%Y-%m-%d %H:%M") if row[3] else "TBD",
                    "Seat_ID": row[4] if row[4] else "Not Assigned",
                    "Status": row[5],
                    "Total_Price": row[6]
                }
            return None
        except Exception as e:
            print(f"Database Error: {e}")
            return None

def get_user_order_history(email: str) -> List[Dict]:
    """
    Fetches order history for a user (customer or guest) including all statuses.
    Returns a list of orders with ticket details.
    """
    with get_db_connection() as cursor:
        query = """
            SELECT 
                o.Order_ID, f.Path_Origin_Airport, f.Path_Dest_Airport, f.Departure_DateTime,
                GROUP_CONCAT(CONCAT(c.Row_Num, c.Column_Letter) SEPARATOR ', ') as Seats,
                o.Status, o.Total_Price, o.Order_Date
            FROM `Order` o
            JOIN Flight f ON o.Flight_ID = f.ID
            LEFT JOIN Assigned a ON o.Order_ID = a.Order_ID
            LEFT JOIN CLASS c ON a.Class_ID = c.ID 
            WHERE (o.Guest_Mail = %s OR o.Costumer_Mail = %s)
            GROUP BY o.Order_ID
            ORDER BY o.Order_Date DESC
        """
        try:
            cursor.execute(query, (email, email))
            rows = cursor.fetchall()
            orders = []
            for row in rows:
                orders.append({
                    "Ticket_ID": row[0],
                    "Origin": row[1],
                    "Destination": row[2],
                    "Departure_Time": row[3].strftime("%Y-%m-%d %H:%M") if row[3] else "TBD",
                    "Seat_ID": row[4] if row[4] else "Not Assigned",
                    "Status": row[5],
                    "Total_Price": row[6],
                    "Order_Date": row[7].strftime("%Y-%m-%d %H:%M") if row[7] else "N/A"
                })
            return orders
        except Exception as e:
            print(f"Database Error: {e}")
            return []

def delete_ticket(order_id: int, email: str):
    """
    Handles cancellation logic using confirmed Departure_DateTime.
    """
    with get_db_connection() as cursor:
        try:
            query = """
                SELECT f.Departure_DateTime, o.Total_Price, o.Status
                FROM `Order` o
                JOIN Flight f ON o.Flight_ID = f.ID
                WHERE o.Order_ID = %s AND (o.Guest_Mail = %s OR o.Costumer_Mail = %s)
            """
            cursor.execute(query, (order_id, email, email))
            result = cursor.fetchone()

            if not result:
                return False, "Order not found or access denied."

            departure_time, current_price, status = result

            if status != 'Active':
                return False, "This order is already cancelled."

            # Check if current time is at least 36 hours before departure
            if departure_time - datetime.now() < timedelta(hours=36):
                return False, "Cancellation is only allowed up to 36 hours before the flight."

            penalty_fee = float(current_price) * 0.05

            # Update status and price in Order table
            cursor.execute("""
                UPDATE `Order` 
                SET Status = 'Costumer Cancelation', Total_Price = %s 
                WHERE Order_ID = %s
            """, (penalty_fee, order_id))

            # Free up the seats
            cursor.execute("DELETE FROM Assigned WHERE Order_ID = %s", (order_id,))

            return True, f"Order successfully cancelled. A 5% fee (${penalty_fee:.2f}) was charged."

        except Exception as e:
            print(f"Database Error during cancellation: {e}")
            return False, "An internal error occurred."

def get_flight_seat_map(flight_id: int):
    with get_db_connection() as cursor:
        query = """
            SELECT 
                c.ID AS seat_id,
                c.Row_Num,
                c.Column_Letter,
                c.Type AS class_type,
                IF(EXISTS(
                    SELECT 1 
                    FROM flytau.assigned a
                    JOIN flytau.`Order` o ON a.Order_ID = o.Order_ID 
                    WHERE a.Class_ID = c.ID 
                      AND o.Flight_ID = %s
                ), 1, 0) AS is_occupied
            FROM flytau.class c
            JOIN flytau.Flight f ON f.Plane_ID = c.Plane_ID
            WHERE f.ID = %s
            ORDER BY c.Row_Num, c.Column_Letter
        """
        cursor.execute(query, (flight_id, flight_id))
        results = cursor.fetchall()


        return [{
            "seat_id": r[0],
            "row_num": r[1],
            "letter": r[2],
            "class_type": r[3],
            "is_occupied": bool(r[4])
        } for r in results]

def get_flight_by_id(flight_id: int) -> Optional[Dict]:
    """
    Fetches details for a single flight to be used in the booking summary.
    """
    with get_db_connection() as cursor:
        cursor.execute("""
            SELECT ID, Departure_DateTime, Path_Origin_Airport, Path_Dest_Airport, 
                   Business_Seat_Price, Economy_Seat_Price 
            FROM Flight WHERE ID = %s
        """, (flight_id,))
        row = cursor.fetchone()
        if row:
            return {
                "flight_id": row[0],
                "departure": row[1],
                "origin": row[2],
                "destination": row[3],
                "business_price": row[4],
                "economy_price": row[5]
            }
        return None


def create_order_with_seats(flight_id: int, selected_seats: list, total_price: float,
                            customer_mail: str = None, guest_mail: str = None) -> int:
    """
    Creates a new order record.
    Note: Passport and DOB are NOT saved here anymore to comply with table constraints.
    """
    with get_db_connection() as cursor:
        cursor.execute("SELECT Plane_ID FROM Flight WHERE ID = %s", (flight_id,))
        plane_result = cursor.fetchone()
        if not plane_result: raise Exception(f"Flight ID {flight_id} not found.")
        plane_id = plane_result[0]

        # SQL query back to original 6-column structure
        order_sql = """
            INSERT INTO `Order` (Status, Order_Date, Total_Price, Flight_ID, Costumer_Mail, Guest_Mail)
            VALUES ('Active', NOW(), %s, %s, %s, %s)
        """
        cursor.execute(order_sql, (total_price, flight_id, customer_mail, guest_mail))
        new_order_id = cursor.lastrowid

        assigned_sql = "INSERT INTO Assigned (Class_ID, Order_ID, Plane_ID) VALUES (%s, %s, %s)"
        for seat_id in selected_seats:
            cursor.execute(assigned_sql, (seat_id, new_order_id, plane_id))
        return new_order_id



def update_active_orders_to_completed() -> int:
    """
    Fetches all orders with status 'Active', joins with Flight table,
    and updates orders to 'Completed' status if the current datetime
    is strictly after the flight's departure datetime.
    
    Returns:
        int: The number of orders updated to 'Completed' status
    """
    with get_db_connection() as cursor:
        try:
            # Query all Active orders with their flight departure datetime
            query = """
                SELECT o.Order_ID, f.Departure_DateTime 
                FROM `Order` o
                JOIN Flight f ON o.Flight_ID = f.ID
                WHERE o.Status = 'Active'
            """
            cursor.execute(query)
            results = cursor.fetchall()
            
            if results:
            
                current_datetime = datetime.now()
                
                # Check each order and update if departure has passed
                for row in results:
                    order_id, departure_datetime = row
                    
                    # Skip if departure_datetime is None
                    if departure_datetime is None:
                        continue
                    
                    # Update order if current datetime is strictly after departure datetime
                    if current_datetime > departure_datetime:
                        cursor.execute(
                            "UPDATE `Order` SET Status = 'Completed' WHERE Order_ID = %s",
                            (order_id)
                        )
            
        except Exception as e:
            print(f"Database Error during order status update: {e}")
            return 0

def get_available_resources(origin, dest, departure_time):
    """
    Fetches resources based on three logic tiers:
    1. NEW: Resources with no flight history.
    2. IDLE: Resources with no flights in the last 72 hours.
    3. ACTIVE: Resources that landed at the 'origin' airport.
    """
    resources = {'planes': [], 'pilots': [], 'attendants': []}
    global_buffer = 72

    with get_db_connection() as cursor:
        # --- 1. PLANES QUERY (Updated to include Model and Size) ---
        query_planes = """
            SELECT p.ID, p.Size FROM plane p
            WHERE p.ID NOT IN (
                -- Plane cannot be in flight during the selected departure
                SELECT Plane_ID FROM flight 
                WHERE (Departure_DateTime <= %s AND Arrival_DateTime >= %s)
            )
            AND (
                p.ID NOT IN (SELECT DISTINCT Plane_ID FROM flight)
                OR 
                p.ID IN (
                    SELECT Plane_ID FROM flight f_idle
                    WHERE f_idle.Arrival_DateTime <= DATE_SUB(%s, INTERVAL %s HOUR)
                )
                OR
                p.ID = (
                    SELECT f1.Plane_ID FROM flight f1 
                    WHERE f1.Arrival_DateTime <= %s 
                    AND f1.Path_Dest_Airport = %s
                    ORDER BY f1.Arrival_DateTime DESC LIMIT 1
                )
            )
        """
        cursor.execute(query_planes,
                       (departure_time, departure_time, departure_time, global_buffer, departure_time, origin))
        resources['planes'] = cursor.fetchall()

        # --- 2. PILOTS QUERY (Fixed location-locking logic) ---
        query_pilots = """
            SELECT p.ID, p.First_Name, p.Last_Name FROM pilot p
            WHERE p.ID NOT IN (
                SELECT Pilot_ID FROM pilot_works_flight pwf
                JOIN flight f ON pwf.Flight_ID = f.ID
                WHERE (f.Departure_DateTime <= %s AND f.Arrival_DateTime >= %s)
            )
            AND (
                p.ID NOT IN (SELECT DISTINCT Pilot_ID FROM pilot_works_flight)
                OR 
                p.ID IN (
                    SELECT pwf_idle.Pilot_ID FROM pilot_works_flight pwf_idle
                    JOIN flight f_idle ON pwf_idle.Flight_ID = f_idle.ID
                    WHERE f_idle.Arrival_DateTime <= DATE_SUB(%s, INTERVAL %s HOUR)
                )
                OR
                p.ID IN (
                    SELECT Pilot_ID FROM (
                        SELECT pwf2.Pilot_ID, f2.Path_Dest_Airport,
                        ROW_NUMBER() OVER (PARTITION BY pwf2.Pilot_ID ORDER BY f2.Arrival_DateTime DESC) as rnk
                        FROM pilot_works_flight pwf2
                        JOIN flight f2 ON pwf2.Flight_ID = f2.ID
                        WHERE f2.Arrival_DateTime <= %s
                    ) AS last_p_flights WHERE rnk = 1 AND Path_Dest_Airport = %s
                )
            )
        """
        cursor.execute(query_pilots,
                       (departure_time, departure_time, departure_time, global_buffer, departure_time, origin))
        resources['pilots'] = cursor.fetchall()

        # --- 3. STEWARDS QUERY ---
        query_stewards = """
            SELECT s.ID, s.First_Name, s.Last_Name FROM steward s
            WHERE s.ID NOT IN (
                SELECT Steward_ID FROM steward_works_flight swf
                JOIN flight f ON swf.Flight_ID = f.ID
                WHERE (f.Departure_DateTime <= %s AND f.Arrival_DateTime >= %s)
            )
            AND (
                s.ID NOT IN (SELECT DISTINCT Steward_ID FROM steward_works_flight)
                OR 
                s.ID IN (
                    SELECT swf_idle.Steward_ID FROM steward_works_flight swf_idle
                    JOIN flight f_idle ON swf_idle.Flight_ID = f_idle.ID
                    WHERE f_idle.Arrival_DateTime <= DATE_SUB(%s, INTERVAL %s HOUR)
                )
                OR
                s.ID IN (
                    SELECT Steward_ID FROM (
                        SELECT swf2.Steward_ID, f2.Path_Dest_Airport,
                        ROW_NUMBER() OVER (PARTITION BY swf2.Steward_ID ORDER BY f2.Arrival_DateTime DESC) as rnk
                        FROM steward_works_flight swf2
                        JOIN flight f2 ON swf2.Flight_ID = f2.ID
                        WHERE f2.Arrival_DateTime <= %s
                    ) AS last_s_flights WHERE rnk = 1 AND Path_Dest_Airport = %s
                )
            )
        """
        cursor.execute(query_stewards,
                       (departure_time, departure_time, departure_time, global_buffer, departure_time, origin))
        resources['attendants'] = cursor.fetchall()

    return resources

def create_path(origin, dest, duration, clock_duration, origin_tz, dest_tz):
    with get_db_connection() as cursor:
        query = """
            INSERT INTO path (Origin_Airport, Dest_Airport, Duration, Clock_Duration, 
                              Origin_Timezone, Dest_Timezone)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (origin, dest, duration, clock_duration, origin_tz, dest_tz))

def get_path_info(origin, dest):
    with get_db_connection() as cursor:
        cursor.execute("SELECT Duration, Clock_Duration FROM path WHERE Origin_Airport = %s AND Dest_Airport = %s", (origin, dest))
        return cursor.fetchone()

def add_new_path(origin, dest, duration, o_tz, d_tz):
    with get_db_connection() as cursor:
        query = """
            INSERT INTO path (Origin_Airport, Dest_Airport, Duration, Origin_Timezone, Dest_Timezone)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (origin, dest, duration, o_tz, d_tz))


def create_aircraft_with_seats(manufacturer, size, eco_cap, bus_cap, purchase_date):
    """
    Handles the database logic for inserting a plane and its seat configuration.
    Note: Total_Capacity is handled by the DB as a generated column.
    """
    with get_db_connection() as cursor:
        # 1. Insert plane record (Removed Total_Capacity from the list)
        sql_plane = """
            INSERT INTO plane (Size, Economy_Capacity, Business_Capacity, Manufacturer, Purchase_Date) 
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(sql_plane, (size, eco_cap, bus_cap, manufacturer, purchase_date))
        plane_id = cursor.lastrowid

        # 2. Generate Business Seats (4 per row: A-D)
        bus_cols = ['A', 'B', 'C', 'D']
        bus_count = 0
        current_row = 1
        while bus_count < bus_cap:
            for col in bus_cols:
                if bus_count < bus_cap:
                    cursor.execute("""
                        INSERT INTO CLASS (Plane_ID, Type, Row_Num, Column_Letter) 
                        VALUES (%s, %s, %s, %s)
                    """, (plane_id, 'Business', current_row, col))
                    bus_count += 1
            current_row += 1

        # 3. Generate Economy Seats (6 per row: A-F)
        eco_cols = ['A', 'B', 'C', 'D', 'E', 'F']
        eco_count = 0
        while eco_count < eco_cap:
            for col in eco_cols:
                if eco_count < eco_cap:
                    cursor.execute("""
                        INSERT INTO CLASS (Plane_ID, Type, Row_Num, Column_Letter) 
                        VALUES (%s, %s, %s, %s)
                    """, (plane_id, 'Economy', current_row, col))
                    eco_count += 1
            current_row += 1

    return plane_id


def add_crew_member(data, role):
    """
    Generic function to insert into pilot or steward tables.
    """
    # 1. Safe ID conversion
    raw_id = data.get('id') or data.get('pilot_id')  # Check both common names
    try:
        if not raw_id:
            raise ValueError("ID is missing")
        member_id = int(str(raw_id).strip())  # Strip spaces and convert
    except (ValueError, TypeError):
        raise ValueError(f"Invalid ID: '{raw_id}'. Please enter numbers only.")

    def to_null(val):
        return val if val and str(val).strip() != "" else None

    # 2. Certification logic
    is_certified = 1 if data.get('long_flight_cer') else 0

    params = (
        member_id,
        data.get('starting_date'),
        data.get('first_name'),
        data.get('last_name'),
        to_null(data.get('city')),
        to_null(data.get('street')),
        to_null(data.get('number')),
        to_null(data.get('phone')),
        is_certified
    )

    with get_db_connection() as cursor:
        sql = f"""
            INSERT INTO {role} (ID, Starting_Date, First_Name, Last_Name, City, Street, Number, Phone, Long_Flight_Cer)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, params)

    return member_id
