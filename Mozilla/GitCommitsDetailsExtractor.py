"""
Git Commit Details Extractor for Mozilla Firefox repository data.

WHAT THIS SCRIPT DOES
---------------------
Reads commit messages from a local Firefox Git repo and updates two sharded tables:

1) [dbo].[GitCommitList_<n>]
     - Sets/updates:
         - [is_backout_commit]
         - [backed_out] (sticky: once 1, it stays 1)
         - [Description]

2) [dbo].[GitCommit_Properties_<n>]
     - Inserts properties (insert-only, duplicate-safe):
         - 'Backout Commit'
         - 'Backed Out By'
         - 'Bug ID Mentioned'

It also repairs partially processed records by re-selecting commits that are missing
expected relationship properties:
- is_backout_commit = 1 but no 'Backout Commit' property
- backed_out = 1 but no 'Backed Out By' property


HOW IT DETECTS INFORMATION
--------------------------
- Backout detection from commit message text using multiple regex patterns.
- Supports short/full hashes and normalizes when possible.
- Converts Hg hashes to Git hashes using [dbo].[HgGit_Mappings], then Lando API fallback.
- Extracts bug IDs from patterns like:
    - Bug 123456
    - Bug #123456
    - bug=123456 / b=123456


CLI ARGUMENTS
-------------
Positional (optional pair):
- start_git_commit_id
- end_git_commit_id

Optional flags:
- --table-number <1..20>
    Targets [GitCommitList_<n>] and [GitCommit_Properties_<n>].

- --repo-path <local_repo_path>
    Local Firefox repo path for this process.

Notes:
- Provide both start/end together, or neither.
- If no range is provided, it processes all candidates in the selected shard.


RUN MODES (current code)
------------------------
The code-level MODE variable controls entry behavior in __main__:
- MODE = "range" (default in this file):
    - with range args: processes that range
    - without range args: processes all records in selected shard
- MODE = "all": process all records in selected shard
- MODE = "single": process TEST_COMMIT only


USAGE EXAMPLES
--------------
Single worker, all pending rows in shard 4:
    python GitCommitsDetailsExtractor.py --table-number 4 --repo-path C:\path\to\firefox_worker_04

Single worker, specific range in shard 4:
    python GitCommitsDetailsExtractor.py --table-number 4 --repo-path C:\path\to\firefox_worker_04 \
            265c42d16f47111316f6a79e5308a0d6ac5d9f71 334746cbcbd83d2bea6bf70ba1227f5a096182ad

Parallel workers (recommended):
- Use one shard per process: --table-number 1..20
- Use one local repo path per process: --repo-path <worker_repo>
    (avoids .git/config.lock contention between processes)


REQUIREMENTS
------------
- Python environment with: pyodbc, requests, pydriller
- SQL Server tables:
    - [dbo].[GitCommitList_1..20]
    - [dbo].[GitCommit_Properties_1..20]
    - [dbo].[HgGit_Mappings]
- Local Firefox Git repo(s)
"""

import pyodbc
import re
import requests
from time import strftime, localtime
from time import sleep
import pydriller
import argparse
import sys
import time

# ========== CONFIGURATION ==========
# Path to local firefox Git repository
REPO_PATH = r'C:\Users\quocb\quocbui\Studies\research\GithubRepo\firefox'

# Database connection string
CONN_STR = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=localhost\\SQLEXPRESS;' \
           'DATABASE=MozillaDataSet2026;' \
           'Connection Timeout=300;' \
           'Login Timeout=300;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'

# Batch size for processing
BATCH_SIZE = 1000

# Debug mode - set to False to reduce log verbosity (only show progress/timing)
DEBUG_MODE = True

# Cache for Hg to Git conversions
HG_TO_GIT_CACHE = {}

# Cache for resolving short Git hashes to full hashes
GIT_HASH_CACHE = {}

# Cache for determining whether a full hash is likely Hg (True) or Git (False)
HASH_TYPE_CACHE = {}

# Infinite retry backoff schedule for public API requests (seconds): grows then caps
API_RETRY_BACKOFF_SECONDS = [1, 2, 5, 10, 30, 60, 120, 300]

# Fixed delay for local resource retries (DB/files)
LOCAL_RETRY_DELAY_SECONDS = 5

# Network timeout for Lando API requests (seconds)
LANDO_API_TIMEOUT_SECONDS = 10

# Retry safety guards (prevents getting stuck on one commit forever)
MAX_LOCAL_RETRY_WINDOW_SECONDS = 900   # 15 minutes for DB/files retries per operation
MAX_API_RETRY_WINDOW_SECONDS = 1800    # 30 minutes for Lando API retries per conversion
RETRY_HEARTBEAT_INTERVAL_SECONDS = 30  # Print retry heartbeat at most once per 30 seconds

# Progress display settings (kept lightweight)
PROGRESS_LOG_INTERVAL = 50
PROGRESS_BAR_WIDTH = 24


def normalize_mapping_hash(mapping_value):
    """
    Normalize mapping values from HgGit_Mappings.
    Treat placeholders like "Not Found" as unresolved (None).
    """
    if mapping_value is None:
        return None

    value = str(mapping_value).strip()
    if not value:
        return None

    normalized = value.lower().replace(' ', '_')
    if normalized == 'not_found' or normalized.startswith('not_found_'):
        return None

    return value


def get_api_retry_delay(attempt):
    """
    Get retry delay in seconds for attempt number (1-based).
    Delay increases progressively and then remains capped.
    """
    if attempt <= 0:
        return API_RETRY_BACKOFF_SECONDS[0]
    index = min(attempt - 1, len(API_RETRY_BACKOFF_SECONDS) - 1)
    return API_RETRY_BACKOFF_SECONDS[index]


def is_git_config_lock_error(error):
    """
    Detect git config lock contention errors.
    """
    if error is None:
        return False

    message = str(error).lower()
    return (
        '.git' in message
        and 'config.lock' in message
        and ('lock for file' in message or 'did already exist' in message)
    )


def print_progress_bar(phase, current, total, indent="  "):
    """
    Print a compact text progress bar.
    """
    if total <= 0:
        return

    ratio = current / total
    if ratio < 0:
        ratio = 0
    if ratio > 1:
        ratio = 1

    filled = int(PROGRESS_BAR_WIDTH * ratio)
    bar = ('#' * filled) + ('-' * (PROGRESS_BAR_WIDTH - filled))
    percent = ratio * 100
    print(
        f"{indent}[{strftime('%H:%M:%S', localtime())}] [{phase}] "
        f"|{bar}| {percent:6.2f}% ({current}/{total})"
    )


