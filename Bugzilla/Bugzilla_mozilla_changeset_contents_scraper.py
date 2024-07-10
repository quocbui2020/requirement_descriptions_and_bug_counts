import traceback
import time
import requests
import re
import pyodbc
import logging
import argparse
from time import strftime, localtime
from logging import info
from datetime import datetime
from collections import namedtuple
from bs4 import BeautifulSoup

# Connection string
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=QUOCBUI\\MSSQLSERVER01;' \
           'DATABASE=ResearchDatasets;' \
           'Connection Timeout=300;' \
           'Login Timeout=300;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

# get_unprocessed_records_from_mozilla_changesets_query: Get unprocessed changesets mined from the ShortLog
get_unprocessed_records_from_mozilla_changesets_query = '''
    WITH Q1 AS (
        SELECT ROW_NUMBER() OVER(ORDER BY Hash_Id ASC) AS Row_Num
            ,Hash_Id
            ,Bug_Ids
            ,Changeset_Link
            ,Parent_Hashes
            ,Backed_Out_By
            ,Task_Group
        FROM Bugzilla_Mozilla_Changesets
        WHERE (Bug_Ids IS NOT NULL AND Bug_Ids <> '' AND Bug_Ids <> '0')
            AND Is_Backed_Out_Changeset = '0'
    )
    SELECT Row_Num, Hash_Id, Bug_Ids, Changeset_Link, Parent_Hashes
    FROM Q1
    WHERE Parent_Hashes IS NULL -- Records have not been processed.
        AND (Backed_Out_By IS NULL OR Backed_Out_By = '')
        AND Task_Group = ?
        AND Row_Num BETWEEN ? AND ?
    ORDER BY Row_Num ASC
'''

# Required input args: Task group, start row number, end row number
get_unprocessed_comment_changesets_query = '''
    SELECT [Row_Num]
        ,[Task_Group]
        ,[Q1_Hash_ID]
        ,[Q1_Mercurial_Type]
        ,[Q1_Full_Link]
        ,[Q2_Hash_Id]
        ,[Q2_Mercurial_Type]
        ,[Q2_Is_Backed_Out_Changeset]
        ,[Q2_Backed_Out_By]
        ,[Q2_Bug_Ids]
        ,[Q2_Parent_Hashes]
        ,[Bugzilla_ID]
        ,[Bugzilla_Resolution]
        ,[Is_Processed]
    FROM [Temp_Comment_Changesets_For_Process]
    WHERE Is_Processed = 0
    AND Task_Group = ?
    AND Row_Num BETWEEN ? AND ?
    ORDER BY Row_Num ASC, Q1_Hash_ID ASC;
'''

save_changeset_parent_child_hashes_query = '''
    UPDATE [dbo].[Bugzilla_Mozilla_Changesets]
    SET [Parent_Hashes] = ?
    , [Child_Hashes] = ?
    WHERE [Hash_Id] = ?
'''

save_commit_file_query = '''
    MERGE [dbo].[Bugzilla_Mozilla_Changeset_Files] AS target
    USING (SELECT ? AS Changeset_Hash_ID, ? AS Previous_File_Name, ? AS Updated_File_Name) AS source
    ON (target.Changeset_Hash_ID = source.Changeset_Hash_ID
        AND target.Previous_File_Name = source.Previous_File_Name
        AND target.Updated_File_Name = source.Updated_File_Name)
    WHEN NOT MATCHED THEN
        INSERT ([Changeset_Hash_ID], [Previous_File_Name], [Updated_File_Name], [File_Status], [Inserted_On])
        VALUES (source.Changeset_Hash_ID, source.Previous_File_Name, source.Updated_File_Name, ?, SYSUTCDATETIME())
'''

def get_records_to_process(task_group, start_row, end_row):
    global conn_str, get_unprocessed_records_from_mozilla_changesets_query
    attempt_number = 1
    max_retries = 999 # max retry for deadlock issue.

    while attempt_number <= max_retries:
        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute(get_unprocessed_records_from_mozilla_changesets_query, (task_group, start_row, end_row))
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
    global conn_str
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

