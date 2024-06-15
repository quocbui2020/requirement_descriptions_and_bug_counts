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
import pandas as pd
import pyodbc
import csv
from datetime import datetime
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydriller import Repository

# Set the desired recursion limit
sys.setrecursionlimit(10**6)

# Increase CSV field size limit
csv.field_size_limit(10**7)  # Setting to 10 million characters

# Connect to the database
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=QUOCBUI\\SQLEXPRESS;' \
           'DATABASE=ResearchDatasets;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

insert_ffmpeg_query = '''INSERT INTO [dbo].[FFmpeg]
            ([ID]
           ,[Summary]
           ,[Type]
           ,[Component]
           ,[Status]
           ,[Resolution]
           ,[Priority]
           ,[Description]
           ,[Ticket_Created_On]
           ,[Ticket_Modified_On]
           ,[Hash_ID]
           ,[Note])
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, null)'''

insert_ffmpeg_function_query = '''
IF NOT EXISTS (
    SELECT 1
    FROM [dbo].[FFmpeg_Functions]
    WHERE [File_Prev_Index] = ? AND [File_Index] = ? AND [Function_Name] = ?
)
BEGIN
    INSERT INTO [dbo].[FFmpeg_Functions] ([File_Prev_Index], [File_Index], [Function_Name], [File_Change_Status])
    VALUES (?, ?, ?, ?);
END
'''

global global_max
global global_page
global ffmpeg_request_url

def error_log_process_commit_diff(error_message):
    with open("C:/Users/quocb/Quoc Bui/Study/phd_in_cs/Research/first_paper/Code/r_to_b_mapping/Ffmpeg/error_log_process_commit_diff.txt", "a") as file:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        file.write(f"[{timestamp}] {error_message}\n")

def log_error(file_name, error_message):
    with open(f"C:/Users/quocb/Quoc Bui/Study/phd_in_cs/Research/first_paper/Code/r_to_b_mapping/Ffmpeg/{file_name}.txt", "a") as file:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        file.write(f"[{timestamp}] {error_message}\n")

#import entries from csv file to database
#For the most part, we can just download data in csv files, then just save the csv files to the database.
def import_csv_to_db(file_path):
    global conn_str, insert_ffmpeg_query

    # Connect to the database
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    try:
        # Read the CSV file
        df = pd.read_csv(file_path)

        # Iterate over the rows of the dataframe and insert them into the database
        for index, row in df.iterrows():
            created = str(row['Created'])
            modified = str(row['Modified'])

            print(f"Inserting row {index + 1}:")
            print(f"Created: {created}")
            print(f"Modified: {modified}")

            # Execute the SQL query
            print("Executing SQL query:")
            print(insert_ffmpeg_query)
            print("Parameters:")
            print(row['id'], row['Summary'], row['Type'], row['Component'], row['Status'], row['Resolution'], row['Priority'], None, created, modified, None)

            # Execute the SQL query
            cursor.execute(insert_ffmpeg_query, 
                row['id'], 
                row['Summary'] if pd.notnull(row['Summary']) else None, 
                row['Type'] if pd.notnull(row['Type']) else None, 
                row['Component'] if pd.notnull(row['Component']) else None, 
                row['Status'] if pd.notnull(row['Status']) else None, 
                row['Resolution'] if pd.notnull(row['Resolution']) else None, 
                row['Priority'] if pd.notnull(row['Priority']) else None, 
                None,  # Description column is set to null
                created, 
                modified, 
                None)  # Hash_ID column is set to null

            # Commit the transaction every 1000 rows to avoid excessive transaction log growth
            if (index + 1) % 1000 == 0:
                conn.commit()

        # Final commit
        conn.commit()

    except Exception as e:
        # Handle any exceptions
        print(f"Error: {e}")

    finally:
        # Close the cursor and connection
        cursor.close()
        conn.close()