def _retry_window_exhausted(start_time, max_window_seconds):
    """
    Return True if retry time window has been exceeded.
    """
    if max_window_seconds is None or max_window_seconds <= 0:
        return False
    return (time.time() - start_time) >= max_window_seconds


def _should_emit_retry_heartbeat(last_heartbeat_time):
    """
    Throttle retry heartbeat logs.
    """
    return (time.time() - last_heartbeat_time) >= RETRY_HEARTBEAT_INTERVAL_SECONDS
# ====================================

# Dynamic table configuration
TABLE_NUMBER = 1
TABLE_GITCOMMITLIST = None
TABLE_GITCOMMIT_PROPERTIES = None

UPDATE_COMMIT_QUERY = None
INSERT_PROPERTY_QUERY = None
GET_ALL_COMMITS_QUERY = None
GET_COMMITS_RANGE_QUERY = None
GET_COMMITS_BATCH_QUERY = None


def configure_table_queries(table_number):
    """
    Configure all SQL queries to target sharded tables:
      [dbo].[GitCommitList_<n>] and [dbo].[GitCommit_Properties_<n>]
    """
    global TABLE_NUMBER, TABLE_GITCOMMITLIST, TABLE_GITCOMMIT_PROPERTIES
    global UPDATE_COMMIT_QUERY, INSERT_PROPERTY_QUERY, GET_ALL_COMMITS_QUERY, GET_COMMITS_RANGE_QUERY, GET_COMMITS_BATCH_QUERY

    TABLE_NUMBER = table_number
    TABLE_GITCOMMITLIST = f"[dbo].[GitCommitList_{table_number}]"
    TABLE_GITCOMMIT_PROPERTIES = f"[dbo].[GitCommit_Properties_{table_number}]"

    UPDATE_COMMIT_QUERY = f'''
        UPDATE {TABLE_GITCOMMITLIST}
        SET [backed_out] = CASE WHEN [backed_out] = 1 OR ? = 1 THEN 1 ELSE 0 END,
            [is_backout_commit] = ?,
            [Description] = ?
        WHERE [Git_Commit_ID] = ?
    '''

    INSERT_PROPERTY_QUERY = f'''
        INSERT INTO {TABLE_GITCOMMIT_PROPERTIES}
            ([Git_Commit_ID], [Name], [Value])
        VALUES (?, ?, ?)
    '''

    GET_ALL_COMMITS_QUERY = f'''
        SELECT g.[Git_Commit_ID]
        FROM {TABLE_GITCOMMITLIST} g
        WHERE g.[Description] IS NULL
           OR (
                g.[is_backout_commit] = 1
                AND NOT EXISTS (
                    SELECT TOP 1 1
                    FROM {TABLE_GITCOMMIT_PROPERTIES} p
                    WHERE p.[Git_Commit_ID] = g.[Git_Commit_ID]
                      AND p.[Name] = 'Backout Commit'
                )
           )
           OR (
                g.[backed_out] = 1
                AND NOT EXISTS (
                    SELECT TOP 1 1
                    FROM {TABLE_GITCOMMIT_PROPERTIES} p
                    WHERE p.[Git_Commit_ID] = g.[Git_Commit_ID]
                      AND p.[Name] = 'Backed Out By'
                )
           )
        ORDER BY g.[Git_Commit_ID]
    '''

    GET_COMMITS_RANGE_QUERY = f'''
        SELECT g.[Git_Commit_ID]
        FROM {TABLE_GITCOMMITLIST} g
        WHERE g.[Git_Commit_ID] >= ?
          AND g.[Git_Commit_ID] <= ?
          AND (
                g.[Description] IS NULL
             OR (
                    g.[is_backout_commit] = 1
                    AND NOT EXISTS (
                        SELECT TOP 1 1
                        FROM {TABLE_GITCOMMIT_PROPERTIES} p
                        WHERE p.[Git_Commit_ID] = g.[Git_Commit_ID]
                          AND p.[Name] = 'Backout Commit'
                    )
                )
             OR (
                    g.[backed_out] = 1
                    AND NOT EXISTS (
                        SELECT TOP 1 1
                        FROM {TABLE_GITCOMMIT_PROPERTIES} p
                        WHERE p.[Git_Commit_ID] = g.[Git_Commit_ID]
                          AND p.[Name] = 'Backed Out By'
                    )
                )
          )
        ORDER BY g.[Git_Commit_ID]
    '''

    GET_COMMITS_BATCH_QUERY = f'''
        SELECT [Git_Commit_ID]
        FROM {TABLE_GITCOMMITLIST}
        WHERE [Git_Commit_ID] > ?
        ORDER BY [Git_Commit_ID]
        OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY
    '''


# Default table set so single-mode/debug runs work without CLI args.
configure_table_queries(1)