# obtain_changeset_properties_raw_rev: scrapping the changeset properties from the raw-rev version:
def obtain_changeset_properties_raw_rev(changeset_link):
    base_url = f"https://hg.mozilla.org"
    request_url = base_url + str(changeset_link)
    request_url = str.replace(request_url, 'rev', 'raw-rev')
    attempt_number = 1
    max_retries = 20

    try:
        while attempt_number <= max_retries:
            try:
                response = requests.get(request_url)
            except requests.exceptions.RequestException as e: # Handle case when the request connection failed
                print(f"Failed request connection.\nRetrying in 10 seconds...", end="", flush=True)
                time.sleep(10)
                attempt_number += 1
                continue

            if response.status_code == 200:  # OK
                break
            # elif response.status_code == 429:  # Code 429: Reach max request limit rate
            else:
                print(f"{str(response.status_code)}.\nRetrying in 10 seconds...", end="", flush=True)
                time.sleep(10)
                attempt_number += 1
            
            if attempt_number == max_retries:
                print(f"Too many failed request attempts. Request url: {request_url}. Exit program.")
                return None
            
        content = response.text

        # Divide the content into block of `diff --git`
        diff_blocks = content.split("\ndiff --git ") 

        # Extract Changeset_Datetime
        datetime_match = re.search(r"^# Date (\d+ [-+]\d+)", diff_blocks[0], re.MULTILINE) # ^: indicates start of the string; \d+: digits; re.MULTILINE: indicates the content consists of multiple lines, so `^` will become "start of the line" (not start of the stirng)
        changeset_datetime = datetime_match.group(1) if datetime_match else None

        # Extract parent hashes
        parent_hashes = " | ".join(re.findall(r"# Parent\s+([0-9a-f]+)", diff_blocks[0]))
        child_hashes = None # Can't extract child hashes in raw-rev version.

        # Extract file changes
        file_changes = []
        
        for block in diff_blocks[1:]:
            lines = block.splitlines() # Split by '\n'
            diff_git_line = lines[0]    # Ignore line[0]
            if lines[1].startswith("---") and lines[2].startswith("+++"):
                previous_file_name = lines[1].split(" ", 1)[1]
                updated_file_name = lines[2].split(" ", 1)[1]
                file_status = "modified"
            elif lines[1].startswith("deleted file mode"):
                previous_file_name = lines[2].split(" ", 1)[1]
                updated_file_name = lines[3].split(" ", 1)[1]
                file_status = "deleted"
            elif lines[1].startswith("rename from") and lines[2].startswith("rename to"):
                if len(lines) >= 4 and lines[3].startswith("---") and lines[4].startswith("+++"):
                    previous_file_name = lines[3].split(" ", 1)[1]
                    updated_file_name = lines[4].split(" ", 1)[1]
                    file_status = "renamed_modified"
                else:
                    previous_file_name = lines[1].split(" ", 2)[2] #split at character " " with at most 2 times.
                    updated_file_name = lines[2].split(" ", 2)[2]
                    file_status = "renamed"
            elif lines[1].startswith("new file mode"):
                previous_file_name = lines[2].split(" ", 1)[1]
                updated_file_name = lines[3].split(" ", 1)[1]
                file_status = "new"
            elif lines[1].startswith("copy from"):
                if "---" in lines[3] and "+++" in lines[4]:
                    previous_file_name = lines[3].split(" ", 1)[1]
                    updated_file_name = lines[4].split(" ", 1)[1]
                else:
                    previous_file_name = lines[1].split(" ", 1)[1]
                    updated_file_name = lines[2].split(" ", 1)[1]
                    
                file_status = "copied"
            else:
                continue

            file_changes.append((previous_file_name, updated_file_name, file_status))

        return (changeset_datetime, parent_hashes, child_hashes, file_changes)

    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        exit()

