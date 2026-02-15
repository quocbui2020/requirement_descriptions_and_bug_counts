"""
Mercurial to Git Hash Mapper - ROBUST OVERNIGHT MODE with PARALLEL PROCESSING

Maps Mercurial changesets to Git commits using Mozilla's Lando API.
Queries database for unmapped Hg hashes and fetches their Git equivalents.

ROBUST FEATURES:
- Infinite retry with progressive backoff (1min -> 2min -> 5min -> 10min indefinitely)
- Zero tolerance for failure - never gives up on a request
- Handles all error types: connection errors, timeouts, HTTP errors, etc.
- 60-second timeout per request
- Progress tracking and statistics

PARALLEL PROCESSING:
- Supports running multiple instances simultaneously with manual range partitioning
- Each instance processes records within a specified hash_id range
- You manually specify start and end hash_id to avoid overlap

USAGE:
    Process all unmapped records:
        python HgGitMapper.py
    
    Process specific hash_id range (hash_id is a string):
        python HgGitMapper.py 000000000000 111111111111
        python HgGitMapper.py 111111111112 222222222222
        python HgGitMapper.py 222222222223 333333333333
        ... etc

    Example for 8 parallel windows (adjust ranges based on your data):
        Window 1: python HgGitMapper.py 000000000000 1fffffffffff
        Window 2: python HgGitMapper.py 200000000000 3fffffffffff
        Window 3: python HgGitMapper.py 400000000000 5fffffffffff
        ... etc

API ENDPOINT:
https://lando.moz.tools/api/hg2git/firefox/{hg_hash}

Response format:
{
    "git_hash": "04e8ba9b990cca54ca74a9e02135cd0e4d8ed9a3",
    "hg_hash": "6ad6c4f493c87d3744405b86636b7ddcbb19e8cf"
}
"""
import requests
from time import strftime, localtime
import pyodbc
import time
import argparse
import sys

# Connection string
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=localhost\\SQLEXPRESS;' \
           'DATABASE=MozillaDataSet2026;' \
           'Connection Timeout=300;' \
           'Login Timeout=300;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

# SQL query templates
# All unmapped records (no range filter)
get_unmapped_hashes_query_all = '''
SELECT hash_id
FROM Changesets s
LEFT JOIN HgGit_Mappings m ON m.Hg_Changeset_ID = s.Hash_Id
WHERE m.Hg_Changeset_ID IS NULL
ORDER BY s.Hash_Id ASC;
'''

# Range-based query (for parallel processing)
get_unmapped_hashes_query_range = '''
SELECT hash_id
FROM Changesets s
LEFT JOIN HgGit_Mappings m ON m.Hg_Changeset_ID = s.Hash_Id
WHERE m.Hg_Changeset_ID IS NULL
  AND s.Hash_Id >= ?
  AND s.Hash_Id <= ?
ORDER BY s.Hash_Id ASC;
'''

insert_mapping_query = '''
INSERT INTO [dbo].[HgGit_Mappings]
    ([Hg_Changeset_ID], [Git_Commit_ID])
VALUES
    (?, ?);
'''


