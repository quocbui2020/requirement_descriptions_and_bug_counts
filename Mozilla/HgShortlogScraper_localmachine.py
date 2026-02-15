"""
Shortlog Scraper for Mozilla Central - LOCAL MERCURIAL VERSION

Mines shortlog data directly from a local Mercurial repository clone.
Stores basic info in Changesets table.

ADVANTAGES OVER WEB SCRAPING:
- 100x faster - no network requests
- No timeouts, rate limits, or connection errors
- Can process 800k+ changesets in minutes instead of days
- Direct access to complete repository history

REQUIREMENTS:
- Local clone of mozilla-central repository
- Mercurial installed (available via pip install mercurial)
"""

import subprocess
import pyodbc
from time import strftime, localtime
from datetime import datetime
import sys

# ========== CONFIGURATION ==========
# Path to local mozilla-central repository
REPO_PATH = r'C:\Users\quocb\quocbui\Studies\research\GithubRepo\firefox_mercurial'

# Database connection string
CONN_STR = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=localhost\\SQLEXPRESS;' \
           'DATABASE=MozillaDataSet2026;' \
           'Connection Timeout=300;' \
           'Login Timeout=300;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

# Batch size for database inserts (adjust based on memory)
BATCH_SIZE = 1000
# ====================================

# SQL query for inserting shortlog records
INSERT_SHORTLOG_QUERY = '''
    INSERT INTO [dbo].[Changesets]
        ([Hash_Id]
        ,[Changeset_Summary]
        ,[Changeset_Datetime]
        ,[Inserted_On])
    VALUES
        (?, ?, ?, SYSUTCDATETIME())
'''


def verify_changeset_exists(hash_id):
    """
    Verify that a changeset exists in the repository.
    
    Args:
        hash_id: Changeset hash to verify
    
    Returns:
        tuple: (exists, rev_number, error_message)
    """
    try:
        cmd = ['hg', 'log', '-r', hash_id, '--template', '{rev}', '--cwd', REPO_PATH]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and result.stdout.strip():
            return True, result.stdout.strip(), None
        else:
            return False, None, result.stderr.strip()
    except Exception as e:
        return False, None, str(e)


def get_changeset_info(hash_id):
    """
    Get detailed information about a changeset.
    
    Args:
        hash_id: Changeset hash
    
    Returns:
        dict: Changeset info (rev, date, author, desc) or None if not found
    """
    try:
        template = "{rev}|{date|isodate}|{author|person}|{desc|firstline}"
        cmd = ['hg', 'log', '-r', hash_id, '--template', template, '--cwd', REPO_PATH]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)
        
        if result.stdout.strip():
            parts = result.stdout.strip().split('|', 3)
            if len(parts) == 4:
                return {
                    'rev': int(parts[0]),
                    'date': parts[1],
                    'author': parts[2],
                    'desc': parts[3]
                }
        return None
    except Exception as e:
        print(f"[ERROR] Failed to get changeset info: {e}")
        return None


def get_hg_log_data(start_hash, end_hash, reverse_order=False):
    """
    Extract shortlog data from local Mercurial repository.
    
    Args:
        start_hash: Starting changeset hash (inclusive)
        end_hash: Ending changeset hash (inclusive)
        reverse_order: If True, process from oldest to newest
    
    Returns:
        list: List of changeset dictionaries
    
    Raises:
        subprocess.CalledProcessError: If hg command fails
    """
    # First, verify both changesets exist and get their info
    print(f"[INFO] Verifying changesets...")
    
    start_info = get_changeset_info(start_hash)
    end_info = get_changeset_info(end_hash)
    
    if not start_info:
        raise ValueError(f"Start changeset not found: {start_hash}")
    if not end_info:
        raise ValueError(f"End changeset not found: {end_hash}")
    
    print(f"[INFO] Start: rev {start_info['rev']} - {start_info['date']} - {start_info['desc'][:50]}")
    print(f"[INFO] End:   rev {end_info['rev']} - {end_info['date']} - {end_info['desc'][:50]}")
    
    # Determine the range using revision numbers (more reliable than hashes with ::)
    start_rev = start_info['rev']
    end_rev = end_info['rev']
    
    # Use revision number range (works regardless of ancestry)
    if start_rev <= end_rev:
        rev_spec = f"{start_rev}:{end_rev}"
        print(f"[INFO] Forward range detected: {start_rev} to {end_rev} ({end_rev - start_rev + 1} changesets)")
    else:
        rev_spec = f"{end_rev}:{start_rev}"
        print(f"[INFO] Reverse range detected: {end_rev} to {start_rev} ({start_rev - end_rev + 1} changesets)")
    
    # Build the hg log command
    # Template format: {node}\t{author|person} - {desc|firstline}\t{date|isodate}
    template = "{node}\\t{author|person} - {desc|firstline}\\t{date|isodate}\\n"
    
    cmd = [
        'hg', 'log',
        '--template', template,
        '-r', rev_spec,
        '--cwd', REPO_PATH
    ]
    
    # Add --reverse flag if needed (oldest first)
    if reverse_order:
        cmd.insert(2, '--reverse')
    
    print(f"[INFO] Running: hg log -r {rev_spec}")
    print(f"[INFO] Repository: {REPO_PATH}")
    
    try:
        # Run the command with timeout (15 minutes should be enough even for large ranges)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=900,  # 15 minutes
            check=True
        )
        
        # Parse the output
        changeset_list = []
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            if not line.strip():
                continue
                
            try:
                # Split by tab: hash_id \t summary \t datetime
                parts = line.split('\t')
                if len(parts) != 3:
                    print(f"[WARNING] Skipping malformed line: {line[:100]}")
                    continue
                
                hash_id = parts[0].strip()
                changeset_summary = parts[1].strip()
                changeset_datetime = parts[2].strip()
                
                changeset_list.append({
                    'hash_id': hash_id,
                    'Changeset_Summary': changeset_summary,
                    'changeset_datetime': changeset_datetime
                })
                
            except Exception as e:
                print(f"[WARNING] Error parsing line: {line[:100]}")
                print(f"[WARNING] Error: {e}")
                continue
        
        print(f"[INFO] Extracted {len(changeset_list)} changesets")
        return changeset_list
        
    except subprocess.TimeoutExpired:
        print("[ERROR] Command timed out after 15 minutes")
        raise
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Command failed with exit code {e.returncode}")
        print(f"[ERROR] stderr: {e.stderr}")
        raise
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        raise