# obtain_changeset_properties_rev: scrapping the changeset properties from the rev version: (backed_out_by, changeset_datetime, parent_hashes, child_hashes, file_changes)
def obtain_changeset_properties_rev(request_url):
    attempt_number = 1
    max_retries = 20 # if we attempt to make web request 20 times, I think it's safe to stop re-trying.

    try:
        while attempt_number <= max_retries:
            try:
                response = requests.get(request_url)
            except requests.exceptions.RequestException as e: # Handle case when the request connection failed
                print(f"Failed request connection.\nRetrying in 10 seconds...", end="", flush=True)
                time.sleep(10)
                attempt_number += 1
                continue

            if response.status_code == 200:
                break
            else: # Handle case when request returns status code other than `200`
                print(f"{str(response.status_code)}.\nRetrying in 10 seconds...", end="", flush=True)
                time.sleep(10)
                attempt_number += 1

            if attempt_number == max_retries:
                print(f"Too many failed request attempts. Request url: {request_url}. Exit program.")
                return None
        
        content = response.text

        file_changes = []
        backed_out_by = ''
        changeset_datetime = ''
        parent_hashes = ''
        child_hashes = ''

        # Split the content
        diff_blocks = content.split(".1\"></a><span id=\"l")

        # Check if there is 'backed out by' message:
        backed_out_by_match = parent_matches = re.search(r'<strong>&#x2620;&#x2620; backed out by <a style="font-family: monospace" href="/mozilla-central/rev/([0-9a-f]+)">', diff_blocks[0]) # \s*: 0 or more white spaces, (): capturing group.
        backed_out_by = backed_out_by_match.group(1) if backed_out_by_match else None
        if backed_out_by != None and backed_out_by != '':
            return (backed_out_by, changeset_datetime, changeset_number, parent_hashes, child_hashes, file_changes)

        # Extract changest number:
        changeset_num_match = re.search(r'<td>changeset (\d+)</td>', diff_blocks[0])
        changeset_number = changeset_num_match.group(1) if changeset_num_match else None

        # Extract parent hashes
        parent_matches = re.findall(r'<td>parent \d+</td>\s*<td style="font-family:monospace">\s*<a class="list"\s*href="/mozilla-central/rev/([0-9a-f]+)">', diff_blocks[0]) # \s*: 0 or more white spaces, (): capturing group.
        parent_hashes = " | ".join(parent_matches) # Note: If no matched, it will be empty string.

        # Extract child hashes
        child_matches = re.findall(r'<td>child \d+</td>\s*<td style="font-family:monospace">\s*<a class="list"\s*href="/mozilla-central/rev/([0-9a-f]+)">', diff_blocks[0])
        child_hashes = " | ".join(child_matches) # Note: If no matched, it will be empty string.

        # Extract changeset datetime
        datetime_match = re.search(r'<td class="date age">(.*?)</td>', diff_blocks[0])
        changeset_datetime = datetime_match.group(1) if datetime_match else None

        # Extract file changes
        for block in diff_blocks[1:]:
            lines = block.splitlines()

            if "---" in lines[0] and "+++" in lines[1]:
                previous_file_name = re.search(r'--- (.*)<', lines[0]).group(1)  # .*: 0 or more characters. 
                updated_file_name = re.search(r'\+\+\+ (.*)<', lines[1]).group(1)
                file_status = "modified"
            elif "deleted file mode" in lines[0]:
                if '">index' in lines[1]:   #Example case '7fe80c3c0f1ce84d05708d448f0394c04890f4d6' with content: <a href="#l7.2"></a><span id="l7.2">index ce953a292517f8fc9f584b7d844e1c0eafe2ef85..0000000000000000000000000000000000000000</span>
                    previous_file_name = re.search(r'">index ([a-fA-F0-9]+)\.\.', lines[1]).group(1)
                    updated_file_name = re.search(r'\.\.([a-fA-F0-9]+)<', lines[1]).group(1)
                elif '</pre>' in lines[0]: #Case '6002440818d91011fb0a1753def417dba834f529'
                    continue
                else:
                    previous_file_name = re.search(r'--- (.*)<', lines[1]).group(1)
                    updated_file_name = re.search(r'\+\+\+ (.*)<', lines[2]).group(1)
                file_status = "deleted"
            elif "new file mode" in lines[0]:
                if '">index' in lines[1]:   #Example case '000bf107254d873d4a1d1d0401274b97b5ce9ac8' (issue same as 'deleted' one)
                    previous_file_name = re.search(r'">index ([a-fA-F0-9]+)\.\.', lines[1]).group(1)
                    updated_file_name = re.search(r'\.\.([a-fA-F0-9]+)<', lines[1]).group(1)
                elif '</pre>' in lines[0]:
                    continue    #Skip it. #Example case '000bf107254d873d4a1d1d0401274b97b5ce9ac8' at line 22946 with content: <a href="#l82.1"></a><span id="l82.1">new file mode 100644</span></pre>
                else:
                    previous_file_name = re.search(r'--- (.*)<', lines[1]).group(1)
                    updated_file_name = re.search(r'\+\+\+ (.*)<', lines[2]).group(1)
                file_status = "new"
            elif "rename from" in lines[0] and "rename to" in lines[1]:
                if "---" in lines[2] and "+++" in lines[3]:
                    previous_file_name = re.search(r'--- (.*)<', lines[2]).group(1)
                    updated_file_name = re.search(r'\+\+\+ (.*)<', lines[3]).group(1)
                    file_status = "renamed_modified"
                else:
                    previous_file_name = re.search(r'rename from (.*)<', lines[0]).group(1)
                    updated_file_name = re.search(r'rename to (.*)<', lines[1]).group(1)
                    file_status = "renamed"
            elif "copy from" in lines[0] and "copy to" in lines[1]:
                if "---" in lines[2] and "+++" in lines[3]:
                    previous_file_name = re.search(r'--- (.*)<', lines[2]).group(1)
                    updated_file_name = re.search(r'\+\+\+ (.*)<', lines[3]).group(1)
                    file_status = "copied_modified"
                else:
                    previous_file_name = re.search(r'copy from (.*)<', lines[0]).group(1)
                    updated_file_name = re.search(r'copy to (.*)<', lines[1]).group(1)
                    file_status = "copied"
            else:
                continue

            file_changes.append((previous_file_name, updated_file_name, file_status))

        return (backed_out_by, changeset_datetime, changeset_number, parent_hashes, child_hashes, file_changes)

    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        exit()

