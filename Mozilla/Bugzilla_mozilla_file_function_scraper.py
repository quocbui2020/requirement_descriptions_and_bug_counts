import sys
import os
import json
import traceback
import time
import requests
import re
import pyodbc
import argparse
from time import strftime, localtime
from datetime import datetime, timedelta
from collections import namedtuple
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Helpers import Extract_Function_From_File_Content_Helper as ExtractFunctionHelper

# Connection string
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=QUOCBUI-PERSONA\\MSSQLSERVER01;' \
           'DATABASE=ResearchDatasets;' \
           'Connection Timeout=300;' \
           'Login Timeout=300;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

class Mozilla_File_Function_Scraper:
    def __init__(self):
        pass

    def get_records_to_process(self, task_group, start_row, end_row):
        global conn_str
        attempt_number = 1
        max_retries = 3 # max retry for deadlock issue.

        while attempt_number <= max_retries:
            try:
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()
                # cursor.execute('''
                #     SELECT cf.Task_Group
                #         ,cf.Row_Num
                #         ,cf.Process_Status
                #         ,cf.Changeset_Hash_ID
                #         ,cf.Previous_File_Name
                #         ,cf.Updated_File_Name
                #         ,cf.File_Status
                #         ,cf.Unique_Hash --Changeset File's Unique Hash
                #         ,c.Mercurial_Type
                #         ,c.Parent_Hashes
                #     FROM Bugzilla_Mozilla_Changeset_Files cf
                #     INNER JOIN Bugzilla_Mozilla_Changesets c ON c.Hash_Id = cf.Changeset_Hash_ID
                #     WHERE cf.Task_Group = ?
                #     AND cf.Row_Num BETWEEN ? AND ?
                #     AND cf.Process_Status IS NULL -- Null status mean the records have not been processed.
                #     ORDER BY cf.Task_Group ASC, cf.Row_Num ASC
                # ''', (task_group, start_row, end_row))
                
                # get records associate with CVE:
                cursor.execute('''
                    SELECT distinct cf.Task_Group
                        ,cf.Row_Num
                        ,cf.Process_Status
                        ,cf.Changeset_Hash_ID
                        ,cf.Previous_File_Name
                        ,cf.Updated_File_Name
                        ,cf.File_Status
                        ,cf.Unique_Hash --Changeset File's Unique Hash
                        ,c.Mercurial_Type
                        ,c.Parent_Hashes
                    FROM Bugzilla_Mozilla_Changeset_Files cf
                    INNER JOIN Bugzilla_Mozilla_Changesets c ON c.Hash_Id = cf.Changeset_Hash_ID
                    INNER JOIN Bugzilla_Mozilla_Changeset_BugIds bmb on bmb.Changeset_Hash_ID = c.Hash_Id
                    INNER JOIN Bugzilla b on b.Id = bmb.Bug_ID
                        AND alias like 'CVE%'
                    WHERE 1=1
                    AND cf.Process_Status IS NULL -- Null status mean the records have not been processed.
                    AND cf.Task_Group BETWEEN ? AND ? 
                    ORDER BY cf.Task_Group ASC, cf.Row_Num ASC
                ''', (start_row, end_row))
                
                rows = cursor.fetchall()
                return rows
            
            except pyodbc.Error as e:
                attempt_number += 1
                time.sleep(5)
                if attempt_number < max_retries:
                    continue

                print(f"Error - get_records_to_process({start_row}, {end_row}): {e}.")
                traceback.print_exc()
                exit()

            except Exception as e:
                # Handle any exceptions
                # Since this function only being run once, it's OK to exit if errored
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
            print(f"Error - get_records_to_process({start_row}, {end_row}): {e}.")
            exit()

    def scrap_mozilla_function_data(self, db_mozilla_changeset_file):
        """
        Make web request to collect functions information from hg.mozilla.org source codes for file types: js, c, cpp, and py.
        
        Parameters:
        content (str): The content of the file as a string.
        
        Returns:
        tuple: (overall_status, process_statuses, list_of_functions_a, dict_function_count_a, list_of_functions_b, dict_function_count_b)
        """

        attempt_number = 1
        max_retries = 6
        response_status_code_a = -1
        response_status_code_b = -1
        request_url_format = "https://hg.mozilla.org/{mercurial_type}/raw-file/{changeset_hash_id}/{file_path}"
        request_url_a = None
        request_url_b = None
        response_a = None
        response_b = None
        mercurial_type_index = 0
        process_statuses = []
        file_extension = ''
        field_name = ['overall_status', 'process_statuses', 'list_of_functions_a', 'dict_function_count_a', 'list_of_functions_b', 'dict_function_count_b']

        try:
            while attempt_number <= max_retries:
                mercurial_type_list = db_mozilla_changeset_file.mercurial_type.split(" | ")

                # Extract file paths. Removed the first 2 characters ("a/" and "b/") from `previous_file_name` and `previous_file_name`:
                file_path_a = db_mozilla_changeset_file.previous_file_name[2:] if "/dev/null" not in db_mozilla_changeset_file.previous_file_name else None
                file_path_b = db_mozilla_changeset_file.updated_file_name[2:] if "/dev/null" not in db_mozilla_changeset_file.updated_file_name else None

                # Extract file extension from file path names:
                if file_path_a:
                    file_extension = file_path_a.rsplit('.', 1)[-1] # rsplit method splits string starting from the right -> left.
                else:
                    file_extension = file_path_b.rsplit('.', 1)[-1]

                # Format the request url for both a and b:
                request_url_a = request_url_format.replace("{mercurial_type}", mercurial_type_list[mercurial_type_index]
                        ).replace("{changeset_hash_id}", db_mozilla_changeset_file.parent_hash
                        ).replace("{file_path}", file_path_a) if file_path_a and not request_url_a else None
                
                request_url_b = request_url_format.replace("{mercurial_type}", mercurial_type_list[mercurial_type_index]
                        ).replace("{changeset_hash_id}", db_mozilla_changeset_file.changeset_hash_id
                        ).replace("{file_path}", file_path_b) if file_path_b and not request_url_b else None

                try:
                    # Make web requests:
                    response_a = requests.get(url=request_url_a, timeout=10000) if request_url_a and not response_a else response_a
                    response_b = requests.get(url=request_url_b, timeout=10000) if request_url_b and not response_b else response_b

                    response_status_code_a = response_a.status_code if response_a != None else -1 # Note, the phrase `response_a is truthy` also means if it doesn't have response code of 200
                    response_status_code_b = response_b.status_code if response_b != None else -1

                except requests.exceptions.RequestException as e:
                    # Cases when issue with internet connection or reach web request limit.
                    # For this case, we don't want to add any process_status. Null process_status means (not yet processed)
                    attempt_number += 1
                    print(f"Failed request connection.\n Attempt {str(attempt_number)}/{str(max_retries)}. Retrying in 10 seconds...", end="", flush=True)
                    time.sleep(10)
                    pass
                 
                # If both requests successful:
                if (response_status_code_a == 200 or not file_path_a) and (response_status_code_b == 200 or not file_path_b):
                    process_statuses.append("200 OK")
                    break

                # Case: Incorrect url for some reason, if so, try different mercurial type
                elif response_status_code_a == 404 or response_status_code_b == 404:
                    attempt_number += 1
                    print(f"Status Code: 404.\n Attempt {str(attempt_number)}/{str(6)}.", end="", flush=True)
                    mercurial_type_index += 1

                    # Switch to other mercurial type:
                    # if incorrect mercurial type, we assumed status code is 404 for both a and b:
                    if mercurial_type_index < len(mercurial_type_list) and (response_status_code_a == 404 and response_status_code_b == 404):
                        process_statuses.append(f"404:{mercurial_type_list[mercurial_type_index-1]}")
                        pass
                    else:
                        break

                # Case when status code other than 200 and 400:
                else: # Handle case when request returns status code other than `200` and `400`
                    print(f"Response code: [a:{str(response_status_code_a)} && b:{str(response_status_code_b)}].\nRetrying in 10 seconds...", end="", flush=True)
                    if attempt_number > max_retries:
                        process_statuses.append(f"Response code: [a:{str(response_status_code_a)} && b:{str(response_status_code_b)}]")
                    
                    time.sleep(10)
                    attempt_number += 1
                    pass

                # Before retry again, let reset some variables:
                if  response_status_code_a != 200:
                    response_a = None
                    response_status_code_a = -1
                if response_status_code_b != 200:
                    response_b = None
                    response_status_code_b = -1

            # Case reaching the maximum attempt web request, then we assume this records have not been processed yet.
            else:
                process_statuses.append("network issue")
                return namedtuple('WebRequestRecord', field_name)(*("network issue", process_statuses, None, None, None, None))
            
            # Exit the function in the case request url failed.
            if response_status_code_a == 404 or response_status_code_b == 404:
                process_statuses.append("404")
                return namedtuple('WebRequestRecord', field_name)(*("404", process_statuses, None, None, None, None))


            #######################################################################################
            # Assuming that all the codes at this point means the web requests being made successful.
            #######################################################################################
           
            function_extractor = ExtractFunctionHelper.ExtractFunctionFromFileContentHelper()
            list_of_functions_a = []
            list_of_functions_b = []

            # Identify the file code:
            # Important: list in python have properties: Order Preservation and Allowing Duplicate Values
            match(file_extension):
                case "js":
                    list_of_functions_a = function_extractor.extract_js_functions(response_a.text) if response_a else list_of_functions_a
                    list_of_functions_b = function_extractor.extract_js_functions(response_b.text) if response_b else list_of_functions_b
                case "c":
                    list_of_functions_a = function_extractor.extract_c_functions(response_a.text) if response_a else list_of_functions_a
                    list_of_functions_b = function_extractor.extract_c_functions(response_b.text) if response_b else list_of_functions_b
                case "cpp":
                    list_of_functions_a = function_extractor.extract_cpp_functions(response_a.text) if response_a else list_of_functions_a
                    list_of_functions_b = function_extractor.extract_cpp_functions(response_b.text) if response_b else list_of_functions_b
                case "py":
                    list_of_functions_a = function_extractor.extract_py_functions(response_a.text) if response_a else list_of_functions_a
                    list_of_functions_b = function_extractor.extract_py_functions(response_b.text) if response_b else list_of_functions_b
                case _: # Default case
                    process_statuses.append("Not js,c,cpp,py Files")
                    return namedtuple('WebRequestRecord', field_name)(*("Uninteresting File", process_statuses, None, None, None, None))

            # Handle the case if the file has multiple similar function names:
            dict_function_count_a = {}
            dict_function_count_b = {}
            updated_list_of_functions_a = []
            updated_list_of_functions_b = []

            for name, implementation in list_of_functions_a:
                # If the function name has been encountered before, increment the count
                if name in dict_function_count_a:
                    dict_function_count_a[name] += 1
                    # Prepend the count to the function name
                    updated_list_of_functions_a.append((f"{dict_function_count_a[name]}-{name}", implementation))
                else:
                    # If first occurrence, initialize the count and use the original name
                    dict_function_count_a[name] = 1
                    updated_list_of_functions_a.append((name, implementation))
            
            for name, implementation in list_of_functions_b:
                # If the function name has been encountered before, increment the count
                if name in dict_function_count_b:
                    dict_function_count_b[name] += 1
                    # Prepend the count to the function name
                    updated_list_of_functions_b.append((f"{dict_function_count_b[name]}-{name}", implementation))
                else:
                    # If first occurrence, initialize the count and use the original name
                    dict_function_count_b[name] = 1
                    updated_list_of_functions_b.append((name, implementation))

            return namedtuple('WebRequestRecord', field_name)(*("successful", process_statuses, updated_list_of_functions_a, dict_function_count_a, updated_list_of_functions_b, dict_function_count_b))

        except Exception as e:
            # TODO: Quoc - ultimately we want to handle generic exception in the case that it doesn't cease the scraper
            print(f"Error: {e}")
            traceback.print_exc()
            exit() # During code development, let exit() if encountered unknown exception
            # return ("human intervention - genetic exception", process_statuses, None, None)
    
    # Save data to the json files (backup storage):
    def save_queries_to_json(self, task_group, row_num, batches):
        # Helper function to convert bytes to hex
        def convert_bytes_to_hex(data):
            if isinstance(data, bytes):
                return data.hex()
            elif isinstance(data, list):
                return [convert_bytes_to_hex(item) for item in data]
            elif isinstance(data, dict):
                return {key: convert_bytes_to_hex(value) for key, value in data.items()}
            return data

        # Get the directory of the current script:
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Define the folder path based on today's date
        date_folder_name = datetime.now().strftime("%m_%d_%Y")
        base_dir = os.path.join(script_dir, "..", "..", "..", "csv_files", date_folder_name)

        # Create the folder if it doesn't exist
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)

        # Define the JSON file path
        json_file_path = os.path.join(base_dir, f"{task_group}_{row_num}.json")

        # Convert batches into a list of dictionaries
        batch_data = [{"parameters": convert_bytes_to_hex(params)} for query, params in batches]

        # Write to JSON file
        with open(json_file_path, "w") as json_file:
            json.dump(batch_data, json_file, indent=4)

    def save_bugzilla_mozilla_functions(self, db_mozilla_changeset_file, web_request_function_data):
        attempt_number = 1
        max_retries = 10 # max retry for database issue.
        max_connection_attempts = 10  # Number of max attempts to establish a connection.
        is_conn_open = False

        while attempt_number <= max_retries:
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
            is_conn_open = True

            # Reminder: dictionary can be used to access value by key: dictionary[key] => value
            dict_of_functions_a = {}
            dict_of_functions_b = {}

            # Variables to query database:
            params = []
            batches = []
            db_queries = ''
            query_count = 0
            query_size_limit = 50

            # Containers used for saving to database:
            deleted_function_list = []
            added_function_list = []
            modified_function_list = []
            unchanged_function_list = []

            def check_batch_limit():
                nonlocal db_queries, params, query_count # Note: `nonlocal` keyword refers the function to use the variables outside of its function, not the local variables inside itself.
                if query_count >= query_size_limit:
                    batches.append((db_queries, list(params))) # Use list() to copy `params` to avoid 'Mutable Variables Issue' when the `params` resets since they share same reference.
                    params = []    # Reset params for next batch
                    db_queries = ''  # Reset db_queries for the next batch
                    query_count = 0  # Reset query count

            # Helper function to remove the prefix numbering from function names.
            def get_original_func_name(func_name):
                # Return function name without the prefix, e.g., "2-functionA(params)" -> "functionA(params)"
                return func_name.split("-", 1)[-1] if "-" in func_name else func_name
            
            try:
                if (web_request_function_data.overall_status == "successful"):
                    # Remove all spacings, new lines characters:
                    if web_request_function_data.list_of_functions_a:
                        dict_of_functions_a = {func_sign: re.sub(r'\s+', '', func_impl) for func_sign, func_impl in web_request_function_data.list_of_functions_a}
                    if web_request_function_data.list_of_functions_b:
                        dict_of_functions_b = {func_sign: re.sub(r'\s+', '', func_impl) for func_sign, func_impl in web_request_function_data.list_of_functions_b}

                    if len(web_request_function_data.list_of_functions_a) > 0 and len(web_request_function_data.list_of_functions_b) > 0:
                        # Create a copy of dict_function_count_a to track deleted functions.
                        copy_function_count_a = web_request_function_data.dict_function_count_a.copy()
                        copy_function_count_b = web_request_function_data.dict_function_count_b.copy()

                        # Loop through functions in dict_of_functions_b and determine status (modified, unchanged, added).
                        for name_b, implementation_b in dict_of_functions_b.items():
                            original_func_name_b = get_original_func_name(name_b)
                            count_b = copy_function_count_b.get(original_func_name_b, 0)

                            if original_func_name_b in copy_function_count_a:
                                # Check if we still have remaining instances in dict_of_functions_a for this function signature.
                                count_a = copy_function_count_a.get(original_func_name_b, 0)

                                # If count_b == 1 and count_a == 1
                                if count_b == 1 and count_a == 1:
                                    if original_func_name_b not in dict_of_functions_a:
                                        deleted_function_list.append(name_b)
                                    elif dict_of_functions_a[original_func_name_b] != implementation_b:
                                        modified_function_list.append(name_b)
                                    elif dict_of_functions_a[original_func_name_b] == implementation_b:
                                        unchanged_function_list.append(name_b)

                                # If count_b >= 2 and count_a == 1
                                elif count_b >= 2 and (count_a == 1 or count_a == 0):
                                    if count_a == 1:
                                        if implementation_b == dict_of_functions_a[original_func_name_b]:
                                            unchanged_function_list.append(name_b)
                                            copy_function_count_a[original_func_name_b] -= 1
                                        else:
                                            # Status for this could be 'modified' or 'added':
                                            modified_function_list.append(name_b)
                                    elif count_a == 0:
                                        added_function_list.append(name_b)

                                # If count_b >= 2 and count_a >= 2
                                elif count_b >= 2 and count_a >= 2:
                                    matched = False
                                    for name_a, implementation_a in dict_of_functions_a.items():
                                        original_func_name_a = get_original_func_name(name_a)
                                        
                                        if implementation_a == implementation_b:
                                            unchanged_function_list.append(name_b)
                                            matched = True
                                            break
                                        else:
                                            continue
                                    
                                    if matched == False:
                                        # This case could be 'added' or 'modified':
                                        modified_function_list.append(name_b)
                            else:
                                added_function_list.append(name_b)
                        
                        # Need to take care of the case when count_a >= 1 and count_b == 0
                        for name_a, implement_a in dict_of_functions_a.items():
                            original_func_name_a = get_original_func_name(name_a)
                            count_a = copy_function_count_a.get(original_func_name_a, 0)
                            count_b = copy_function_count_b.get(original_func_name_a, 0)

                            if count_a >= 1 and count_b == 0:
                                deleted_function_list.append(name_a)
                    
                    # If the file is 'deleted' or newly 'added', then all the functions should have the status of "deleted" or "added":
                    elif len(web_request_function_data.list_of_functions_b) > 0:
                        added_function_list = list(dict_of_functions_b.keys())
                    elif len(web_request_function_data.list_of_functions_a) > 0:
                        deleted_function_list = list(dict_of_functions_a.keys())

                    ## Prepare the query batches to save to the database:
                    insert_function_query_template = '''IF NOT EXISTS (SELECT 1 FROM [dbo].[Bugzilla_Mozilla_Functions] WHERE [Changeset_File_Unique_Hash] = ? AND [Function_Signature] = ?) INSERT INTO [dbo].[Bugzilla_Mozilla_Functions] ([Changeset_File_Unique_Hash], [Function_Signature], [Function_Status], [Inserted_On]) VALUES (?, ?, ?, GETUTCDATE());'''
                    for func_sign in added_function_list:
                        db_queries += insert_function_query_template
                        func_sign = func_sign.strip()
                        params.extend([db_mozilla_changeset_file.changeset_file_unique_hash, func_sign, db_mozilla_changeset_file.changeset_file_unique_hash, func_sign, "added"])
                        query_count += 1
                        check_batch_limit()
                    for func_sign in deleted_function_list:
                        db_queries += insert_function_query_template
                        func_sign = func_sign.strip()
                        params.extend([db_mozilla_changeset_file.changeset_file_unique_hash, func_sign, db_mozilla_changeset_file.changeset_file_unique_hash, func_sign, "deleted"])
                        query_count += 1
                        check_batch_limit()
                    for func_sign in modified_function_list:
                        db_queries += insert_function_query_template
                        func_sign = func_sign.strip()
                        params.extend([db_mozilla_changeset_file.changeset_file_unique_hash, func_sign, db_mozilla_changeset_file.changeset_file_unique_hash, func_sign, "modified"])
                        query_count += 1
                        check_batch_limit()
                    for func_sign in unchanged_function_list:
                        db_queries += insert_function_query_template
                        func_sign = func_sign.strip()
                        params.extend([db_mozilla_changeset_file.changeset_file_unique_hash, func_sign, db_mozilla_changeset_file.changeset_file_unique_hash, func_sign, "unchanged"])
                        query_count += 1
                        check_batch_limit()
                
                # Prepare query to update the process status in `Bugzilla_Mozilla_Changeset_Files`:
                update_process_statuses = " | ".join(web_request_function_data.process_statuses) if web_request_function_data.process_statuses else None
                db_queries += '''UPDATE [Bugzilla_Mozilla_Changeset_Files] SET [Process_Status] = ? WHERE [Task_Group] = ? AND [Row_Num] = ?;'''
                params.extend([update_process_statuses, db_mozilla_changeset_file.task_group, db_mozilla_changeset_file.row_num])

                # Add any remaining queries to the last batch:
                if db_queries:
                    batches.append((db_queries, params))

                try_again = "first try"
                save_data_attempt_number = 1
                while try_again == "first try" or try_again == "true":
                    try:
                        if is_conn_open == False:
                            conn = pyodbc.connect(conn_str)
                            cursor = conn.cursor()
                            is_conn_open = True

                        # Note: set this to 'True' if we want to save data to json files without even attempt save data to SQL server:
                        if False:
                            # Save data to the second storage: json file:
                            self.save_queries_to_json(db_mozilla_changeset_file.task_group, db_mozilla_changeset_file.row_num, batches)
                            try_again = "false"
                            print(f"\nData save failed after {save_data_attempt_number} attempts. Data saved to JSON file...", end="\n", flush=True)

                            # Re-open connection to update process status:
                            conn = pyodbc.connect(conn_str)
                            cursor = conn.cursor()

                            cursor.execute('''
                                UPDATE Bugzilla_Mozilla_Changeset_Files
                                    SET process_status = 'json_file'
                                where Row_Num = ?
                                    and Task_Group = ?
                                    and process_status is null;
                                ''',(db_mozilla_changeset_file.row_num, db_mozilla_changeset_file.task_group))
                            
                            conn.commit()
                            return


                        # Start transactions:
                        cursor.execute("BEGIN TRANSACTION")

                        # Execute batches of queries
                        for batch_query, batch_params in batches:
                            cursor.execute(batch_query, batch_params)

                        # Commit the transaction
                        cursor.execute("COMMIT")
                        conn.commit()

                        # Free resource for other processes b/c we don't want a process to hold resource for too long
                        cursor.close()
                        conn.close()
                        is_conn_open = False

                        if batches:
                            # Re-establish new cursor and conn:
                            conn = pyodbc.connect(conn_str)
                            cursor = conn.cursor()

                            # Check to see if the data actually being save:
                            cursor.execute('''
                                select top 1 process_status
                                from Bugzilla_Mozilla_Changeset_Files
                                where Row_Num=?
                                    and Task_Group=?;
                                ''',(db_mozilla_changeset_file.row_num, db_mozilla_changeset_file.task_group))
                            
                            process_status_after_db_saved = cursor.fetchone()
                            
                            if process_status_after_db_saved and process_status_after_db_saved[0] is not None:
                                try_again = "false"
                                return
                            else:
                                if save_data_attempt_number < 1:
                                    try_again = "true"
                                    print(f"Attempt: {str(save_data_attempt_number)}/3. Data save failed.", end="", flush=True)
                                    save_data_attempt_number += 1
                                else:
                                    # Closed cursor and conn first:
                                    cursor.close()
                                    conn.close()
                                    is_conn_open = False

                                    # Save data to the second storage: json file:
                                    self.save_queries_to_json(db_mozilla_changeset_file.task_group, db_mozilla_changeset_file.row_num, batches)
                                    try_again = "false"
                                    print(f"\nData save failed after {save_data_attempt_number} attempts. Data saved to JSON file...", end="\n", flush=True)

                                    # Re-open connection to update process status:
                                    conn = pyodbc.connect(conn_str)
                                    cursor = conn.cursor()

                                    cursor.execute('''
                                        UPDATE Bugzilla_Mozilla_Changeset_Files
                                            SET process_status = 'json_file'
                                        where Row_Num = ?
                                            and Task_Group = ?
                                            and process_status is null;
                                        ''',(db_mozilla_changeset_file.row_num, db_mozilla_changeset_file.task_group))
                                    
                                    conn.commit()

                    except pyodbc.Error as e:
                        cursor.execute("ROLLBACK TRANSACTION")  # Rollback transaction
                        conn.rollback()  # Ensure the rollback is completed

                        attempt_number += 1
                        print(f"pyodbc.Error:{e}.\nAttempt number: {attempt_number}. Retrying in 10 seconds...", end="\r", flush=True)
                        time.sleep(10)

                        if attempt_number >= max_retries:
                            # if reach max re-try for deadlock error, save data to json file
                            try_again = "false"
                            if batches:
                                try:
                                    # Closed cursor and conn first:
                                    cursor.close()
                                    conn.close()
                                    is_conn_open = False
                                except:
                                    pass

                                # Save data to the second storage: json file:
                                self.save_queries_to_json(db_mozilla_changeset_file.task_group, db_mozilla_changeset_file.row_num, batches)
                                try_again = "false"
                                print(f"\nData save failed after {save_data_attempt_number} attempts. Data saved to JSON file...", end="\n", flush=True)

                                # Re-open connection to update process status:
                                conn = pyodbc.connect(conn_str)
                                cursor = conn.cursor()

                                cursor.execute('''
                                    UPDATE Bugzilla_Mozilla_Changeset_Files
                                        SET process_status = 'json_file'
                                    where Row_Num = ?
                                        and Task_Group = ?
                                        and process_status is null;
                                    ''',(db_mozilla_changeset_file.row_num, db_mozilla_changeset_file.task_group))
                                
                                conn.commit()
                        else:
                            try_again = "true"
                    finally:
                        # Close the cursor and connection.
                        try:
                            cursor.close()
                            conn.close()
                            is_conn_open = False
                        except:
                            pass
                            
            # How to deal with generic error:
            except: 
                if attempt_number >= max_retries:
                    print(f"Max attempt reached. Skipped", end="", flush=True)
                    continue
            
            finally:
                # Close the cursor and connection
                try:
                    cursor.close()
                    conn.close()
                    is_conn_open = False
                except:
                    pass

    def migrate_json_file_to_db(self, start_folder, end_folder):
        ##############################################################################
        # https://chatgpt.com/c/672cb43d-8190-8004-88e5-f7b79afaada9
        # Helper Functions:
        # Helper Function to generate date folders in 'MM_DD_YYYY' format:
        def generate_date_folders(start_folder, end_folder):
            # Convert folder names to date objects
            try:
                start_date = datetime.strptime(start_folder, "%m_%d_%Y")
                end_date = datetime.strptime(end_folder, "%m_%d_%Y")
            except ValueError:
                print("Error: Invalid date format. Please use 'MM_DD_YYYY'.")
                return

            date_folders = []
            current_date = start_date
            while current_date <= end_date:
                date_folders.append(current_date.strftime("%m_%d_%Y"))
                current_date += timedelta(days=1)
            return date_folders

        def save_to_database(data):
            print(f"Saving to db...", end="", flush=True)

            attempt_number = 1
            max_connection_attempts = 10  # Number of max attempts to establish a connection.

            while attempt_number <= 5:
                connection_attempt = 1

                while connection_attempt <= max_connection_attempts:
                    try:
                        conn = pyodbc.connect(conn_str)
                        break
                    except pyodbc.Error as conn_err:
                        if conn_err.args[0] in ['08S01']:  # The connection is broken and recovery is not possible.
                            connection_attempt += 1
                            print(f"08S01.\nConnection attempt {connection_attempt} failed. Retrying in 5 seconds...", end="", flush=True)
                            time.sleep(5)
                        else:
                            raise conn_err
                else:
                    raise Exception("Failed to establish a connection after multiple attempts.")

                try:
                    cursor = conn.cursor()
                    changeset_file_unique_hash = ""
                    j = 0
                    #for entry in data:
                    while j < len(data):
                        parameters = data[j].get("parameters", [])

                        # Handle the case when the last 'parameters has only 3 elements (Example: 2_106019.json):
                        if len(parameters) == 3 and j == len(data) - 1:
                            # We update records based on task group and row num since we may not have unique hash data available to us
                            process_status = parameters[0]
                            task_group = parameters[1]
                            row_num = parameters[2]

                            update_query = """
                            UPDATE [dbo].[Bugzilla_Mozilla_Changeset_Files]
                            SET [Process_Status] = ?
                            WHERE [Task_Group] = ?
                                AND [Row_Num] = ?;
                            """
                            try:
                                cursor.execute(update_query, process_status, task_group, row_num)
                                print(f"Updated Process_Status for [task group-row num]: [{task_group}-{row_num}]")
                            except Exception as e:
                                print(f"Error updating Process_Status: {e}")
                                return False

                            conn.commit()
                            print("Data saved successfully.", flush=True)
                            return True

                        # Skip insufficient parameters (log the issue)
                        if len(parameters) < 4:
                            print(f"Skipping invalid entry: {parameters}")
                            return False

                        save_last_3 = 0
                        if j == len(data) - 1:
                            save_last_3 = 3

                        # Process function entries in chunks of 5
                        for i in range(0, len(parameters) - save_last_3, 5):
                            try:
                                if i == 0:
                                    changeset_file_unique_hash = parameters[i]

                                function_signature = parameters[i + 1]
                                function_status = parameters[i + 4]

                                # Insert into `Bugzilla_Mozilla_Functions`
                                query = """
                                IF NOT EXISTS (
                                    SELECT 1 FROM [dbo].[Bugzilla_Mozilla_Functions]
                                    WHERE [Changeset_File_Unique_Hash] = ? AND [Function_Signature] = ?
                                )
                                INSERT INTO [dbo].[Bugzilla_Mozilla_Functions] (
                                    [Changeset_File_Unique_Hash],
                                    [Function_Signature],
                                    [Function_Status],
                                    [Inserted_On]
                                ) VALUES (?, ?, ?, GETUTCDATE());
                                """
                                binary_changeset_file_hash = bytes.fromhex(changeset_file_unique_hash)
                                cursor.execute(query,
                                            binary_changeset_file_hash,
                                            function_signature,
                                            binary_changeset_file_hash,
                                            function_signature,
                                            function_status)
                            except IndexError:
                                print(f"Skipping malformed parameters: {parameters}")
                                return False
                            except Exception as e:
                                print(f"Error inserting function entry: {e}")
                                return False

                        # Update final `Process_Status` if parameters is the very last parameters:
                        if len(parameters) >= 3 and j == len(data) - 1:
                            process_status = parameters[-3]
                            try:
                                update_query = """
                                UPDATE [dbo].[Bugzilla_Mozilla_Changeset_Files]
                                SET [Process_Status] = ?
                                WHERE [Unique_Hash] = CONVERT(VARBINARY(64), ?, 1);
                                """
                                cursor.execute(update_query, process_status, bytes.fromhex(changeset_file_unique_hash))
                            except Exception as e:
                                print(f"Error updating changeset file: {e}")
                                return False

                        j += 1

                    conn.commit()
                    print("Data saved successfully.", flush=True)
                    return True

                except Exception as e:
                    print(f"Error saving to database: {e}", flush=True)
                    conn.rollback()  # Rollback on failure
                    return False

                finally:
                    conn.close()  # Ensure connection is closed


        ##############################################################################

        # Generate list of date folders to process
        date_folders = generate_date_folders(start_folder, end_folder)

        # Get the base script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Process each folder in the date range
        for date_folder_name in date_folders:
            directory = os.path.join(script_dir, "..", "..", "..", "csv_files", date_folder_name)
            
            if not os.path.exists(directory):
                print(f"Directory '{directory}' does not exist. Skipping.")
                continue

            # Process each JSON file in the folder
            for filename in os.listdir(directory):
                # filename='2_119736.json' # Quoc: removed this afterward
                if filename.endswith(".json") and not filename.startswith("COMPLETED_"):
                    file_path = os.path.join(directory, filename)
                    
                    print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}]({str(date_folder_name)} - {str(filename)}): ", end="", flush=True)
                    
                    # Read the JSON file
                    with open(file_path, 'r') as file:
                        try:
                            print(f"Reading file...", end="", flush=True)
                            data = json.load(file)
                        except json.JSONDecodeError:
                            print(f"Error decoding JSON in file: {file_path}")
                            continue

                    # Save data to the database
                    if save_to_database(data):
                        print(f"Renaming file...", end="", flush=True)

                        # Rename the file to mark it as completed
                        completed_file_path = os.path.join(directory, f"COMPLETED_{filename}")
                        os.rename(file_path, completed_file_path)
                        print(f"Successful")
                    else:
                        print(f"Somwhere failed, do not rename filename: {filename}")

    
    def process_remaining_status_json_file(self):
        # This method should only be run after 'migrate_json_file_to_db'. The 'migrate_json_file_to_db' function didn't handle the cases when
        # the 'parameters' have less than 4 elements. For example '2_106916.json' or 'COMPLETED_2_106916.json' AND '2_112154.json' or 'COMPLETED_2_112154.json'
        # Good thing that those records still have the file status of 'json_file'
        pass

    def revert_file_names(self, directory_path, list_of_files):
        """
        Revert file names by removing the 'COMPLETED_' prefix for files in the directory that match the list of files.
        
        Args:
            directory_path (str): Path to the directory where the files are located.
            list_of_files (list): List of filenames (without the 'COMPLETED_' prefix) to revert.

        Returns:
            list: A list of tuples containing (old_name, new_name) for files that were renamed successfully.
        """
        global conn_str
        renamed_files = []  # To store successfully renamed files for reporting
        
        for file_id in list_of_files:
            completed_file_name = f"COMPLETED_{file_id}.json"
            original_file_name = f"{file_id}.json"
            
            # Full paths to the old and new filenames
            completed_file_path = os.path.join(directory_path, completed_file_name)
            original_file_path = os.path.join(directory_path, original_file_name)
            
            try:
                # Check if the file exists
                if os.path.exists(completed_file_path):
                    # Rename the file
                    os.rename(completed_file_path, original_file_path)
                    renamed_files.append((completed_file_name, original_file_name))
                    print(f"Renamed: {completed_file_name} -> {original_file_name}")
                else:
                    print(f"File not found: {completed_file_name}")
            except Exception as e:
                print(f"Error renaming {completed_file_name}: {e}")
        
        return renamed_files


    def run_scraper(self, task_group, start_row, end_row):
        records_to_be_processed = self.get_records_to_process(task_group, start_row, end_row)
        total_records = len(records_to_be_processed)
        remaining_records = total_records

        for i in range(total_records):
            # While True gives us ability to re-do the iteration if needed.
            re_run_iteration_count = 1
            while re_run_iteration_count <= 5:
                db_mozilla_changeset_file = namedtuple('Record',
                        ['task_group', 'row_num', 'process_status', 'changeset_hash_id',
                         'previous_file_name', 'updated_file_name', 'file_status',
                         'changeset_file_unique_hash', 'mercurial_type', 'parent_hash'])(*records_to_be_processed[i])
                
                print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] Task Group: {str(task_group)} [{str(start_row)}-{str(end_row)}]. Remainings: {str(remaining_records)}. Process row number {db_mozilla_changeset_file.row_num}...", end="", flush=True)

                web_request_function_data = self.scrap_mozilla_function_data(db_mozilla_changeset_file)

                # overall statuses: {'Uninteresting File', 'network issue', '404', 'successful'}
                if web_request_function_data.overall_status in {"successful", "404", "Uninteresting File" }:
                    self.save_bugzilla_mozilla_functions(db_mozilla_changeset_file, web_request_function_data)
                    print(f"{web_request_function_data.overall_status}")
                    break

                # Cases: "Network issue" - If so, we treated it as has not been processed, so we re-do it.
                else:
                    if re_run_iteration_count <= 5:
                        print(f"{web_request_function_data.overall_status}. Go Sleep for 10s. Attempt: {re_run_iteration_count}/5.")
                        time.sleep(10)
                        re_run_iteration_count += 1
                    else:
                        print(f"Max attempt reach. Attempt: {re_run_iteration_count}/5. Skipped.")

            remaining_records -= 1
                        


