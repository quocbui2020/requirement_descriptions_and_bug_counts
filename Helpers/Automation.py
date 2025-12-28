# This file dedicated for small automation tasks:

import sys
import os
import traceback
import time
import requests
import re
import pyodbc
import argparse
from time import strftime, localtime
from datetime import datetime
from collections import namedtuple

# Connection string
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=QUOCBUI-PERSONA\\MSSQLSERVER01;' \
           'DATABASE=ResearchDatasets;' \
           'Connection Timeout=300;' \
           'Login Timeout=300;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

class Automation:
    def __init__(self):
        pass

    def task_splitChangesetBugIdsIntoSeparateTable(self):
        # Move data from [Bugzilla_Mozilla_Changesets].[Bug_Ids] over to new bridge table [Bugzilla_Mozilla_Changeset_BugIds].
        # https://chatgpt.com/c/67264edd-905c-8004-ad0f-b52ef8192a34
        # Query to check result:
        ## SELECT c.Bug_Ids
        ##     ,b.*
        ## FROM Bugzilla_Mozilla_Changesets c
        ## INNER JOIN Bugzilla_Mozilla_Changeset_BugIds b ON b.changeset_hash_id = c.Hash_Id
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT Hash_Id, bug_ids
            FROM Bugzilla_Mozilla_Changesets AS bmc
            WHERE bug_ids IS NOT NULL
            AND bug_ids != ''
            AND NOT EXISTS (
                SELECT 1 
                FROM Bugzilla_Mozilla_Changeset_BugIds AS bcb
                WHERE bcb.Changeset_Hash_ID = bmc.Hash_Id
            )
        ''')

        rows = cursor.fetchall()
        record_count = len(rows)

        query_count = 0
        query_batch = ""
        query_params = []

        insert_query_template = '''IF NOT EXISTS (SELECT 1 FROM Bugzilla_Mozilla_Changeset_BugIds WHERE Changeset_Hash_ID=? AND Bug_ID=? AND Type=?) BEGIN INSERT INTO Bugzilla_Mozilla_Changeset_BugIds (Changeset_Hash_ID, Bug_ID, Type) VALUES (?, ?, ?) END;'''
        try:
            for record in rows:
                hash_id, bug_ids = record
                # end="\r": This parameter controls what character(s) are printed at the end of the line...
                # ...By default, print() adds a newline ("\n"), moving the cursor to the next line after each print statement.
                # flush=True: This parameter forces the output to be written immediately, rather than being buffered.
                print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] Remaining Records: {str(record_count)}", end="\r", flush=True)
                record_count -= 1

                # Split bug_ids based on '|' delimiter and set default type if needed
                bug_id_pairs = bug_ids.split(" | ")
                for pair in bug_id_pairs:
                    if ':' in pair:
                        bug_id, type_ = pair.split(':')[:2] # if bad data: pair="960276:InTitle:InTitle", then just take the first 2 values in the string.
                    else:
                        bug_id = pair
                        type_ = "InTitle"  # Default type if no label exists

                    query_batch += insert_query_template
                    query_params.extend([hash_id, bug_id, type_, hash_id, bug_id, type_])
                    query_count += 1

                if query_count >= 50:
                    # Execute the conditional insert
                    cursor.execute(query_batch, query_params)
                    conn.commit()  # Commit after each insert to keep the connection consistent
                    query_count = 0
                    query_batch = ""
                    query_params = []

            # Final batch execution for any remaining queries
            if query_count > 0:
                cursor.execute(query_batch, query_params)
                conn.commit()

        except Exception as e:
            print(f"Error processing records: {e}")
        finally:
            # Ensure connection is closed in case of any error
            cursor.close()
            conn.close()


    def compute_file_links(self):
        conn = None
        try:
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            print("Retrieving processed records...", end="", flush=True)
            cursor.execute('''
                SELECT cf.Unique_Hash,
                    cf.Previous_File_Name,
                    cf.Updated_File_Name,
                    c.Mercurial_Type,
                    cf.Changeset_Hash_ID,
                    c.Parent_Hashes
                FROM Bugzilla_Mozilla_Changeset_Files cf
                INNER JOIN Bugzilla_Mozilla_Changesets c 
                    ON c.Hash_Id = cf.Changeset_Hash_ID
                WHERE 
                    (CHARINDEX('.', cf.Previous_File_Name) > 0 OR CHARINDEX('.', cf.Updated_File_Name) > 0) -- Ensure correct file names (have at least a character '.')
                    AND Previous_File_Link IS NULL -- Retrieve records have not been processed.
                    AND (c.Parent_Hashes IS NOT NULL AND CHARINDEX('|', c.Parent_Hashes) = 0) -- Retrieve only records that have one and only one parent hashes.
            ''')

            rows = cursor.fetchall()
            print("Complete")

            record_count = len(rows)
            link_format = "https://hg.mozilla.org/{mercurial_type}/raw-file/{changeset_hash_id}/{file_path}"

            def generate_file_link(mercurial_type, changeset_hash_id, file_path):
                return link_format.format(
                    mercurial_type=mercurial_type,
                    changeset_hash_id=changeset_hash_id,
                    file_path=file_path[2:]  # Remove "a/" or "b/" prefixes
                )

            for row in rows:
                unique_hash, prev_file, updated_file, mercurial_type, changeset_id, parent_hashes = row
                previous_file_links, updated_file_links = [], []

                print(
                    f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] Remaining Records: {record_count}", 
                    end="\r", 
                    flush=True
                )

                if mercurial_type:
                    mercurial_type_list = mercurial_type.split(" | ")

                    # TODO: Quoc: Need to revisit this logics. Looks like we should've use the 'parent_hashes' for this.
                    # Generate Previous File Links
                    if prev_file and prev_file[:2] == 'a/':
                        previous_file_links = [
                            generate_file_link(m_type, changeset_id, prev_file)
                            for m_type in mercurial_type_list
                        ]

                    # TODO: Quoc: Need to revisit this logics. Looks like we should've use the 'changeset_id' for this.
                    # Generate Updated File Links
                    if updated_file and updated_file[:2] == 'b/':
                        updated_file_links = [
                            generate_file_link(m_type, parent_hashes, updated_file)
                            for m_type in mercurial_type_list
                        ]

                # Join links with " | " if multiple links are present
                previous_file_link = " | ".join(previous_file_links) if previous_file_links else "not available"
                updated_file_link = " | ".join(updated_file_links) if updated_file_links else "not available"

                # Save to database:
                cursor.execute('''
                    UPDATE [Bugzilla_Mozilla_Changeset_Files]
                    SET Previous_File_Link = ?, Updated_File_Link = ? 
                    WHERE Unique_Hash = ?
                ''', (previous_file_link, updated_file_link, unique_hash))
                record_count -= 1

            # Commit after all updates
            conn.commit()
            print("\nUpdate complete.")

        except Exception as e:
            # Rollback in case of error
            if conn:
                conn.rollback()
            print(f"An error occurred: {e}")
        finally:
            # Ensure resources are cleaned up
            if conn:
                conn.close()


if __name__ == "__main__":
    obj = Automation()
    obj.compute_file_links()