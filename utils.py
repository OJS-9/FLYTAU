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


def guest_sign_in(email: str, first_name: str, last_name: str, phones: list) -> None:
    with get_db_connection() as cursor:
        cursor.execute("SELECT Mail FROM Guest WHERE Mail = %s", (email,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO Guest (Mail, first_name, last_name) VALUES (%s, %s, %s)",
                (email, first_name, last_name)
            )
        else:
            cursor.execute(
                "UPDATE Guest SET first_name = %s, last_name = %s WHERE Mail = %s",
                (first_name, last_name, email)
            )

        for phone in phones:
            clean_phone = phone.strip() if hasattr(phone, 'strip') else str(phone)
            if clean_phone:
                cursor.execute(
                    "INSERT IGNORE INTO guest_phone (Mail, phone) VALUES (%s, %s)",
                    (email, clean_phone)
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

def get_all_future_flights(page: int = 1, per_page: int = 10) -> Dict:
    """
    Get all future flights with at least 1 available seat, with pagination support.
    Returns flights ordered by departure datetime (ascending).
    """
    with get_db_connection() as cursor:
        # Calculate offset for pagination
        offset = (page - 1) * per_page
        
        # First, get total count
        cursor.execute(
            """
            SELECT COUNT(DISTINCT f.ID)
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
            WHERE f.Departure_DateTime >= NOW()
              AND (p.Total_Capacity - COALESCE(seat_counts.booked_seats, 0)) >= 1
            """,
        )
        total_count = cursor.fetchone()[0]
        
        # Then get paginated results
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
            WHERE f.Departure_DateTime >= NOW()
              AND (p.Total_Capacity - COALESCE(seat_counts.booked_seats, 0)) >= 1
            ORDER BY f.Departure_DateTime ASC
            LIMIT %s OFFSET %s
            """,
            (per_page, offset),
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

        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 0
        
        return {
            "flights": flights,
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages
        }

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


def get_employee_hours_report() -> List[Dict]:
    with get_db_connection() as cursor:
        query = """
            SELECT 
                Full_Name,
                Staff_Role,
                SUM(CASE WHEN Flight_Duration > 6 THEN Flight_Duration ELSE 0 END) AS Long_Flight_Hours,
                SUM(CASE WHEN Flight_Duration <= 6 THEN Flight_Duration ELSE 0 END) AS Short_Flight_Hours,
                SUM(Flight_Duration) AS Total_Hours
            FROM (
                SELECT 
                    CONCAT(p.First_Name, ' ', p.Last_Name) AS Full_Name, 
                    'Pilot' AS Staff_Role, 
                    pa.Duration AS Flight_Duration
                FROM pilot p
                JOIN pilot_works_flight pwf ON p.ID = pwf.Pilot_ID
                JOIN flight f ON pwf.Flight_ID = f.ID
                JOIN path pa ON f.Path_Dest_Airport = pa.Dest_Airport 
                             AND f.Path_Origin_Airport = pa.Origin_Airport 
                             AND f.Path_Clock_Duration = pa.Clock_Duration
                WHERE f.Departure_DateTime < NOW()

                UNION ALL

                SELECT 
                    CONCAT(s.First_Name, ' ', s.Last_Name) AS Full_Name, 
                    'Steward' AS Staff_Role, 
                    pa.Duration AS Flight_Duration
                FROM steward s
                JOIN steward_works_flight swf ON s.ID = swf.Steward_ID
                JOIN flight f ON swf.Flight_ID = f.ID
                JOIN path pa ON f.Path_Dest_Airport = pa.Dest_Airport 
                             AND f.Path_Origin_Airport = pa.Origin_Airport 
                             AND f.Path_Clock_Duration = pa.Clock_Duration
                WHERE f.Departure_DateTime < NOW()
            ) AS All_Staff_Flights
            GROUP BY Full_Name, Staff_Role
            ORDER BY Total_Hours DESC
        """
        cursor.execute(query)
        results = cursor.fetchall()

        report_data = []
        for row in results:
            report_data.append({
                "name": f"{row[0]} ({row[1]})",
                "role": row[1],
                "long_hours": float(row[2]),
                "short_hours": float(row[3]),
                "total": float(row[4])
            })

        return report_data


def get_flight_occupancy_report() -> List[Dict]:
    with get_db_connection() as cursor:
        query = """
            SELECT 
                f.ID,
                CONCAT(f.Path_Origin_Airport, '-', f.Path_Dest_Airport) AS Route,
                DATE_FORMAT(f.Departure_DateTime, '%d/%m/%Y %H:%i') AS Flight_Date,
                COUNT(a.Order_ID) AS Passengers_Count,
                (p.Economy_Capacity + p.Business_Capacity) AS Total_Seats,
                ROUND((COUNT(a.Order_ID) / (p.Economy_Capacity + p.Business_Capacity)) * 100, 2) AS Occupancy_Percentage
            FROM flight f
            JOIN plane p ON f.Plane_ID = p.ID
            JOIN `order` o ON f.ID = o.Flight_ID
            JOIN assigned a ON o.Order_ID = a.Order_ID 
            WHERE f.Departure_DateTime < NOW() 
              AND o.Status = 'Completed'
            GROUP BY f.ID, p.Economy_Capacity, p.Business_Capacity
            ORDER BY f.Departure_DateTime DESC
            LIMIT 10;
        """
        cursor.execute(query)
        results = cursor.fetchall()

        report_data = []
        for row in results:
            label = f"{row[1]}\n({row[2]})"

            report_data.append({
                "flight_label": label,
                "passengers": row[3],
                "capacity": row[4],
                "percentage": float(row[5]) if row[5] is not None else 0
            })

        return report_data


def get_total_revenue_report() -> List[Dict]:
    """
    Returns aggregated revenue per plane size, manufacturer and class type.
    Uses the provided SQL logic to compute:
      - Total_Revenue (sum of Total_Price)
      - Number_of_Tickets (count of orders)
    for orders with status Active / Completed / Costumer Cancelation.
    """
    with get_db_connection() as cursor:
        query = """
            SELECT 
                p.Size AS Plane_Size, 
                p.Manufacturer, 
                c.Type,
                SUM(o.Total_Price) AS Total_Revenue,
                COUNT(o.Order_ID) AS Number_of_Tickets
            FROM `Order` o
            JOIN Assigned a ON o.Order_ID = a.Order_ID
            JOIN Plane p ON a.Plane_ID = p.ID
            JOIN Class c ON a.Class_ID = c.ID AND a.Plane_ID = c.Plane_ID
            WHERE o.Status IN ('Active', 'Completed', 'Costumer Cancelation')
            GROUP BY p.Size, p.Manufacturer, c.Type
            ORDER BY Total_Revenue DESC
        """
        cursor.execute(query)
        results = cursor.fetchall()

        report_data: List[Dict] = []
        for row in results:
            report_data.append({
                "plane_size": row[0],
                "manufacturer": row[1],
                "class_type": row[2],
                "total_revenue": float(row[3]) if row[3] is not None else 0.0,
                "ticket_count": int(row[4]) if row[4] is not None else 0,
            })

        return report_data


def get_cancellation_rate_report() -> List[Dict]:
    """
    Returns monthly customer cancellation statistics.
    Excludes system/manager cancellations, and calculates percentage of
    customer cancellations out of all relevant orders per month.
    """
    with get_db_connection() as cursor:
        query = """
            SELECT 
                YEAR(o.Order_Date) AS Order_Year,
                MONTH(o.Order_Date) AS Order_Month,
                COUNT(CASE WHEN o.Status = 'Costumer Cancelation' THEN 1 END) AS Customer_Cancelled_Count,
                COUNT(o.Order_ID) AS Relevant_Orders_Count,
                ROUND(
                    (COUNT(CASE WHEN o.Status = 'Costumer Cancelation' THEN 1 END) / COUNT(o.Order_ID)) * 100, 
                    2
                ) AS Cancellation_Rate_Percentage
            FROM `Order` o
            WHERE o.Status != 'System Cancelation'
            GROUP BY YEAR(o.Order_Date), MONTH(o.Order_Date)
            ORDER BY Order_Year DESC, Order_Month DESC
        """
        cursor.execute(query)
        results = cursor.fetchall()

        report_data: List[Dict] = []
        for row in results:
            year = int(row[0])
            month = int(row[1])
            cancelled = int(row[2])
            total = int(row[3])
            rate = float(row[4]) if row[4] is not None else 0.0

            # Label format: YYYY-MM (e.g., 2025-01)
            label = f"{year}-{month:02d}"

            report_data.append({
                "label": label,
                "year": year,
                "month": month,
                "cancelled": cancelled,
                "total": total,
                "rate": rate,
            })

        # Reverse to show oldest month on the left if desired
        report_data.reverse()
        return report_data


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

def create_path(origin, dest, duration, origin_tz, dest_tz):
    with get_db_connection() as cursor:
        query = """
            INSERT INTO path (Origin_Airport, Dest_Airport, Duration, 
                              Origin_Timezone, Dest_Timezone)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (origin, dest, duration, origin_tz, dest_tz))

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


def get_aircraft_activity_report():
    with get_db_connection() as cursor:
        query = """
        WITH PlaneRoutes AS (
            SELECT 
                f.Plane_ID, 
                f.Path_Origin_Airport, 
                f.Path_Dest_Airport,
                COUNT(*) AS Frequency,
                ROW_NUMBER() OVER (PARTITION BY f.Plane_ID ORDER BY COUNT(*) DESC, f.Path_Dest_Airport ASC) AS RouteRank
            FROM flight f
            WHERE f.is_active = 1 
              AND f.Departure_DateTime >= DATE_SUB(NOW(), INTERVAL 30 DAY) 
            GROUP BY f.Plane_ID, f.Path_Origin_Airport, f.Path_Dest_Airport
        )
        SELECT 
            p.ID AS Plane_ID,
            p.Manufacturer,
            COUNT(CASE WHEN f.is_active = 1 THEN 1 END) AS Flights_Performed,
            COUNT(CASE WHEN f.is_active = 0 THEN 1 END) AS Flights_Cancelled,
            ROUND((SUM(CASE WHEN f.is_active = 1 THEN pa.Duration ELSE 0 END) / 720.0) * 100, 2) AS Utilization_Rate_Percent,
            COALESCE(MAX(CASE WHEN pr.RouteRank = 1 THEN CONCAT(pr.Path_Origin_Airport, '-', pr.Path_Dest_Airport) END), 'No Flights') AS Dominant_Route
        FROM plane p
        LEFT JOIN flight f ON p.ID = f.Plane_ID AND f.Departure_DateTime >= DATE_SUB(NOW(), INTERVAL 30 DAY) 
        LEFT JOIN path pa ON f.Path_Dest_Airport = pa.Dest_Airport 
                          AND f.Path_Origin_Airport = pa.Origin_Airport 
                          AND f.Path_Clock_Duration = pa.Clock_Duration
        LEFT JOIN PlaneRoutes pr ON p.ID = pr.Plane_ID
        GROUP BY p.ID, p.Manufacturer
        ORDER BY Utilization_Rate_Percent DESC;
        """
        cursor.execute(query)
        results = cursor.fetchall()

        data = []
        for row in results:
            data.append({
                "plane_id": f"Plane {row[0]} ({row[1]})",
                "flights": row[2],
                "cancelled": row[3],
                "utilization": float(row[4]) if row[4] else 0,
                "route": row[5]
            })
        return data
def process_system_cancellation(flight_id):
    # כאן אנחנו משתמשים ב-with על הפונקציה שלך שמחזירה cursor
    with get_db_connection() as cursor:
        try:
            # 1. עדכון הטיסה ללא פעילה
            # (וודא שהרצת ALTER TABLE flight ADD COLUMN is_active TINYINT(1) DEFAULT 1;)
            print(f"DEBUG: Setting flight {flight_id} as inactive")
            cursor.execute("UPDATE flight SET is_active = 0 WHERE ID = %s", (flight_id,))

            # 2. עדכון סטטוס ההזמנות
            print(f"DEBUG: Updating orders status for flight {flight_id}")
            cursor.execute("""
                UPDATE `Order` 
                SET Status = 'System Cancelation', Total_Price = 0 
                WHERE Flight_ID = %s
            """, (flight_id,))

            # אין צורך ב-commit() כי הגדרת autocommit=True בפונקציית החיבור!

            print("DEBUG: Success! Changes saved automatically via autocommit.")
            return True

        except Exception as e:
            print(f"CRITICAL ERROR in process_system_cancellation: {e}")
            return False


def get_all_airports():
    """שליפת שדות תעופה לפי מיקום הטור כדי לעקוף שמות עם רווחים"""
    with get_db_connection() as cursor:
        try:
            # אנחנו שולפים את הכל מהטבלה
            cursor.execute("SELECT * FROM path")
            rows = cursor.fetchall()

            airports = set()
            for row in rows:
                # row[0] ו-row[1] הם בדרך כלל המוצא והיעד
                if row[0]: airports.add(str(row[0]).strip())
                if row[1]: airports.add(str(row[1]).strip())

            return sorted(list(airports))
        except Exception as e:
            print(f"Error fetching airports: {e}")
            return []
