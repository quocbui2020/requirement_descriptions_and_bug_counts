# This file is responsible for scraping "before" and "after" raw files from Bugzilla Mozilla bugs and storing them in a SQL Server database.

import traceback
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re
import pyodbc
import argparse
import os
from time import strftime, localtime
from datetime import datetime
from collections import namedtuple

# Connection string
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=localhost\\SQLEXPRESS;' \
           'DATABASE=FixFox_v3;' \
           'Connection Timeout=300;' \
           'Login Timeout=300;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

def retrieve_unprocessed_records():
    conn = None
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        print("Retrieving processed records...", end="", flush=True)
        cursor.execute('''
            SELECT cf.[Unique_Hash]
                ,cf.Previous_File_Links
                ,cf.Updated_File_Links
            FROM [Changeset_Raw_File_Contents] crfc
            INNER JOIN [Changeset_Files] cf ON cf.Unique_Hash = crfc.Changeset_File_Unique_Hash
            WHERE crfc.[Before_Raw_File_Content] IS NULL AND crfc.[After_Raw_File_Content] IS NULL -- Ensure to get only unprocessed records.
        ''')

        rows = cursor.fetchall()
        print("Complete")

        return rows

    except Exception as e:
        # Rollback in case of error
        if conn:
            conn.rollback()
        print(f"An error occurred: {e}")
    finally:
        # Ensure resources are cleaned up
        if conn:
            conn.close()

def retrieve_failed_request_records():
    conn = None
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        print("Retrieving failed request records...", end="", flush=True)
        cursor.execute('''
            select
                b.Unique_Hash
                ,b.Previous_File_Links
                ,b.Updated_File_Links
                ,CASE
                    WHEN a.Before_Raw_File_Content = 'Failed web requests' AND (a.After_Raw_File_Content <> 'Failed web requests' OR a.After_Raw_File_Content IS NULL) THEN 0
                    WHEN (a.Before_Raw_File_Content <> 'Failed web requests' OR a.Before_Raw_File_Content IS NULL) AND a.After_Raw_File_Content = 'Failed web requests' THEN 1
                    WHEN a.Before_Raw_File_Content = 'Failed web requests' AND a.After_Raw_File_Content = 'Failed web requests' THEN 2
                END Failed_Request_Option
            from FixFox_v3.dbo.Changeset_Raw_File_Contents a
            inner join FixFox_v3.dbo.Changeset_Files b on b.Unique_Hash = a.Changeset_File_Unique_Hash
            where a.Before_Raw_File_Content = 'Failed web requests'
            or a.After_Raw_File_Content = 'Failed web requests';
        ''')

        rows = cursor.fetchall()
        print("Complete")

        return rows

    except Exception as e:
        # Rollback in case of error
        if conn:
            conn.rollback()
        print(f"An error occurred: {e}")
    finally:
        # Ensure resources are cleaned up
        if conn:
            conn.close()

