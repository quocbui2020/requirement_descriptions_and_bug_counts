import requests
from datetime import datetime
#from prettytable import PrettyTable
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

get_records_to_process_query = '''
    WITH Q1 AS (
        SELECT ROW_NUMBER() OVER(ORDER BY Hash_Id ASC) AS Row_Num
            ,Hash_Id
            ,Bug_Ids
            ,Changeset_Link
            ,Is_Done_Parent_Child_Hashes
        FROM Bugzilla_Mozilla_Changesets
        WHERE (Backed_Out_By IS NULL OR Backed_Out_By = '')
            AND (Bug_Ids IS NOT NULL AND Bug_Ids <> '' AND Bug_Ids <> '0')
            AND Is_Backed_Out_Changeset = '0'
    )
    SELECT Row_Num
        ,Hash_Id
        ,Bug_Ids
        ,Changeset_Link
        ,Is_Done_Parent_Child_Hashes
    FROM Q1
    WHERE Is_Done_Parent_Child_Hashes = 0 -- Include records have not been processed.
        AND Row_Num BETWEEN ? AND ?
'''

save_changeset_parent_child_hashes_query = '''
    INSERT INTO [dbo].[Bugzilla_Mozilla_Changeset_Parent_Child_Hashes]
        ([Changeset_Hash]
        ,[Changeset_Datetime]
        ,[Bug_Ids]
        ,[Parent_Hashes]
        ,[Inserted_On])
    VALUES (?, ?, ?, ?, SYSUTCDATETIME())
'''

save_commit_file_query = '''
    INSERT INTO [dbo].[Bugzilla_Mozilla_Commit_File]
        ([Chsnageset_Hash_ID]
        ,[diff_git]
        ,[---]
        ,[+++]
        ,[File_Status]
        ,[Inserted_On])
    VALUES (?, ?, ?, ?, SYSUTCDATETIME())
'''


def get_records_to_process(start_row, end_row):
    global conn_str, get_records_to_process_query
    attempt_number = 1
    max_retries = 999 # max retry for deadlock issue.

    while attempt_number <= max_retries:
        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute(get_records_to_process_query, (start_row, end_row))
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
            traceback.print_exc()
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
    global conn_str, get_records_to_process_query
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
            traceback.print_exc()
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

def obtain_changeset_info(Changeset_Link):
    base_url = f"https://hg.mozilla.org"
    request_url = base_url + str(Changeset_Link)
    request_url = str.replace(request_url, 'rev', 'raw-rev')
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

        # Divide the content into block of `diff --git`
        diff_blocks = content.split("\ndiff --git ") 

        # Extract Changeset_Datetime
        datetime_match = re.search(r"^# Date (\d+ [-+]\d+)", diff_blocks[0], re.MULTILINE) # ^: indicates start of the string; \d+: digits; re.MULTILINE: indicates the content consists of multiple lines, so `^` will become "start of the line" (not start of the stirng)
        changeset_datetime = datetime_match.group(1) if datetime_match else None

        # Extract parent hashes
        parent_hashes = " | ".join(re.findall(r"# Parent\s+([0-9a-f]+)", diff_blocks[0]))

        # Extract file changes
        file_changes = []
        
        for block in diff_blocks[1:]:
            lines = block.splitlines() # Split by '\n'
            diff_git_line = lines[0] #ignore this line
            if lines[1].startswith("---") and lines[2].startswith("+++"):
                triple_neg_file_name = lines[1].split(" ", 1)[1]
                triple_pos_file_name = lines[2].split(" ", 1)[1]
                file_status = "modified"
            elif lines[1].startswith("deleted file mode"):
                triple_neg_file_name = lines[2].split(" ", 1)[1]
                triple_pos_file_name = lines[3].split(" ", 1)[1]
                file_status = "deleted"
            elif lines[1].startswith("rename from") and lines[2].startswith("rename to"):
                if len(lines) >= 4 and lines[3].startswith("---") and lines[4].startswith("+++"):
                    triple_neg_file_name = lines[3].split(" ", 1)[1]
                    triple_pos_file_name = lines[4].split(" ", 1)[1]
                    file_status = "renamed_modified"
                else:
                    triple_neg_file_name = lines[1].split(" ", 2)[2] #split at character " " with at most 2 times.
                    triple_pos_file_name = lines[2].split(" ", 2)[2]
                    file_status = "renamed"
            elif lines[1].startswith("new file mode"):
                triple_neg_file_name = lines[2].split(" ", 1)[1]
                triple_pos_file_name = lines[3].split(" ", 1)[1]
                file_status = "new"
            elif lines[1].startswith("copy from"):
                if "---" in lines[3] and "+++" in lines[4]:
                    triple_neg_file_name = lines[3].split(" ", 1)[1]
                    triple_pos_file_name = lines[4].split(" ", 1)[1]
                    file_status = "copied"
                else:
                    triple_neg_file_name = lines[1].split(" ", 1)[1]
                    triple_pos_file_name = lines[2].split(" ", 1)[1]
                    file_status = "copied"
            else:
                continue

            file_changes.append((triple_neg_file_name, triple_pos_file_name, file_status))

        return (changeset_datetime, parent_hashes, file_changes)

    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        exit()

