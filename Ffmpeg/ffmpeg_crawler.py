import requests
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
import numpy as np

#statsmodels-0.14.2
import statsmodels.api as sm 
from statsmodels.stats.outliers_influence import variance_inflation_factor

from scipy import stats
import seaborn as sns #seaborn-0.13.2 (Aim for data visualization)
import matplotlib.pyplot as plt #matplotlib-3.9.0
#scikit-learn-1.5.0
from sklearn.decomposition import PCA
from sklearn.model_selection import train_test_split, GridSearchCV #scikit-learn-1.5.0
from sklearn.linear_model import LinearRegression, Ridge, LogisticRegression
from sklearn.metrics import mean_squared_error, r2_score, roc_curve, auc, roc_auc_score

import csv
from datetime import datetime
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydriller import Repository
import spacy
from collections import Counter


# Set the desired recursion limit
sys.setrecursionlimit(10**6)

# Increase CSV field size limit
csv.field_size_limit(10**7)  # Setting to 10 million characters

# Connection string
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=QUOCBUI\MSSQLSERVER01;' \
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

insert_ffmpeg_statistical_measurement = '''INSERT INTO [dbo].[FFmpeg_Statistical_Measurements]
            ([Ticket_ID]
           ,[version]
           ,[flesch_kincaid_reading_ease]
           ,[flesch_kincaid_grade_level]
           ,[gunning_fog_score]
           ,[smog_index]
           ,[coleman_liau_index]
           ,[automated_readability_index]
           ,[number_of_words]
           ,[number_of_complex_words]
           ,[average_grade_level]
           ,[Number_Of_Predicates])
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''

select_ticket_description = '''
WITH EnhancementTicketQuery AS (
    SELECT 
        FFmpeg.ID as Ticket_ID,
        FFmpeg.Type as Ticket_Type,
		FFmpeg.Summary,
		FFmpeg.Description_Original,
		FFmpeg.Description_Without_SigNonNL,
		FFmpeg.Characters_Removed_Percentage,
		FFmpeg.Is_Contain_SigNonNL,
        FFmpeg.Ticket_Created_On,
        FFmpeg_Commit_Diff.File_Name,
        FFmpeg_functions.Function_Name,
        FFmpeg_functions.File_Change_Status,
        FFmpeg_Commit_Diff.Date AS Date
    FROM 
        FFmpeg
    INNER JOIN 
        FFmpeg_Commit_Diff ON FFmpeg_Commit_Diff.Ticket_ID = FFmpeg.ID
    INNER JOIN 
        FFmpeg_functions ON FFmpeg_functions.File_Index = FFmpeg_Commit_Diff.File_Index 
                         AND FFmpeg_functions.File_Prev_Index = FFmpeg_Commit_Diff.File_Prev_Index 
    WHERE 
        FFmpeg.Type = 'enhancement'
        AND FFmpeg.Status = 'closed'
        AND FFmpeg.Resolution = 'fixed'
        AND FFmpeg.Hash_ID IS NOT NULL
        AND FFmpeg.Component <> 'documentation'
        AND (FFmpeg_functions.File_Change_Status = 'modified' 
             OR FFmpeg_functions.File_Change_Status = 'added')
),

DefectTicketQuery AS (
    SELECT 
        FFmpeg.ID as Ticket_ID,
        FFmpeg.Type as Ticket_Type,
        FFmpeg.Ticket_Created_On,
        FFmpeg_Commit_Diff.File_Name,
        FFmpeg_functions.Function_Name,
        FFmpeg_functions.File_Change_Status,
        FFmpeg_Commit_Diff.Date AS Date
    FROM 
        FFmpeg
    INNER JOIN 
        FFmpeg_Commit_Diff ON FFmpeg_Commit_Diff.Ticket_ID = FFmpeg.ID
    INNER JOIN 
        FFmpeg_functions ON FFmpeg_functions.File_Index = FFmpeg_Commit_Diff.File_Index 
                         AND FFmpeg_functions.File_Prev_Index = FFmpeg_Commit_Diff.File_Prev_Index 
    WHERE 
        FFmpeg.Type = 'defect'
        AND FFmpeg.Status = 'closed'
        AND FFmpeg.Resolution = 'fixed'
        AND FFmpeg.Hash_ID IS NOT NULL
        AND FFmpeg.Component <> 'documentation'
        AND (FFmpeg_functions.File_Change_Status = 'modified' 
             OR FFmpeg_functions.File_Change_Status = 'deleted')
),