def save_raw_file_content(changeset_file_unique_hash, before_raw_file_content, after_raw_file_content):
    conn = None
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE [Changeset_Raw_File_Contents]
            SET [Before_Raw_File_Content] = ?
                ,[After_Raw_File_Content] = ?
            WHERE [Changeset_File_Unique_Hash] = ?
        ''', before_raw_file_content, after_raw_file_content, changeset_file_unique_hash)

        conn.commit()

        return True

    except Exception as e:
        # Rollback in case of error
        if conn:
            conn.rollback()
        return False
    
    finally:
        # Ensure resources are cleaned up
        if conn:
            conn.close()

def save_specific_raw_file_content(file_type, changeset_file_unique_hash, raw_file_content):
    conn = None
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        if file_type == "before":
            cursor.execute('''
                UPDATE [Changeset_Raw_File_Contents]
                SET [Before_Raw_File_Content] = ?
                WHERE [Changeset_File_Unique_Hash] = ?
            ''', raw_file_content, changeset_file_unique_hash)
        elif file_type == "after":
            cursor.execute('''
                UPDATE [Changeset_Raw_File_Contents]
                SET [After_Raw_File_Content] = ?
                WHERE [Changeset_File_Unique_Hash] = ?
            ''', raw_file_content, changeset_file_unique_hash)
        else:
            return False

        conn.commit()

        return True

    except Exception as e:
        # Rollback in case of error
        if conn:
            conn.rollback()
        return False
    
    finally:
        # Ensure resources are cleaned up
        if conn:
            conn.close()

def scrap_raw_files(links):
    # Return (result, response_content)
    if "http" not in links:
        return (True, None)
    
    # Set up session with retries
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        if " | " in links:
            link_list = links.split(" | ")
        else:
            link_list = [links]
        
        for link in link_list:
            try:
                response = session.get(link, timeout=60, headers=headers)
                if response.status_code == 200:
                    return (True, response.text)
            except Exception as e:
                print(f"An error occurred for link {link}: {e}")
                continue
        
        return (True, "Failed web requests")
        
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return (False, None)

def extract_file_content_to_txt(changeset_file_unique_hash, output_dir):
    ## Example of extracting file content to text files (pretty format)
    # if __name__ == "__main__":
    #     hash_hex = '0014C975B99C2EAC639667BBC7243A4FA8664C3568B9D0A89FE656F01F9AA440'
    #     hash_bytes = bytes.fromhex(hash_hex)
    #     extract_file_content_to_txt(hash_bytes, "C:\\Users\\quocb\\quocbui\\Studies\\research\\GithubRepo\\requirement_descriptions_and_bug_counts")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    conn = None
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        hash_str = changeset_file_unique_hash.hex()
        print(f"Querying for hash: {hash_str}")

        cursor.execute('''
            SELECT [Before_Raw_File_Content], [After_Raw_File_Content]
            FROM [Changeset_Raw_File_Contents]
            WHERE [Changeset_File_Unique_Hash] = ?
        ''', changeset_file_unique_hash)

        row = cursor.fetchone()
        if row:
            before_content, after_content = row
            print(f"Found row: before_content length {len(before_content) if before_content else 0}, after_content length {len(after_content) if after_content else 0}")
            
            if before_content:
                filepath = os.path.join(output_dir, f'before_{hash_str}.txt')
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(before_content)
                print(f"Saved {filepath}")
            
            if after_content:
                filepath = os.path.join(output_dir, f'after_{hash_str}.txt')
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(after_content)
                print(f"Saved {filepath}")
            
            return True
        else:
            print("No content found for the given hash.")
            return False

    except Exception as e:
        print(f"Error extracting content: {e}")
        return False
    
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    ###################################################################################
    ## First scraping attempt ##
    # rows = retrieve_unprocessed_records()
    # record_count = len(rows)

    # for row in rows:
    #     changeset_file_unique_hash, previous_file_links, updated_file_links = row
    #     print(
    #         f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] Remaining Records: {record_count} - ", 
    #         end=""
    #     )
    #     print("Scraping Previous File Content...", end="", flush=True)
    #     before_result, before_raw_file_content = scrap_raw_files(previous_file_links)
    #     time.sleep(2)
    #     print("Scraping Updated File Content...", end="", flush=True)
    #     after_result, after_raw_file_content = scrap_raw_files(updated_file_links)
    #     print("Saving Contents to Database...", end="", flush=True)

    #     if before_result and after_result:
    #         save_result = save_raw_file_content(changeset_file_unique_hash, before_raw_file_content, after_raw_file_content)
        
    #     record_count -= 1
    #     print("Done")
    ###################################################################################
    ## Next scraping attempt (Keep re-running until no more failed request records) ##
    # rows = retrieve_failed_request_records()
    # record_count = len(rows)

    # for row in rows:
    #     # failed_request_option: 0 = before failed, 1 = after failed, 2 = both failed
    #     changeset_file_unique_hash, previous_file_links, updated_file_links, failed_request_option = row
    #     print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] Remaining Records: {record_count} - ", end="")

    #     if failed_request_option == 0 or failed_request_option == 2:
    #         print(f"Re-scraping Previous File Content...", end="")
    #         before_result, before_raw_file_content = scrap_raw_files(previous_file_links)
    #         print(f"{before_result}. ", end="")
    #         save_result = save_specific_raw_file_content("before", changeset_file_unique_hash, before_raw_file_content)
    #         time.sleep(10)
    #     if failed_request_option == 1 or failed_request_option == 2:
    #         print(f"Re-scraping Updated File Content...", end="")
    #         after_result, after_raw_file_content = scrap_raw_files(updated_file_links)
    #         print(f"{after_result}. ", end="")
    #         save_result = save_specific_raw_file_content("after", changeset_file_unique_hash, after_raw_file_content)
    #         time.sleep(10)
            
    #     record_count -= 1
    #     print("Done")

    ## Example of extracting file content to text files (pretty format)
    if __name__ == "__main__":
        hash_hex = '0014C975B99C2EAC639667BBC7243A4FA8664C3568B9D0A89FE656F01F9AA440'
        hash_bytes = bytes.fromhex(hash_hex)
        extract_file_content_to_txt(hash_bytes, "C:\\Users\\quocb\\quocbui\\Studies\\research\\GithubRepo\\requirement_descriptions_and_bug_counts")