def get_fixed_enhancement_ids():
    try:
        # Connect to the database
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # SQL query
        query = '''
                SELECT id
                FROM ffmpeg
                ORDER BY id ASC;
                '''

        # Execute the query
        cursor.execute(query)

        # Fetch all rows
        rows = cursor.fetchall()

        # Close the cursor and connection
        cursor.close()
        conn.close()

        return rows

    except Exception as e:
        print(f"Error: {e}")
        return None
    
def update_descriptions(ids_result, csv_file_path):
    try:
        # Connect to the database
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Read the CSV file
        with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            next(reader)  # Skip the header row

            # Iterate over the IDs
            for i in range(len(ids_result)):
                current_id = ids_result[i][0]

                # Initialize description
                description = ""

                # Iterate over each line in the CSV file
                for row in reader:
                    if row[0] == str(current_id):
                        # Append description, including leading " and trailing newline
                        description += row[1] + '\n'
                    elif i < len(ids_result) - 1 and row[0] == str(ids_result[i + 1][0]):
                        break  # Stop at the next ID
                    elif i == len(ids_result) - 1 and row[0] == str(ids_result[i][0]):
                        description += row[1]  # Append description in the last row

                # Reset the reader to the beginning of the file
                csvfile.seek(0)
                next(reader)  # Skip the header row again

                # Update ffmpeg table with the description using parameterized query
                update_query = '''
                                UPDATE ffmpeg
                                SET Description=?
                                WHERE id=?
                                '''

                # Execute the update query with parameters
                cursor.execute(update_query, (description, current_id))
                conn.commit()

    except Exception as e:
        print(f"Error: {e}")

    finally:
        # Close the cursor and connection
        cursor.close()
        conn.close()


###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
## Mining the hash ids for each tickets ##

def get_fixed_ticket_ids():
    try:
        # Connect to the database
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Define the query
        query = '''
        SELECT id
        FROM FFmpeg
        WHERE [Status] = 'closed'
        AND [Resolution] = 'fixed'
        AND (Hash_ID is null or Hash_ID='')
        ORDER BY id ASC;
        '''
        
        # Execute the query
        cursor.execute(query)
        results = cursor.fetchall()

        # Extract IDs from the results
        ids = [row[0] for row in results]

        # Print the results for verification
        print("Query executed successfully. Result:")
        for id in ids:
            print(id)

        return ids

    except Exception as e:
        print(f"Error: {e}")

    finally:
        cursor.close()
        conn.close()

def ffmpeg_rss_ticket_content_crawler(ticketId):
    # Construct the URL with the given ticketId
    url = f"https://trac.ffmpeg.org/ticket/{ticketId}?format=rss"
    
    # Make the GET request
    response = requests.get(url)
    
    # Check if the request was successful
    if response.status_code == 200:
        # Return the content of the request
        return response.content
    else:
        # Return an error message if the request failed
        return f"Failed to retrieve data: {response.status_code}"

def get_hash_ids(rss_content):
    # Convert bytes content to string if necessary
    if isinstance(rss_content, bytes):
        rss_content = rss_content.decode('utf-8')

    # Search for the match string
    matches = re.finditer(r'&lt;span class="trac-field-new"&gt;fixed&lt;/span&gt;', rss_content)
    
    hash_ids = set()  # Use a set to store unique hash IDs
    
    for match in matches:
        # Start position after the match
        start_pos = match.end()
        # Find the end of the description tag
        end_pos = rss_content.find('</description>', start_pos)
        
        if end_pos != -1:
            # Substring between match and end of description
            description_content = rss_content[start_pos:end_pos]
            # Find all potential hash IDs in the description content
            potential_hash_ids = re.findall(r'\b[a-fA-F0-9]{7,40}\b', description_content)
            
            # Add all found hash IDs to the set
            hash_ids.update(potential_hash_ids)
    
    # Join all hash IDs with " | " and return
    return " | ".join(hash_ids)