JoinedQuery AS (
    SELECT 
        e.Ticket_ID AS Enhancement_Ticket_ID,
        e.Ticket_Type AS Enhancement_Type,
        e.Ticket_Created_On AS Enhancement_Ticket_Created_On,
        e.File_Name AS Enhancement_File_Name,
        e.Function_Name AS Enhancement_Function_Name,
        e.File_Change_Status AS Enhancement_File_Change_Status,
        e.Date AS Enhancement_Commit_Date,
		e.Summary,
		e.Description_Original,
		e.Description_Without_SigNonNL,
		e.Characters_Removed_Percentage,
		e.Is_Contain_SigNonNL,
		d.File_Name AS Defect_File_Name,
		d.Function_Name AS Defect_Function_Name,
        d.Ticket_ID AS Defect_Ticket_ID,
        d.Ticket_Type AS Defect_Type,
        d.Ticket_Created_On AS Defect_Ticket_Created_On,
        d.File_Change_Status AS Defect_File_Change_Status,
        d.Date AS Defect_Commit_Date
    FROM 
        EnhancementTicketQuery e
    LEFT JOIN 
        DefectTicketQuery d ON e.File_Name = d.File_Name 
                           AND e.Function_Name = d.Function_Name
						   AND CONVERT(datetime2, SUBSTRING(e.Date, 6, 20)) < CONVERT(datetime2, SUBSTRING(d.Date, 6, 20))
),
DistinctQuery AS (
	SELECT DISTINCT Enhancement_Ticket_ID, Defect_Ticket_ID, Summary, Description_Original, Description_Without_SigNonNL, Characters_Removed_Percentage, Is_Contain_SigNonNL
	FROM JoinedQuery
)
Select distinct
Enhancement_Ticket_ID
,Description_Original
,Description_Without_SigNonNL
from DistinctQuery
where 1=1
order by Enhancement_Ticket_ID asc;
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
        
        #Eixsting file has been removed:
        if curr_file_index == '0000000000':
            deleted_functions = extract_function_names_and_implementations_c_code(';' + remove_comments_c_file(get_c_file_content(prev_file_index)))
            for name, _ in deleted_functions:
                cursor.execute(insert_ffmpeg_function_query, (prev_file_index, curr_file_index, name, prev_file_index, curr_file_index, name, 'deleted'))
        #File is created:
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

 #insert_ffmpeg_functions('68a8ea31f1', 'b4107ac873') # Just testing single commit




# # Define a function to process each tuple in c_file_commit_diff
# def process_tuple(tuple_data):
#     prev_file_index, curr_file_index, _ = tuple_data
#     print(f"Progressing index: ({prev_file_index}, {curr_file_index})...", end="", flush=True)
#     insert_ffmpeg_functions(prev_file_index, curr_file_index)
#     print("Done")

# # Get the c_file_commit_diff data
# c_file_commit_diff = get_c_file_indices_from_commit_diff()

# # Create a ThreadPoolExecutor with a maximum of, for example, 5 threads
# with ThreadPoolExecutor(max_workers=1) as executor:
#     # Submit tasks for each tuple in c_file_commit_diff
#     futures = [executor.submit(process_tuple, tuple_data) for tuple_data in c_file_commit_diff]

#     # Wait for all tasks to complete
#     for future in as_completed(futures):
#         try:
#             future.result()  # Get the result of each task (this will propagate any exceptions)
#         except Exception as e:
#             print(f"An error occurred: {e}")