def parse_arguments():
    """
    Parse command-line arguments for range-based parallel processing.
    
    Returns:
        argparse.Namespace with start_git_commit_id and end_git_commit_id (or None for both)
    """
    parser = argparse.ArgumentParser(
        description='Extract Git commit details (supports parallel processing)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  Process all unprocessed commits:
    python GitCommitsDetailsExtractor.py
  
  Process specific Git_Commit_ID range:
    python GitCommitsDetailsExtractor.py 000000000000 1fffffffffff
    python GitCommitsDetailsExtractor.py 200000000000 3fffffffffff
    python GitCommitsDetailsExtractor.py 400000000000 5fffffffffff

  Example for parallel processing:
    Window 1: python GitCommitsDetailsExtractor.py 000000000000 1fffffffffff
    Window 2: python GitCommitsDetailsExtractor.py 200000000000 3fffffffffff
    Window 3: python GitCommitsDetailsExtractor.py 400000000000 5fffffffffff
    ... (adjust ranges based on your data distribution)
        '''
    )
    
    parser.add_argument(
        'start_git_commit_id',
        type=str,
        nargs='?',
        default=None,
        help='Starting Git_Commit_ID string (inclusive)'
    )
    
    parser.add_argument(
        'end_git_commit_id',
        type=str,
        nargs='?',
        default=None,
        help='Ending Git_Commit_ID string (inclusive)'
    )

    parser.add_argument(
        '--table-number',
        type=int,
        default=1,
        help='Table shard number (1-20). Example: --table-number 7 uses GitCommitList_7 and GitCommit_Properties_7'
    )

    parser.add_argument(
        '--repo-path',
        type=str,
        default=REPO_PATH,
        help='Path to local firefox Git repository for this process'
    )
    
    args = parser.parse_args()
    
    # Validation
    if (args.start_git_commit_id is None) != (args.end_git_commit_id is None):
        parser.error("Both start_git_commit_id and end_git_commit_id must be specified together")
    
    if args.start_git_commit_id is not None and args.end_git_commit_id is not None:
        if args.start_git_commit_id > args.end_git_commit_id:
            parser.error(f"start_git_commit_id ({args.start_git_commit_id}) must be <= end_git_commit_id ({args.end_git_commit_id})")

    if args.table_number < 1 or args.table_number > 20:
        parser.error(f"table_number must be between 1 and 20 (got {args.table_number})")
    
    return args

def insert_property_skip_duplicate(cursor, git_commit_id, name, value):
    """
    Insert a property row and skip if it already exists (primary key/unique constraint).
    """
    if value is None:
        return

    try:
        cursor.execute(INSERT_PROPERTY_QUERY, git_commit_id, name, value)
    except pyodbc.IntegrityError:
        if DEBUG_MODE:
            print(f"  [DEBUG] Property already exists, skipping: {name}={str(value)[:24]}...")

def detect_backout_info(commit_message):
    """
    Detect if a commit is a backout commit and extract the backed out commit hash(es).
    Enhanced version from GitCommitListScraper.py
    
    Args:
        commit_message: The commit message to analyze
        
    Returns:
        dict with:
        - is_backout: Boolean indicating if this is a backout commit
        - backed_out_hashes: List of commit hashes that were backed out
    """
    message_lower = commit_message.lower()
    
    # Enhanced backout patterns - comprehensive list
    # IMPORTANT: Use (?=.*[a-f]) to require at least one letter to avoid matching pure numeric bug IDs
    backout_patterns = [
        # Standard patterns with "changeset"
        r'[Bb]acked?\s+out\s+changeset\s+((?=.*[a-f])[0-9a-f]{7,40})',
        r'[Bb]ack(?:ing)?\s+out\s+changeset\s+((?=.*[a-f])[0-9a-f]{7,40})',
        r'[Bb]ackout\s+changeset\s+((?=.*[a-f])[0-9a-f]{7,40})',
        
        # Standard patterns with "commit"
        r'[Bb]acked?\s+out\s+commit\s+((?=.*[a-f])[0-9a-f]{7,40})',
        r'[Bb]ack(?:ing)?\s+out\s+commit\s+((?=.*[a-f])[0-9a-f]{7,40})',
        r'[Bb]ackout\s+commit\s+((?=.*[a-f])[0-9a-f]{7,40})',
        
        # Patterns without "changeset/commit" but with clear context
        r'[Bb]acked?\s+out\s+(?:rev\s+)?((?=.*[a-f])[0-9a-f]{7,40})',
        r'[Bb]ackout(?:\s+of)?\s+((?=.*[a-f])[0-9a-f]{7,40})',
        r'[Bb]acking\s+out\s+((?=.*[a-f])[0-9a-f]{7,40})',
        
        # Multiple changesets/commits
        r'[Bb]acked?\s+out\s+\d+\s+(?:changesets|commits).*?((?=.*[a-f])[0-9a-f]{7,40})',
        
        # Revert patterns with quoted text (e.g., Revert "Feature X" abc123)
        r'[Rr]evert\s+".*".*\s+((?=.*[a-f])[0-9a-f]{7,40})',
        
        # Git-style revert patterns (GitHub workflow) - flexible with/without "commit"
        r'[Rr]everts?\s+commit\s+version\s+((?=.*[a-f])[0-9a-f]{40})',
        r'[Rr]everts?\s+(?:commit\s+)?((?=.*[a-f])[0-9a-f]{40})',
        r'[Tt]his\s+reverts\s+(?:commit\s+)?((?=.*[a-f])[0-9a-f]{40})',
        r'[Rr]evert(?:ed|ing)?\s+((?=.*[a-f])[0-9a-f]{40})',
    ]
    
    # Check if this looks like a backout
    is_backout = any([
        'backed out' in message_lower,
        'back out' in message_lower,
        message_lower.startswith('backout'),
        message_lower.startswith('revert'),
        'this reverts' in message_lower,
    ])
    
    backed_out_hashes = []
    
    if is_backout:
        # Try to extract commit hashes
        for pattern in backout_patterns:
            matches = re.finditer(pattern, commit_message, re.IGNORECASE)
            for match in matches:
                commit_hash = match.group(1)
                if len(commit_hash) >= 7:  # Valid hash length
                    # Additional validation: ensure it contains at least one letter (a-f)
                    # This prevents matching pure numeric bug IDs like "1387894"
                    if any(c in 'abcdef' for c in commit_hash.lower()):
                        backed_out_hashes.append(commit_hash.lower())
        
        # Remove duplicates while preserving order
        seen = set()
        unique_hashes = []
        for h in backed_out_hashes:
            if h not in seen:
                seen.add(h)
                unique_hashes.append(h)
        backed_out_hashes = unique_hashes
    
    return {
        'is_backout': is_backout,
        'backed_out_hashes': backed_out_hashes
    }


def extract_bug_ids(commit_message):
    """
    Extract bug IDs mentioned in commit message.
    
    Mozilla commonly uses patterns like:
    - "Bug 123456"
    - "bug 123456"
    - "Bug #123456"
    - "r=reviewer bug=123456"
    
    Args:
        commit_message: The commit message to analyze
        
    Returns:
        list: List of bug IDs (as strings)
    """
    bug_patterns = [
        r'[Bb]ug\s+#?(\d+)',
        r'bug=(\d+)',
        r'b=(\d+)',
    ]
    
    bug_ids = []
    
    for pattern in bug_patterns:
        matches = re.finditer(pattern, commit_message)
        for match in matches:
            bug_id = match.group(1)
            if bug_id not in bug_ids:
                bug_ids.append(bug_id)
    
    return bug_ids


def convert_hg_to_git(hg_hash):
    """
    Convert Mercurial changeset hash to Git commit hash.
    Uses HgGit_Mappings table first, then falls back to Lando API.
    
    Args:
        hg_hash: Mercurial changeset hash (12 or 40 chars)
        
    Returns:
        str: Git commit hash (40 chars) or original hash if conversion fails
    """
    # Check cache first
    if hg_hash in HG_TO_GIT_CACHE:
        return HG_TO_GIT_CACHE[hg_hash]
    
    full_hg_hash = hg_hash

    db_attempt = 0
    db_retry_started = time.time()
    db_last_heartbeat = 0
    while True:
        db_attempt += 1
        conn = None
        cursor = None
        try:
            # Try database first
            conn = pyodbc.connect(CONN_STR)
            cursor = conn.cursor()

            # Query for Hg changeset (handles both 12 and 40 char hashes)
            query = '''
                SELECT [Git_Commit_ID]
                FROM [dbo].[HgGit_Mappings]
                WHERE [Hg_Changeset_ID] LIKE ?
            '''
            cursor.execute(query, hg_hash + '%')
            row = cursor.fetchone()

            if row:
                git_hash = normalize_mapping_hash(row[0])
            else:
                git_hash = None

            if git_hash:
                HG_TO_GIT_CACHE[hg_hash] = git_hash
                cursor.close()
                conn.close()
                if DEBUG_MODE:
                    print(f"[{strftime('%H:%M:%S', localtime())}] [DEBUG] Converted Hg {hg_hash[:12]} -> Git {git_hash[:7]} (from HgGit_Mappings)")
                return git_hash

            cursor.close()
            conn.close()

            # Fallback to Lando API with full hash
            print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Hg hash {full_hg_hash[:12]} not in HgGit_Mappings, trying Lando API...")
            break

        except Exception as e:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

            if _retry_window_exhausted(db_retry_started, MAX_LOCAL_RETRY_WINDOW_SECONDS):
                print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Database lookup retries exceeded while converting Hg {hg_hash[:12]}; keeping original hash")
                return hg_hash

            print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] Database lookup issue while converting Hg {hg_hash[:12]} (attempt {db_attempt}): {e}. Retrying in {LOCAL_RETRY_DELAY_SECONDS}s...")

            if _should_emit_retry_heartbeat(db_last_heartbeat):
                elapsed = int(time.time() - db_retry_started)
                print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Still retrying DB lookup for Hg {hg_hash[:12]}... elapsed={elapsed}s attempts={db_attempt}")
                db_last_heartbeat = time.time()

            sleep(LOCAL_RETRY_DELAY_SECONDS)

    # Infinite retry for transient network/API issues (overnight mode)
    api_url = f'https://lando.moz.tools/api/hg2git/firefox/{full_hg_hash}'
    attempt = 0
    api_retry_started = time.time()
    api_last_heartbeat = 0

    while True:
        attempt += 1

        try:
            response = requests.get(api_url, timeout=LANDO_API_TIMEOUT_SECONDS)

            if response.status_code == 200:
                data = response.json()
                git_hash = data.get('git_hash')  # API returns 'git_hash', not 'git_commit_id'
                if git_hash:
                    HG_TO_GIT_CACHE[hg_hash] = git_hash
                    if full_hg_hash != hg_hash:
                        HG_TO_GIT_CACHE[full_hg_hash] = git_hash  # Cache both short and full
                    print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Converted Hg {full_hg_hash[:12]} -> Git {git_hash[:7]} (from Lando API)")
                    return git_hash

                # Unexpected payload: retry forever (treat as transient)
                print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] Invalid Lando API response for {full_hg_hash[:12]} (attempt {attempt}), retrying...")

            elif response.status_code == 404:
                # No mapping exists; this is not a transient network issue
                print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] Could not convert Hg hash {full_hg_hash[:12]} to Git (404 Not Found), keeping original")
                return hg_hash

            else:
                print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] Lando API HTTP {response.status_code} for Hg {full_hg_hash[:12]} (attempt {attempt}), retrying...")

        except requests.exceptions.RequestException as e:
            print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] Network/API error converting Hg {full_hg_hash[:12]} (attempt {attempt}): {e}")
        except Exception as e:
            print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] Unexpected API error converting Hg {full_hg_hash[:12]} (attempt {attempt}): {e}")

        if _retry_window_exhausted(api_retry_started, MAX_API_RETRY_WINDOW_SECONDS):
            print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Lando API retry window exceeded for Hg {full_hg_hash[:12]}; keeping original hash")
            return hg_hash

        if _should_emit_retry_heartbeat(api_last_heartbeat):
            elapsed = int(time.time() - api_retry_started)
            print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Still retrying Lando API for Hg {full_hg_hash[:12]}... elapsed={elapsed}s attempts={attempt}")
            api_last_heartbeat = time.time()

        delay = get_api_retry_delay(attempt)
        print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Waiting {delay}s before retrying Hg {full_hg_hash[:12]}...")
        sleep(delay)


def is_likely_hg_hash(hash_str):
    """
    Determine if a hash is likely a Mercurial changeset (vs Git commit).
    Hg hashes are typically 12 chars in Mozilla commit messages.
    Git hashes are typically 7 or 40 chars.
    
    Args:
        hash_str: Hash string to check
        
    Returns:
        bool: True if likely an Hg hash
    """
    # Mercurial short hashes in Mozilla are typically 12 characters
    # Git short hashes are typically 7 characters
    if len(hash_str) == 12:
        return True
    elif len(hash_str) == 7:
        return False
    elif len(hash_str) == 40:
        # Cache first to avoid repeated DB lookups for the same hash
        if hash_str in HASH_TYPE_CACHE:
            return HASH_TYPE_CACHE[hash_str]

        attempt = 0
        retry_started = time.time()
        last_heartbeat = 0

        while True:
            attempt += 1
            conn = None
            cursor = None
            try:
                conn = pyodbc.connect(CONN_STR)
                cursor = conn.cursor()

                # Check if it's in HgGit_Mappings as Hg
                cursor.execute(
                    "SELECT TOP 1 1 FROM [dbo].[HgGit_Mappings] WHERE [Hg_Changeset_ID] = ?",
                    hash_str
                )
                is_hg_in_mappings = cursor.fetchone() is not None

                if is_hg_in_mappings:
                    HASH_TYPE_CACHE[hash_str] = True
                    cursor.close()
                    conn.close()
                    return True

                # Check if it's in HgGit_Mappings as Git
                cursor.execute(
                    "SELECT TOP 1 1 FROM [dbo].[HgGit_Mappings] WHERE [Git_Commit_ID] = ?",
                    hash_str
                )
                is_git_in_mappings = cursor.fetchone() is not None

                if is_git_in_mappings:
                    HASH_TYPE_CACHE[hash_str] = False
                    cursor.close()
                    conn.close()
                    return False

                cursor.close()
                conn.close()

                # Not found in HgGit_Mappings at all; treat as non-Hg.
                HASH_TYPE_CACHE[hash_str] = False
                return False

            except Exception as e:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()

                if _retry_window_exhausted(retry_started, MAX_LOCAL_RETRY_WINDOW_SECONDS):
                    print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Retry window exceeded in is_likely_hg_hash for {hash_str[:12]}... assuming Git")
                    HASH_TYPE_CACHE[hash_str] = False
                    return False

                print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] is_likely_hg_hash DB lookup failed for {hash_str[:12]} (attempt {attempt}): {e}. Retrying in {LOCAL_RETRY_DELAY_SECONDS}s...")

                if _should_emit_retry_heartbeat(last_heartbeat):
                    elapsed = int(time.time() - retry_started)
                    print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Still retrying is_likely_hg_hash for {hash_str[:12]}... elapsed={elapsed}s attempts={attempt}")
                    last_heartbeat = time.time()

                sleep(LOCAL_RETRY_DELAY_SECONDS)
    
    return False


def resolve_commit_hash(short_hash):
    """
    Resolve a short Git hash to full 40-char hash using git rev-parse.
    Similar to HgChangesetsDetailsExtractor.py's resolve_rev_to_hash()
    
    Args:
        short_hash: Short commit hash (7-40 chars)
    
    Returns:
        str: Full 40-char hash, or original if not found
    """
    # Already full hash
    if len(short_hash) == 40:
        return short_hash
    
    # Check cache first
    if short_hash in GIT_HASH_CACHE:
        return GIT_HASH_CACHE[short_hash]
    
    try:
        import subprocess
        cmd = ['git', 'rev-parse', short_hash]
        result = subprocess.run(
            cmd,
            cwd=REPO_PATH,
            capture_output=True,
            text=True,
            timeout=5,
            check=True
        )
        full_hash = result.stdout.strip()
        if full_hash and len(full_hash) == 40:
            GIT_HASH_CACHE[short_hash] = full_hash
            return full_hash
    except Exception:
        pass
    
    # Fallback to database queries
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        
        # Priority 1: Check HgGit_Mappings table
        query = '''
            SELECT [Git_Commit_ID]
            FROM [dbo].[HgGit_Mappings]
            WHERE [Git_Commit_ID] LIKE ?
        '''
        cursor.execute(query, short_hash + '%')
        row = cursor.fetchone()
        
        if row:
            full_hash = normalize_mapping_hash(row[0])
        else:
            full_hash = None

        if full_hash:
            GIT_HASH_CACHE[short_hash] = full_hash
            cursor.close()
            conn.close()
            if DEBUG_MODE:
                print(f"[{strftime('%H:%M:%S', localtime())}] [DEBUG] Resolved short Git {short_hash[:7]} -> {full_hash[:12]}... (from HgGit_Mappings)")
            return full_hash

        cursor.close()
        conn.close()
    except Exception:
        pass
    
    # Return original if resolution failed
    return short_hash


def get_commit_details_from_repo(commit_hash, repo_path):
    """
    Extract detailed information about a single commit using PyDriller.
    
    Args:
        commit_hash: Git commit hash
        repo_path: Path to local repository
    
    Returns:
        dict: Detailed commit info including backout info and bug IDs
    """
    attempt = 0

    while True:
        attempt += 1

        try:
            # Get commit from repository
            commits = list(pydriller.Repository(
                repo_path,
                single=commit_hash
            ).traverse_commits())

            if not commits:
                print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] Commit {commit_hash[:7]} not found in repository")
                return None

            commit = commits[0]

            # Detect backout information
            backout_info = detect_backout_info(commit.msg)

            # Extract bug IDs
            bug_ids = extract_bug_ids(commit.msg)

            # Build details dict
            details = {
                'hash_id': commit.hash,
                'description': commit.msg.strip(),
                'is_backout_changeset': backout_info['is_backout'],
                'backed_out_changesets': backout_info['backed_out_hashes'],
                'bug_ids': bug_ids,
            }

            return details

        except Exception as e:
            if is_git_config_lock_error(e):
                delay = LOCAL_RETRY_DELAY_SECONDS
                print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] Git config lock contention for {commit_hash[:7]} (attempt {attempt}), retrying in {delay}s")
                sleep(delay)
                continue

            print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Failed to get details for {commit_hash[:7]}: {e}")
            return None


def find_backed_out_by_commit(hash_id, backout_commits_map):
    """
    Find if this commit was backed out by another commit.
    
    Args:
        hash_id: The commit to check (full 40-char hash)
        backout_commits_map: Dict mapping backed_out_hash -> list of backout_hashes
    
    Returns:
        list: List of commit hashes that backed out this commit
    """
    backed_out_by = []
    short_hash = hash_id[:7]
    
    # Check both short and full hashes
    for backed_out_hash, backout_hash_list in backout_commits_map.items():
        # Match if the backed_out_hash matches our hash (full or short)
        if backed_out_hash == hash_id or backed_out_hash == short_hash:
            backed_out_by.extend(backout_hash_list)
        # Also check if it's a short hash that starts with our hash
        elif len(backed_out_hash) < 40 and hash_id.startswith(backed_out_hash):
            backed_out_by.extend(backout_hash_list)
    
    # Remove duplicates
    return list(set(backed_out_by))


def update_backed_out_commits_in_db(backout_commit_hash, backed_out_hashes):
    """
    Update the commits that were backed out by marking them as backed_out=1
    and adding 'Backed Out By' properties.
    
    Args:
        backout_commit_hash: The hash of the backout commit
        backed_out_hashes: List of hashes that were backed out
    
    Returns:
        int: Number of commits successfully updated
    """
    if not backed_out_hashes:
        return 0
    
    attempt = 0
    retry_started = time.time()
    last_heartbeat = 0

    while True:
        attempt += 1
        updated_count = 0
        conn = None
        cursor = None

        try:
            conn = pyodbc.connect(CONN_STR)
            cursor = conn.cursor()

            for backed_out_hash in backed_out_hashes:
                # Resolve to full hash if needed using git rev-parse
                full_hash = resolve_commit_hash(backed_out_hash)

                if DEBUG_MODE:
                    print(f"  [DEBUG] Updating backed-out commit: {full_hash[:12]}... (from backout {backout_commit_hash[:12]}...)")

                # Check if commit exists in database and get current backed_out value
                cursor.execute(
                    f"SELECT [backed_out] FROM {TABLE_GITCOMMITLIST} WHERE [Git_Commit_ID] = ?",
                    full_hash
                )
                result = cursor.fetchone()

                if result is not None:
                    if DEBUG_MODE:
                        current_value = result[0]
                        print(f"  [DEBUG]   Current backed_out value: {current_value}")

                    # Update backed_out flag
                    cursor.execute(
                        f"UPDATE {TABLE_GITCOMMITLIST} SET [backed_out] = 1 WHERE [Git_Commit_ID] = ?",
                        full_hash
                    )

                    if DEBUG_MODE:
                        rows_affected = cursor.rowcount
                        print(f"  [DEBUG]   UPDATE affected {rows_affected} row(s)")

                        # Verify the update
                        cursor.execute(
                            f"SELECT [backed_out] FROM {TABLE_GITCOMMITLIST} WHERE [Git_Commit_ID] = ?",
                            full_hash
                        )
                        new_value = cursor.fetchone()[0]
                        print(f"  [DEBUG]   New backed_out value: {new_value}")

                    # Add 'Backed Out By' property
                    try:
                        cursor.execute(INSERT_PROPERTY_QUERY,
                                     full_hash,
                                     'Backed Out By',
                                     backout_commit_hash)
                        if DEBUG_MODE:
                            print(f"  [DEBUG]   Added 'Backed Out By' property")
                    except pyodbc.IntegrityError:
                        # Property already exists, skip
                        if DEBUG_MODE:
                            print(f"  [DEBUG]   'Backed Out By' property already exists")
                        pass

                    updated_count += 1
                else:
                    if DEBUG_MODE:
                        print(f"  [{strftime('%H:%M:%S', localtime())}] [WARNING] Backed out commit {backed_out_hash} not found in database (normalized to {full_hash[:12]}...)")

            conn.commit()
            cursor.close()
            conn.close()
            return updated_count

        except Exception as e:
            print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Failed to update backed out commits (attempt {attempt}): {e}")
            if conn:
                conn.rollback()
            if cursor:
                cursor.close()
            if conn:
                conn.close()

            if _retry_window_exhausted(retry_started, MAX_LOCAL_RETRY_WINDOW_SECONDS):
                print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Retry window exceeded while updating backed-out commits for {backout_commit_hash[:12]}... skipping this update")
                return 0

            if _should_emit_retry_heartbeat(last_heartbeat):
                elapsed = int(time.time() - retry_started)
                print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Still retrying backed-out commit updates for {backout_commit_hash[:12]}... elapsed={elapsed}s attempts={attempt}")
                last_heartbeat = time.time()

            print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Retrying local DB update in {LOCAL_RETRY_DELAY_SECONDS}s...")
            sleep(LOCAL_RETRY_DELAY_SECONDS)


def update_commit_in_db(commit_details, backed_out_by_list):
    """
    Update a single commit and its properties in the database.
    
    Args:
        commit_details: Dict with commit details
        backed_out_by_list: List of commits that backed out this one
    
    Returns:
        bool: Success status
    """
    hash_id = commit_details.get('hash_id', 'UNKNOWN_HASH')
    attempt = 0
    retry_started = time.time()
    last_heartbeat = 0

    while True:
        attempt += 1
        conn = None
        cursor = None
        try:
            conn = pyodbc.connect(CONN_STR)
            cursor = conn.cursor()

            # Determine if this commit was backed out
            backed_out = 1 if backed_out_by_list else 0
            is_backout = 1 if commit_details['is_backout_changeset'] else 0
            description = commit_details['description']

            # Update GitCommitList table
            cursor.execute(UPDATE_COMMIT_QUERY,
                          backed_out,
                          is_backout,
                          description,
                          hash_id)

            # Insert backout properties (convert Hg to Git if needed, then normalize to full hash)
            full_backed_out_hashes = []  # Collect full hashes for later use
            backout_commit_values_to_store = []
            if commit_details['backed_out_changesets']:
                for backed_out_hash in commit_details['backed_out_changesets']:
                    original_hash = backed_out_hash
                    property_value_to_store = original_hash

                    try:
                        # Check if this is an Hg hash and convert to Git
                        if is_likely_hg_hash(backed_out_hash):
                            converted_hash = convert_hg_to_git(backed_out_hash)

                            # If conversion succeeded, store converted value; otherwise keep original hash
                            if converted_hash and converted_hash != original_hash:
                                property_value_to_store = converted_hash
                            else:
                                print(f"  [{strftime('%H:%M:%S', localtime())}] [WARNING] Could not convert Hg hash {original_hash[:12]} to Git, storing original hash")
                        else:
                            # Resolve short Git hash to full 40-char hash when possible
                            resolved_hash = resolve_commit_hash(backed_out_hash)
                            if resolved_hash:
                                property_value_to_store = resolved_hash
                    except Exception as conversion_error:
                        print(f"  [{strftime('%H:%M:%S', localtime())}] [WARNING] Failed normalizing backout hash {original_hash[:12]}: {conversion_error}. Storing original hash")
                        property_value_to_store = original_hash

                    # GUARANTEE: always keep what we parsed (or best normalized value)
                    backout_commit_values_to_store.append(property_value_to_store)

                    # Only attempt backed_out flag updates for plausible Git commit IDs
                    if len(property_value_to_store) == 40:
                        full_backed_out_hashes.append(property_value_to_store)

                # Insert Backout Commit properties (deduplicated)
                seen_backout_values = set()
                for value in backout_commit_values_to_store:
                    if not value or value in seen_backout_values:
                        continue
                    seen_backout_values.add(value)
                    insert_property_skip_duplicate(cursor, hash_id, 'Backout Commit', value)

                # Commit the properties first before updating backed-out commits
                conn.commit()

                # Update the backed-out commits (set their backed_out=1 and add 'Backed Out By' property)
                # Pass the list of FULL hashes (not short hashes) to avoid re-resolution
                count = update_backed_out_commits_in_db(hash_id, full_backed_out_hashes)
                if count > 0:
                    print(f"  [{strftime('%H:%M:%S', localtime())}] [INFO] Updated {count} backed-out commit(s)")

            # Insert 'Backed Out By' properties
            if backed_out_by_list:
                for backout_hash in backed_out_by_list:
                    insert_property_skip_duplicate(cursor, hash_id, 'Backed Out By', backout_hash)

            # Insert bug ID properties
            if commit_details['bug_ids']:
                for bug_id in commit_details['bug_ids']:
                    insert_property_skip_duplicate(cursor, hash_id, 'Bug ID Mentioned', bug_id)

            # Commit all remaining changes (if not already committed)
            if conn:
                conn.commit()
            cursor.close()
            conn.close()

            return True

        except Exception as e:
            print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Failed to update commit {hash_id[:7]} (attempt {attempt}): {e}")
            if conn:
                conn.rollback()
            if cursor:
                cursor.close()
            if conn:
                conn.close()

            if _retry_window_exhausted(retry_started, MAX_LOCAL_RETRY_WINDOW_SECONDS):
                print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Retry window exceeded for commit {hash_id[:7]}; marking as update failure and continuing")
                return False

            if _should_emit_retry_heartbeat(last_heartbeat):
                elapsed = int(time.time() - retry_started)
                print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Still retrying DB write for commit {hash_id[:7]}... elapsed={elapsed}s attempts={attempt}")
                last_heartbeat = time.time()

            print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Retrying local DB write in {LOCAL_RETRY_DELAY_SECONDS}s...")
            sleep(LOCAL_RETRY_DELAY_SECONDS)


def get_commits_from_db(start_git_commit_id=None, end_git_commit_id=None):
    """
    Get all commit hashes from the database that need processing.
    
    Args:
        start_git_commit_id: Starting Git_Commit_ID (inclusive), None for no lower bound
        end_git_commit_id: Ending Git_Commit_ID (inclusive), None for no upper bound
    
    Returns:
        list: List of commit hashes in the specified range
    """
    use_range = (start_git_commit_id is not None and end_git_commit_id is not None)
    
    attempt = 0
    retry_started = time.time()
    last_heartbeat = 0

    while True:
        attempt += 1
        conn = None
        cursor = None
        try:
            conn = pyodbc.connect(CONN_STR)
            cursor = conn.cursor()

            if use_range:
                # Range mode: filter by Git_Commit_ID range
                cursor.execute(GET_COMMITS_RANGE_QUERY, (start_git_commit_id, end_git_commit_id))
            else:
                # All mode: fetch all unprocessed
                cursor.execute(GET_ALL_COMMITS_QUERY)

            commits = [row[0] for row in cursor.fetchall()]

            cursor.close()
            conn.close()

            return commits

        except Exception as e:
            print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Failed to get commits from database (attempt {attempt}): {e}")
            if cursor:
                cursor.close()
            if conn:
                conn.close()

            if _retry_window_exhausted(retry_started, MAX_LOCAL_RETRY_WINDOW_SECONDS):
                raise RuntimeError("Database read retry window exceeded while fetching commits") from e

            if _should_emit_retry_heartbeat(last_heartbeat):
                elapsed = int(time.time() - retry_started)
                print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Still retrying commit fetch... elapsed={elapsed}s attempts={attempt}")
                last_heartbeat = time.time()

            print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Retrying local DB read in {LOCAL_RETRY_DELAY_SECONDS}s...")
            sleep(LOCAL_RETRY_DELAY_SECONDS)


def process_all_commits(start_git_commit_id=None, end_git_commit_id=None):
    """
    Process all commits from the database and extract detailed information.
    Uses batch processing with incremental database saves for crash recovery.
    
    Args:
        start_git_commit_id: Starting Git_Commit_ID (inclusive), None for no lower bound
        end_git_commit_id: Ending Git_Commit_ID (inclusive), None for no upper bound
    """
    use_range = (start_git_commit_id is not None and end_git_commit_id is not None)
    
    print("=" * 80)
    if use_range:
        print(f"[{strftime('%H:%M:%S', localtime())}] GIT COMMIT DETAILS EXTRACTOR - PYDRILLER VERSION [RANGE MODE]")
        print(f"Processing Git_Commit_ID range: {start_git_commit_id} to {end_git_commit_id}")
    else:
        print(f"[{strftime('%H:%M:%S', localtime())}] GIT COMMIT DETAILS EXTRACTOR - PYDRILLER VERSION [ALL RECORDS]")
    print("=" * 80)
    print(f"[{strftime('%H:%M:%S', localtime())}] Repository:  {REPO_PATH}")
    print(f"[{strftime('%H:%M:%S', localtime())}] Batch size:  {BATCH_SIZE}")
    print(f"[{strftime('%H:%M:%S', localtime())}] Start time:  {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    print("=" * 80)
    
    # Count total commits to process
    print(f"\n[{strftime('%H:%M:%S', localtime())}] [STEP 1/3] Counting commits to process...")
    commits = get_commits_from_db(start_git_commit_id, end_git_commit_id)
    
    if not commits:
        if use_range:
            print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] No commits found in range {start_git_commit_id} to {end_git_commit_id}")
        else:
            print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] No commits found to process")
        return
    
    total_commits = len(commits)
    if use_range:
        print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Found {total_commits} commits to process in range {start_git_commit_id[:12]}...{end_git_commit_id[:12]}")
    else:
        print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Found {total_commits} commits to process")
    
    # Process in batches with incremental saves
    print(f"\n[{strftime('%H:%M:%S', localtime())}] [STEP 2/3] Processing in batches of {BATCH_SIZE} (saves to database after each batch)...")
    
    total_processed = 0
    total_failed = 0
    total_updated = 0
    total_update_failed = 0
    batch_num = 0
    
    # Process by repeatedly querying for unprocessed commits
    # This allows resuming if the script crashes
    while True:
        # Get next batch of unprocessed commits
        batch_commits = get_commits_from_db(start_git_commit_id, end_git_commit_id)
        
        if not batch_commits:
            print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] No more commits to process")
            break
        
        # Limit to BATCH_SIZE
        batch_commits = batch_commits[:BATCH_SIZE]
        batch_num += 1
        
        print(f"\n[{strftime('%H:%M:%S', localtime())}] [BATCH {batch_num}] Processing {len(batch_commits)} commits...")
        
        # Extract details for this batch
        batch_details = {}
        batch_backout_map = {}
        batch_total = len(batch_commits)
        print_progress_bar("Extract", 0, batch_total)
        
        for idx, hash_id in enumerate(batch_commits, 1):
            details = get_commit_details_from_repo(hash_id, REPO_PATH)
            
            if details:
                batch_details[hash_id] = details
                total_processed += 1
                
                # Build backout map for this batch
                if details['is_backout_changeset'] and details['backed_out_changesets']:
                    for backed_out_hash in details['backed_out_changesets']:
                        if backed_out_hash not in batch_backout_map:
                            batch_backout_map[backed_out_hash] = []
                        batch_backout_map[backed_out_hash].append(hash_id)
            else:
                total_failed += 1
            
            # Progress within extraction phase
            if idx % PROGRESS_LOG_INTERVAL == 0 or idx == batch_total:
                print_progress_bar("Extract", idx, batch_total)
        
        # Normalize backed-out hashes for this batch
        normalized_backout_map = {}
        normalize_total = len(batch_backout_map)
        if normalize_total > 0:
            print_progress_bar("Normalize", 0, normalize_total)

        for normalize_idx, (backed_out_hash, backout_list) in enumerate(batch_backout_map.items(), 1):
            full_hash = resolve_commit_hash(backed_out_hash)
            
            if full_hash not in normalized_backout_map:
                normalized_backout_map[full_hash] = []
            
            for backout_hash in backout_list:
                if backout_hash not in normalized_backout_map[full_hash]:
                    normalized_backout_map[full_hash].append(backout_hash)

            if normalize_total > 0 and (normalize_idx % PROGRESS_LOG_INTERVAL == 0 or normalize_idx == normalize_total):
                print_progress_bar("Normalize", normalize_idx, normalize_total)
        
        # Update database for this batch
        batch_updated = 0
        batch_failed = 0
        update_total = len(batch_details)
        if update_total > 0:
            print_progress_bar("DB Update", 0, update_total)
        
        for update_idx, (hash_id, details) in enumerate(batch_details.items(), 1):
            # Find if this commit was backed out
            backed_out_by = find_backed_out_by_commit(hash_id, normalized_backout_map)
            
            # Update this commit
            success = update_commit_in_db(details, backed_out_by)
            
            if success:
                batch_updated += 1
                total_updated += 1
            else:
                batch_failed += 1
                total_update_failed += 1

            if update_total > 0 and (update_idx % PROGRESS_LOG_INTERVAL == 0 or update_idx == update_total):
                print_progress_bar("DB Update", update_idx, update_total)
        
        # Batch complete - data is already saved to database
        print(f"[{strftime('%H:%M:%S', localtime())}] [BATCH {batch_num}] Complete: {batch_updated} commits saved to database ({total_updated}/{total_commits} total)")
        
        # Safety check: if batch size was less than BATCH_SIZE, we're done
        if len(batch_commits) < BATCH_SIZE:
            break
    
    # Final summary
    print(f"\n[{strftime('%H:%M:%S', localtime())}] [STEP 3/3] Final Summary")
    print("=" * 80)
    if use_range:
        print(f"EXTRACTION COMPLETE - RANGE {start_git_commit_id[:12]}...{end_git_commit_id[:12]}")
    else:
        print("EXTRACTION COMPLETE - ALL RECORDS")
    print("=" * 80)
    print(f"Total commits:                 {total_commits}")
    print(f"Details extracted:             {total_processed}")
    print(f"Extraction failed:             {total_failed}")
    print(f"Database updates successful:   {total_updated}")
    print(f"Database updates failed:       {total_update_failed}")
    print(f"Total batches:                 {batch_num}")
    print(f"End time:                      {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    print("=" * 80)


def process_single_commit(hash_id):
    """
    Process a single commit for testing purposes.
    
    Args:
        hash_id: Commit hash to process
    """
    print(f"Processing single commit: {hash_id}")
    print("=" * 80)
    
    details = get_commit_details_from_repo(hash_id, REPO_PATH)
    
    if not details:
        print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Failed to get details for commit {hash_id}")
        return
    
    print(f"Hash ID:              {details['hash_id']}")
    print(f"Is Backout:           {details['is_backout_changeset']}")
    print(f"Backed Out Changes:   {len(details['backed_out_changesets'])}")
    for backed_out in details['backed_out_changesets']:
        print(f"  - {backed_out}")
    print(f"Bug IDs:              {len(details['bug_ids'])}")
    for bug_id in details['bug_ids']:
        print(f"  - Bug {bug_id}")
    
    print(f"\nDescription:\n{details['description'][:500]}")
    print("=" * 80)
    
    # Build a small backout map for testing
    backout_map = {}
    if details['is_backout_changeset']:
        for backed_out_hash in details['backed_out_changesets']:
            backout_map[backed_out_hash] = [hash_id]
    
    # Check if this was backed out
    backed_out_by = find_backed_out_by_commit(hash_id, backout_map)
    
    if backed_out_by:
        print(f"\nThis commit was backed out by:")
        for backout_hash in backed_out_by:
            print(f"  - {backout_hash}")
    
    # Update database
    print(f"\n[{strftime('%H:%M:%S', localtime())}] Updating database...")
    success = update_commit_in_db(details, backed_out_by)
    
    if success:
        print(f"[{strftime('%H:%M:%S', localtime())}] [SUCCESS] Database updated successfully")
    else:
        print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Failed to update database")


if __name__ == "__main__":
    # ========== CONFIGURATION ==========
    
    # MODE: "all" to process all commits, "single" to test one commit, "range" to use command-line args
    MODE = "range"  # "all", "single", or "range"
    
    # Debug mode - set to False to reduce log verbosity (only show progress/timing)
    DEBUG_MODE = False
    
    # For single mode, specify the commit hash
    # Example: a known backout commit for testing
    # TEST_COMMIT = "a929f957f0e89b88bfc47ab9024224b4765443fb" # Test case: Backout changeset with Hg changeset hashes in description (https://hg-edge.mozilla.org/mozilla-central/rev/ce76fa05c90f3f24f8db09950eadd4a8cdec9088)
    # TEST_COMMIT = "becded629c7a6ae23a793035bc7d35eeb267f0a3" # Test case: regular (https://hg-edge.mozilla.org/mozilla-central/rev/0df381e9da8fa9bad1881075bbf25f2e5c0b413a)
    # TEST_COMMIT = "55b2aa39f52c75f74351f056ec1c2e76bf5a88d9" # Test case: Backout commit with Git commit hashes in description (https://hg-edge.mozilla.org/mozilla-central/rev/01064dcdd2abd69e53837af1b41d6d6a0c8ac30e)
    TEST_COMMIT = "0006c9b86c7c307de509cf383f29cec3d6f0e3e8" # Test case: hash ID mentioned on description not found
    # ===================================
    
    cli_args = parse_arguments()
    configure_table_queries(cli_args.table_number)
    REPO_PATH = cli_args.repo_path
    print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Using tables: {TABLE_GITCOMMITLIST} and {TABLE_GITCOMMIT_PROPERTIES}")
    print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Using repo path: {REPO_PATH}")

    if MODE == "all":
        process_all_commits()
    elif MODE == "single":
        process_single_commit(TEST_COMMIT)
    elif MODE == "range":
        # Parse command-line arguments for range-based parallel processing
        args = cli_args

        # args = type('Args', (object,), {})()  # Create a simple object to hold args
        # args.start_git_commit_id = '00000163a890eb9f05f98c4084cd07846aa7cbf0'
        # args.end_git_commit_id = '0cc73f8e55a9781a93769b17be8a0571064430b7'

        if args.start_git_commit_id is not None and args.end_git_commit_id is not None:
            print(f"\n>>> Running in RANGE mode: Git_Commit_ID {args.start_git_commit_id} to {args.end_git_commit_id}")
            process_all_commits(start_git_commit_id=args.start_git_commit_id, end_git_commit_id=args.end_git_commit_id)
        else:
            # Process all unprocessed commits
            print("\n>>> Running in ALL RECORDS mode")
            process_all_commits()
    else:
        print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Invalid MODE: {MODE}")
        print(f"[{strftime('%H:%M:%S', localtime())}] Valid options: 'all', 'single', or 'range'")
        sys.exit(1)
    
    print(f"\n[{strftime('%H:%M:%S', localtime())}] Script completed. Exiting.")
