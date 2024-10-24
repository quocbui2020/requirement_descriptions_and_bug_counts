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
                cursor.execute('''
                    SELECT cf.Task_Group
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
                    WHERE cf.Task_Group = ?
                    AND cf.Row_Num BETWEEN ? AND ?
                    AND cf.Process_Status IS NULL -- Null status mean the records have not been processed.
                    ORDER BY cf.Task_Group ASC, cf.Row_Num ASC
                ''', (task_group, start_row, end_row))
                
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
    
    def save_bugzilla_mozilla_functions(self, db_mozilla_changeset_file, web_request_function_data):
        attempt_number = 1
        max_retries = 10 # max retry for database issue.
        max_connection_attempts = 10  # Number of max attempts to establish a connection.
        
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

            # Reminder: dictionary can be used to access value by key: dictionary[key] => value
            dict_of_functions_a = {}
            dict_of_functions_b = {}

            # Variables to query database:
            params = []
            batches = []
            db_queries = ''
            query_count = 0
            query_size_limit = 100

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
                    
                # Start transactions:
                cursor.execute("BEGIN TRANSACTION")

                # Execute batches of queries
                for batch_query, batch_params in batches:
                    cursor.execute(batch_query, batch_params)

                # Commit the transaction
                cursor.execute("COMMIT")
                conn.commit()
                return

            except pyodbc.Error as e:
                error_code = e.args[0]
                cursor.execute("ROLLBACK TRANSACTION")  # Rollback transaction
                conn.rollback()  # Ensure the rollback is completed

                attempt_number += 1
                print(f"pyodbc.Error.\nAttempt number: {attempt_number}. Retrying in 10 seconds...", end="", flush=True)
                time.sleep(10)

                if attempt_number >= max_retries:
                    print(f"Max attempt reached. Skipped", end="", flush=True)
                    continue
            
            finally:
                # Close the cursor and connection
                cursor.close()
                conn.close()

            # TODO: Handle error: if it can't insert because of duplicate PK. We don't want it to stop the craper

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
    parser = argparse.ArgumentParser(description="")
    parser.add_argument('arg_1', type=int, help='Argument 1')
    parser.add_argument('arg_2', type=int, help='Argument 2')
    parser.add_argument('arg_3', type=int, help='Argument 3')
    parser_args = parser.parse_args()
    task_group = parser_args.arg_1
    start_row = parser_args.arg_2
    end_row = parser_args.arg_3

    # Testing specific input arguments:
    # task_group = 1   # Task group
    # start_row = 75302   # Start row
    # end_row = 75302   # End row

    scraper = Mozilla_File_Function_Scraper()
    scraper.run_scraper(task_group, start_row, end_row)

print(f"[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] PROGRAM FINISHED. EXIT!")