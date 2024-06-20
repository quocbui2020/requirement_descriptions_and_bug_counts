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

Get_Records_To_Process_Query = '''
    WITH Q1 AS (
        SELECT ROW_NUMBER() OVER(ORDER BY Hash_Id ASC) AS Row_Num
            ,Hash_Id
            ,Bug_Ids
            ,Commit_Link
            ,Is_Done_Parent_Child_Hashes
        FROM Bugzilla_Mozilla_ShortLog
        WHERE (Backed_Out_By IS NULL OR Backed_Out_By = '')
            AND (Bug_Ids IS NOT NULL AND Bug_Ids <> '' AND Bug_Ids <> '0')
            AND Is_Backed_Out_Commit = '0'
    )
    SELECT Row_Num
        ,Hash_Id
        ,Bug_Ids
        ,Commit_Link
        ,Is_Done_Parent_Child_Hashes
    FROM Q1
    WHERE Is_Done_Parent_Child_Hashes = 0 -- Include records have not been processed.
        AND Row_Num BETWEEN ? AND ?
'''

def get_records_to_process(start_row, end_row):
    global conn_str, Get_Records_To_Process_Query
    attempt_number = 1
    max_retries = 999 # max retry for deadlock issue.

    while attempt_number <= max_retries:
        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute(Get_Records_To_Process_Query, (start_row, end_row))
            rows = cursor.fetchall()
            return rows
        
        except pyodbc.Error as e:
            error_code = e.args[0]
            if error_code in ['40001', '40P01']:  # Deadlock error codes
                attempt_number += 1
                time.sleep(5)
                if attempt_number < max_retries:
                    continue
            print(f"Error - get_records_to_process({start_row}, {end_row}): {e}.")
            exit()

        except Exception as e:
            # Handle any exceptions
            print(f"Error - get_records_to_process({start_row}, {end_row}): {e}.")
            exit()

        finally:
            # Close the cursor and connection if they are not None
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    else:
        print("\nFailed after maximum retry attempts due to deadlock.")
        exit()

def is_resolved_bug(bug_id):
    global conn_str, Get_Records_To_Process_Query
    attempt_number = 1
    max_retries = 999 # max retry for deadlock issue.

    while attempt_number <= max_retries:
        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute(f"SELECT [resolution] WHERE id = ?", (bug_id))
            resolution = cursor.fetchone() # fetch one is enough because id is unique.

            if resolution == None or resolution != 'FIXED':
                return False
            return True
        
        except pyodbc.Error as e:
            error_code = e.args[0]
            if error_code in ['40001', '40P01']:  # Deadlock error codes
                attempt_number += 1
                time.sleep(5)
                if attempt_number < max_retries:
                    continue
            print(f"Error - is_resolved_bug({bug_id}): {e}.")
            exit()

        except Exception as e:
            # Handle any exceptions
            print(f"Error - is_resolved_bug({bug_id}): {e}.")
            exit()

        finally:
            # Close the cursor and connection if they are not None
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    else:
        print("\nFailed after maximum retry attempts due to deadlock.")
        exit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="")
    parser.add_argument('arg_1', type=int, help='Argument 1')
    parser.add_argument('arg_2', type=int, help='Argument 2')
    args = parser.parse_args()
    arg_1 = args.arg_1
    arg_2 = args.arg_2

    list_of_records = get_records_to_process(arg_1, arg_2)
    record_count = len(list_of_records)

    for record in list_of_records:
        Row_Num, Hash_Id, Bug_Ids, Commit_Link, Is_Done_Parent_Child_Hashes = record

        # Iterate through 'Bug_Ids' and check if any of them are 'resolved' bugs. If not, no need to process further
        is_resolved = is_resolved_bug(Bug_Ids)


        print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] Remainings: {str(record_count)}. Process hash {Hash_Id}...", end="", flush=True)
        # Quoc: check if bug ids in the hash id has been resolved or not.
        print("Done")
        record_count -= 1

print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] PROGRAM FINISHED. EXIT!")