def save_changeset_properties(changeset_hash_id, changeset_properties):
    global conn_str, save_changeset_parent_child_hashes_query, save_commit_file_query
    attempt_number = 1
    max_retries = 999  # Number of max attempts if fail sql execution (such as deadlock issue).
    max_connection_attempts = 10  # Number of max attempts to establish a connection.

    backed_out_by, changeset_datetime, changeset_number, parent_hashes, child_hashes, file_changes = changeset_properties  # No need 'changeset_datetime' because it has been mined?

    while attempt_number <= max_retries:
        try:
            # Attempt to establish a connection with retry logic
            connection_attempt = 1

            while connection_attempt <= max_connection_attempts:
                try:
                    conn = pyodbc.connect(conn_str)  # Increase timeout value
                    break
                except pyodbc.Error as conn_err:
                    if conn_err.args[0] in ['08S01']: # The connection is broken and recovery is not possible.
                        connection_attempt += 1
                        print(f"08S01.\nConnection attempt {connection_attempt} failed. Retrying in 5 seconds...", end="", flush=True)
                        time.sleep(5)
                    else:
                        raise conn_err
            else:
                raise Exception("Failed to establish a connection after multiple attempts.")

            cursor = conn.cursor()

            save_changeset_properties_query_batches = []
            batch_count = 0
            batch_size_limit = 100

            # Build batches of queries
            save_changeset_properties_queries = ''
            params = []

            # Check 'backed_out_by' field:
            if backed_out_by:
                save_changeset_properties_queries += "UPDATE [Bugzilla_Mozilla_Changesets] SET [Backed_Out_By] = ? WHERE Hash_Id = ?;"
                params.extend([backed_out_by, changeset_hash_id])
            else:
                # Save parent hashes:
                save_changeset_properties_queries += save_changeset_parent_child_hashes_query + ";"
                params.extend([parent_hashes, child_hashes, changeset_hash_id])

                # Save commit files in batches to optimize the resources (prevent a process to hold resource for too long).
                # Some changeset consists of 1000+ commit files. So, for each file, run cursor.execute() to hold the resource lock is not optimal.
                # Optimal way: Create a list of batches, and concatenate 100 queries in each batch (don't want to exceed string limit), and then, iterate through each batch to run cursor.execute().
                for file_change in file_changes:
                    previous_file_name, updated_file_name, file_status = file_change
                    save_changeset_properties_queries += save_commit_file_query + ";"
                    params.extend([changeset_hash_id, previous_file_name, updated_file_name, file_status])

                    batch_count += 1
                    if batch_count == batch_size_limit:
                        save_changeset_properties_query_batches.append((save_changeset_properties_queries, params)) # Add a query to the batch
                        save_changeset_properties_queries = ''
                        params = []
                        batch_count = 0

            # Add any remaining queries to the last batch
            if save_changeset_properties_queries:
                save_changeset_properties_query_batches.append((save_changeset_properties_queries, params))

            # Start a transaction
            cursor.execute("BEGIN TRANSACTION")

            # Execute batches of queries
            for batch_query, batch_params in save_changeset_properties_query_batches:
                cursor.execute(batch_query, batch_params)

             # Commit the transaction
            cursor.execute("COMMIT")
            conn.commit() 

            if backed_out_by:
                return "Backed Out"
            else:
                return "Done"

        except pyodbc.Error as e:
            error_code = e.args[0]
            cursor.execute("ROLLBACK TRANSACTION")  # Rollback to the beginning of the transaction
            if error_code in ['40001', '40P01']:  # Deadlock error codes
                attempt_number += 1
                print(f"Deadlock.\nAttempt number: {attempt_number}. Retrying in 5 seconds...", end="", flush=True)
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