def save_hash_to_database(ticket_id, hash_ids):
    global conn_str

    # Update query
    update_query = """
    UPDATE FFmpeg
    SET Hash_ID = ?
    WHERE Id = ?
    """

    try:
        # Connect to the database
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Execute the update query with parameters
        cursor.execute(update_query, (hash_ids, ticket_id))
        conn.commit()

    except pyodbc.Error as e:
        print(f"Error occurred: {e}")

    finally:
        # Close the cursor and connection
        cursor.close()
        conn.close()

def process_ticket_ids(ticket_ids):
    for ticket_id in ticket_ids:
        print(f"Progressing ticket {ticket_id}...", end="", flush=True)
        rss_content = ffmpeg_rss_ticket_content_crawler(ticket_id)
        hash_ids = get_hash_ids(rss_content)
        save_hash_to_database(ticket_id, hash_ids)
        print("Done")


###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
## Extract modified files from commit ##

# 1. Get the list of hash ids by ticket id:
def get_ffmpeg_hash_ids():
    global conn_str
    
    # List to store the results
    hash_ids = []
    
    # SQL query to fetch the hash_ids
    query = """
        SELECT ID, FFmpeg.Hash_ID
        FROM FFmpeg
        WHERE [Status] = 'closed'
        AND [Resolution] = 'fixed'
        AND [Hash_ID] IS NOT NULL
        AND ID NOT IN (
            SELECT DISTINCT ticket_id
            FROM FFmpreg_Commit_Diff
        );
    """
    
    try:
        # Connect to the database
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Execute the query
        cursor.execute(query)
        
        # Fetch all rows from the executed query
        rows = cursor.fetchall()
        
        # Iterate through the rows and append to the list
        for row in rows:
            hash_ids.append((row.ID, row.Hash_ID))
        
    except pyodbc.Error as e:
        print("Error in connection or execution: ", e)
    
    finally:
        # Ensure the connection is closed properly
        if 'conn' in locals():
            conn.close()
    
    # Return the list of (ID, Hash_ID) pairs
    return hash_ids

