# https://dbdiagram.io/d/66bc97af8b4bb5230e1968f4
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
           'SERVER=QUOCBUI-PERSONA\\MSSQLSERVER01;' \
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
        ,[Q1_ID]
        ,[Q2_Hash_Id]
        ,[Q2_Mercurial_Type]
        ,[Q2_Is_Backed_Out_Changeset]
        ,[Q2_Backed_Out_By]
        ,[Q2_Bug_Ids]
        ,[Q2_Parent_Hashes]
        ,[Bugzilla_ID]
        ,[Bugzilla_Resolution]
        ,[Process_Status]
        ,[ID] --unique identifier
    FROM [Temp_Comment_Changesets_For_Process]
    WHERE [Process_Status] IS NULL
    AND [Task_Group] = ?
    AND [Row_Num] BETWEEN ? AND ?
    ORDER BY [Row_Num] ASC, [Q1_Hash_ID] ASC; 
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
            traceback.print_exc()
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
            traceback.print_exc()
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

# get_changeset_properties_rev: scrapping the changeset properties from the rev version: (backed_out_by, changeset_datetime, parent_hashes, child_hashes, file_changes)
def get_changeset_properties_rev(request_url):
    attempt_number = 1
    max_retries = 20 # if we attempt to make web request 20 times, I think it's safe to stop re-trying.
    response_status_code = 0
    response = None
    try:
        while attempt_number <= max_retries:
            try:
                # request_url = 'https://hg.mozilla.org/mozilla-central/rev/00002cc231f4' # Quoc: This is a test url
                response = requests.get(request_url)
            except requests.exceptions.RequestException as e: # Handle case when the request connection failed
                print(f"Failed request connection.\nRetrying in 10 seconds...", end="", flush=True)
                time.sleep(10)
                attempt_number += 1
                response = None
                continue

            response_status_code = response.status_code

            if response_status_code == 200 or response_status_code == 404:
                break
            else: # Handle case when request returns status code other than `200`
                print(f"{str(response.status_code)}.\nRetrying in 10 seconds...", end="", flush=True)
                time.sleep(10)
                attempt_number += 1

            if attempt_number == max_retries:
                print(f"Too many failed request attempts. Request url: {request_url}. Exit program.")
                return None
        
        if response:
            content = response.text
        else:
            content = None
            response_status_code = -1

        file_changes = []
        backed_out_by = ''
        changeset_datetime = ''
        parent_hashes = ''
        child_hashes = ''
        changeset_hash_id = ''
        changeset_number = ''
        changeset_summary_raw_content = ''
        bug_ids_from_summary = ''
        is_backed_out_changeset = False
        backout_hashes = ''

        ChangesetProperties = namedtuple('ChangesetProperties', ['backed_out_by', 'changeset_datetime', 'changeset_number', 'hash_id', 'parent_hashes', 'child_hashes', 'file_changes', 'response_status_code', 'changeset_summary_raw_content', 'bug_ids_from_summary', 'is_backed_out_changeset', 'backout_hashes'])
        # returnResult = ChangesetProperties(backed_out_by, changeset_datetime, changeset_number, changeset_hash_id, parent_hashes, child_hashes, file_changes, response_status_code, changeset_summary_raw_content, bug_ids_from_summary, is_backed_out_changeset, backout_hashes)

        if response_status_code == 404 or response_status_code == -1:
            return ChangesetProperties(backed_out_by, changeset_datetime, changeset_number, changeset_hash_id, parent_hashes, child_hashes, file_changes, response_status_code, changeset_summary_raw_content, bug_ids_from_summary, is_backed_out_changeset, backout_hashes)

        # Split the content
        diff_blocks = content.split(".1\"></a><span id=\"l")

        # Extract changeset number and changeset hash id:
        changeset_hash_id_match = re.search(r'<title>.+changeset\s(\d+):([0-9a-f]+)<\/title>', diff_blocks[0])
        changeset_number, changeset_hash_id = changeset_hash_id_match.group(1), changeset_hash_id_match.group(2) if changeset_hash_id_match else None

        # Extract the changeset summary (title):
        changeset_summary_match = re.search(r'<div class="page_body description">(.+?)</div>', diff_blocks[0], re.DOTALL) # re.DOTALL: single line
        changeset_summary_raw_content = changeset_summary_match.group(1) if changeset_summary_match else None

        # Remove HTML tags from the changeset summary content
        # changeset_summary_html_removed = re.sub(r'<.*?>', '', changeset_summary_raw_content).strip()

        # Extract the list of bug IDs from changeset summary/title:
        bug_id_matches = re.findall(r'show_bug.cgi\?id=(\d+)', changeset_summary_raw_content)
        if bug_id_matches:
            unique_bug_ids = set(bug_id_matches)  # Use a set to get unique bug IDs
            bug_ids_from_summary = " | ".join(sorted(unique_bug_ids))

        # Extract parent hashes
        parent_matches = re.findall(r'<td>parent \d+</td>\s*<td style="font-family:monospace">\s*<a class="list"\s*href="/.+/rev/([0-9a-f]+)">', diff_blocks[0]) # \s*: 0 or more white spaces, (): capturing group.
        parent_hashes = " | ".join(parent_matches) # Note: If no matched, it will be empty string.

        # Extract child hashes
        child_matches = re.findall(r'<td>child \d+</td>\s*<td style="font-family:monospace">\s*<a class="list"\s*href="/.+/rev/([0-9a-f]+)">', diff_blocks[0])
        child_hashes = " | ".join(child_matches) # Note: If no matched, it will be empty string.

        # Extract changeset datetime
        datetime_match = re.search(r'<td class="date age">(.*?)</td>', diff_blocks[0])
        changeset_datetime = datetime.strptime(datetime_match.group(1), '%a, %d %b %Y %H:%M:%S %z').strftime('%Y-%m-%d %H:%M %z') if datetime_match else None

        # quoc continue: if the changeset is backed out by, we still want to collect some info from it, right? think about it
        ## Need to retrieve full hash id of the changeset and the parent, child hashes.
        # Return when the changeset is backed out by other or 404 status code:
        backed_out_by_match = re.search(r'<strong>&#x2620;&#x2620; backed out by <a style="font-family: monospace" href="/.+/rev/([0-9a-f]+)">', diff_blocks[0]) # \s*: 0 or more white spaces, (): capturing group.
        backed_out_by = backed_out_by_match.group(1) if backed_out_by_match else ''
        if backed_out_by != None and backed_out_by != '':
            return ChangesetProperties(backed_out_by, changeset_datetime, changeset_number, changeset_hash_id, parent_hashes, child_hashes, file_changes, response_status_code, changeset_summary_raw_content, bug_ids_from_summary, is_backed_out_changeset, backout_hashes)

        # If it's backout changeset, extract back out hashes:
        content_block_contains_backout_hashes_match = re.search(r'<td>backs out<\/td>(.+?)<\/tr>',diff_blocks[0], re.DOTALL) # ? quantifier: matches as few characters as possible. This to ensure its search content stopped at the very first </tr> it encouters, not the last one.
        backouted_hashes_matches = re.findall(r'\/rev\/([0-9a-fA-F]+)">', content_block_contains_backout_hashes_match.group(0), re.DOTALL) if content_block_contains_backout_hashes_match else None
        backout_hashes = " | ".join(set(backouted_hashes_matches)) if backouted_hashes_matches else ''

        # Extract for backout keywords - indicate this is a backout changeset (re.IGNORECASE: case-insensitive):
        if backout_hashes != '' or re.search(r'\bback.{0,8}out\b', changeset_summary_raw_content, re.IGNORECASE): # If there is a keyword 'back out' in the summary content, then we know this is the backout changeset.
            is_backed_out_changeset = True
        else:
            is_backed_out_changeset = False

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
            
        return ChangesetProperties(
            backed_out_by, 
            changeset_datetime, 
            changeset_number, 
            changeset_hash_id, 
            parent_hashes, 
            child_hashes, 
            file_changes, 
            response_status_code, 
            changeset_summary_raw_content, 
            bug_ids_from_summary, 
            is_backed_out_changeset, 
            backout_hashes)

    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        exit()

