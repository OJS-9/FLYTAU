import mysql.connector
from contextlib import contextmanager
import os
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
            database=os.getenv("DB_NAME")
        )
        cursor = mydb.cursor()
        yield cursor
    finally:
        if cursor:
            cursor.close()
        if mydb:
            mydb.close()