###########################################################################################
## Test extract_function_names_and_implementations_c_code function ##
file_content = ''';

#include "config_components.h"

static void draw_digit(int digit, uint8_t *dst, ptrdiff_t dst_linesize,
                       int segment_width)
{
#define TOP_HBAR        1
#define MID_HBAR        2
#define BOT_HBAR        4
#define LEFT_TOP_VBAR   8
#define LEFT_BOT_VBAR  16
#define RIGHT_TOP_VBAR 32
#define RIGHT_BOT_VBAR 64
    struct segments {
        int x, y, w, h;
    } segments[] = {
        { 1,  0, 5, 1 }, /* TOP_HBAR */
        { 1,  6, 5, 1 }, /* MID_HBAR */
        { 1, 12, 5, 1 }, /* BOT_HBAR */
        { 0,  1, 1, 5 }, /* LEFT_TOP_VBAR */
        { 0,  7, 1, 5 }, /* LEFT_BOT_VBAR */
        { 6,  1, 1, 5 }, /* RIGHT_TOP_VBAR */
        { 6,  7, 1, 5 }  /* RIGHT_BOT_VBAR */
    };
    static const unsigned char masks[10] = {
        /* 0 */ TOP_HBAR         |BOT_HBAR|LEFT_TOP_VBAR|LEFT_BOT_VBAR|RIGHT_TOP_VBAR|RIGHT_BOT_VBAR,
        /* 1 */                                                        RIGHT_TOP_VBAR|RIGHT_BOT_VBAR,
        /* 2 */ TOP_HBAR|MID_HBAR|BOT_HBAR|LEFT_BOT_VBAR                             |RIGHT_TOP_VBAR,
        /* 3 */ TOP_HBAR|MID_HBAR|BOT_HBAR                            |RIGHT_TOP_VBAR|RIGHT_BOT_VBAR,
        /* 4 */          MID_HBAR         |LEFT_TOP_VBAR              |RIGHT_TOP_VBAR|RIGHT_BOT_VBAR,
        /* 5 */ TOP_HBAR|BOT_HBAR|MID_HBAR|LEFT_TOP_VBAR                             |RIGHT_BOT_VBAR,
        /* 6 */ TOP_HBAR|BOT_HBAR|MID_HBAR|LEFT_TOP_VBAR|LEFT_BOT_VBAR               |RIGHT_BOT_VBAR,
        /* 7 */ TOP_HBAR                                              |RIGHT_TOP_VBAR|RIGHT_BOT_VBAR,
        /* 8 */ TOP_HBAR|BOT_HBAR|MID_HBAR|LEFT_TOP_VBAR|LEFT_BOT_VBAR|RIGHT_TOP_VBAR|RIGHT_BOT_VBAR,
        /* 9 */ TOP_HBAR|BOT_HBAR|MID_HBAR|LEFT_TOP_VBAR              |RIGHT_TOP_VBAR|RIGHT_BOT_VBAR,
    };
    unsigned mask = masks[digit];
    int i;

    draw_rectangle(0, dst, dst_linesize, segment_width, 0, 0, 8, 13);
    for (i = 0; i < FF_ARRAY_ELEMS(segments); i++)
        if (mask & (1<<i))
            draw_rectangle(255, dst, dst_linesize, segment_width,
                           segments[i].x, segments[i].y, segments[i].w, segments[i].h);
}

#define GRADIENT_SIZE (6 * 256)

static void test_fill_picture(AVFilterContext *ctx, AVFrame *frame)
{
    TestSourceContext *test = ctx->priv;
    uint8_t *p, *p0;
    int x, y;
    int color, color_rest;
    int icolor;
    int radius;
    int quad0, quad;
    int dquad_x, dquad_y;
    int grad, dgrad, rgrad, drgrad;
    int seg_size;
    int second;
    int i;
    uint8_t *data = frame->data[0];
    int width  = frame->width;
    int height = frame->height;

    /* draw colored bars and circle */
    radius = (width + height) / 4;
    quad0 = width * width / 4 + height * height / 4 - radius * radius;
    dquad_y = 1 - height;
    p0 = data;
    for (y = 0; y < height; y++) {
        p = p0;
        color = 0;
        color_rest = 0;
        quad = quad0;
        dquad_x = 1 - width;
        for (x = 0; x < width; x++) {
            icolor = color;
            if (quad < 0)
                icolor ^= 7;
            quad += dquad_x;
            dquad_x += 2;
            *(p++) = icolor & 1 ? 255 : 0;
            *(p++) = icolor & 2 ? 255 : 0;
            *(p++) = icolor & 4 ? 255 : 0;
            color_rest += 8;
            if (color_rest >= width) {
                color_rest -= width;
                color++;
            }
        }
        quad0 += dquad_y;
        dquad_y += 2;
        p0 += frame->linesize[0];
    }

    /* draw sliding color line */
    p0 = p = data + frame->linesize[0] * (height * 3/4);
    grad = (256 * test->nb_frame * test->time_base.num / test->time_base.den) %
        GRADIENT_SIZE;
    rgrad = 0;
    dgrad = GRADIENT_SIZE / width;
    drgrad = GRADIENT_SIZE % width;
    for (x = 0; x < width; x++) {
        *(p++) =
            grad < 256 || grad >= 5 * 256 ? 255 :
            grad >= 2 * 256 && grad < 4 * 256 ? 0 :
            grad < 2 * 256 ? 2 * 256 - 1 - grad : grad - 4 * 256;
        *(p++) =
            grad >= 4 * 256 ? 0 :
            grad >= 1 * 256 && grad < 3 * 256 ? 255 :
            grad < 1 * 256 ? grad : 4 * 256 - 1 - grad;
        *(p++) =
            grad < 2 * 256 ? 0 :
            grad >= 3 * 256 && grad < 5 * 256 ? 255 :
            grad < 3 * 256 ? grad - 2 * 256 : 6 * 256 - 1 - grad;
        grad += dgrad;
        rgrad += drgrad;
        if (rgrad >= GRADIENT_SIZE) {
            grad++;
            rgrad -= GRADIENT_SIZE;
        }
        if (grad >= GRADIENT_SIZE)
            grad -= GRADIENT_SIZE;
    }
    p = p0;
    for (y = height / 8; y > 0; y--) {
        memcpy(p+frame->linesize[0], p, 3 * width);
        p += frame->linesize[0];
    }

    /* draw digits */
    seg_size = width / 80;
    if (seg_size >= 1 && height >= 13 * seg_size) {
        int64_t p10decimals = 1;
        double time = av_q2d(test->time_base) * test->nb_frame *
                      ff_exp10(test->nb_decimals);
        if (time >= INT_MAX)
            return;

        for (x = 0; x < test->nb_decimals; x++)
            p10decimals *= 10;

        second = av_rescale_rnd(test->nb_frame * test->time_base.num, p10decimals, test->time_base.den, AV_ROUND_ZERO);
        x = width - (width - seg_size * 64) / 2;
        y = (height - seg_size * 13) / 2;
        p = data + (x*3 + y * frame->linesize[0]);
        for (i = 0; i < 8; i++) {
            p -= 3 * 8 * seg_size;
            draw_digit(second % 10, p, frame->linesize[0], seg_size);
            second /= 10;
            if (second == 0)
                break;
        }
    }
}
#endif /* CONFIG_ZONEPLATE_FILTER */
'''
# functions = extract_function_names_and_implementations_c_code(file_content)
# for function_name, implementation in functions:
#     print("Function Name:", function_name)
#     print("Function Implementation:")
#     print(implementation)
#     print("-----")

