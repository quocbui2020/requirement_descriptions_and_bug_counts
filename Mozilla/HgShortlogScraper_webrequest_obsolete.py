"""
Shortlog Scraper for Mozilla Central - ROBUST OVERNIGHT MODE

Crawls shortlog pages from start_changeset_id to end_changeset_id and stores basic info in Shortlog_MozillaCentral_webrequest table.

ROBUST FEATURES FOR OVERNIGHT SCRAPING:
- Infinite retry with progressive backoff (1min -> 2min -> 5min -> 10min -> 10min indefinitely)
- Zero tolerance for failure - never gives up on a request
- Handles all error types: connection errors, timeouts, HTTP errors, etc.
- 120-second timeout per request to prevent hanging
- Automatic retry schedule ensures overnight completion

BACKOFF SCHEDULE:
- Attempt 1 fail: Wait 1 minute
- Attempt 2 fail: Wait 2 minutes
- Attempt 3 fail: Wait 5 minutes
- Attempt 4+ fail: Wait 10 minutes (indefinitely)
"""
import requests
from time import strftime, localtime
import pyodbc
import re
import time

# Connection string
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=localhost\\SQLEXPRESS;' \
           'DATABASE=MozillaDataSet2026;' \
           'Connection Timeout=300;' \
           'Login Timeout=300;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

# SQL query for inserting shortlog records
insert_shortlog_query = '''
    INSERT INTO [dbo].[Shortlog_MozillaCentral_webrequest]
        ([Hash_Id]
        ,[Changeset_Summary]
        ,[Changeset_Datetime]
        ,[Inserted_On])
    VALUES
        (?, ?, ?, SYSUTCDATETIME())
'''

