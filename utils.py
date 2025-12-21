import mysql.connector
from contextlib import contextmanager
import os
from typing import Optional, Tuple, List, Dict
from dotenv import load_dotenv

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