###########################################################################################


###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
## Calculate the Readability Scores ##
def post_url_readable_tool(text):
    html_entities = ''.join([f'&#{ord(char)};' for char in text])
    
    # Define the URL and payload
    url = 'https://www.webfx.com/tools/m/ra/check.php'
    payload = {
        'tab': 'Test by Direct Link',
        'input': html_entities
    }
    
    # Make the POST request
    response = requests.post(url, data=payload)
    if response.status_code != 200:
        return None
    
    # Return the response content
    return response.content

def extract_readability_values(byte_content):
    # Step 1: Decode byte content to string
    content = byte_content.decode('utf-8')
    
    # Step 2: Extract `card-percent` values
    card_percent_values = re.findall(r'class=\\"card-percent\\">([\d.-]+)<\\/p>', content)
    card_percent_values = card_percent_values[:6]  # Get only the first 6 values

    # Step 3: Extract `card-value` values
    card_value_values = re.findall(r'class=\\"card-value\\">([\d.-]+)<\\/p>', content)
    card_value_values = card_value_values[:6]  # Get only the first 6 values

    # Combine both lists
    values = card_percent_values + card_value_values

    return values

def insert_readability_measures_to_db(ticket_id, version, result_list):
    try:
        # Connect to the database
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Extract values from the result list
        flesch_kincaid_reading_ease = float(result_list[0])
        flesch_kincaid_grade_level = float(result_list[1])
        gunning_fog_score = float(result_list[2])
        smog_index = float(result_list[3])
        coleman_liau_index = float(result_list[4])
        automated_readability_index = float(result_list[5])
        number_of_words = int(result_list[7])
        number_of_complex_words = int(result_list[8])
        
        # Calculate average grade level
        average_grade_level = (
            flesch_kincaid_grade_level + 
            coleman_liau_index + 
            smog_index + 
            automated_readability_index + 
            gunning_fog_score
        ) / 5.0

        # Insert the values into the database
        cursor.execute(insert_ffmpeg_statistical_measurement, 
                       ticket_id, version, flesch_kincaid_reading_ease, flesch_kincaid_grade_level, gunning_fog_score, 
                       smog_index, coleman_liau_index, automated_readability_index, number_of_words, 
                       number_of_complex_words, average_grade_level, None)

        # Commit the transaction
        conn.commit()
        
    except pyodbc.Error as e:
        print(f"Database error: {e}")
    finally:
        # Close the cursor and connection
        cursor.close()
        conn.close()

def get_ticket_descriptions_from_db():
    try:
        # Connect to the database
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Execute the select query
        cursor.execute(select_ticket_description)
        
        # Fetch all results
        rows = cursor.fetchall()
        
        # Process the results into a list of dictionaries
        result = []
        for row in rows:
            result.append((row.Enhancement_Ticket_ID, row.Description_Original, row.Description_Without_SigNonNL))
        
        return result
    
    except pyodbc.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        # Close the cursor and connection
        cursor.close()
        conn.close()