def save_shortlog_batch_to_db(changeset_batch):
    """
    Save a batch of shortlog records to the database.
    
    Args:
        changeset_batch: List of changeset dictionaries
    
    Returns:
        tuple: (inserted_count, skipped_count)
    """
    if not changeset_batch:
        return 0, 0
    
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()
    
    inserted_count = 0
    skipped_count = 0
    
    try:
        for record in changeset_batch:
            hash_id = record['hash_id']
            changeset_summary = record['Changeset_Summary']
            changeset_datetime = record['changeset_datetime']
            
            try:
                cursor.execute(
                    INSERT_SHORTLOG_QUERY,
                    hash_id,
                    changeset_summary,
                    changeset_datetime
                )
                inserted_count += 1
            except pyodbc.IntegrityError:
                # Skip duplicates (primary key violation)
                skipped_count += 1
            except Exception as e:
                print(f"[WARNING] Error inserting {hash_id}: {e}")
                skipped_count += 1
        
        # Commit the batch
        conn.commit()
        return inserted_count, skipped_count
    
    except Exception as e:
        print(f"[ERROR] Batch insert failed: {e}")
        conn.rollback()
        raise
    
    finally:
        cursor.close()
        conn.close()


def mine_shortlog_range(start_changeset_id, end_changeset_id, skip_start=False, skip_end=True):
    """
    Mine shortlog data from local Mercurial repository and save to database.
    
    Args:
        start_changeset_id: Starting changeset hash
        end_changeset_id: Ending changeset hash
        skip_start: If True, exclude the start changeset
        skip_end: If True, exclude the end changeset (default behavior to match web scraper)
    """
    print("=" * 80)
    print("LOCAL MERCURIAL SHORTLOG MINER")
    print("=" * 80)
    print(f"Repository:      {REPO_PATH}")
    print(f"Start changeset: {start_changeset_id}")
    print(f"End changeset:   {end_changeset_id}")
    print(f"Skip start:      {skip_start}")
    print(f"Skip end:        {skip_end}")
    print(f"Batch size:      {BATCH_SIZE}")
    print(f"Start time:      {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    print("=" * 80)
    
    try:
        # Extract data from local repository
        print("\n[STEP 1/2] Extracting data from local Mercurial repository...")
        changeset_list = get_hg_log_data(start_changeset_id, end_changeset_id)
        
        if not changeset_list:
            print("[ERROR] No changesets found in the specified range")
            return
        
        # Filter out start/end changesets if requested
        filtered_list = []
        for changeset in changeset_list:
            hash_id = changeset['hash_id']
            
            # Skip start changeset if requested
            if skip_start and hash_id == start_changeset_id:
                print(f"[INFO] Skipping start changeset: {start_changeset_id}")
                continue
            
            # Skip end changeset if requested (default behavior)
            if skip_end and hash_id == end_changeset_id:
                print(f"[INFO] Skipping end changeset: {end_changeset_id}")
                continue
            
            filtered_list.append(changeset)
        
        print(f"[INFO] Total changesets to process: {len(filtered_list)}")
        
        # Save to database in batches
        print(f"\n[STEP 2/2] Saving to database (batch size: {BATCH_SIZE})...")
        total_inserted = 0
        total_skipped = 0
        batch_count = 0
        
        for i in range(0, len(filtered_list), BATCH_SIZE):
            batch = filtered_list[i:i + BATCH_SIZE]
            batch_count += 1
            
            print(f"[{strftime('%H:%M:%S', localtime())}] Processing batch {batch_count} "
                  f"({i + 1}-{min(i + BATCH_SIZE, len(filtered_list))} of {len(filtered_list)})...", 
                  end="", flush=True)
            
            inserted, skipped = save_shortlog_batch_to_db(batch)
            total_inserted += inserted
            total_skipped += skipped
            
            print(f" Done (Inserted: {inserted}, Skipped: {skipped})")
        
        # Final summary
        print("\n" + "=" * 80)
        print("MINING SUMMARY")
        print("=" * 80)
        print(f"Total changesets extracted:  {len(changeset_list)}")
        print(f"Total changesets processed:  {len(filtered_list)}")
        print(f"Total inserted:              {total_inserted}")
        print(f"Total skipped (duplicates):  {total_skipped}")
        print(f"Batches processed:           {batch_count}")
        print(f"End time:                    {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
        print("=" * 80)
        
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Mercurial command failed: {e}")
        print("[ERROR] Make sure:")
        print("  1. Mercurial is installed (pip install mercurial)")
        print("  2. Repository path is correct")
        print("  3. Changeset hashes are valid")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def mine_all_changesets():
    """
    Mine ALL changesets from the repository (from first to latest).
    WARNING: This will process 800k+ changesets and may take a while!
    """
    print("=" * 80)
    print("MINING ALL CHANGESETS FROM REPOSITORY")
    print("=" * 80)
    print(f"Repository: {REPO_PATH}")
    print(f"Start time: {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    print("=" * 80)
    
    try:
        # Get all changesets using -r "all()"
        template = "{node}\\t{author|person} - {desc|firstline}\\t{date|isodate}\\n"
        
        cmd = [
            'hg', 'log',
            '--template', template,
            '-r', 'all()',
            '--cwd', REPO_PATH
        ]
        
        print("[INFO] Running: hg log -r all()")
        print("[INFO] This may take several minutes for 800k+ changesets...")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minutes for all changesets
            check=True
        )
        
        # Parse and save in batches
        lines = result.stdout.strip().split('\n')
        print(f"[INFO] Extracted {len(lines)} changesets")
        
        total_inserted = 0
        total_skipped = 0
        batch = []
        batch_count = 0
        
        for idx, line in enumerate(lines, 1):
            if not line.strip():
                continue
            
            try:
                parts = line.split('\t')
                if len(parts) != 3:
                    continue
                
                batch.append({
                    'hash_id': parts[0].strip(),
                    'Changeset_Summary': parts[1].strip(),
                    'changeset_datetime': parts[2].strip()
                })
                
                # Save when batch is full
                if len(batch) >= BATCH_SIZE:
                    batch_count += 1
                    print(f"[{strftime('%H:%M:%S', localtime())}] Batch {batch_count} "
                          f"({idx - BATCH_SIZE + 1}-{idx} of {len(lines)})...", 
                          end="", flush=True)
                    
                    inserted, skipped = save_shortlog_batch_to_db(batch)
                    total_inserted += inserted
                    total_skipped += skipped
                    print(f" Done (Inserted: {inserted}, Skipped: {skipped})")
                    batch = []
                    
            except Exception as e:
                print(f"[WARNING] Error parsing line {idx}: {e}")
                continue
        
        # Save remaining items
        if batch:
            batch_count += 1
            print(f"[{strftime('%H:%M:%S', localtime())}] Final batch {batch_count}...", 
                  end="", flush=True)
            inserted, skipped = save_shortlog_batch_to_db(batch)
            total_inserted += inserted
            total_skipped += skipped
            print(f" Done (Inserted: {inserted}, Skipped: {skipped})")
        
        # Final summary
        print("\n" + "=" * 80)
        print("MINING SUMMARY")
        print("=" * 80)
        print(f"Total changesets:           {len(lines)}")
        print(f"Total inserted:             {total_inserted}")
        print(f"Total skipped (duplicates): {total_skipped}")
        print(f"Batches processed:          {batch_count}")
        print(f"End time:                   {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n[ERROR] Failed to mine all changesets: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # ========== CONFIGURATION - CHOOSE YOUR MODE ==========
    
    # MODE 1: Mine a specific range of changesets
    # MODE 2: Mine ALL changesets (800k+)
    MODE = "all"  # "range" or "all"
    
    if MODE == "range":
        # Mine changesets between start and end
        start_changeset_id = "58efc2517a7d65f69a92170977f671c650b1c0fc"
        end_changeset_id = "239b0e59042a82e9d970abe120b2815e562264c3"
        skip_start_changeset = False  # If True, exclude start changeset
        skip_end_changeset = True     # If True, exclude end changeset (matches web scraper behavior)
        
        mine_shortlog_range(
            start_changeset_id, 
            end_changeset_id, 
            skip_start=skip_start_changeset,
            skip_end=skip_end_changeset
        )
    
    elif MODE == "all":
        # MODE 2: Mine ALL changesets from the repository
        # WARNING: This processes 800k+ changesets!
        mine_all_changesets()
    
    else:
        print(f"[ERROR] Invalid MODE: {MODE}")
        print("Valid modes: 'range' or 'all'")
        sys.exit(1)
    
    # =======================================================
    
    print("\nScript completed. Exiting.")
