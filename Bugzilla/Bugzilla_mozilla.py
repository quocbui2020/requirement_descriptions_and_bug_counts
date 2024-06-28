# Optimize crawler
#   1. Reduce number of API calls.
#       1.1) Get as much bug ids as possible, use filter 'include_fields' to specific only important field.   
#   2. Filters
#       2.1) include_fields=cf_last_resolved,description,type,product,id,cf_user_story,resolution,status, comments.creation_time,comments.raw_text
#       2.2) order=bug_id DESC
#       2.3) Use limit and offset
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

logging.basicConfig(level=logging.INFO, filename=f"C:\\Users\\quocb\\Quoc Bui\\Study\\phd_in_cs\\Research\\first_paper\\Code\\r_to_b_mapping\\bugzilla\\logs\\logger_{strftime('%Y%m%d_%H-%M-%S', localtime())}.log", filemode='w', format='%(levelname)s-%(message)s')

# Connect to the database
conn = pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};'
                        'SERVER=QUOCBUI\\MSSQLSERVER01;'
                        'DATABASE=ResearchDatasets;'
                        'LongAsMax=yes;'
                        'TrustServerCertificate=yes;'
                        'Trusted_Connection=yes;')

# Prepare the SQL query
create_bugzilla_query = '''INSERT INTO [dbo].[Bugzilla]
            ([id]
           ,[bug_title]
           ,[alias]
           ,[product]
           ,[component]
           ,[type]
           ,[status]
           ,[resolution]
           ,[resolved_comment_datetime]
           ,[bug_description]
           ,[user_story]
           ,[changeset_links]
           ,[inserted_on])
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())'''
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

create_api_call_log_query = '''INSERT INTO [dbo].[API_Call_Log]
            ([Request_Url]
            ,[Is_Success])
        VALUES
            (?, ?)'''

global current_bug_id
global global_offset
global global_limit
global global_bug_request_url


def get_bug_url(offset, limit):
    base_url = "https://bugzilla.mozilla.org/rest/bug"
    request_url = base_url + "?offset=" + str(offset) + "&limit=" + str(limit) + "&order=bug_id ASC&bug_id_type=nowords&bug_id=0&include_fields=cf_last_resolved,description,type,product,id,cf_user_story,resolution,status,comments.creation_time,comments.raw_text,comments.count,summary,component,alias"
    request_url = request_url + ",history.when,history.changes" # History: Remove this
    return request_url