###########################################################################################
## This is the loop to obtain readability measures and store in FFmpeg_Statistical_Measurements:
# list_of_records = get_ticket_descriptions_from_db()
# for record in list_of_records:  
#     ticket_id, description = record
#     print(f"Processing ticket id {ticket_id}...", end="", flush=True)
#     response_content = None
#     if description != '' and description != None:
#         response_content = post_url_readable_tool(description)
#     if response_content != None:
#         readability_scores = extract_readability_values(response_content)
#         insert_readability_measures_to_db(ticket_id, 'Description_Without_SigNonNL', readability_scores)
#         print("Done")
#     else:
#         print("Failed")

###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
## Extract and save predicates of the text ##
def extract_predicates(text):
    nlp = spacy.load('en_core_web_sm')
    # Process the text
    doc = nlp(text)
    predicates = []

    for sent in doc.sents:
        subject = ""
        predicate = ""
        for token in sent:
            if token.dep_ == 'nsubj':
                subject = token.text
                predicate = ' '.join([tok.text for tok in token.head.subtree if tok.dep_ != 'nsubj'])
                break
        if predicate:
            predicates.append((subject, predicate))

    return predicates

# count_predicates: count number of predicates.
def count_predicates(predicates):
    # Extract just the predicates from the subject-predicate pairs
    predicate_list = [predicate for subject, predicate in predicates]
    # Use Counter to count the occurrences of each predicate
    predicate_counts = Counter(predicate_list)
    # Return the number of unique predicates
    num_of_predicates = len(predicate_counts)
    return num_of_predicates

def save_predicate_count_to_db(num_of_predicates, ticket_id, version):
    try:
        # Connect to the database
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Execute the select query
        update_predicate_query = '''
            update FFmpeg_Statistical_Measurements
            set Number_Of_Predicates = ?
            where Ticket_ID= ? AND version = ? AND Number_Of_Predicates is null
        '''
        cursor.execute(update_predicate_query, (num_of_predicates, ticket_id, version))
        conn.commit()
    
    except pyodbc.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        # Close the cursor and connection
        cursor.close()
        conn.close()

###########################################################################################
## Initiates processing predicates:
# list_of_records = get_ticket_descriptions_from_db()
# for record in list_of_records:  
#     ticket_id, description = record
#     print(f"Extract Predicates from ticket id {ticket_id}...", end="", flush=True)
#     predicates = extract_predicates(description)
#     num_of_predicates = count_predicates(predicates)
#     save_predicate_count_to_db(num_of_predicates, ticket_id, "Description_Original")
#     # save_predicate_count_to_db(num_of_predicates, ticket_id, "Description_Without_SigNonNL")
#     print("Done")

###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
## Process `Characters_Removed_Percentage` and `Is_Contain_SigNonNL` ##
def save_characters_removed_percentage_in_db(ticket_id, original_description, cleaned_description):
    len_original_description = len(original_description)
    len_cleaned_description = len(cleaned_description)
    char_rm_percentage = ((len_original_description - len_cleaned_description) / len_original_description) * 100

    try:
        # Connect to the database
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Execute the select query
        update_Characters_Removed_Percentage_query = '''
            update FFmpeg
            set Characters_Removed_Percentage = ?
            where ID= ? AND Characters_Removed_Percentage is null
        '''
        cursor.execute(update_Characters_Removed_Percentage_query, (char_rm_percentage, ticket_id))
        conn.commit()
    
    except pyodbc.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        # Close the cursor and connection
        cursor.close()
        conn.close()

###########################################################################################
## Initiates the process `Characters_Removed_Percentage`:
# list_of_records = get_ticket_descriptions_from_db()
# for record in list_of_records:
#     ticket_id, description_orig, description_cleaned = record
#     print(f"Process `Characters_Removed_Percentage` for ticket id {ticket_id}...", end="", flush=True)
#     save_characters_removed_percentage_in_db(ticket_id, description_orig, description_cleaned)
#     print("Done")

###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
###########################################################################################
## Perform statistical analysis

# call_stored_procedure_sp_GeFFmpegData: Execute stored procedure `sp_GeFFmpegData`:
def call_stored_procedure_sp_GeFFmpegData(version, Characters_Removed_Percentage):
    # Connect to the database
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    # Execute the stored procedure
    cursor.execute(f"EXEC sp_GetFFmpegData @version=N'{version}', @Characters_Removed_Percentage='{Characters_Removed_Percentage}'")
    
    # Fetch all rows from the executed stored procedure
    rows = cursor.fetchall()
    
    # Get column names
    columns = [column[0] for column in cursor.description]
    
    # Convert rows into a list of dictionaries
    dataset = [dict(zip(columns, row)) for row in rows]
    
    # Close the cursor and connection
    cursor.close()
    conn.close()
    
    return dataset