def save_changeset_properties(changeset_hash_id, changeset_properties):
    global conn_str, save_changeset_parent_child_hashes_query, save_commit_file_query
    attempt_number = 1
    max_retries = 999  # Number of max attempts if fail sql execution (such as deadlock issue).
    max_connection_attempts = 10  # Number of max attempts to establish a connection.

    backed_out_by, changeset_datetime, changeset_number, hash_id, parent_hashes, child_hashes, file_changes, response_status_code, changeset_summary_raw_content, bug_ids_from_summary = changeset_properties  # No need 'changeset_datetime' because it has been mined?

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
                    if batch_count >= batch_size_limit:
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

        except Exception as e:
            print(f"save_changeset_properties({changeset_hash_id}, changeset_properties): {e}")
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
            print(f"Error - get_unprocessed_comment_changeset_records({str(task_group)}, {str(start_row)}, {str(end_row)}): {e}.")
            traceback.print_exc()
            exit()

        except Exception as e:
            # Handle any exceptions
            print(f"Error - get_unprocessed_comment_changeset_records({str(task_group)}, {str(start_row)}, {str(end_row)}): {e}.")
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

def get_bugzilla_mozilla_changesets_by_hash_id(hash_id):
    if not hash_id:
        return None
    
    global conn_str
    attempt_number = 1
    max_retries = 999 # max retry for deadlock issue.

    while attempt_number <= max_retries:
        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT [Hash_Id]
                    ,[Changeset_Summary]
                    ,[Bug_Ids] -- Found in the changeset title/summary
                    ,[Changeset_Link]
                    ,[Mercurial_Type]
                    ,[Changeset_Datetime]
                    ,[Is_Backed_Out_Changeset]
                    ,[Backed_Out_By]
                    ,[Parent_Hashes]
                    ,[Child_Hashes]
                FROM [dbo].[Bugzilla_Mozilla_Changesets]
                WHERE [Hash_Id] = ?
                ''', (hash_id))
            
            row = cursor.fetchone()
            if row:
                return namedtuple('ChangesetQueryResult', 
                    ['hash_id',
                    'changeset_summary', 
                    'bug_ids', 
                    'changeset_link', 
                    'mercurial_type', 
                    'changeset_datetime', 
                    'is_backed_out_changeset', 
                    'backed_out_by', 
                    'parent_hashes', 
                    'child_hashes'])(*row)
            else:
                return None
    
        except pyodbc.Error as e:
            error_code = e.args[0]
            if error_code in ['40001', '40P01']:  # Deadlock error codes
                attempt_number += 1
                time.sleep(5)
                if attempt_number < max_retries:
                    continue
            print(f"pyodbc.Error - get_bugzilla_mozilla_changesets_by_hash_id({hash_id}): {e}.")
            traceback.print_exc()
            exit()

        except Exception as e:
            # Handle any exceptions
            print(f"Error - get_bugzilla_mozilla_changesets_by_hash_id({hash_id}): {e}.")
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


def is_temp_comment_changeset_done(id):
    if not id:
        return False
    
    global conn_str
    attempt_number = 1
    max_retries = 5 # max retry for deadlock issue.

    while attempt_number <= max_retries:
        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT TOP 1 1
                FROM [dbo].[Temp_Comment_Changesets_For_Process]
                WHERE [ID] = ?
                    AND [Process_Status] IS NOT NULL
                ''', (id))
            
            row = cursor.fetchone()
            if row:
                return True
            else:
                return False
    
        except pyodbc.Error as e:
            error_code = e.args[0]
            if error_code in ['40001', '40P01']:  # Deadlock error codes
                attempt_number += 1
                time.sleep(5)
                if attempt_number < max_retries:
                    continue
            print(f"pyodbc.Error - is_temp_comment_changeset_done({id}): {e}.")
            traceback.print_exc()
            return False

        except Exception as e:
            # Handle any exceptions
            print(f"Error - is_temp_comment_changeset_done({id}): {e}.")
            traceback.print_exc()
            return False

        finally:
            # Close the cursor and connection if they are not None
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    else:
        print("\nFailed after maximum retry attempts due to deadlock.")
        return False