# 2. Collect data of commit diff for each ticket_id:
def get_ffmpeg_commit_details(ticket_id, hash_ids_str):
    # Parse the hash IDs directly within the function
    hash_ids_list = hash_ids_str.split(" | ")
    hash_ids_list = [hash_id.strip() for hash_id in hash_ids_list]
    
    # Regular expressions to extract required data
    date_regex = re.compile(r"^Date:\s+(.+)$", re.MULTILINE)
    diff_git_regex = re.compile(r"^diff --git a\/(.+?) b\/", re.MULTILINE)
    index_regex = re.compile(r"^index\s+(\w+)\.\.(\w+)\s+", re.MULTILINE)
    
    max_connection_reset_retries = 3  # Maximum retries for ConnectionResetError
    
    while True:
        try:
            # Connect to the database
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()
            
            for hash_id in hash_ids_list:
                url = f"https://git.ffmpeg.org/gitweb/ffmpeg.git/commitdiff_plain/{hash_id}"
                response = requests.get(url)
                
                if response.status_code == 200:
                    content = response.text
                    
                    # Extract the date from the second row
                    date_match = date_regex.search(content)
                    if date_match:
                        date_str = date_match.group(1).strip()
                    
                    # Initialize lists to store extracted data
                    file_names = []
                    file_prev_indices = []
                    file_indices = []
                    
                    # Extract file paths and indices
                    diff_git_matches = diff_git_regex.finditer(content)
                    for diff_git_match in diff_git_matches:
                        file_name = diff_git_match.group(1)
                        file_names.append(file_name)
                        
                        # Find the index after the current diff --git
                        start_pos = diff_git_match.end()
                        index_match = index_regex.search(content, start_pos)
                        if index_match:
                            file_prev_index = index_match.group(1)
                            file_index = index_match.group(2)
                            file_prev_indices.append(file_prev_index)
                            file_indices.append(file_index)
                    
                    # Insert or update the data into the database
                    for file_name, file_prev_index, file_index in zip(file_names, file_prev_indices, file_indices):
                        # Use MERGE SQL statement to insert or update records
                        cursor.execute("""
                            MERGE INTO dbo.FFmpreg_Commit_Diff AS Target
                            USING (VALUES (?, ?, ?, ?, ?, ?)) AS Source (Ticket_Id, Hash_Id, File_Name, File_Index, File_Prev_Index, Date)
                            ON Target.Ticket_Id = Source.Ticket_Id
                            AND Target.Hash_Id = Source.Hash_Id
                            WHEN NOT MATCHED THEN
                                INSERT (Ticket_Id, Hash_Id, File_Name, File_Index, File_Prev_Index, Date)
                                VALUES (Source.Ticket_Id, Source.Hash_Id, Source.File_Name, Source.File_Index, Source.File_Prev_Index, Source.Date);
                        """, (ticket_id, hash_id, file_name, file_index, file_prev_index, date_str))
                    
                    # Commit the transaction
                    conn.commit()
            
            # If execution reaches here, transaction is successful
            break
            
        except pyodbc.DatabaseError as e:
            # Check if the error is due to deadlock
            sql_state = e.args[0].split(',')[0]
            if sql_state == '40001':  # Deadlock error
                print(f"Deadlock detected. Retrying transaction indefinitely...")
                error_log_process_commit_diff(f"Deadlock error for Ticket ID {ticket_id}: {str(e)}")
                time.sleep(1)  # Wait for a short delay before retrying
                continue
            
            # If it's a connection reset error, retry the row for a limited number of attempts
            elif isinstance(e.args[1], ConnectionResetError):
                print(f"Connection reset error. Retrying transaction ({max_connection_reset_retries} attempts left)...")
                error_log_process_commit_diff(f"Connection reset error for Ticket ID {ticket_id}: {str(e)}")
                max_connection_reset_retries -= 1
                if max_connection_reset_retries <= 0:
                    print("Maximum retries for connection reset error reached. Exiting...")
                    error_log_process_commit_diff(f"Maximum retries reached for connection reset error for Ticket ID {ticket_id}")
                    break
                time.sleep(1)  # Wait for a short delay before retrying
                continue
                
            # If it's not a deadlock or connection reset error, raise the exception
            raise
            
        except Exception as e:
            error_message = f"Error encountered for Ticket ID {ticket_id}: {str(e)}"
            print(error_message)
            error_log_process_commit_diff(error_message)
            
            # Rollback any changes if there was an error
            if 'conn' in locals():
                conn.rollback()
            
            # Exit the program
            sys.exit(1)
        
        finally:
            # Ensure the connection is closed properly
            if 'conn' in locals():
                conn.close()

# 3. Generate multiple threads and divide tickets among them:
def process_commit_diff_record(record):
    ticket_id, hash_ids_str = record
    print(f"Progressing ticket {ticket_id}...", end="", flush=True)
    get_ffmpeg_commit_details(ticket_id, hash_ids_str)
    print("Done")

def begin_process_commit_diff():
    try:
        # Fetch the list of (ticket_id, hash_ids_str)
        records = get_ffmpeg_hash_ids()

        # Number of threads to use
        num_threads = 4  # Adjust the number of threads as needed

        # Create a ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            # Submit tasks to the executor
            futures = [executor.submit(process_commit_diff_record, record) for record in records]
            
            # Wait for all tasks to complete
            for future in as_completed(futures):
                try:
                    future.result()  # This will re-raise any exceptions that occurred in the thread
                except Exception as e:
                    print(f"Exception occurred during thread execution: {e}")
    except Exception as e:
        print(f"Error encountered during execution: {e}")
        sys.exit(1)


###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
## Extract Modified Files in c ##