def BugzillaCrawler():
    global current_bug_id
    global global_offset
    global global_limit
    global global_bug_request_url

    # Base URL for Bugzilla
    global_bug_request_url = get_bug_url(global_offset, global_limit)

    try:
        #open existing csv file
        #file_path = r"C:\Users\quocb\Quoc Bui\Study\phd_in_cs\Research\first_paper\Code\r_to_b_mapping\data_and_loggers\second_attempt.csv"
        #with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        #writer = csv.writer(file)

        response = None
        for x in range(0, 3):
            # Making the GET request
            print("Making bug API request...", end="", flush=True)
            response = requests.get(global_bug_request_url)
            print("Done")

            if response.status_code == 200:
                global_limit = 1200
                break;
            
            if x == 0:
                print("Failed main API call. Go sleep for 60 seconds...")
                print(global_bug_request_url)
                time.sleep(60)
            elif x == 1:
                print("Failed main API call. Reduce global_limit to: ", end="", flush=True)
                global_limit = global_limit - (global_limit // 4)
                print(f"{str(global_limit)}.")
                global_bug_request_url = get_bug_url(global_offset, global_limit)
                time.sleep(30)
            elif x == 2:
                # If the request was not successful, print an error message
                print(f"Failed main API call.\nError at {strftime('%m/%d/%Y %H:%M:%S', localtime())}.\nCurrent URL link: {global_bug_request_url}.\nCurrent Offset={global_offset}.\nCurrent Limit={global_limit}.\n")
                info(f"#### Failed main API call.\nError at {strftime('%m/%d/%Y %H:%M:%S', localtime())}.\nCurrent URL link: {global_bug_request_url}.\nCurrent Offset={global_offset}.\nCurrent Limit={global_limit}.\n")
                # Create a new record in Bugzilla_History_Log:
                create_bugzilla_history_error_log(None, global_bug_request_url, "Failed to get 200 OK response for main request.", None, global_offset, global_limit)

                create_api_call_log(global_bug_request_url, 0)
                print(f"Exit due to multiple failed attempt to API calls.")
                exit()

        # Deserialize the response:
        json_response = response.json()
        
        # Iterate through each bug:
        for bug in json_response['bugs']:
            current_bug_id = bug.get('id', -1)
            resolved_comment_time_string = get_resolved_comment_datetime(bug)
            if resolved_comment_time_string == "failed_history_request":
                create_bugzilla_history_error_log(current_bug_id,None,"Failed history API call", "Failed history API call", None, None)
                exit()

            # Extract urls related to the bugs:
            changeset_link_list = ExtractBugChangesetLink(bug, resolved_comment_time_string)
            changeset_urls = None
            if changeset_link_list != None and len(changeset_link_list):
                changeset_urls = ''
                for link in changeset_link_list:
                    changeset_urls += link + " | "

            #Write row in Excel:
            #writer.writerow([bug['id'], bug['product'], bug['type'], bug['status'], bug['resolution'], bug['description'], bug['cf_user_story'] , changeset_urls])

            #Insert a row in Bugzilla:
            create_bugzilla(bug, changeset_urls, resolved_comment_time_string)
        
        create_api_call_log(global_bug_request_url, 1)
        return "success"
    
    except Exception as e:
        # If an exception occurs during the request, print the exception
        traceback.print_exc()
        info(f"### Error at {strftime('%m/%d/%Y %H:%M:%S', localtime())}.\nBug Id: {current_bug_id}.\nError Detail: {e}.\nCurrent URL link: {global_bug_request_url}.\nCurrent Offset={global_offset}.\n")
        info(f'{traceback.format_exc()}\n')
        create_bugzilla_history_error_log(current_bug_id, global_bug_request_url, "Failed due to exception.", traceback.format_exc(), global_offset, global_limit)
        create_api_call_log(global_bug_request_url, 0)
        exit()
        return "error"

# Update to database: [bugzilla]
def create_bugzilla(bug, changeset_urls, resolved_comment_time_string):
    # Execute the query for each bug
    cursor = conn.cursor()
    cursor.setinputsizes([(pyodbc.SQL_WVARCHAR,0,0),])

    # Extract bug information from the dictionary
    bug_id = bug['id']
    product = bug['product']
    bug_type = bug['type']
    bug_title = bug['summary']
    bug_component = bug['component']
    status = bug['status']
    resolution = bug['resolution']
    alias = bug.get('alias', None)

    if bug['cf_user_story'] == "":
        bug['cf_user_story'] = None
    user_story = bug.get('cf_user_story', None)

    if bug['description'] == "":
        bug['description'] = None
    bug_description: str = bug['description'] # Quoc: Fix this issue

    if resolved_comment_time_string == "":
        resolved_comment_time_string = None

    # Execute the query with parameterized values
    #encode_utf8_bug_description = bug_description.encode('utf-8')
    cursor.execute(create_bugzilla_query, (bug_id, bug_title, alias, product, bug_component, bug_type, status, resolution, resolved_comment_time_string, bug_description, user_story, changeset_urls))
    
    # Commit changes and close cursor/connection
    conn.commit()
    cursor.close()
    
def create_bugzilla_history_error_log(bug_id, url, error_message, detail_error_message, offset, limit):
    cursor = conn.cursor()
    cursor.execute(create_bugzilla_error_log_query, (bug_id, url, error_message, detail_error_message, offset, limit))
    conn.commit()
    cursor.close()

def create_api_call_log(request_url, is_success):
    cursor = conn.cursor()
    cursor.execute(create_api_call_log_query, (request_url, is_success))
    conn.commit()
    cursor.close()

def get_bugzilla_count(start_id, end_id):
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(id) FROM bugzilla where id >= 475363 and id <= 950725")
    return cursor.fetchone()[0]

def get_resolved_comment_datetime(bug):
    resolved_comment_time_string = bug['cf_last_resolved']

    ########################################################################################################################
    # History: uncomment these:
    # response = requests.get(f"https://bugzilla.mozilla.org/rest/bug/{current_bug_id}/history")
    # if response.status_code != 200:
    #     return "failed_history_request"

    # json_response = response.json()
    # bug_histories = json_response['bugs'][0]['history']
    ########################################################################################################################

    if resolved_comment_time_string == None or resolved_comment_time_string == "":
        resolved_comment_time_string = "1800-01-01T00:00:00Z"
    resolved_comment_time = datetime.strptime(resolved_comment_time_string, "%Y-%m-%dT%H:%M:%SZ")

    bug_histories = bug['history'] # History: Remove this
    for history in bug_histories:
        if datetime.strptime(history['when'], "%Y-%m-%dT%H:%M:%SZ") <= resolved_comment_time:
            continue

        for change in history['changes']:
            if change['field_name'] == "resolution" and change['added'] == "FIXED":
                resolved_comment_time_string = history['when']
                resolved_comment_time = datetime.strptime(resolved_comment_time_string, "%Y-%m-%dT%H:%M:%SZ")
                break
    return resolved_comment_time_string

# This function extract changeset link of each bug:
def ExtractBugChangesetLink(bug, resolved_comment_time_string):
    if bug['status'] != "RESOLVED" or bug['resolution'] != "FIXED":
        return None

    resolved_comment_count = -1
    resolved_comment = ''
    # 1. Search for resolved comment and extract link from it:
    for comment in bug['comments']:
        if (comment['creation_time'] == resolved_comment_time_string):
            resolved_comment_count = comment['count']
            resolved_comment = comment['raw_text']
            if resolved_comment != None and resolved_comment != '':
                url_matches = re.findall(r'https?://[\w\-.:/]+', comment['raw_text']) # Extract all URLs using the provided url_pattern
                if (len(url_matches) > 0):
                    unique_urls = list(set(url_matches))
                    return unique_urls
        else:
            continue

    # 2. If the comment is not absolutely blank, make a call to url to obtain the links base on the comment:
    if resolved_comment != None and resolved_comment != '':
        url = "https://bugzilla.mozilla.org/show_bug.cgi?id=0&id=" + str(bug['id']) + "&format=multiple"
        response = requests.get(url)
        # If API call failed
        if response.status_code != 200:
            info(f"#### Failed extract link API call: {current_bug_id}.\n")
            print(f"#### Failed extract link API call: {current_bug_id}.")

            # Create a new record in Bugzilla_History_Log:
            create_bugzilla_history_error_log(current_bug_id, url, "Failed to get 200 OK response from api request for changeset urls", None, None, None)
            return None
        pattern = rf'id="c{resolved_comment_count}".*?<pre.*?>(.*?)</pre>' #pattern to extract content in <pre> tag
        match_pre_content = re.search(pattern, response.content.decode('utf-8'), re.DOTALL)
        if match_pre_content:
            pre_content = match_pre_content.group(1)
            url_matches = re.findall(r'href="(https?://[^"]+)"', pre_content) # Extract all URLs using the provided url_pattern

            # Extract href attributes and append them to the base URL
            href_matches = re.findall(r'href="(/[^"]+)"', pre_content)
            for href in href_matches:
                absolute_url = "https://bugzilla.mozilla.org" + href
                url_matches.append(absolute_url)
             # Return unique URLs
            unique_urls = list(set(url_matches))
            return unique_urls
    else:
        return None

###########################################################################################
###########################################################################################

errorCount = 0
crawler_offset = 464887
global_offset = get_bugzilla_count() + crawler_offset
global_limit = 1200

for x in range(0,999):
    print(f"\n{str(x+1)}.Current offset value: {global_offset} | Current time: {strftime('%m/%d/%Y %H:%M:%S', localtime())}")
    print(f"{str(x+1)}.Processing offset ranges:[" + str(global_offset) + "-" + str(global_offset + global_limit) + "]")

    result = BugzillaCrawler()
    if result == "error":
        errorCount += 1
    else:
        errorCount = 0
    global_offset = get_bugzilla_count() + crawler_offset

print(f"\nCompleted: Bugzilla Crawler Executed.\n")
conn.close()