# save_comment_changeset_properties: this function saves all the properties of the comment changeset after finished processed:
# Save the `Bugzilla_Mozilla_Changesets.mercurial_type`, `Bugzilla_Mozilla_Changesets.Is_Processed`, `Bugzilla_Mozilla_Changesets.Bug_Ids` if it is empty (From Bugzilla table)
def save_comment_changeset_properties(process_status, temp_comment_changesets_for_process, changeset_properties, existing_bug_mozilla_changeset):
    global conn_str, save_bugzilla_mozilla_changesets, save_commit_file_query
    attempt_number = 1
    max_retries = 999 # max retry for deadlock issue.
    max_connection_attempts = 10  # Number of max attempts to establish a connection.

    while attempt_number <= max_retries:
        try:
            connection_attempt = 1

            while connection_attempt <= max_connection_attempts:
                try:
                    conn = pyodbc.connect(conn_str)
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


            query_count = 0
            save_comment_changeset_properties_queries = ''
            params = []

            #####################################################################
            ## Section: save `Temp_Comment_Changesets_For_Process` (Completed) ##
            #####################################################################
            # Note: All process row need to update this table.
            # 1. We do not want to update any columns in this table, just update columns that indicates the record has been processed.
            # 2. Since we don't update columns in this table, its values become obselete after processed.
            # 3. `Row_Num` represents each row in `Bugzilla_Mozilla_Comment_Changeset_Links`

            # Update temp_comment_changesets_for_process.q2_hash_id if there is a mismatch with changeset_properties.hash_id:
            updated_q2_hash_id = temp_comment_changesets_for_process.q2_hash_id
            if changeset_properties and changeset_properties.response_status_code == 200:
                updated_q2_hash_id = changeset_properties.hash_id
            elif existing_bug_mozilla_changeset and existing_bug_mozilla_changeset.hash_id:
                updated_q2_hash_id = existing_bug_mozilla_changeset.hash_id
                
            # cursor.execute('''
            #     UPDATE [Temp_Comment_Changesets_For_Process]
            #     SET [Is_Finished_Process] = 1
            #         ,[Process_Status] = ?
            #         ,[Q2_Hash_Id] = ?
            #     WHERE [ID] = ?
            #     ''', (process_status, updated_q2_hash_id, temp_comment_changesets_for_process.id))

            query_count += 1
            save_comment_changeset_properties_queries += '''
                UPDATE [Temp_Comment_Changesets_For_Process]
                SET [Is_Finished_Process] = 1
                    ,[Process_Status] = ?
                    ,[Q2_Hash_Id] = ?
                WHERE [ID] = ?;
                '''
            params.extend([process_status, updated_q2_hash_id, temp_comment_changesets_for_process.id])


            ##############################################################
            ## Section: save `Bugzilla_Mozilla_Comment_Changeset_Links` ##
            ##############################################################
            # Note: Each hg link found in the bug pages is a record in this table.
            # 0. This is a Q1.
            # 1. Hash id can be duplicated.
            # 2. A link can be founded in multiple bug pages (so, it can have multiple Temp_Comment_Changesets_For_Process.Bugzilla_ID).
            # 3. A link can have multiple mercurial types.

            is_valid_link = 1
            full_hash_id = temp_comment_changesets_for_process.q1_hash_id

            if changeset_properties:
                if changeset_properties.response_status_code != 200:
                    is_valid_link = 1
                else:
                    full_hash_id = changeset_properties.hash_id
            elif process_status == "Failed Url - Human Intervention":
                is_valid_link = 0

            # cursor.execute('''
            #     UPDATE [Bugzilla_Mozilla_Comment_Changeset_Links]
            #     SET [Hash_ID] = ?
            #         ,[Is_Valid_Link] = ?
            #         ,[Is_Processed] = 1
            #     WHERE [ID] = ?
            #     ''', (full_hash_id, is_valid_link, temp_comment_chakngesets_for_process.q1_id))

            query_count += 1
            save_comment_changeset_properties_queries +='''
                UPDATE [Bugzilla_Mozilla_Comment_Changeset_Links]
                SET [Hash_ID] = ?
                    ,[Is_Valid_Link] = ?
                    ,[Is_Processed] = 1
                WHERE [ID] = ?;
                '''
            params.extend([full_hash_id, is_valid_link, temp_comment_changesets_for_process.q1_id])

            if changeset_properties and changeset_properties.response_status_code != 200:
                # conn.commit() # Quoc: For testing in the development, I commented this out.
                cursor.execute("BEGIN TRANSACTION")
                cursor.execute(save_comment_changeset_properties_queries, params)
                cursor.execute("COMMIT")
                conn.commit()
                return


            ###############################################################################################
            ## Section: save `Bugzilla_Mozilla_Changesets` (Important, need this table to be more clean) ##
            ###############################################################################################
            # Note: One changeset could be mapped to multiple bug ids (bug ids mentioned in changeset title or bug page contains this changeset). So, we will label each bug id to indicate where they are found.
            #   `InTitle`: Bug id found in changeset summary title.
            #   `InComment`: Changeset found in the comment of the main bug page.
            #   For future: we can make another run to label the bug id that found in the resolved comment.

            ### Prepare 'bug_ids' for saving:
            bug_ids_list_to_be_saved = list()
            bug_ids_list_to_be_saved.append(str(temp_comment_changesets_for_process.bugzilla_id) + ":InComment")   # Let start here since we know that the record'll always have 'bugzilla_id'

            # Extract bug ids from the record in the database:
            if existing_bug_mozilla_changeset and existing_bug_mozilla_changeset.bug_ids:
                existing_bug_mozilla_changeset_bug_ids = existing_bug_mozilla_changeset.bug_ids.split(" | ")
                if ':' not in existing_bug_mozilla_changeset.bug_ids:
                    for e in existing_bug_mozilla_changeset_bug_ids:
                        bug_ids_list_to_be_saved.append(e + ":InTitle")
                else:
                    for e in existing_bug_mozilla_changeset_bug_ids:
                        bug_ids_list_to_be_saved.append(e)

            # Extract bug id from web request's changeset properties summary:
            if changeset_properties and changeset_properties.bug_ids_from_summary:
                bug_ids_from_changeset_properties = changeset_properties.bug_ids_from_summary.split(" | ")
                for element in bug_ids_from_changeset_properties:
                    bug_ids_list_to_be_saved.append(element + ":InTitle")

            bug_ids_list_to_be_saved = set(list(bug_ids_list_to_be_saved)) # Remove dups - Ensure unique elements.
            bug_ids_list_to_be_saved_string = " | ".join(bug_ids_list_to_be_saved)

            ### Prepare 'mercurial_type' for saving:
            mercurial_type_list_to_be_saved = list()
            mercurial_type_list_to_be_saved.append(temp_comment_changesets_for_process.q1_mercurial_type)

            if existing_bug_mozilla_changeset and existing_bug_mozilla_changeset.mercurial_type:
                mercurial_type_list = existing_bug_mozilla_changeset.mercurial_type.split(" | ")
                for element in mercurial_type_list:
                    mercurial_type_list_to_be_saved.append(element)
            
            mercurial_type_list_to_be_saved = list(set(mercurial_type_list_to_be_saved)) # Remove dups - Ensure unique elements.
            mercurial_type_list_string = " | ".join(mercurial_type_list_to_be_saved)

            if existing_bug_mozilla_changeset:
                query_count += 1
                save_comment_changeset_properties_queries += '''
                    UPDATE [Bugzilla_Mozilla_Changesets]
                    SET [Bug_Ids] = ?
                        ,[Mercurial_Type] = ?
                        ,[Modified_On] = SYSUTCDATETIME()
                    WHERE [Hash_ID] = ?;
                    '''
                params.extend([bug_ids_list_to_be_saved_string, mercurial_type_list_string, existing_bug_mozilla_changeset.hash_id])
            else:
                query_count += 1
                save_comment_changeset_properties_queries += '''
                INSERT INTO [dbo].[Bugzilla_Mozilla_Changesets]
                    ([Hash_Id]
                    ,[Changeset_Summary]
                    ,[Bug_Ids]
                    ,[Changeset_Link] --> '' (*empty string*)
                    ,[Mercurial_Type]
                    ,[Changeset_Datetime]
                    ,[Is_Backed_Out_Changeset]
                    ,[Backed_Out_By]
                    ,[Backout_Hashes]
                    ,[Parent_Hashes]
                    ,[Child_Hashes]
                    ,[Inserted_On] --> SYSUTCDATETIME()
                    ,[Task_Group] --> NULL
                    ,[Modified_On]) 
                VALUES
                    (?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME(), NULL, SYSUTCDATETIME());
                '''
                params.extend([
                    changeset_properties.hash_id, # Hash_Id
                    changeset_properties.changeset_summary_raw_content, # Changeset_Summary
                    bug_ids_list_to_be_saved_string, # Bug_Ids
                    mercurial_type_list_string, # Mercurial_Type
                    changeset_properties.changeset_datetime, # Changeset_Datetime
                    changeset_properties.is_backed_out_changeset, # Is_Backed_Out_Changeset
                    changeset_properties.backed_out_by, # Backed_Out_By
                    changeset_properties.backout_hashes, # Backout_Hashes
                    changeset_properties.parent_hashes, # Parent_Hashes
                    changeset_properties.child_hashes # Child_Hashes
                ])

            # save `Bugzilla_Mozilla_Changeset_Files` (Note that, we could have a very long list of file changes, therefore, should save in batches):
            query_size_limit = 100
            save_changeset_properties_query_batches = []
            

            if changeset_properties and changeset_properties.file_changes:
                for file_change in changeset_properties.file_changes:
                    previous_file_name, updated_file_name, file_status = file_change
                    
                    # cursor.execute(save_commit_file_query, (changeset_properties.hash_id, previous_file_name, updated_file_name, file_status))
                    if query_count <= query_size_limit:
                        query_count += 1
                        save_comment_changeset_properties_queries += save_commit_file_query + ";"
                        params.extend([changeset_properties.hash_id, previous_file_name, updated_file_name, file_status])
                    else:
                        save_changeset_properties_query_batches.append((save_comment_changeset_properties_queries, params)) # Add a query to the batch
                        save_comment_changeset_properties_queries = ''
                        params = []
                        query_count = 0 #Reset count

            # Add any remaining queries to the last batch
            if save_comment_changeset_properties_queries:
                save_changeset_properties_query_batches.append((save_comment_changeset_properties_queries, params))

            cursor.execute("BEGIN TRANSACTION")

            # Execute batches of queries
            for batch_query, batch_params in save_changeset_properties_query_batches:
                cursor.execute(batch_query, batch_params)

            # Commit the transaction
            cursor.execute("COMMIT")
            conn.commit() # Quoc: For testing in the development, I commented this out.

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

            print(f"Error - save_comment_changeset_properties(process_status, temp_comment_changesets_for_process, changeset_properties, existing_bug_mozilla_changeset): {e}")
            traceback.print_exc()
            exit()

        except Exception as e:
            # Handle any exceptions
            print(f"Error - save_comment_changeset_properties(process_status, temp_comment_changesets_for_process, changeset_properties, existing_bug_mozilla_changeset): {e}")
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