#1. Get file indices of c files:
def get_c_file_indices_from_commit_diff():
    global conn_str

    try:
        # Connect to the database
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Execute the SQL query to retrieve File_Name, File_Prev_Index, and File_Index
        cursor.execute("""
            SELECT DISTINCT c.[File_Prev_Index], c.[File_Index], c.[Ticket_Id]
            FROM FFmpreg_Commit_Diff AS c
            LEFT JOIN FFmpeg_Functions AS f
                ON c.File_Prev_Index = f.File_Prev_Index
                AND c.File_Index = f.File_Index
            WHERE f.File_Prev_Index IS NULL
                AND f.File_Index IS NULL
                AND RIGHT(c.File_Name, 2) = '.c'
            ORDER By c.[File_Prev_Index] ASC;
        """)

        # Fetch all rows and return as a list of tuples
        rows = cursor.fetchall()
        file_indices = [(row.File_Prev_Index, row.File_Index, row.Ticket_Id) for row in rows]

        return file_indices

    except pyodbc.DatabaseError as e:
        print(f"Database error: {e}")
        # Handle the error as per your requirement

    finally:
        # Close the database connection
        if 'conn' in locals():
            conn.close()

#2. Function to remove all the comments in c files:
def remove_comments_c_file(file_content):
    # Regular expression patterns to match C-style comments
    block_comment_pattern = re.compile(r'/\*.*?\*/', re.DOTALL)
    line_comment_pattern = re.compile(r'//.*?$' , re.MULTILINE)
    
    # Remove block comments
    file_content_without_comments = re.sub(block_comment_pattern, '', file_content)
    # Remove line comments
    file_content_without_comments = re.sub(line_comment_pattern, '', file_content_without_comments)
    
    return file_content_without_comments

#3. Function to extract only the function names in c file content:
def extract_function_names_c_code_content(file_content):
    # List of C keywords that are not function names
    c_keywords = {
        'auto', 'break', 'case', 'char', 'const', 'continue', 'default', 'do', 'double', 'else',
        'enum', 'extern', 'float', 'for', 'goto', 'if', 'inline', 'int', 'long', 'register',
        'restrict', 'return', 'short', 'signed', 'sizeof', 'static', 'struct', 'switch',
        'typedef', 'union', 'unsigned', 'void', 'volatile', 'while', '_Bool', '_Complex', '_Imaginary'
    }

    # Regular expression to find potential function definitions
    regex_pattern = re.compile(r'\W(\w+)\s*\(')

    parenthesis_count = 0
    function_names = []
    keyword = ''

    pos = 0
    while pos < len(file_content):
        if parenthesis_count == 0:
            match = regex_pattern.search(file_content, pos)
            if match:
                keyword = match.group(1)
                pos = match.end()
                parenthesis_count += 1
            else:
                break  # No more matches
        else:
            if file_content[pos] == '(':
                parenthesis_count += 1
            elif file_content[pos] == ')':
                parenthesis_count -= 1
                if parenthesis_count == 0 and keyword:
                    # Check for '{' after closing parenthesis with possible spaces/newlines in between
                    rest_of_content = file_content[pos+1:].lstrip()
                    if rest_of_content.startswith('{'):
                        if keyword not in c_keywords:
                            function_names.append(keyword)

                    keyword = ''
            pos += 1

    return function_names

