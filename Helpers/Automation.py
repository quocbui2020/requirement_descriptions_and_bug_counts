# This file dedicated for 

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

if __name__ == "__main__":
    obj = Automation()
    obj.task_splitChangesetBugIdsIntoSeparateTable()