def start_scraper(task_group, start_row, end_row, scraper_type):
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

                changeset_properties = get_changeset_properties_rev(f"https://hg.mozilla.org{str(Changeset_Link)}")

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
                'q1_id', # foreign key to [Bugzilla_Mozilla_Comment_Changeset_Links]
                'q2_hash_id', 
                'q2_mercurial_type', 
                'q2_is_backed_out_changeset', 
                'q2_backed_out_by', 
                'q2_bug_ids', 
                'q2_parent_hashes',
                'bugzilla_id',
                'bugzilla_resolution', 
                'process_status',
                'id'
            ]

            records = get_unprocessed_comment_changeset_records(task_group, start_row, end_row)
            total_records = len(records)
            prev_temp_comment_changesets_for_process = None
            prev_changeset_properties = None
            remaining_records = total_records

            for i in range(total_records):
                # While True gives us ability to re-do the iteration. Found that something the data weren't being saved to the db correctly. For such cases, re-do it.
                re_run_iteration_count = 1
                while re_run_iteration_count <= 5:
                    # Define and Convert the record to namedtuple
                    namedtuple_type = namedtuple('Record', field_names)
                    temp_comment_changesets_for_process = namedtuple_type(*records[i]) # namedtuple type
                    process_status = 'Unknown'
                    changeset_properties = None
                    print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] Remainings: {str(remaining_records)}. Process row number {temp_comment_changesets_for_process.row_num}...", end="", flush=True)

                    lookup_hash_id = temp_comment_changesets_for_process.q2_hash_id
                    
                    # Case when the row_num is same as previous:
                    # How: (1) multiple `Bugzilla_ID` (row_num: 79190) - A changeset link found in multiple bugzilla pages.
                    if prev_temp_comment_changesets_for_process and (temp_comment_changesets_for_process.row_num == prev_temp_comment_changesets_for_process.row_num):
                        # Check the bug ids from the previous processed changeset to see if they are found in the title or not. If not in title, we can save this bug id for the current processed record.
                        process_status = "Skipped: Dup q1.row_num"
                        # Assuming that the current 'temp_comment_changesets_for_process' record has similar changeset than previous one:
                        if prev_changeset_properties and prev_changeset_properties.hash_id and not temp_comment_changesets_for_process.q2_hash_id:
                            lookup_hash_id = prev_changeset_properties.hash_id
                    
                    # Cases when current hash id is same as previous hash id (which means it has been processed):
                    # How: multiple `q2_mercurial_type` and/or `Bugzilla_ID`
                    elif prev_temp_comment_changesets_for_process and (prev_temp_comment_changesets_for_process.q1_hash_id.startswith(temp_comment_changesets_for_process.q1_hash_id) or temp_comment_changesets_for_process.q1_hash_id.startswith(prev_temp_comment_changesets_for_process.q1_hash_id)):
                        process_status = "Skipped: Dup q1_hash_id"
                        # Assuming that the current 'temp_comment_changesets_for_process' record has similar changeset than previous one:
                        if prev_changeset_properties and prev_changeset_properties.hash_id and not temp_comment_changesets_for_process.q2_hash_id:
                            lookup_hash_id = prev_changeset_properties.hash_id


                    # Get record of bugzilla_changeset by q2 hash id.
                    existing_bug_mozilla_changeset = get_bugzilla_mozilla_changesets_by_hash_id(lookup_hash_id)


                    if process_status != 'Unknown':
                        pass  # Do nothing
                    elif existing_bug_mozilla_changeset:
                        process_status = "Already Processed"

                    # Cases when we want to make a web request to scrap changeset info:
                    # Cover cases: (1) When q2 doesn't exist. (2) When it's not backout related changesets. (3) When bug_id='' (No bug id found in changeset title - We process it if it found in the bug comment).
                    # Handle: (1) When hash id is a changeset number.
                    # Goal: we don't want to scrap the changeset link again if it has been done.
                    elif not temp_comment_changesets_for_process.q2_parent_hashes and (temp_comment_changesets_for_process.q2_is_backed_out_changeset == False or temp_comment_changesets_for_process.q2_backed_out_by == None or temp_comment_changesets_for_process.q2_backed_out_by == ''):
                        # Make web request to get changeset properties:
                        changeset_properties = get_changeset_properties_rev(temp_comment_changesets_for_process.q1_full_link)

                        # Just to be safe, make another call to retrieve 'bugzilla_mozilla_changesets' from db for current record in case q2.hash_id has incorrect mapping:
                        if changeset_properties.response_status_code == 200 and not existing_bug_mozilla_changeset:
                            existing_bug_mozilla_changeset = get_bugzilla_mozilla_changesets_by_hash_id(changeset_properties.hash_id)

                        # Determine the process_status for processed changeset:
                        if changeset_properties.response_status_code == 404:
                            process_status = "Processed: 404"
                        elif changeset_properties.response_status_code == -1:
                            process_status = "Failed Url - Human Intervention"
                        elif (not changeset_properties.bug_ids_from_summary or changeset_properties.bug_ids_from_summary == '') and (not temp_comment_changesets_for_process.q2_bug_ids or temp_comment_changesets_for_process.q2_bug_ids == ''):
                            process_status = "Processed: No Bug Ids in Changeset Title"
                        elif changeset_properties.backed_out_by:
                            process_status = "Processed: Backed Out By" 
                        elif changeset_properties.is_backed_out_changeset:
                            process_status = "Processed: Backout Changeset"
                        else:
                            process_status = "Processed"
                    
                    # save to database:
                    save_comment_changeset_properties(process_status, temp_comment_changesets_for_process, changeset_properties, existing_bug_mozilla_changeset)

                    # Make another call to database to check making sure it's actually done. Found that some cases, the data weren't saved to the db, not sure why:
                    if is_temp_comment_changeset_done(temp_comment_changesets_for_process.id):
                        # Update previous record
                        prev_temp_comment_changesets_for_process = temp_comment_changesets_for_process
                        if process_status.startswith("Processed"):
                            prev_changeset_properties = changeset_properties

                        print(f"{process_status}")
                        remaining_records = total_records - i - 1
                        re_run_iteration_count = 1
                        
                        break
                    else:
                        time.sleep(3)
                        print(f"Record didn't save to database, Re-do it. Attempt: {re_run_iteration_count}/5")
                        re_run_iteration_count = re_run_iteration_count + 1
                        continue


##################################################################################################### 

if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description="")
    # parser.add_argument('arg_1', type=int, help='Argument 1')
    # parser.add_argument('arg_2', type=int, help='Argument 2')
    # parser.add_argument('arg_3', type=int, help='Argument 3')
    # parser_args = parser.parse_args()
    # task_group = parser_args.arg_1
    # start_row = parser_args.arg_2
    # end_row = parser_args.arg_3

    # Testing specific input arguments:
    task_group = 2   # Task group
    start_row = 0   # Start row
    end_row = 12500   # End row
    
    start_scraper(task_group, start_row, end_row, 'Changesets_From_Comments')

print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] PROGRAM FINISHED. EXIT!")
