import mysql.connector
from mysql.connector import Error
import os
from typing import Optional, Tuple, List, Dict
from dotenv import load_dotenv
from datetime import datetime, timedelta
load_dotenv()


class DatabaseManager:
    """
    Singleton class for managing database connections.
    Maintains one persistent MySQL connection with automatic reconnection.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connection = None
            cls._instance._initialized = False
        return cls._instance
    
    def _initialize_connection(self):
        """Initialize the database connection."""
        try:
            self._connection = mysql.connector.connect(
                host=os.getenv("DB_HOST"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                database=os.getenv("DB_NAME"),
                autocommit=True,
            )
            self._initialized = True
        except Error as e:
            print(f"Error connecting to database: {e}")
            raise
    
    def reconnect(self):
        """Reconnect to the database."""
        try:
            if self._connection:
                self._connection.close()
        except Error:
            pass  # Ignore errors when closing old connection
        
        self._connection = None
        self._initialized = False
        self._initialize_connection()
    
    def get_connection(self):
        """Get the database connection, creating it if necessary."""
        if not self._connection or not self._connection.is_connected():
            if self._connection:
                self.reconnect()
            else:
                self._initialize_connection()
        return self._connection
    
    def get_cursor(self):
        """Get a cursor from the database connection."""
        connection = self.get_connection()
        try:
            # Check if connection is still alive
            if not connection.is_connected():
                self.reconnect()
                connection = self._connection
            return connection.cursor()
        except Error as e:
            # If we get an error, try reconnecting once
            print(f"Database error: {e}, attempting reconnect...")
            self.reconnect()
            return self._connection.cursor()
    
    def close_connection(self):
        """Close the database connection (for graceful shutdown)."""
        if self._connection and self._connection.is_connected():
            self._connection.close()
            self._connection = None
            self._initialized = False


# Create module-level singleton instance
db_manager = DatabaseManager()


def get_customer_by_email_and_password(email: str, password: str) -> Optional[Tuple[str, str, str]]:
    """
    Return (Mail, First_Name, Last_Name) for a matching customer, or None.
    """
    cursor = db_manager.get_cursor()
    try:
        cursor.execute(
            "SELECT Mail, First_Name, Last_Name FROM Costumer WHERE Mail = %s AND Password = %s",
            (email, password),
        )
        return cursor.fetchone()
    finally:
        cursor.close()


def get_manager_by_id_and_password(manager_id: int, password: str) -> Optional[Tuple[int, str, str]]:
    """
    Return (ID, First_Name, Last_Name) for a matching manager, or None.
    """
    cursor = db_manager.get_cursor()
    try:
        cursor.execute(
            "SELECT ID, First_Name, Last_Name FROM Manager WHERE ID = %s AND Password = %s",
            (manager_id, password),
        )
        return cursor.fetchone()
    finally:
        cursor.close()


def customer_email_exists(email: str) -> bool:
    """
    Check if a customer with the given email already exists.
    """
    cursor = db_manager.get_cursor()
    try:
        cursor.execute("SELECT Mail FROM Costumer WHERE Mail = %s", (email,))
        return cursor.fetchone() is not None
    finally:
        cursor.close()


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
    cursor = db_manager.get_cursor()
    try:
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
    finally:
        cursor.close()


def guest_sign_in(email: str) -> None:
    """
    Ensure a guest with the given email exists in the Guest table.

    Flow:
    - If the email already exists in Guest -> do nothing.
    - If it does not exist -> insert a new row with this email.

    Assumes a table similar to:
        Guest(Mail VARCHAR PRIMARY KEY, Signup_date DATE, ...)
    """
    cursor = db_manager.get_cursor()
    try:
        # Check if guest already exists
        cursor.execute("SELECT Mail FROM Guest WHERE Mail = %s", (email,))
        if cursor.fetchone():
            return

        # Insert new guest
        cursor.execute(
            "INSERT INTO Guest (Mail) VALUES (%s)",
            (email,),
        )
    finally:
        cursor.close()


def search_flights(origin_airport: str, destination_airport: str, departure_date: str, passengers: int) -> List[Dict]:
    """
    Search for flights based on origin, destination, date, and required capacity.
    Uses Class_ID for seat identification in the Assigned table as per the schema.
    """
    cursor = db_manager.get_cursor()
    try:
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
    finally:
        cursor.close()

def get_ticket_details(order_id: int, email: str):
    """
    Fetches ticket details without passenger identity fields (Passport/DOB)
    as per the requirement to keep the Order table structure original.
    """
    cursor = db_manager.get_cursor()
    try:
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
    finally:
        cursor.close()

def get_user_order_history(email: str) -> List[Dict]:
    """
    Fetches order history for a user (customer or guest) including all statuses.
    Returns a list of orders with ticket details.
    """
    cursor = db_manager.get_cursor()
    try:
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
    finally:
        cursor.close()

def delete_ticket(order_id: int, email: str):
    """
    Handles cancellation logic using confirmed Departure_DateTime.
    """
    cursor = db_manager.get_cursor()
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
    finally:
        cursor.close()

def get_flight_seat_map(flight_id: int):
    cursor = db_manager.get_cursor()
    try:
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
    finally:
        cursor.close()

def get_flight_by_id(flight_id: int) -> Optional[Dict]:
    """
    Fetches details for a single flight to be used in the booking summary.
    """
    cursor = db_manager.get_cursor()
    try:
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
    finally:
        cursor.close()


def create_order_with_seats(flight_id: int, selected_seats: list, total_price: float,
                            customer_mail: str = None, guest_mail: str = None) -> int:
    """
    Creates a new order record.
    Note: Passport and DOB are NOT saved here anymore to comply with table constraints.
    """
    cursor = db_manager.get_cursor()
    try:
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
    finally:
        cursor.close()


def update_active_orders_to_completed() -> int:
    """
    Fetches all orders with status 'Active', joins with Flight table,
    and updates orders to 'Completed' status if the current datetime
    is strictly after the flight's departure datetime.
    
    Returns:
        int: The number of orders updated to 'Completed' status
    """
    cursor = db_manager.get_cursor()
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
                        (order_id,)
                    )
        
    except Exception as e:
        print(f"Database Error during order status update: {e}")
        return 0
    finally:
        cursor.close()