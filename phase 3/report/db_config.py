
import pyodbc

#
SERVER_NAME = 'localhost'
DATABASE_NAME = 'TireShopDB'

def get_connection():

    try:

        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={SERVER_NAME};"
            f"DATABASE={DATABASE_NAME};"
            f"Trusted_Connection=yes;"
        )
        conn = pyodbc.connect(conn_str)
        return conn
    except pyodbc.Error as e:
        print(f"Error connecting to the database: {e}")
        return None