def save_changeset_info(changeset_info_record):
    global conn_str, save_changeset_parent_child_hashes_query, save_commit_file_query
    attempt_number = 1
    max_retries = 999 # Number of max attempts if deadlock encountered.

    while attempt_number <= max_retries:
        try:
            changeset_datetime, parent_hashes, file_changes = changeset_info_record
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute(save_changeset_parent_child_hashes_query, ())

        except pyodbc.Error as e:
            error_code = e.args[0]
            if error_code in ['40001', '40P01']:  # Deadlock error codes
                attempt_number += 1
                print("Deadlock.")
                print(f"Attempt number: {str(attempt_number)}. Sleep for 5 second and try again...", end="", flush=True)
                time.sleep(5)
                if attempt_number < max_retries:
                    continue
            print(f"\nError: {e}")
            traceback.print_exc()
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


##################################################################################################### 

if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description="")
    # parser.add_argument('arg_1', type=int, help='Argument 1')
    # parser.add_argument('arg_2', type=int, help='Argument 2')
    # args = parser.parse_args()
    # start_row = args.arg_1
    # end_row = args.arg_2
    start_row = 4400
    end_row = 4400

    #list_of_records = get_records_to_process(start_row, end_row)
    list_of_records = []
    list_of_records.append(('4400', '26cce0d3e1030a3ede35b55e257dcf1e36539153', '840877', '/mozilla-central/rev/26cce0d3e1030a3ede35b55e257dcf1e36539153', False))
    
    record_count = len(list_of_records)

    for record in list_of_records:
        Row_Num, changeset_hash_Id, Bug_Ids, Changeset_Link, Is_Done_Parent_Child_Hashes = record

        print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] Remainings: {str(record_count)}. Process changeset {changeset_hash_Id}...", end="", flush=True)

        # Iterate through 'Bug_Ids' and check if any of them are 'resolved' bugs. If not, no need to process further
        list_of_bug_id = Bug_Ids.split(" | ")
        is_skipped = True
        for bug_id in list_of_bug_id:
            #is_resolved = is_resolved_bug(bug_id)
            is_resolved = True
            # If at least one of the bug in the changeset is 'resolved', then we will process this changeset
            if is_resolved == True:
                is_skipped = False
                break

        if is_skipped == True:
            print("Skipped - Bugs Not 'Resolved'")
            continue

        changeset_info_record = obtain_changeset_info(Changeset_Link)

        # Save to database:
        save_changeset_info(changeset_hash_Id, Bug_Ids, changeset_info_record)

        print("Done")
        record_count -= 1

print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] PROGRAM FINISHED. EXIT!")