# 1. Perform correlation_analysis: Correlation Coeffient matrix:
def correlation_analysis(data):
    # Convert the data to a pandas DataFrame
    df = pd.DataFrame(data)
    
    # Select the relevant columns for correlation analysis
    columns = [
        'Does_Contain_Any_Bug',
        'flesch_kincaid_reading_ease',
        'flesch_kincaid_grade_level',
        #'gunning_fog_score',
        #'smog_index',
        'coleman_liau_index',
        #'automated_readability_index',
        'number_of_words',
        'number_of_complex_words',
        #'average_grade_level',
        'Number_Of_Predicates',
        #'Does_Contain_NonNL',
        'Characters_Removed_Percentage'
    ]
    
    # Subset the DataFrame to include only the relevant columns
    df_subset = df[columns]
    
    # Calculate the correlation matrix
    correlation_matrix = df_subset.corr()
    
    # Print the correlation matrix
    print("Correlation Matrix:")
    print(correlation_matrix)
    
    # Visualize the correlation matrix
    plt.figure(figsize=(12, 10))
    sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', vmin=-1, vmax=1)
    plt.title('Correlation Matrix')
    plt.show()
    
    return correlation_matrix

# calculate_vif: Perform Variance Inflation Factor (VIF) to handle Multicollinearity
def calculate_vif(data):
    # Convert the data to a pandas DataFrame
    df = pd.DataFrame(data)

    # Define the independent variables
    independent_vars = [
        'flesch_kincaid_reading_ease',
        'flesch_kincaid_grade_level',
        'gunning_fog_score',
        'smog_index',
        'coleman_liau_index',
        'automated_readability_index',
        'number_of_words',
        'number_of_complex_words',
        'average_grade_level',
        'Number_Of_Predicates'
    ]

    # Ensure the column names are correct
    X = df[independent_vars]

    # Add a constant term
    X = sm.add_constant(X)
    
    # Calculate VIF for each variable
    vif_data = pd.DataFrame()
    vif_data["Feature"] = X.columns
    vif_data["VIF"] = [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]
    
    # Handle infinite VIFs
    while vif_data["VIF"].max() > 10:  # You can adjust the threshold as needed
        max_vif_feature = vif_data.loc[vif_data["VIF"].idxmax(), "Feature"]
        print(f"Removing {max_vif_feature} due to high VIF")
        if max_vif_feature == "const":
            break
        X = X.drop(columns=[max_vif_feature])
        
        vif_data = pd.DataFrame()
        vif_data["Feature"] = X.columns
        vif_data["VIF"] = [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]
    
    return vif_data

def remove_high_vif(data, threshold=10.0):
    df = pd.DataFrame(data)
    independent_vars = [
        'flesch_kincaid_reading_ease',
        'flesch_kincaid_grade_level',
        'gunning_fog_score',
        'smog_index',
        'coleman_liau_index',
        'automated_readability_index',
        'number_of_words',
        'number_of_complex_words',
        'average_grade_level',
        'Number_Of_Predicates'
    ]
    X = df[independent_vars]
    X = sm.add_constant(X)
    
    while True:
        vif_data = pd.DataFrame()
        vif_data["Feature"] = X.columns
        vif_data["VIF"] = [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]
        
        max_vif = vif_data['VIF'].max()
        if max_vif > threshold:
            max_vif_feature = vif_data.loc[vif_data['VIF'].idxmax(), 'Feature']
            print(f"Removing {max_vif_feature} due to high VIF of {max_vif}")
            X = X.drop(columns=[max_vif_feature])
        else:
            break
    
    return X.columns.tolist()

def multiple_linear_regression_full_data(data):
    # Convert the data to a pandas DataFrame
    df = pd.DataFrame(data)
    
    # Define the independent variables
    independent_vars = [
        'flesch_kincaid_reading_ease',
        'flesch_kincaid_grade_level',
        #'gunning_fog_score',
        #'smog_index',
        'coleman_liau_index',
        #'automated_readability_index',
        'number_of_words',
        'number_of_complex_words',
        #'average_grade_level',
        'Number_Of_Predicates'
    ]
    
    # Define the dependent variable
    dependent_var = 'Bug_Count'
    
    # Prepare the data for regression
    X = df[independent_vars]
    y = df[dependent_var]
    
    # Add a constant term (intercept)
    X = sm.add_constant(X)
    
    # Fit the model using statsmodels to get the summary statistics
    model_stats = sm.OLS(y, X).fit()
    
    # Print the summary statistics
    print(model_stats.summary())
    
    # Calculate predictions
    y_pred = model_stats.predict(X)
    
    # Calculate performance metrics
    mse = mean_squared_error(y, y_pred)
    r_squared = r2_score(y, y_pred)
    
    print(f'Mean Squared Error: {mse}')
    print(f'R-squared: {r_squared}')
    
    return model_stats

