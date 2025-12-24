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


def search_flights(origin_airport: str, destination_airport: str, departure_date: str) -> List[Dict]:
    """
    Search for flights by origin airport, destination airport, and departure date.
    
    Parameters:
        origin_airport: Airport code (e.g., "TLV")
        destination_airport: Airport code
        departure_date: Date string in format YYYY-MM-DD
    
    Returns:
        List of dictionaries containing flight details:
        - flight_id: Flight ID
        - departure_datetime: Departure date/time
        - arrival_datetime: Arrival date/time
        - origin_airport: Origin airport code
        - destination_airport: Destination airport code
        - business_seat_price: Business class seat price
        - economy_seat_price: Economy class seat price
        - plane_id: Plane ID
    """
    with get_db_connection() as cursor:
        cursor.execute(
            """
            SELECT 
                f.ID,
                f.Departure_DateTime,
                f.Arrival_DateTime,
                f.Path_Origin_Airport,
                f.Path_Dest_Airport,
                f.Business_Seat_Price,
                f.Economy_Seat_Price,
                f.Plane_ID
            FROM Flight f
            WHERE f.Path_Origin_Airport = %s
              AND f.Path_Dest_Airport = %s
              AND DATE(f.Departure_DateTime) = %s
            ORDER BY f.Departure_DateTime ASC
            """,
            (origin_airport.upper(), destination_airport.upper(), departure_date),
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
    Fetches comprehensive booking details including status and total price.
    Updated to include Total_Price to fix the Jinja2 UndefinedError in the frontend.
    """
    with get_db_connection() as cursor:
        # SQL Query includes all necessary fields for the management UI
        query = """
            SELECT 
                o.Order_ID, 
                f.Path_Origin_Airport, 
                f.Path_Dest_Airport, 
                f.Departure_DateTime,
                a.Class_ID,
                o.Status,
                o.Total_Price
            FROM `Order` o
            LEFT JOIN Order_contains_Flight ocf ON o.Order_ID = ocf.Order_Order_ID
            LEFT JOIN Flight f ON ocf.Flight_ID = f.ID
            LEFT JOIN Assigned a ON o.Order_ID = a.Order_ID
            WHERE o.Order_ID = %s AND (o.Guest_Mail = %s OR o.Costumer_Mail = %s)
        """
        try:
            cursor.execute(query, (order_id, email, email))
            row = cursor.fetchone()

            if row:
                # Mapping the database row to a dictionary for easy template access
                return {
                    "Ticket_ID": row[0],
                    "Origin": row[1] if row[1] else "N/A",
                    "Destination": row[2] if row[2] else "N/A",
                    "Departure_Time": row[3].strftime("%Y-%m-%d %H:%M") if row[3] else "TBD",
                    "Seat_ID": row[4] if row[4] else "Not Assigned",
                    "Status": row[5],
                    "Total_Price": row[6]  # Critical for showing the 5% penalty fee
                }
            return None
        except Exception as e:
            print(f"Error fetching ticket details: {e}")
            return None

def delete_ticket(order_id: int, email: str):
    """
    Handles the cancellation logic:
    1. Validates that the cancellation occurs at least 36 hours before departure.
    2. Updates the order status to 'Costumer Cancelation'.
    3. Calculates a 5% penalty fee and updates the Total_Price.
    4. Frees up the assigned seat.

    Returns: (bool, string) -> (Success status, Message for the user)
    """
    with get_db_connection() as cursor:
        try:
            # Fetch flight departure time, current price, and order status
            query = """
                SELECT f.Departure_DateTime, o.Total_Price, o.Status
                FROM `Order` o
                JOIN Order_contains_Flight ocf ON o.Order_ID = ocf.Order_Order_ID
                JOIN Flight f ON ocf.Flight_ID = f.ID
                WHERE o.Order_ID = %s AND (o.Guest_Mail = %s OR o.Costumer_Mail = %s)
            """
            cursor.execute(query, (order_id, email, email))
            result = cursor.fetchone()

            if not result:
                return False, "Order not found or access denied."

            departure_time, current_price, status = result

            if status != 'Active':
                return False, "This order is already cancelled."

            # Time Logic: Check if current time is at least 36 hours before departure
            now = datetime.now()
            if departure_time - now < timedelta(hours=36):
                return False, "Cancellation is only allowed up to 36 hours before the flight."

            # Penalty Logic: Calculate 5% of the original price
            # Converting to float to ensure mathematical precision
            penalty_fee = float(current_price) * 0.05

            # Database Update: Update status/price and remove seat assignment
            # Update Order table
            cursor.execute("""
                UPDATE `Order` 
                SET Status = 'Costumer Cancelation', Total_Price = %s 
                WHERE Order_ID = %s
            """, (penalty_fee, order_id))

            # Remove from Assigned table to make the seat available
            cursor.execute("DELETE FROM Assigned WHERE Order_ID = %s", (order_id,))

            return True, f"Order successfully cancelled. A 5% fee (${penalty_fee:.2f}) was charged."

        except Exception as e:
            print(f"Database Error during cancellation: {e}")
            return False, "An internal error occurred. Please try again later."