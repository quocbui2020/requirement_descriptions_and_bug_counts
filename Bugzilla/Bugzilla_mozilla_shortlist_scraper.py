# Note, at this moment, we set backed_out_by=null. After finished crawling through all the shortlogs, we will update 'backed_out_by' field based on the commit's datetime as well.
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
           'SERVER=QUOCBUI\\MSSQLSERVER01;' \
           'DATABASE=ResearchDatasets;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

# Prepare the SQL queries:
insert_Bugzilla_Mozilla_Changesets_query = '''
    INSERT INTO [dbo].[Bugzilla_Mozilla_Changesets]
        ([Hash_Id]
        ,[Changeset_Summary]
        ,[Bug_Ids]
        ,[Changeset_Link]
        ,[Mercurial_Type]
        ,[Changeset_Datetime]
        ,[Is_Backed_Out_Changeset]
        ,[Backed_Out_By]
        ,[Does_Required_Human_Inspection]
        ,[Inserted_On])
    VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
'''

create_bugzilla_error_log_query = '''
    INSERT INTO [dbo].[Bugzilla_Error_Log]
        ([ID]
        ,[Bug_ID]
        ,[Request_Url]
        ,[Error_Messages]
        ,[Detail_Error_Message]
        ,[Offset]
        ,[Limit]
        ,[Completed]
        ,[inserted_on])
    VALUES
        (NEWID(), ?, ?, ?, ?, ?, ?, 0, SYSUTCDATETIME())
'''

get_backout_commits_query = '''
WITH Q1 AS(
	SELECT ROW_NUMBER() OVER(ORDER BY Hash_Id ASC) AS Row_Num, Hash_Id, Changeset_Link, Backout_Hashes FROM Bugzilla_Mozilla_Changesets
	WHERE Is_Backed_Out_Changeset = 1
	AND Bug_Ids <> ''
)
SELECT Hash_Id, Changeset_Link, Row_Num, Backout_Hashes from Q1
WHERE Row_Num BETWEEN ? AND ?
AND Backout_Hashes IS NULL -- Include records have not been processes
ORDER BY Row_Num ASC; 
'''

save_backout_hashes_query = '''
    UPDATE [dbo].[Bugzilla_Mozilla_Changesets]
    SET Backout_Hashes = ?
    WHERE Backout_Hashes IS NULL and Hash_Id = ?
'''

set_back_out_by_field_query = '''
    UPDATE Bugzilla_Mozilla_Changesets
    SET Backed_Out_By = ?
    WHERE Hash_Id = ?
'''

def crawl_mozilla_central_shortlog(hash_id, max_retries=5):
    global conn_str, create_bugzilla_error_log_query
    request_url = f"https://hg.mozilla.org/mozilla-central/shortlog/{hash_id}"
    retries = 0

    try:
        while retries < max_retries:
            response = requests.get(request_url)
            if response.status_code == 200:
                break
            elif response.status_code == 429:
                print("Too many requests. Sleeping for 10 seconds before retrying...")
                time.sleep(10)
                retries += 1
            else:
                print(f"Failed to retrieve the webpage. Status code: {response.status_code}")
                return []

        if retries == max_retries:
            print("Max retries reached. Exiting.")
            return []

        content = response.text
        changeset_info_list = []

        # Define the regular expression pattern for extracting rows
        row_pattern = re.compile(
            r'<tr class="parity[01]">.*?<a href="(/mozilla-central/rev/.*?)">diff</a>.*?<i class="age">(.*?)</i>.*?<strong><cite>(.*?)</cite> - (.*?)</strong>', re.DOTALL)

        # Find all matching rows
        rows = row_pattern.findall(content)

        for row in rows:
            changeset_link = row[0]
            extracted_hash_id = changeset_link.split('/')[-1]
            changeset_datetime = row[1].strip()
            Changeset_Summary = f"{row[2]} - {row[3]}"

            # Extract bug_ids
            bug_id_matches = re.findall(r'show_bug.cgi\?id=(\d+)', Changeset_Summary)
            if bug_id_matches:
                bug_ids = ' | '.join(bug_id_matches)
                Does_Required_Human_Inspection = False
            else:
                bug_ids = None
                Does_Required_Human_Inspection = True

            # Check for backout keywords
            Is_Backed_Out_Changeset = False
            if re.search(r'\bback.{0,8}out\b', Changeset_Summary, re.IGNORECASE):
                Is_Backed_Out_Changeset = True
            else:
                Is_Backed_Out_Changeset = False

            # Add the information to the list
            changeset_info_list.append({
                "changeset_link": changeset_link,
                "hash_id": extracted_hash_id,
                "changeset_datetime": changeset_datetime,
                "bug_ids": bug_ids,
                "Does_Required_Human_Inspection": Does_Required_Human_Inspection,
                "Changeset_Summary": Changeset_Summary,
                "Is_Backed_Out_Changeset": Is_Backed_Out_Changeset
            })

        # Define the regular expression pattern for extracting next_hash
        next_hash_pattern = re.compile(
            r"shortlog/%next%',\s*'([\w]*)'", re.DOTALL)

        next_hash_match = next_hash_pattern.search(content)

        if next_hash_match:
            next_hash = next_hash_match.group(1)
            if not next_hash:
                next_hash = "no_next_hash"
        else:
            next_hash = "no_next_hash"

        return changeset_info_list, next_hash
    
    except Exception as e:
        # Handle any exceptions
        print(f"Request url: {request_url}. Error: {e}.")
        exit()