def get_unprocessed_comment_changeset_records(task_group, start_row, end_row):
    global conn_str, get_unprocessed_comment_changesets_query
    attempt_number = 1
    max_retries = 999 # max retry for deadlock issue.

    while attempt_number <= max_retries:
        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute(get_unprocessed_comment_changesets_query, (task_group, start_row, end_row))
            rows = cursor.fetchall()
            return rows
        
        except pyodbc.Error as e:
            error_code = e.args[0]
            if error_code in ['40001', '40P01']:  # Deadlock error codes
                attempt_number += 1
                time.sleep(5)
                if attempt_number < max_retries:
                    continue
            print(f"Error - get_unprocessed_comment_changeset_records({task_group}, {start_row}, {end_row}): {e}.")
            exit()

        except Exception as e:
            # Handle any exceptions
            print(f"Error - get_unprocessed_comment_changeset_records({task_group}, {start_row}, {end_row}): {e}.")
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


# save_comment_changeset_properties: this function saves all the properties of the comment changeset after finished processed:
# Save the `Bugzilla_Mozilla_Changesets.mercurial_type`, `Bugzilla_Mozilla_Changesets.Is_Processed`, `Bugzilla_Mozilla_Changesets.Bug_Ids` if it is empty (From Bugzilla table)
def save_comment_changeset_properties():
    global should_not_process_query, conn_str

    attempt_number = 1
    max_retries = 999 # max retry for deadlock issue.

    while attempt_number <= max_retries:
        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute('''UPDATE FROM ''', (f"{hash_id}%"))
            queryResult = cursor.fetchone()

            if not queryResult or queryResult[0] == None:
                return True
            return False
        
        except pyodbc.Error as e:
            error_code = e.args[0]
            if error_code in ['40001', '40P01']:  # Deadlock error codes
                attempt_number += 1
                time.sleep(5)
                if attempt_number < max_retries:
                    continue
            print(f"Error - should_process({hash_id}): {e}.")
            exit()

        except Exception as e:
            # Handle any exceptions
            print(f"Error - should_process({hash_id}): {e}.")
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