def parse_arguments():
    """
    Parse command-line arguments for range-based parallel processing.
    
    Returns:
        argparse.Namespace with start_hash_id and end_hash_id (or None for both)
    """
    parser = argparse.ArgumentParser(
        description='Map Mercurial changesets to Git commits (supports parallel processing)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  Process all unmapped records:
    python HgGitMapper.py
  
  Process specific hash_id range (hash_id is a string):
    python HgGitMapper.py 000000000000 1fffffffffff
    python HgGitMapper.py 200000000000 3fffffffffff
    python HgGitMapper.py 400000000000 5fffffffffff

  Example for 8 parallel windows:
    Window 1: python HgGitMapper.py 000000000000 1fffffffffff
    Window 2: python HgGitMapper.py 200000000000 3fffffffffff
    Window 3: python HgGitMapper.py 400000000000 5fffffffffff
    ... (adjust ranges based on your data distribution)
        '''
    )
    
    parser.add_argument(
        'start_hash_id',
        type=str,
        nargs='?',
        default=None,
        help='Starting hash_id string (inclusive)'
    )
    
    parser.add_argument(
        'end_hash_id',
        type=str,
        nargs='?',
        default=None,
        help='Ending hash_id string (inclusive)'
    )
    
    args = parser.parse_args()
    
    # Validation
    if (args.start_hash_id is None) != (args.end_hash_id is None):
        parser.error("Both start_hash_id and end_hash_id must be specified together")
    
    if args.start_hash_id is not None and args.end_hash_id is not None:
        if args.start_hash_id > args.end_hash_id:
            parser.error(f"start_hash_id ({args.start_hash_id}) must be <= end_hash_id ({args.end_hash_id})")
    
    return args


def get_unmapped_hashes(start_hash_id=None, end_hash_id=None):
    """
    Get list of Hg changesets that haven't been mapped to Git commits yet.
    
    Args:
        start_hash_id: Starting hash_id (inclusive), None for no lower bound
        end_hash_id: Ending hash_id (inclusive), None for no upper bound
    
    Returns:
        List of Hg changeset IDs in the specified range
    """
    global conn_str
    
    # Determine which query to use
    use_range = (start_hash_id is not None and end_hash_id is not None)
    
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        if use_range:
            # Range mode: filter by hash_id range
            cursor.execute(get_unmapped_hashes_query_range, (start_hash_id, end_hash_id))
        else:
            # All mode: fetch all unmapped
            cursor.execute(get_unmapped_hashes_query_all)
        
        rows = cursor.fetchall()
        
        # Extract hash_id from each row
        hashes = [row[0] for row in rows]
        
        return hashes
    
    except Exception as e:
        print(f"Error fetching unmapped hashes: {e}")
        raise
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def fetch_git_hash_for_hg(hg_hash):
    """
    Fetch Git commit hash for a given Mercurial changeset hash.
    ROBUST MODE: Infinite retry with progressive backoff.
    
    Args:
        hg_hash: Mercurial changeset hash
    
    Returns:
        tuple: (git_hash, hg_hash) or (None, None) if not found
    """
    request_url = f"https://lando.moz.tools/api/hg2git/firefox/{hg_hash}"
    attempt = 0
    
    # Progressive backoff schedule: 1min, 2min, 5min, 10min, then 10min indefinitely
    backoff_schedule = [60, 120, 300, 600]  # seconds
    
    while True:  # INFINITE RETRY - never give up!
        attempt += 1
        
        try:
            # Make request with timeout
            response = requests.get(request_url, timeout=60)
            
            if response.status_code == 200:
                # SUCCESS - parse the JSON response
                data = response.json()
                git_hash = data.get('git_hash')
                hg_hash_returned = data.get('hg_hash')
                
                # Validate response
                if git_hash and hg_hash_returned:
                    return git_hash, hg_hash_returned
                else:
                    print(f"\n[WARNING] Invalid response format: {data}")
                    return None, None
                    
            elif response.status_code == 404:
                # Not found - this is a valid response, don't retry
                print(f"\n[NOT FOUND] No Git mapping exists for {hg_hash}")
                return None, None
                
            elif response.status_code == 429:
                # Rate limited
                print(f"\n[ATTEMPT {attempt}] Rate limited (429)")
                print(f"[URL] {request_url}")
                
            else:
                # Other HTTP error
                print(f"\n[ATTEMPT {attempt}] HTTP {response.status_code} error")
                print(f"[URL] {request_url}")
                
        except requests.exceptions.Timeout:
            print(f"\n[ATTEMPT {attempt}] Request timeout (exceeded 60 seconds)")
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
        print(f"[WAIT] Waiting {wait_minutes:.1f} minute(s) before retry...")
        print(f"[INFO] Will retry at: {strftime('%Y-%m-%d %H:%M:%S', localtime(time.time() + wait_time))}")
        
        # Countdown timer
        for remaining in range(int(wait_time), 0, -1):
            print(f"\rWaiting for ({int(wait_time)} seconds): {remaining} seconds remaining...", end="", flush=True)
            time.sleep(1)
        print()  # New line after countdown
        
        print(f"[RETRY] Retrying now (Attempt {attempt + 1})...")


def save_mapping_to_db(hg_hash, git_hash):
    """
    Save Hg-Git mapping to database.
    
    Args:
        hg_hash: Mercurial changeset hash
        git_hash: Git commit hash
    
    Returns:
        bool: True if inserted successfully, False if already exists
    """
    global conn_str
    
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        cursor.execute(insert_mapping_query, (hg_hash, git_hash))
        conn.commit()
        
        return True
    
    except pyodbc.IntegrityError:
        # Already exists (primary key violation)
        return False
    
    except Exception as e:
        print(f"\nError saving mapping to database: {e}")
        if conn:
            conn.rollback()
        raise
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def map_hg_to_git(start_hash_id=None, end_hash_id=None):
    """
    Main function to map all unmapped Hg changesets to Git commits.
    
    Args:
        start_hash_id: Starting hash_id (inclusive), None for no lower bound
        end_hash_id: Ending hash_id (inclusive), None for no upper bound
    """
    use_range = (start_hash_id is not None and end_hash_id is not None)
    
    print("=" * 80)
    if use_range:
        print(f"ROBUST OVERNIGHT MODE - Hg to Git Mapper [RANGE MODE]")
        print(f"Processing hash_id range: {start_hash_id} to {end_hash_id}")
    else:
        print("ROBUST OVERNIGHT MODE - Hg to Git Mapper [ALL RECORDS]")
    print(f"Start time: {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    print("=" * 80)
    
    # Get list of unmapped hashes in the specified range
    print("\nFetching unmapped Hg changesets from database...", end="", flush=True)
    unmapped_hashes = get_unmapped_hashes(start_hash_id, end_hash_id)
    total_count = len(unmapped_hashes)
    print(f"Done")
    
    if use_range:
        print(f"Records in range {start_hash_id}-{end_hash_id}: {total_count:,}")
    else:
        print(f"Total unmapped: {total_count:,}")
    
    if total_count == 0:
        print("\nNo unmapped hashes found in this range. All done!")
        return
    
    print("\n" + "=" * 80)
    print("Starting mapping process...")
    print("=" * 80)
    
    # Statistics
    processed_count = 0
    mapped_count = 0
    not_found_count = 0
    skipped_count = 0
    
    # Process each hash
    for idx, hg_hash in enumerate(unmapped_hashes, 1):
        remaining = total_count - idx + 1
        
        range_label = f"RANGE {start_hash_id}-{end_hash_id}" if use_range else "ALL"
        print(f"\n[{strftime('%m/%d/%Y %H:%M:%S', localtime())}] [{range_label}] [{idx}/{total_count}] Remaining: {remaining}")
        print(f"Processing Hg hash: {hg_hash}...", end="", flush=True)
        
        # Fetch Git hash from API
        git_hash, hg_hash_returned = fetch_git_hash_for_hg(hg_hash)
        
        if git_hash and hg_hash_returned:
            # Save to database with actual Git hash
            success = save_mapping_to_db(hg_hash_returned, git_hash)
            
            if success:
                print(f"Mapped!")
                print(f"  Hg: {hg_hash_returned}")
                print(f"  Git: {git_hash}")
                mapped_count += 1
            else:
                print(f"Skipped (already exists)")
                skipped_count += 1
        else:
            # No Git mapping found - save as "Not Found"
            success = save_mapping_to_db(hg_hash, "Not Found")
            
            if success:
                print(f"Not found (saved as 'Not Found')")
                not_found_count += 1
            else:
                print(f"Skipped (already marked as 'Not Found')")
                skipped_count += 1
        
        processed_count += 1
        
        # Progress summary every 10 records
        if processed_count % 10 == 0:
            print(f"\n[CHECKPOINT {range_label}] Processed: {processed_count:,}/{total_count:,} | Mapped: {mapped_count:,} | Not Found: {not_found_count:,} | Skipped: {skipped_count:,}")
        
        # Small delay between requests to be respectful
        time.sleep(2)
    
    # Final summary
    print("\n" + "=" * 80)
    if use_range:
        print(f"MAPPING COMPLETE - RANGE {start_hash_id} to {end_hash_id}")
    else:
        print("MAPPING COMPLETE - ALL RECORDS")
    print("=" * 80)
    print(f"Total processed:  {processed_count:,}")
    print(f"Mapped:           {mapped_count:,}")
    print(f"Not found:        {not_found_count:,}")
    print(f"Skipped:          {skipped_count:,}")
    print(f"End time:         {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    print("=" * 80)


if __name__ == "__main__":
    # Parse command-line arguments
    args = parse_arguments()

    r""" ## For Debugging:
    start_hash_id = '002359e80ee7f1e64555104fb9cb53b13cb10951' # For Debugging
    end_hash_id = '714e3e145b19775dcf9c3b1623d6e9b22664c07e' # For Debugging

    if start_hash_id is not None and end_hash_id is not None: 
        print(f"\n>>> Running in RANGE mode: hash_id {start_hash_id} to {end_hash_id}")
        map_hg_to_git(start_hash_id=start_hash_id, end_hash_id=end_hash_id)
    """

    ## Run mapper with or without range filtering
    if args.start_hash_id is not None and args.end_hash_id is not None:
        print(f"\n>>> Running in RANGE mode: hash_id {args.start_hash_id} to {args.end_hash_id}")
        map_hg_to_git(start_hash_id=args.start_hash_id, end_hash_id=args.end_hash_id)
    else:
        # Process all unmapped records
        print("\n>>> Running in ALL RECORDS mode")
        map_hg_to_git()
    
    print("\nScript completed. Exiting.")