# Combine between `multiple_linear_regression` and `multiple_linear_regression_sklearn` - It split data
def multiple_linear_regression_split80_20(data):
    # Convert the data to a pandas DataFrame
    df = pd.DataFrame(data)
    
    # Define the independent variables
    independent_vars = [
        'flesch_kincaid_reading_ease',
        #'flesch_kincaid_grade_level',
        #'gunning_fog_score',
        #'smog_index',
        #'coleman_liau_index',
        'automated_readability_index',
        #'number_of_words',
        'number_of_complex_words',
        #'average_grade_level',
        'Number_Of_Predicates'
    ]
    
    # Define the dependent variable
    dependent_var = 'Bug_Count'
    
    # Prepare the data for regression
    X = df[independent_vars]
    y = df[dependent_var]
    
    # Add a constant term
    X = sm.add_constant(X)
    
    # Split the data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Fit the model using training data
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    # Predict on the test data
    y_pred = model.predict(X_test)
    
    # Calculate model performance metrics
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    # Print model performance metrics
    print("Mean Squared Error:", mse)
    print("R-squared:", r2)
    
    # Use statsmodels to calculate the p-values and standard errors on the training set
    model_stats = sm.OLS(y_train, X_train).fit()
    
    # Extracting the coefficients, standard errors, t-values, and p-values
    coef = model_stats.params
    std_err = model_stats.bse
    t_values = model_stats.tvalues
    p_values = model_stats.pvalues
    
    # Summary
    summary = pd.DataFrame({
        'Coefficient': coef,
        'Standard Error': std_err,
        't-Statistic': t_values,
        'p-Value': p_values
    })
    
    # Print summary
    print(summary)
    
    return model

# logistic_regression_analysis (Applied when independent vars is binary value)
def logistic_regression_analysis_split_80_20(data):
    # Convert the data to a pandas DataFrame
    df = pd.DataFrame(data)
    
    # Define the independent variables
    independent_vars = [
        'flesch_kincaid_reading_ease',
        'flesch_kincaid_grade_level',
        #'gunning_fog_score',
        #'smog_index',
        'coleman_liau_index',
        #'automated_readability_index',
        'number_of_words',
        'number_of_complex_words',
        #'average_grade_level',
        'Number_Of_Predicates'
    ]
    
    # Define the dependent variable
    dependent_var = 'Bug_Count'
    
    # Prepare the data for regression
    X = df[independent_vars]
    y = df[dependent_var]
    
    # Split the data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Create a logistic regression model
    model = LogisticRegression()
    
    # Fit the model to the training data
    model.fit(X_train, y_train)
    
    # Predict on the test data
    y_pred = model.predict(X_test)
    
    # Calculate accuracy
    accuracy = accuracy_score(y_test, y_pred)
    
    # Calculate confusion matrix
    conf_matrix = confusion_matrix(y_test, y_pred)
    
    # Calculate classification report
    class_report = classification_report(y_test, y_pred)
    
    # Print model performance metrics
    print("Accuracy:", accuracy)
    print("Confusion Matrix:\n", conf_matrix)
    print("Classification Report:\n", class_report)
    
    # Print the coefficients
    coeff_df = pd.DataFrame(model.coef_.flatten(), X.columns, columns=['Coefficient'])
    print(coeff_df)
    
    return model


#########################################################################


# logistic_regression_analysis (Applied when independent vars is binary value)
def logistic_regression_analysis_full_data(data):
    # Convert the data to a pandas DataFrame
    df = pd.DataFrame(data)
    
    # Define the independent variables
    independent_vars = [
        'flesch_kincaid_reading_ease',
        'flesch_kincaid_grade_level',
        #'gunning_fog_score',
        #'smog_index',
        'coleman_liau_index',
        #'automated_readability_index',
        'number_of_words',
        'number_of_complex_words',
        #'average_grade_level',
        'Number_Of_Predicates',
        #'Does_Contain_NonNL',
        'Characters_Removed_Percentage'
    ]
    
    # Convert independent variables to numeric and handle errors
    for var in independent_vars:
        df[var] = pd.to_numeric(df[var], errors='coerce')

    # Define the dependent variable
    dependent_var = 'Does_Contain_Any_Bug'
    
    # Prepare the data for regression
    X = df[independent_vars]
    y = df[dependent_var]
    
    # Add a constant term (intercept) to the model
    X = sm.add_constant(X)
    
    # Fit the logistic regression model using statsmodels
    logit_model = sm.Logit(y, X)
    result = logit_model.fit()
    
    # Print the summary of the model
    print(result.summary())
    
    return result

