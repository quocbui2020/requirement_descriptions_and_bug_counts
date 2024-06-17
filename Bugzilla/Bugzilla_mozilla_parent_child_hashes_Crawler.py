import requests
from datetime import datetime
from prettytable import PrettyTable
from bs4 import BeautifulSoup
import logging
from logging import info
from time import strftime, localtime
import pyodbc
import traceback
import re
import time
import argparse


# Connection string
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=QUOCBUI\\SQLEXPRESS;' \
           'DATABASE=ResearchDatasets;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

Get_Records_To_Process_Query = '''SELECT hash_id, Bug_Ids 
            FROM Bugzilla_Mozilla_ShortLog
            --JOIN Bugzilla ON
            WHERE (Backed_Out_By IS NULL OR Backed_Out_By = '')
                AND (Bug_Ids IS NOT NULL AND Bug_Ids <> '' AND Bug_Ids <> '0')
            ORDER BY Bug_Ids ASC
            OFFSET ? ROWS --offset
            FETCH NEXT ? ROWS ONLY; --limit
            '''

def get_records_to_process(offset, limit):
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute(Get_Records_To_Process_Query, str(offset), str(limit))
        rows = cursor.fetchall()
        return rows
    
    except Exception as e:
        # Handle any exceptions
        print(f"get_records_to_process({str(offset)}, {str(limit)}): {e}.")
        exit()

    finally:
         # Close the cursor and connection if they are not None
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="")
    parser.add_argument('offset', type=int, help='The offset')
    parser.add_argument('limit', type=int, help='The limit')
    args = parser.parse_args()
    offset = args.offset
    limit = args.limit

    list_of_records = get_records_to_process(offset, limit)
    record_count = len(list_of_records)

    for record in list_of_records:
        # Quoc: get hash_id from the record.
        print(f"[{strftime('%Y%m%d_%H-%M-%S', localtime())}] Total Remaining Records: {str(record_count)}. Process bug id {hash_id}...", end="", flush=True)
        # Quoc: check if bug ids in the hash id has been resolved or not.
        print("Done")
        record_count -= 1