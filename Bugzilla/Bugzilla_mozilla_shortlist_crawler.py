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

# Connect to the database
conn = pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};'
                        'SERVER=QUOCBUI\SQLEXPRESS;'
                        'DATABASE=ResearchDatasets;'
                        'LongAsMax=yes;'
                        'TrustServerCertificate=yes;'
                        'Trusted_Connection=yes;')

# Prepare the SQL queries:
insert_bugzilla_mozilla_shortlog_query = '''INSERT INTO [dbo].[Bugzilla_Mozilla_ShortLog]
            ([Hash_Id]
           ,[Commit_Title] --Quoc: change this column to `Commit_Summary`
           ,[Bug_Ids]
           ,[Changeset_Links]
           ,[Mercurial_Type]
           ,[Is_Backed_Out_Commit]
           ,[Backed_Out_By]
           ,[Does_Required_Human_Inspection]
           ,[Inserted_On])
           --Quoc: Added another column 'changeset_datetime'
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())'''

create_bugzilla_error_log_query = '''INSERT INTO [dbo].[Bugzilla_Error_Log]
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
            (NEWID(), ?, ?, ?, ?, ?, ?, 0, SYSUTCDATETIME())'''


def crawl_mozilla_central_shortlog(hash_id, max_retries=5):
    request_url = f"https://hg.mozilla.org/mozilla-central/shortlog/{hash_id}"
    retries = 0

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
        commit_summary = f"{row[2]} - {row[3]}"

        # Extract bug_ids
        bug_id_matches = re.findall(r'show_bug.cgi\?id=(\d+)', commit_summary)
        if bug_id_matches:
            bug_ids = ' | '.join(bug_id_matches)
            Does_Required_Human_Inspection = False
        else:
            bug_ids = None
            Does_Required_Human_Inspection = True

        # Check for backout keywords
        if re.search(r'\bback.{0,8}out\b', commit_summary, re.IGNORECASE):
            Is_Backed_Out_Commit = True
        else:
            Is_Backed_Out_Commit = False

        # Add the information to the list
        changeset_info_list.append({
            "changeset_link": changeset_link,
            "hash_id": extracted_hash_id,
            "changeset_datetime": changeset_datetime,
            "bug_ids": bug_ids,
            "Does_Required_Human_Inspection": Does_Required_Human_Inspection,
            "commit_summary": commit_summary,
            "Is_Backed_Out_Commit": Is_Backed_Out_Commit
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


######################################################################
if __name__ = "__main__":
    # Example usage
    url = "5559cc25760716b15bf6649eb227e04fb151a265"
    changeset_info, next_hash = crawl_mozilla_central_shortlog(url)
    for info in changeset_info:
        print(info)
    print(f"Next hash: {next_hash}")