# Plot ROC curve (Applied when independent vars is binary value)
def plot_roc_curve(data):
    # Convert the data to a pandas DataFrame
    df = pd.DataFrame(data)
    
    # Define the independent variables
    # Define the independent variables
    independent_vars = [
        'flesch_kincaid_reading_ease',
        'flesch_kincaid_grade_level',
        #'gunning_fog_score',
        #'smog_index',
        'coleman_liau_index',
        #'automated_readability_index',
        'number_of_words',
        'number_of_complex_words',
        #'average_grade_level',
        'Number_Of_Predicates',
        #'Does_Contain_NonNL',
        'Characters_Removed_Percentage'
    ]
    
    # Define the dependent variable
    dependent_var = 'Does_Contain_Any_Bug'
    
    # Prepare the data for logistic regression
    X = df[independent_vars]
    y = df[dependent_var]
    
    # Fit logistic regression model
    model = LogisticRegression()
    model.fit(X, y)
    
    # Calculate ROC curve
    fpr, tpr, thresholds = roc_curve(y, model.predict_proba(X)[:,1])
    
    # Calculate AUC
    roc_auc = auc(fpr, tpr)
    
    # Plot ROC curve
    plt.figure()
    plt.plot(fpr, tpr, color='darkorange', lw=2, label='ROC curve (area = %0.2f)' % roc_auc)
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('Receiver Operating Characteristic')
    plt.legend(loc="lower right")
    plt.show()


def compute_auc_for_each_predictor(data):
    df = pd.DataFrame(data)
    
    # Define the independent variables
    independent_vars = [
        'flesch_kincaid_reading_ease',
        'flesch_kincaid_grade_level',
        #'gunning_fog_score',
        #'smog_index',
        'coleman_liau_index',
        #'automated_readability_index',
        'number_of_words',
        'number_of_complex_words',
        #'average_grade_level',
        'Number_Of_Predicates',
        #'Does_Contain_NonNL',
        'Characters_Removed_Percentage'
    ]
    
    # Define the dependent variable
    dependent_var = 'Does_Contain_Any_Bug'
    
    # Prepare the data for analysis
    X = df[independent_vars]
    y = df[dependent_var]
    
    # Initialize an empty dictionary to store AUC values for each predictor
    auc_values = {}
    
    # Fit a logistic regression model for each predictor individually and compute AUC
    for predictor in independent_vars:
        # Fit logistic regression model
        model = LogisticRegression()
        model.fit(X[[predictor]], y)
        
        # Predict probabilities
        y_pred_proba = model.predict_proba(X[[predictor]])[:, 1]
        
        # Compute AUC
        auc = roc_auc_score(y, y_pred_proba)
        
        # Store AUC value for the predictor
        auc_values[predictor] = auc
        
    return auc_values


###########################################################################################
if __name__ == "__main__":
    #dataset = call_stored_procedure_sp_GeFFmpegData(version='Description_Original', Characters_Removed_Percentage='99')
    dataset = call_stored_procedure_sp_GeFFmpegData(version='Description_Without_SigNonNL', Characters_Removed_Percentage='99')
    # dataset = call_stored_procedure_sp_GeFFmpegData(version='Description_Original', Characters_Removed_Percentage='0')
    
    correlation_matrix = correlation_analysis(dataset)
    # vif_data = calculate_vif(dataset)
    # selected_vars = remove_high_vif(dataset)
    # print(f"\n\n***Selected variables after removing high VIF: {selected_vars}")
    # print("\n\nMultiple_linear_regression_split80_20:")
    # model = multiple_linear_regression_split80_20(dataset)
    # print("\nMultiple_linear_regression_full_data:")
    # model = multiple_linear_regression_full_data(dataset)

    #Bug_Count is binary values:
    print("\n\nLogistic_regression_analysis_full_data:")
    model = logistic_regression_analysis_full_data(dataset)

    print("\n\nCompute_auc_for_each_predictor:")
    print(compute_auc_for_each_predictor(dataset))

    print("\n\nPlot_roc_curve:")
    model = plot_roc_curve(dataset)