def start_scraper(parser_args, scraper_type):
    task_group = parser_args.arg_1
    start_row = parser_args.arg_2
    end_row = parser_args.arg_3

    match scraper_type:
        # Process changesets found in the ShortLog (Onyl Mozilla-Central at the moment)
        case 'Changesets_From_ShortLog':
            list_of_records = get_records_to_process(task_group, start_row, end_row)
            record_count = len(list_of_records)

            for record in list_of_records:
                Row_Num, changeset_hash_Id, Bug_Ids, Changeset_Link, Parent_Hashes = record

                print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] Remainings: {str(record_count)}. Scraping properties of {changeset_hash_Id}...", end="", flush=True)

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

                changeset_properties = obtain_changeset_properties_rev(f"https://hg.mozilla.org{str(Changeset_Link)}")

                # Save to database:
                complete_status = save_changeset_properties(changeset_hash_Id, changeset_properties)

                print(f"{complete_status}") # either 'Done' or 'Backed Out'
                record_count -= 1

        # Process changesets found in every comments per bug:
        case 'Changesets_From_Comments':
            # Define the field names (The order of these fields must match the order of the columns in database):
            field_names = [
                'row_num', 
                'task_group', 
                'q1_hash_id', 
                'q1_mercurial_type', 
                'q1_full_link', 
                'q2_hash_id', 
                'q2_mercurial_type', 
                'q2_is_backed_out_changeset', 
                'q2_backed_out_by', 
                'q2_bug_ids', 
                'q2_parent_hashes', 
                'bugzilla_resolution', 
                'is_processed'
            ]

            records = get_unprocessed_comment_changeset_records(task_group, start_row, end_row)
            record_count = len(records)

            prev_record = None
            prev_changeset_saved_info = None

            for i in range(record_count):
                # Define and Convert the record to namedtuple
                namedtuple_type = namedtuple('Record', field_names)
                record = namedtuple_type(*records[i]) # namedtuple type
                print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] Remainings: {str(record_count)}. Scraping properties of {changeset_hash_Id}...", end="", flush=True)

                # Case when the row_num is same as previous:
                # How: (1) multiple `Bugzilla_ID` (row_num: 79190)
                if prev_record and (record.row_num == record.row_num):
                    # Check the bug ids from the previous processed changeset to see if they are found in the title or not. If not in title, we can save this bug id for the current processed record.
                    #if prev_changeset_saved_info and 
                    # TODO: Quoc - Finish this after the other cases.
                    return
                
                # Case when current hash id is same as previous hash id (which means it has been processed):
                # How: multiple `q2_mercurial_type` and/or `Bugzilla_ID`
                elif prev_record and (record.q1_hash_id in prev_record.q1_hash_id or prev_record.q1_hash_id in record.q1_hash_id):
                    # TODO: Quoc - Finish this after the other cases.
                    return
                
                # Case when we want to make a web request to scrap changeset info:
                # Cover cases: (1) When q2 doesn't exist. (2) When it's not backout related changesets.
                # Handle: (1) When hash id is a changeset number.
                elif record.q2_parent_hashes and (record.q2_is_backed_out_changeset == 0 or record.q2_is_backed_out_changeset == ''):
                    obtain_changeset_properties_rev(record.q1_full_link)

                    return

                # Update previous record
                prev_record = record

                

##################################################################################################### 

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="")
    parser.add_argument('arg_1', type=int, help='Argument 1')
    parser.add_argument('arg_2', type=int, help='Argument 2')
    parser.add_argument('arg_3', type=int, help='Argument 3')
    parser_args = parser.parse_args()
    
    start_scraper(parser_args, 'Changeset_Records_From_Comments')

print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] PROGRAM FINISHED. EXIT!")