# save_shortlog_to_db: 
def save_shortlog_to_db(changeset_info):
    global conn_str, insert_Bugzilla_Mozilla_Changesets_query

    # Connect to the database
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    try:
        # Iterate over 'changeset_info'
        for record in changeset_info:
            # Extract values from the record
            hash_id = record['hash_id']
            Changeset_Summary = record['Changeset_Summary']
            bug_ids = record['bug_ids'] if record['bug_ids'] else ''
            changeset_link = record['changeset_link']
            mercurial_type = "mozilla-central"
            changeset_datetime = record['changeset_datetime']
            Is_Backed_Out_Changeset = int(record['Is_Backed_Out_Changeset'])
            backed_out_by = None
            does_required_human_inspection = int(record['Does_Required_Human_Inspection'])

            # Execute the SQL query per record in the changeset_info
            cursor.execute(insert_Bugzilla_Mozilla_Changesets_query, 
                           hash_id, 
                           Changeset_Summary, 
                           bug_ids, 
                           changeset_link, 
                           mercurial_type, 
                           changeset_datetime,
                           Is_Backed_Out_Changeset, 
                           backed_out_by, 
                           does_required_human_inspection)
        
        # Commit the transaction
        conn.commit()
    
    except Exception as e:
        # Handle any exceptions
        print(f"Error: {e}")
        exit()
    
    finally:
        # Close the cursor and connection
        cursor.close()
        conn.close()

def get_backout_commits(arg_1, arg_2):
    global conn_str

    try:
        # Connect to the database
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        cursor.execute(get_backout_commits_query, (arg_1, arg_2))
        rows = cursor.fetchall()
        return rows
    
    except Exception as e:
        # Handle any exceptions
        print(f"Error: {e}")
        exit()
    
    finally:
        # Close the cursor and connection
        cursor.close()
        conn.close()

def get_backout_hashes_by(Changeset_Link):
    base_url = f"https://hg.mozilla.org"
    request_url = base_url + str(Changeset_Link)
    
    set_of_backouted_hashes = set()

    try:
        attempt_number = 1
        while attempt_number <= 5:
            response = requests.get(request_url)
            if response.status_code == 200:
                content = response.text
                soup = BeautifulSoup(content, 'html.parser')
                backs_out_td = soup.find('td', string='backs out')
                if backs_out_td:
                    next_td = backs_out_td.find_next_sibling('td')
                    if next_td:
                        links = next_td.find_all('a', href=True)
                        set_of_backouted_hashes.update(link.text for link in links)
                break
            elif response.status_code == 404:
                print("Error 404: Not Found")
                break
            else:
                print(f"Attempt {attempt_number} failed with status code {response.status_code}. Retrying...")
                attempt_number += 1
                time.sleep(5)
        else:
            print("Failed after 3 attempts.")
            exit()

    except Exception as e:
        print(f"Error: {e}")
        exit()

    return set_of_backouted_hashes

def save_backouted_hashes(Backed_Out_By, set_of_backouted_hashes):
    global conn_str
    attempt_number = 1
    max_retries = 999 # Number of max attempts if deadlock encountered.
    
    while attempt_number <= max_retries:
        try:
            # Connect to the database
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            list_of_backouted_hashes = " | ".join(set_of_backouted_hashes)
            if list_of_backouted_hashes == "" or list_of_backouted_hashes == None:
                list_of_backouted_hashes = "NO_HASHES_FOUND"
            
            cursor.execute(save_backout_hashes_query, (list_of_backouted_hashes, Backed_Out_By))

            for backout_hash in set_of_backouted_hashes:
                cursor.execute(set_back_out_by_field_query, (Backed_Out_By, backout_hash))

            # Commit the transaction
            conn.commit()

            # If commit is successful, break the retry loop
            break

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

######################################################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="")
    parser.add_argument('arg_1', type=str, help='Argument 1')
    parser.add_argument('arg_2', type=str, help='Argument 2')
    args = parser.parse_args()
    arg_1 = args.arg_1
    arg_2 = args.arg_2

    ## Step 1: Crawling for all shortlog records (Done for mozilla-central)
    # next_hash = "a0fe8d257aa715bf45880b8e7661f949fa242a10"
    # while True:
    #     print(f"Processing next hash: {next_hash}...", end="", flush=True)
    #     changeset_info, next_hash = crawl_mozilla_central_shortlog(next_hash)
    #     save_shortlog_to_db(changeset_info)
    #     print("Done")
    #     if next_hash == "no_next_hash":
    #         break

    ## Step 2: For each backout commit, retreated the backout hashes and and updated 'Backout_Hashes' and 'Is_Backed_Out_Changeset'
    list_of_commits = get_backout_commits(arg_1, arg_2)
    record_count = len(list_of_commits)

    for commit in list_of_commits:
        Backed_Out_By, Changeset_Link, Row_Num, Backout_Hashes = commit

        print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] Remainings: {str(record_count)}. Process hash {Backed_Out_By}...", end="", flush=True)
        set_of_backouted_hashes = get_backout_hashes_by(Changeset_Link)
        save_backouted_hashes(Backed_Out_By, set_of_backouted_hashes)
        print("Done")
        record_count -= 1

print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] Remainings: 0. Finished processing. Exit program.")