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

save_changeset_info_query = '''
    INSERT INTO [dbo].[Bugzilla_Mozilla_Changeset_Parent_Child_Hashes]
        ([Changeset_Hash]
        ,[Changeset_Datetime]
        ,[Bug_Ids]
        ,[Parent_Hash]
        ,[Child_Hash]
        ,[File_Names]
        ,[Inserted_On])
    VALUES (?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
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

            cursor.execute(f"SELECT [resolution] from Bugzilla WHERE id = ?", (bug_id))
            queryResult = cursor.fetchone() # fetch one is enough because id is unique.

            # If query yields no data or the resolution is null or not 'FIXED', return false. Otherwise, return true
            if not queryResult or queryResult[0] == None or queryResult[0] != 'FIXED':
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

def obtain_changeset_info(Commit_Link):
    base_url = f"https://hg.mozilla.org"
    request_url = base_url + str(Commit_Link)
    attempt_number = 1
    max_attempt = 5

    try:
        while attempt_number <= max_attempt:
            response = requests.get(request_url)
            if response.status_code == 200:
                break
            elif response.status_code == 429:
                print("Failed with 429 code")
                print("Sleep for 10s and retry...", end="", flush=True)
                time.sleep(10)
                attempt_number += 1
            else:
                print(f"Request has status code other than 200. Request url: {request_url}.")
                exit() # if code status is not 200 or 429. It should require human interaction.
            
            if attempt_number == max_attempt:
                print(f"Failed too many request attempts. Status code: {response.status_code}. Exit program.")
                return None
            
            content = response.text

            # Extract parents hashes and file names
            # Confirm again this is not 'backed out' changeset. Example: https://hg.mozilla.org/mozilla-central/raw-rev/9bb52c6580dd4eea416e1a2b7bce7635c3acf84d . Not possible to re-confirm in 'raw' view.
            # Confirm again this should only have 1 parent, if changeset has 2 parents and associated with at least one bug --> require human inspection.
            # Pay attention to keywords: 'rename', 'deleted file mode', 'new file mode', 'rename from', 'rename to', 'new file mode', 'copy from', 'copy to' (Do not consider '-/+diff --git'). Good example for all those keywords: https://hg.mozilla.org/mozilla-central/raw-rev/26cce0d3e1030a3ede35b55e257dcf1e36539153 
            # file_modes: modified, deleted, new, renamed, renamed_modified


    except Exception as e:
        print(f"Error: {e}")
        exit()

if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description="")
    # parser.add_argument('arg_1', type=int, help='Argument 1')
    # parser.add_argument('arg_2', type=int, help='Argument 2')
    # args = parser.parse_args()
    # start_row = args.arg_1
    # end_row = args.arg_2
    start_row = 4399
    end_row = 4400

    list_of_records = get_records_to_process(start_row, end_row)
    record_count = len(list_of_records)

    for record in list_of_records:
        Row_Num, changeset_hash_Id, Bug_Ids, Commit_Link, Is_Done_Parent_Child_Hashes = record

        print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] Remainings: {str(record_count)}. Process changeset {changeset_hash_Id}...", end="", flush=True)

        # Iterate through 'Bug_Ids' and check if any of them are 'resolved' bugs. If not, no need to process further
        list_of_bug_id = Bug_Ids.split(" | ")
        is_skipped = True
        for bug_id in list_of_bug_id:
            is_resolved = is_resolved_bug(bug_id)
            # If at least one of the bug in the changeset is 'resolved', then we will process this changeset
            if is_resolved == True:
                is_skipped = False
                break

        if is_skipped == True:
            print("Skipped (Bugs Not 'Resolved')")
            continue

        
        data_tuple = obtain_changeset_info(Commit_Link)

        print("Done")
        record_count -= 1

print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] PROGRAM FINISHED. EXIT!")