#4. Function to extract function implementation in c file content:
def extract_function_names_and_implementations_c_code(file_content):
    function_names = []
    function_implementations = []
    #function_pattern = re.compile(r'(?:[^a-zA-Z0-9\s*\r\n\{\(])\s*([\w\s*]+)\s+([a-zA-Z_]\w*)\s*\(') #Close to work
    #function_pattern = re.compile(r'\b\w+\s*\*?\s*(\w+)\s*\(') #Works, but missing retur type
    function_pattern = re.compile(r'(?:[^a-zA-Z0-9\s*\r\n\{\(])\s*\w+([\w\s*]+)\(')
    
    parenthesis_count = 0
    curly_bracket_count = 0
    keyword = ''
    implementation_start = 0
    
    def c_keywords():
        return {
            'if', 'else', 'while', 'for', 'do', 'switch', 'case', 'default',
            'break', 'continue', 'return', 'goto', 'typedef', 'struct', 'union',
            'enum', 'static', 'const', 'volatile', 'inline', 'extern', 'auto',
            'register', 'sizeof'
        }
    
    i = 0
    while i < len(file_content):
        if parenthesis_count == 0:
            match = function_pattern.search(file_content, i)
            if match:
                # Attempt to get the potential class name.
                keyword = match.group(1)
                keyword_matches = re.findall(r'\b[a-zA-Z0-9_]+\b', keyword)
                if keyword_matches:
                    keyword = keyword_matches[-1]  # Get the last match as the function name
                else:
                    keyword = ''  # Set keyword to an empty string if no matches are found

                i = match.end()  # Set i to the end of the matched pattern
                parenthesis_count += 1
                implementation_start = match.start(1)  # Start of function implementation
            else:
                i += 1
        else:
            if file_content[i] == '(':
                parenthesis_count += 1
            elif file_content[i] == ')':
                parenthesis_count -= 1
                if parenthesis_count == 0 and curly_bracket_count == 0 and keyword:
                    # Skip whitespace and check for '{'
                    j = i + 1
                    while j < len(file_content) and file_content[j] in ' \t\n\r':
                        j += 1
                    if j < len(file_content) and file_content[j] == '{':
                        curly_bracket_count += 1
                        i = j + 1  # Move i to the position right after '{'
                        while i < len(file_content) and curly_bracket_count > 0:
                            if file_content[i] == '{':
                                curly_bracket_count += 1
                            elif file_content[i] == '}':
                                curly_bracket_count -= 1
                            i += 1
                        if curly_bracket_count == 0:
                            i -= 1 # set i index back to '}' character
                            function_implementation = file_content[implementation_start:i+1].strip()
                            if keyword not in c_keywords():
                                function_names.append(keyword)
                                function_implementations.append((keyword, function_implementation))
                                i -= 1 #set i index to character before '}'
                            keyword = ''
                    else:
                        keyword = ''
            i += 1
    return function_implementations

#5. Function to determine status of each function names and save to 
def insert_ffmpeg_functions(prev_file_index, curr_file_index):
    global conn_str
    global insert_ffmpeg_function_query
    
    try:
        # Connect to the database
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        if curr_file_index == '0000000000':
            deleted_functions = extract_function_names_and_implementations_c_code(';' + remove_comments_c_file(get_c_file_content(prev_file_index)))
            for name, _ in deleted_functions:
                cursor.execute(insert_ffmpeg_function_query, (prev_file_index, curr_file_index, name, prev_file_index, curr_file_index, name, 'deleted'))
        elif prev_file_index == '0000000000':
            added_functions = extract_function_names_and_implementations_c_code(';' + remove_comments_c_file(get_c_file_content(curr_file_index)))
            for name, _ in added_functions:
                cursor.execute(insert_ffmpeg_function_query, (prev_file_index, curr_file_index, name, prev_file_index, curr_file_index, name, 'added'))
        else:
            # Extract functions from both commits
            list_of_prev_commit_functions = extract_function_names_and_implementations_c_code(';' + remove_comments_c_file(get_c_file_content(prev_file_index)))
            list_of_current_commit_functions = extract_function_names_and_implementations_c_code(';' + remove_comments_c_file(get_c_file_content(curr_file_index)))

            # Create dictionaries to hold function implementations
            prev_commit_functions = {name: re.sub(r'\s+', '', impl) for name, impl in list_of_prev_commit_functions}
            current_commit_functions = {name: re.sub(r'\s+', '', impl) for name, impl in list_of_current_commit_functions}

            # Determine function status
            modified_functions = []
            deleted_functions = []
            added_functions = []
            unchanged_functions = []

            for name, prev_implementation in prev_commit_functions.items():
                if name in current_commit_functions:
                    current_implementation = current_commit_functions[name]
                    if prev_implementation != current_implementation:
                        modified_functions.append(name)
                    else:
                        unchanged_functions.append(name)
                    del current_commit_functions[name]
                else:
                    deleted_functions.append(name)

            added_functions = list(current_commit_functions.keys())

            # Insert modified functions into the database
            for name in modified_functions:
                query = insert_ffmpeg_function_query
                cursor.execute(query, (prev_file_index, curr_file_index, name, prev_file_index, curr_file_index, name, 'modified'))

            # Insert unchanged functions into the database
            for name in unchanged_functions:
                query = insert_ffmpeg_function_query
                cursor.execute(query, (prev_file_index, curr_file_index, name, prev_file_index, curr_file_index, name, 'unchanged'))

            # Insert deleted functions into the database
            for name in deleted_functions:
                query = insert_ffmpeg_function_query
                cursor.execute(query, (prev_file_index, curr_file_index, name, prev_file_index, curr_file_index, name, 'deleted'))

            # Insert added functions into the database
            for name in added_functions:
                query = insert_ffmpeg_function_query
                cursor.execute(query, (prev_file_index, curr_file_index, name, prev_file_index, curr_file_index, name, 'added'))

        # Commit transaction
        conn.commit()

    except pyodbc.DatabaseError as e:
        # Rollback transaction on error and log error
        if 'cursor' in locals():
            conn.rollback()
        log_error("log_error_ffmpeg_functions", f"Database error: {e}")
        print(f"Database error: {e}")
    except Exception as e:
        # Rollback transaction on general error and log error
        if 'cursor' in locals():
            conn.rollback()
        log_error("log_error_ffmpeg_functions", f"Error: {e}")
        print(f"Error: {e}")
    finally:
        # Close the database connection
        if 'conn' in locals():
            conn.close()

