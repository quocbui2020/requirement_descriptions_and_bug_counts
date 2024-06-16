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

#TODO: If the request failed (Could be due to large context Code status: 502 Bad Gateway), then logged and reduce the size of the limit. And try again
#TODO: The code is good for now. In the future, we can write code to validate links and exclusively get all the links from all comments.

logging.basicConfig(level=logging.INFO, filename=f"C:\\Users\\quocb\\Quoc Bui\\Study\\phd_in_cs\\Research\\first_paper\\Code\\r_to_b_mapping\\bugzilla\\logs\\changeset_hashes_crawler_logger_{strftime('%Y%m%d_%H-%M-%S', localtime())}.log", filemode='w', format='%(levelname)s-%(message)s')

# Connection string
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=QUOCBUI\\SQLEXPRESS;' \
           'DATABASE=ResearchDatasets;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

update_changeset_links_query = '''
            UPDATE [dbo].[Bugzilla]
                SET [changeset_links] = ?
            WHERE [ID] = ?
            AND (changeset_links IS NULL OR changeset_links NOT LIKE '%FINISHED_CHANGESET_LINKS_CRAWLING |')
            '''

# Get_UnProcessed_BugIds: Get bug ids that have not being processed starting from startId up to endId:
def Get_UnProcessed_BugIds(startId, endId):
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id
            FROM Bugzilla
            WHERE resolution = 'FIXED'
            AND (
                potential_hashes <> ' | FINISHED_CHANGESET_HASHES_CRAWLING |'
                AND potential_hashes IS NOT NULL
                AND potential_hashes LIKE '%FINISHED_CHANGESET_HASHES_CRAWLING |'
                )
            AND (changeset_links IS NULL OR changeset_links NOT LIKE '%FINISHED_CHANGESET_LINKS_CRAWLING |')
            AND (id >= ? AND id <= ?)
            ORDER BY id ASC""", (startId, endId))
        
        rows = cursor.fetchall()
        return [row[0] for row in rows]  # Extract ids from rows
    except Exception as e:
        print(f"Error: {e}")
        exit()
    finally:
        # Close the cursor and connection if they are not None
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def Crawling_For_Changeset_Links(bugId):
    url = f"https://bugzilla.mozilla.org/show_bug.cgi?id=0&id={bugId}&format=multiple"

    try:
        attempt_number = 1
        while True:
            response = requests.get(url)
            if response.status_code == 200:
                # Find all contents between <pre class="bz_comment_text"> and </pre> tags
                content = response.text
                pre_contents = re.findall(r'<pre class="bz_comment_text">(.*?)</pre>', content, re.DOTALL)
                
                # Initialize a set to store unique URLs
                url_set = set()

                # Define the pattern for URLs containing /rev/ and hash-like strings
                url_pattern = re.compile(r'http[s]?://[^\s">]+/rev/[a-fA-F0-9]{6,40}')

                # Search for all the URLs in the content
                for pre_content in pre_contents:
                    found_urls = url_pattern.findall(pre_content)
                    url_set.update(found_urls)

                # Join all unique URLs with " | "
                HashIdsString = " | ".join(url_set)
                
                # Add the final string
                HashIdsString += " | FINISHED_CHANGESET_LINKS_CRAWLING |"
                
                return HashIdsString
            elif response.status_code == 429:
                print("429.")
                print(f"Go sleep for 10 seconds...", end="", flush=True)
                time.sleep(10)
                print("Woke up.")
                if attempt_number == 5:
                    break

                attempt_number += 1
                print(f"Attempt number: {attempt_number}. Re-process bug id {bugId}...", end="", flush=True)
                continue

            else:
                print(f"Error: Received status code {response.status_code}")
                return None
            
        print(f"\nToo many re-attempts. Exit the program.")
        exit()

    except Exception as e:
        print(f"Error: {e}")
        return None

def Update_Changeset_Links(bugId, HashIdsString):
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute(update_changeset_links_query, HashIdsString, bugId)
        conn.commit()
    except Exception as e:
        # Handle any exceptions
        print(f"Error: {e}")
        exit()
    finally:
        # Close the cursor and connection if they are not None
        if cursor:
            cursor.close()
        if conn:
            conn.close()

######################################################################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process some bug IDs.")

    # Get start_id and end_id from command prompt input:
    parser.add_argument('start_id', type=int, help='The starting bug ID')
    parser.add_argument('end_id', type=int, help='The ending bug ID') # id <= 481297 (for version 1)
    args = parser.parse_args()
    start_id = args.start_id
    end_id = args.end_id

    list_of_bugIds = Get_UnProcessed_BugIds(str(start_id), str(end_id))
    record_count = len(list_of_bugIds)

    for bugId in list_of_bugIds:
        print(f"Total Remaining Records: {str(record_count)}. Process bug id {bugId}...", end="", flush=True)
        HashIdsString = Crawling_For_Changeset_Links(bugId)
        #HashIdsString = None
        if HashIdsString:
            Update_Changeset_Links(bugId, HashIdsString)
        print("Done")
        record_count -= 1