def crawl_mozilla_central_shortlog(hash_id):
    """
    Crawl a single shortlog page and extract changeset information.
    ROBUST OVERNIGHT MODE: Infinite retry with progressive backoff.
    NEVER GIVES UP - will retry indefinitely until success.
    
    Args:
        hash_id: The changeset hash to start from
    
    Returns:
        tuple: (changeset_info_list, next_hash)
    """
    request_url = f"https://hg.mozilla.org/mozilla-central/shortlog/{hash_id}"
    attempt = 0
    
    # Progressive backoff schedule: 1min, 2min, 5min, 10min, then 10min indefinitely
    backoff_schedule = [60, 120, 300, 600]  # seconds
    
    while True:  # INFINITE RETRY - never give up!
        attempt += 1
        
        try:
            # Add timeout to prevent hanging forever
            response = requests.get(request_url, timeout=120)
            
            if response.status_code == 200:
                # SUCCESS - parse the content
                content = response.text
                changeset_info_list = []

                # Define the regular expression pattern for extracting rows
                row_pattern = re.compile(
                    r'<tr class="parity[01]">.*?<a href="(/mozilla-central/rev/.*?)">diff</a>.*?<i class="age">(.*?)</i>.*?<strong><cite>(.*?)</cite> - (.*?)</strong>', 
                    re.DOTALL)

                # Find all matching rows
                rows = row_pattern.findall(content)

                for row in rows:
                    changeset_link = row[0]
                    extracted_hash_id = changeset_link.split('/')[-1]
                    changeset_datetime = row[1].strip()
                    Changeset_Summary = f"{row[2]} - {row[3]}"

                    # Add the information to the list
                    changeset_info_list.append({
                        "hash_id": extracted_hash_id,
                        "changeset_datetime": changeset_datetime,
                        "Changeset_Summary": Changeset_Summary
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
                
            elif response.status_code == 429:
                # Rate limited
                print(f"\n[ATTEMPT {attempt}] Rate limited (429)")
                print(f"[URL] {request_url}")
                
            else:
                # Other HTTP error
                print(f"\n[ATTEMPT {attempt}] HTTP {response.status_code} error")
                print(f"[URL] {request_url}")
                
        except requests.exceptions.Timeout:
            print(f"\n[ATTEMPT {attempt}] Request timeout (exceeded 120 seconds)")
            print(f"[URL] {request_url}")
            
        except (requests.exceptions.ConnectionError, ConnectionResetError) as e:
            print(f"\n[ATTEMPT {attempt}] Connection error: {type(e).__name__}")
            print(f"[URL] {request_url}")
            
        except Exception as e:
            print(f"\n[ATTEMPT {attempt}] Unexpected error: {type(e).__name__}: {e}")
            print(f"[URL] {request_url}")
        
        # Calculate wait time using progressive backoff
        if attempt <= len(backoff_schedule):
            wait_time = backoff_schedule[attempt - 1]
        else:
            wait_time = 600  # 10 minutes for all subsequent attempts
        
        wait_minutes = wait_time / 60
        print(f"[INFO] Will retry at: {strftime('%Y-%m-%d %H:%M:%S', localtime(time.time() + wait_time))}")
        
        # Countdown timer
        for remaining in range(int(wait_time), 0, -1):
            print(f"\rWaiting for ({int(wait_time)} seconds): {remaining} seconds remaining...", end="", flush=True)
            time.sleep(1)
        print()  # New line after countdown
        
        print(f"[RETRY] Retrying now (Attempt {attempt + 1})...")


def save_shortlog_to_db(changeset_info):
    """
    Save shortlog records to the database.
    
    Args:
        changeset_info: List of changeset dictionaries
    
    Returns:
        tuple: (inserted_count, skipped_count)
    """
    global conn_str, insert_shortlog_query

    # Connect to the database
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    
    inserted_count = 0
    skipped_count = 0
    
    try:
        # Iterate over 'changeset_info'
        for record in changeset_info:
            # Extract values from the record
            hash_id = record['hash_id']
            Changeset_Summary = record['Changeset_Summary']
            changeset_datetime = record['changeset_datetime']

            try:
                # Execute the SQL query per record in the changeset_info
                cursor.execute(insert_shortlog_query, 
                               hash_id, 
                               Changeset_Summary, 
                               changeset_datetime)
                inserted_count += 1
            except pyodbc.IntegrityError:
                # Skip duplicates (primary key violation)
                skipped_count += 1
        
        # Commit the transaction
        conn.commit()
        return inserted_count, skipped_count
    
    except Exception as e:
        # Handle any exceptions
        print(f"Error: {e}")
        conn.rollback()
        raise
    
    finally:
        # Close the cursor and connection
        cursor.close()
        conn.close()


def scrape_shortlog_range(start_changeset_id, end_changeset_id, skip_start_changeset_id=False):
    """
    Scrape shortlog pages from start_changeset_id until end_changeset_id is found.
    ROBUST OVERNIGHT MODE: Will retry indefinitely on any failure.
    
    Args:
        start_changeset_id: Starting changeset hash
        end_changeset_id: Ending changeset hash (EXCLUSIVE - not processed, used as stop marker)
        skip_start_changeset_id: If True, skip the start_changeset_id and begin from the next one
    """
    next_hash = start_changeset_id
    total_inserted = 0
    total_skipped = 0
    page_count = 0
    end_reached = False
    
    print("=" * 80)
    print(f"ROBUST OVERNIGHT MODE - Shortlog Scraper")
    print(f"Start changeset: {start_changeset_id}")
    print(f"Skip start:      {skip_start_changeset_id}")
    print(f"End changeset:   {end_changeset_id}")
    print(f"Start time:      {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    print("=" * 80)
    
    while True:
        page_count += 1
        print(f"\n[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] Page {page_count} | Hash: {next_hash}...", end="", flush=True)
        
        # Fetch the shortlog page (will retry indefinitely until success)
        changeset_info, next_hash = crawl_mozilla_central_shortlog(next_hash)
        
        # Check if we have changesets (should always have some unless we reached the end)
        if not changeset_info:
            print("\nNo changesets found on page. Reached end of repository.")
            break
        
        # Check if we've reached the end changeset
        changesets_to_save = []
        for changeset in changeset_info:
            # Check if we've reached the end changeset (STOP BEFORE processing it)
            if changeset['hash_id'] == end_changeset_id:
                end_reached = True
                print(f"\nReached end changeset (not processed): {end_changeset_id}")
                break
            
            # Skip the start changeset if flag is set and we're on the first page
            if skip_start_changeset_id and page_count == 1 and changeset['hash_id'] == start_changeset_id:
                print(f"\nSkipping start changeset: {start_changeset_id}")
                continue
            
            changesets_to_save.append(changeset)
        
        # Save to database
        inserted, skipped = save_shortlog_to_db(changesets_to_save)
        total_inserted += inserted
        total_skipped += skipped
        
        print(f"Done (Inserted: {inserted}, Skipped: {skipped})")
        print(f"Total: {total_inserted} inserted, {total_skipped} skipped")
        
        # Stop if we've reached the end changeset
        if end_reached:
            print(f"\n{'=' * 80}")
            print("Reached end changeset. Scraping complete!")
            break
        
        # Stop if no more pages
        if next_hash == "no_next_hash":
            print(f"\n{'=' * 80}")
            print("No more pages. Scraping complete!")
            break
        
        # Small delay to be respectful to the server
        time.sleep(1)
    
    # Final summary
    print("=" * 80)
    print("SCRAPING SUMMARY")
    print("=" * 80)
    print(f"Pages processed:     {page_count}")
    print(f"Total inserted:      {total_inserted}")
    print(f"Total skipped:       {total_skipped}")
    print(f"End time:            {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    print("=" * 80)


if __name__ == "__main__":
    # ========== CONFIGURATION - EDIT THESE VALUES ==========
    start_changeset_id = "58efc2517a7d65f69a92170977f671c650b1c0fc"  # Starting changeset hash
    end_changeset_id = "239b0e59042a82e9d970abe120b2815e562264c3"    # Ending changeset hash (EXCLUSIVE - not processed, used as stop marker)
    skip_start_changeset_id = False  # If True, skip start_changeset_id and begin from next one
    # =======================================================
    
    scrape_shortlog_range(start_changeset_id, end_changeset_id, skip_start_changeset_id)
    
    print("\nScript completed. Exiting.")