#NN. Testing function
def get_c_file_content(file_index):
    url = f"https://git.ffmpeg.org/gitweb/ffmpeg.git/blob_plain/{file_index}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad status codes
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching file content for index {file_index}: {e}")
        return None

###########################################################################################
## Real Run ##
# c_file_commit_diff = get_c_file_indices_from_commit_diff()
# for tuple_data in c_file_commit_diff:
#     prev_file_index, curr_file_index, _ = tuple_data  # Extracting only prev_file_index and curr_file_index
#     print(f"Progressing index: ({prev_file_index}, {curr_file_index})...", end="", flush=True)
#     insert_ffmpeg_functions(prev_file_index, curr_file_index)
#     print("Done")

# insert_ffmpeg_functions('68a8ea31f1', 'b4107ac873') # Just testing single commit













# Define a function to process each tuple in c_file_commit_diff
def process_tuple(tuple_data):
    prev_file_index, curr_file_index, _ = tuple_data
    print(f"Progressing index: ({prev_file_index}, {curr_file_index})...", end="", flush=True)
    insert_ffmpeg_functions(prev_file_index, curr_file_index)
    print("Done")

# Get the c_file_commit_diff data
c_file_commit_diff = get_c_file_indices_from_commit_diff()

# Create a ThreadPoolExecutor with a maximum of, for example, 5 threads
with ThreadPoolExecutor(max_workers=1) as executor:
    # Submit tasks for each tuple in c_file_commit_diff
    futures = [executor.submit(process_tuple, tuple_data) for tuple_data in c_file_commit_diff]

    # Wait for all tasks to complete
    for future in as_completed(futures):
        try:
            future.result()  # Get the result of each task (this will propagate any exceptions)
        except Exception as e:
            print(f"An error occurred: {e}")










###########################################################################################
## Test extract_function_names_and_implementations_c_code function ##
# file_content = ''';
# '''
# functions = extract_function_names_and_implementations_c_code(file_content)
# for function_name, implementation in functions:
#     print("Function Name:", function_name)
#     print("Function Implementation:")
#     print(implementation)
#     print("-----")

###########################################################################################