#########################################################################

if __name__ == "__main__":
    object = Mozilla_File_Function_Scraper()

    # parser = argparse.ArgumentParser(description="")
    # parser.add_argument('arg_1', type=int, help='Argument 1')
    # parser.add_argument('arg_2', type=int, help='Argument 2')
    # parser.add_argument('arg_3', type=int, help='Argument 3')
    # parser_args = parser.parse_args()
    # task_group = parser_args.arg_1
    # start_row = parser_args.arg_2
    # end_row = parser_args.arg_3

    # Testing specific input arguments:
    # task_group = 0   # Task group
    # start_row = 2   # Start row
    # end_row = start_row   # End row

    # object.run_scraper(task_group, start_row, end_row)

    object.migrate_json_file_to_db('11_07_2024', '11_08_2024')


    # object.revert_file_names(
    #     r"C:\Users\quocb\Quoc Bui\Study\phd_in_cs\Research\first_paper\Code\r_to_b_mapping\csv_files\11_07_2024",
    # [
    #     '2_114131', '2_114132', '2_114133', '2_114134',
    #     '2_114135', '2_114136', '2_114639', '2_114863',
    #     '2_114864', '2_114865', '2_114866', '2_115547',
    #     '2_115711', '2_116537', '2_116538', '2_116766',
    #     '2_117151', '2_117152', '2_117153', '2_117154',
    #     '2_117155', '2_117156', '2_117157', '2_117296',
    #     '2_117297', '2_117298', '2_117302', '2_117303',
    #     '2_117485', '2_117862', '2_117924', '2_117925',
    #     '2_119205', '2_119239', '2_119439', '2_119735',
    #     '2_119736', '2_119783', '2_119784', '2_120091',
    #     '2_120092', '2_120094', '2_120206', '2_120207',
    #     '2_120208', '2_120843', '2_120992', '2_121733',
    #     '2_121734', '2_121887', '2_121888', '2_121889',
    #     '2_122111', '2_122513', '2_122514', '2_123403',
    #     '2_124121', '2_124122', '2_124123', '2_124135',
    #     '2_124136', '2_124137', '2_124138', '2_124139',
    #     '2_124140', '2_124412', '2_124413', '2_124468',
    #     '2_124469', '2_124574', '2_124575', '2_124576',
    #     '2_124577', '2_125645', '2_125646', '2_126189',
    #     '2_126237', '2_126238', '2_126239', '2_126240',
    #     '2_126241', '2_126275', '2_126616', '2_126617',
    #     '2_126640', '2_126743', '2_126752', '2_126753',
    #     '2_126870', '2_126871', '2_127186', '2_128140',
    #     '2_128154', '2_128307', '2_128308', '2_128378',
    #     '2_128379', '2_128400', '2_128847', '2_129020',
    #     '2_129437', '2_129465', '2_129466', '2_129584',
    #     '2_130610', '2_131114', '2_131134', '2_131135',
    #     '2_131136', '2_131137', '2_131138', '2_131639',
    #     '2_131640', '2_131880', '2_131881', '2_131897',
    #     '2_132857', '2_132858', '2_132859', '2_132912',
    #     '2_133336', '2_133420', '2_133990', '2_133992',
    #     '2_133993', '2_133994', '2_134198', '2_134222',
    #     '2_134279', '2_134280', '2_135091', '2_135259',
    #     '2_135512', '2_135513', '2_135514', '2_135824',
    #     '2_135909', '2_136660', '2_136661', '2_136904',
    #     '2_136905', '2_137097', '2_137177', '2_137543',
    #     '2_137544', '2_137643', '2_137773', '2_137784',
    #     '2_137785', '2_137786', '2_137787'
    # ])
    
    print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] PROGRAM FINISHED. EXIT!")
