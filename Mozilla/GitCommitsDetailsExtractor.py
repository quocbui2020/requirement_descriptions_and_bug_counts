"""
Git Commit Details Extractor for Mozilla Firefox Repository

Extracts detailed information from local Git repository and updates:
1. GitCommitList table - Updates is_backout_commit, backed_out, Description flags
2. GitCommit_Properties table - Stores backout relationships and bug IDs

EXTRACTED INFORMATION:
- Backout relationships (backed_out, is_backout_commit flags)
- Backout commit links (parsed from commit messages)
- Bug IDs mentioned in commit messages (Bug XXXXXX pattern)
- Backed Out By relationships

BACKOUT DETECTION:
- Checks various backout message formats
- Enhanced regex patterns to catch backout variations
- Supports both short (7-char) and full (40-char) hash matching

BACKOUT PATTERNS DETECTED:
- "Backed out changeset abc123" 
- "Back out changeset abc123"
- "Backout abc123"
- "Backing out abc123"
- "Reverted changeset abc123"
- And more variations (case-insensitive)

BUG ID PATTERNS:
- "Bug 123456"
- "bug 123456"
- "Bug #123456"
- Multiple bugs in one commit

REQUIREMENTS:
- Local clone of firefox Git repository
- PyDriller installed  
- GitCommitList table already populated with basic info
"""

import pyodbc
import re
import requests
from time import strftime, localtime
from time import sleep
import pydriller

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

# Cache for Hg to Git conversions
HG_TO_GIT_CACHE = {}
# ====================================

# SQL Queries
UPDATE_COMMIT_QUERY = '''
    UPDATE [dbo].[GitCommitList]
    SET [backed_out] = ?,
        [is_backout_commit] = ?,
        [Description] = ?
    WHERE [Git_Commit_ID] = ?
'''

INSERT_PROPERTY_QUERY = '''
    INSERT INTO [dbo].[GitCommit_Properties]
        ([Git_Commit_ID], [Name], [Value])
    VALUES (?, ?, ?)
'''

DELETE_PROPERTIES_QUERY = '''
    DELETE FROM [dbo].[GitCommit_Properties]
    WHERE [Git_Commit_ID] = ?
'''

GET_ALL_COMMITS_QUERY = '''
    SELECT [Git_Commit_ID]
    FROM [dbo].[GitCommitList]
    WHERE [Description] IS NULL
    ORDER BY [Git_Commit_ID]
'''

GET_COMMITS_BATCH_QUERY = '''
    SELECT [Git_Commit_ID]
    FROM [dbo].[GitCommitList]
    WHERE [Git_Commit_ID] > ?
    ORDER BY [Git_Commit_ID]
    OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY
'''


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
    backout_patterns = [
        r'[Bb]acked?\s+out\s+(?:changeset|change set|commit|revision)s?\s+([a-f0-9]{7,40})',
        r'[Bb]ack(?:ing)?\s+out\s+(?:changeset|change set|commit|revision)s?\s+([a-f0-9]{7,40})',
        r'[Bb]ackout\s+(?:changeset|change set|commit|revision)?\s*([a-f0-9]{7,40})',
        r'[Rr]evert\s+(?:changeset|change set|commit|revision)?\s+([a-f0-9]{7,40})',
        r'[Rr]evert\s+".*".*\s+([a-f0-9]{7,40})',
        r'[Bb]acked?\s+out\s+([a-f0-9]{7,40})',
        r'[Bb]ack(?:ing)?\s+out\s+([a-f0-9]{7,40})',
        r'[Bb]ackout\s+([a-f0-9]{7,40})',
        r'[Rr]everts?\s+(?:commit\s+)?([a-f0-9]{40})',
        r'[Tt]his\s+reverts\s+(?:commit\s+)?([a-f0-9]{40})',
        r'[Rr]evert(?:ed|ing)?\s+([a-f0-9]{40})',
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
        cursor.close()
        conn.close()
        
        if row:
            git_hash = row[0]
            HG_TO_GIT_CACHE[hg_hash] = git_hash
            print(f"[INFO] Converted Hg {hg_hash[:12]} -> Git {git_hash[:7]} (from database)")
            return git_hash
        
        # Fallback to Lando API
        print(f"[INFO] Hg hash {hg_hash[:12]} not in database, trying Lando API...")
        api_url = f'https://lando.moz.tools/api/hg2git/firefox/{hg_hash}'
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            git_hash = data.get('git_commit_id')
            if git_hash:
                HG_TO_GIT_CACHE[hg_hash] = git_hash
                print(f"[INFO] Converted Hg {hg_hash[:12]} -> Git {git_hash[:7]} (from API)")
                return git_hash
        
        print(f"[WARNING] Could not convert Hg hash {hg_hash[:12]} to Git, keeping original")
        return hg_hash
        
    except Exception as e:
        print(f"[WARNING] Error converting Hg to Git for {hg_hash[:12]}: {e}")
        return hg_hash


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
        # For full hashes, check in database
        try:
            conn = pyodbc.connect(CONN_STR)
            cursor = conn.cursor()
            
            # Check if it's in HgGit_Mappings as Hg
            cursor.execute(
                "SELECT COUNT(*) FROM [dbo].[HgGit_Mappings] WHERE [Hg_Changeset_ID] = ?",
                hash_str
            )
            is_hg = cursor.fetchone()[0] > 0
            cursor.close()
            conn.close()
            
            return is_hg
        except:
            pass
    
    return False


def normalize_commit_hash(short_hash, repo_commits_map):
    """
    Normalize a short hash (7-12 chars) to full 40-char hash.
    
    Args:
        short_hash: Short commit hash
        repo_commits_map: Dict mapping short hashes to full hashes
        
    Returns:
        str: Full 40-char hash, or original if not found
    """
    if len(short_hash) == 40:
        return short_hash
    
    # Try to find in the map
    for full_hash in repo_commits_map.values():
        if full_hash.startswith(short_hash.lower()):
            return full_hash
    
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
    try:
        # Get commit from repository
        commits = list(pydriller.Repository(
            repo_path, 
            single=commit_hash
        ).traverse_commits())
        
        if not commits:
            print(f"[WARNING] Commit {commit_hash[:7]} not found in repository")
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
        print(f"[ERROR] Failed to get details for {commit_hash[:7]}: {e}")
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


def update_backed_out_commits_in_db(backout_commit_hash, backed_out_hashes, repo_commits_map):
    """
    Update the commits that were backed out by marking them as backed_out=1
    and adding 'Backed Out By' properties.
    
    Args:
        backout_commit_hash: The hash of the backout commit
        backed_out_hashes: List of hashes that were backed out
        repo_commits_map: Dict mapping short hashes to full hashes
    
    Returns:
        int: Number of commits successfully updated
    """
    if not backed_out_hashes:
        return 0
    
    updated_count = 0
    
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        
        for backed_out_hash in backed_out_hashes:
            # Normalize to full hash if needed
            full_hash = normalize_commit_hash(backed_out_hash, repo_commits_map)
            
            # Check if commit exists in database
            cursor.execute(
                "SELECT COUNT(*) FROM [dbo].[GitCommitList] WHERE [Git_Commit_ID] = ?",
                full_hash
            )
            exists = cursor.fetchone()[0] > 0
            
            if exists:
                # Update backed_out flag
                cursor.execute(
                    "UPDATE [dbo].[GitCommitList] SET [backed_out] = 1 WHERE [Git_Commit_ID] = ?",
                    full_hash
                )
                
                # Add 'Backed Out By' property
                try:
                    cursor.execute(INSERT_PROPERTY_QUERY, 
                                 full_hash, 
                                 'Backed Out By', 
                                 backout_commit_hash)
                except pyodbc.IntegrityError:
                    # Property already exists, skip
                    pass
                
                updated_count += 1
            else:
                print(f"[WARNING] Backed out commit {backed_out_hash} not found in database")
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"[ERROR] Failed to update backed out commits: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
    
    return updated_count


def update_commit_in_db(commit_details, backed_out_by_list):
    """
    Update a single commit and its properties in the database.
    
    Args:
        commit_details: Dict with commit details
        backed_out_by_list: List of commits that backed out this one
    
    Returns:
        bool: Success status
    """
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        
        hash_id = commit_details['hash_id']
        
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
        
        # Delete existing properties for this commit
        cursor.execute(DELETE_PROPERTIES_QUERY, hash_id)
        
        # Insert backout properties (convert Hg to Git if needed)
        if commit_details['backed_out_changesets']:
            for backed_out_hash in commit_details['backed_out_changesets']:
                # Check if this is an Hg hash and convert to Git
                if is_likely_hg_hash(backed_out_hash):
                    backed_out_hash = convert_hg_to_git(backed_out_hash)
                
                cursor.execute(INSERT_PROPERTY_QUERY,
                             hash_id,
                             'Backout Commit',
                             backed_out_hash)
        
        # Insert 'Backed Out By' properties
        if backed_out_by_list:
            for backout_hash in backed_out_by_list:
                cursor.execute(INSERT_PROPERTY_QUERY,
                             hash_id,
                             'Backed Out By',
                             backout_hash)
        
        # Insert bug ID properties
        if commit_details['bug_ids']:
            for bug_id in commit_details['bug_ids']:
                cursor.execute(INSERT_PROPERTY_QUERY,
                             hash_id,
                             'Bug ID',
                             bug_id)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to update commit {hash_id[:7]}: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


def get_commits_from_db():
    """
    Get all commit hashes from the database that need processing.
    
    Returns:
        list: List of commit hashes
    """
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        
        cursor.execute(GET_ALL_COMMITS_QUERY)
        commits = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return commits
        
    except Exception as e:
        print(f"[ERROR] Failed to get commits from database: {e}")
        return []


def build_repo_commits_map(repo_path):
    """
    Build a mapping of all commits in the repository (short hash -> full hash).
    This helps normalize short hashes found in commit messages.
    
    Args:
        repo_path: Path to local repository
        
    Returns:
        dict: Mapping of short hashes to full hashes
    """
    print("[INFO] Building repository commits map...")
    commits_map = {}
    
    try:
        count = 0
        for commit in pydriller.Repository(repo_path).traverse_commits():
            commits_map[commit.hash[:7]] = commit.hash
            commits_map[commit.hash[:12]] = commit.hash
            commits_map[commit.hash] = commit.hash
            count += 1
            
            if count % 1000 == 0:
                print(f"[INFO] Mapped {count} commits...")
        
        print(f"[INFO] Mapped {count} total commits")
        return commits_map
        
    except Exception as e:
        print(f"[ERROR] Failed to build commits map: {e}")
        return {}


def process_all_commits():
    """
    Process all commits from the database and extract detailed information.
    """
    print("=" * 80)
    print("GIT COMMIT DETAILS EXTRACTOR - PYDRILLER VERSION")
    print("=" * 80)
    print(f"Repository:  {REPO_PATH}")
    print(f"Batch size:  {BATCH_SIZE}")
    print(f"Start time:  {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    print("=" * 80)
    
    # Step 1: Get all commits from database
    print("\n[STEP 1/5] Loading commits from database...")
    commits = get_commits_from_db()
    
    if not commits:
        print("[WARNING] No commits found to process")
        return
    
    print(f"[INFO] Found {len(commits)} commits to process")
    
    # Step 2: Build repository commits map
    print("\n[STEP 2/5] Building repository commits map...")
    repo_commits_map = build_repo_commits_map(REPO_PATH)
    
    # Step 3: Extract details and build backout map
    print("\n[STEP 3/5] Extracting details from Git repository...")
    
    all_details = {}
    backout_map = {}  # Maps backed_out_hash -> [backout_hash1, backout_hash2, ...]
    
    processed = 0
    failed = 0
    
    for idx, hash_id in enumerate(commits, 1):
        if idx % 10 == 0:
            print(f"[PROGRESS] {idx}/{len(commits)} - Processing {hash_id[:7]}...")
        
        details = get_commit_details_from_repo(hash_id, REPO_PATH)
        
        if details:
            all_details[hash_id] = details
            processed += 1
            
            # Build backout map
            if details['is_backout_changeset'] and details['backed_out_changesets']:
                for backed_out_hash in details['backed_out_changesets']:
                    if backed_out_hash not in backout_map:
                        backout_map[backed_out_hash] = []
                    backout_map[backed_out_hash].append(hash_id)
        else:
            failed += 1
        
        # Progress indicator
        if idx % 100 == 0:
            print(f"[INFO] Progress: {idx}/{len(commits)} ({processed} processed, {failed} failed)")
    
    print(f"\n[INFO] Extraction complete: {processed} processed, {failed} failed")
    print(f"[INFO] Found {len(backout_map)} backed out commits")
    
    # Step 4: Normalize backed-out hashes to full 40-char format
    print("\n[STEP 4/5] Normalizing hash formats...")
    normalized_backout_map = {}
    for backed_out_hash, backout_list in backout_map.items():
        # Normalize the backed_out_hash
        full_hash = normalize_commit_hash(backed_out_hash, repo_commits_map)
        
        if full_hash not in normalized_backout_map:
            normalized_backout_map[full_hash] = []
        
        # Add all backout commits (they should already be full hashes)
        for backout_hash in backout_list:
            if backout_hash not in normalized_backout_map[full_hash]:
                normalized_backout_map[full_hash].append(backout_hash)
    
    print(f"[INFO] Normalized map has {len(normalized_backout_map)} backed out commits")
    
    # Step 5: Update database
    print("\n[STEP 5/5] Updating database...")
    
    updated = 0
    update_failed = 0
    backed_out_updates = 0
    batch_num = 0
    
    for idx, (hash_id, details) in enumerate(all_details.items(), 1):
        # Find if this commit was backed out
        backed_out_by = find_backed_out_by_commit(hash_id, normalized_backout_map)
        
        # Update this commit
        success = update_commit_in_db(details, backed_out_by)
        
        if success:
            updated += 1
            
            # If this is a backout commit, update the backed out commits
            if details['is_backout_changeset'] and details['backed_out_changesets']:
                count = update_backed_out_commits_in_db(
                    hash_id, 
                    details['backed_out_changesets'],
                    repo_commits_map
                )
                backed_out_updates += count
        else:
            update_failed += 1
        
        # Batch commit progress
        if idx % BATCH_SIZE == 0:
            batch_num += 1
            print(f"[INFO] Batch {batch_num} complete: {updated}/{idx} commits updated")
    
    # Final summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)
    print(f"Total commits:                 {len(commits)}")
    print(f"Details extracted:             {processed}")
    print(f"Extraction failed:             {failed}")
    print(f"Database updates successful:   {updated}")
    print(f"Database updates failed:       {update_failed}")
    print(f"Backout relationships found:   {len(backout_map)}")
    print(f"Backed-out commits updated:    {backed_out_updates}")
    print(f"End time:                      {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    print("=" * 80)
    
    # Additional statistics
    backout_count = sum(1 for d in all_details.values() if d['is_backout_changeset'])
    backed_out_count = len([h for h in all_details.keys() 
                           if find_backed_out_by_commit(h, backout_map)])
    commits_with_bugs = sum(1 for d in all_details.values() if d['bug_ids'])
    
    print("\nSTATISTICS:")
    print(f"Backout commits:               {backout_count}")
    print(f"Backed out commits:            {backed_out_count}")
    print(f"Commits with bug IDs:          {commits_with_bugs}")
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
        print(f"[ERROR] Failed to get details for commit {hash_id}")
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
    print("\nUpdating database...")
    success = update_commit_in_db(details, backed_out_by)
    
    if success:
        print("[SUCCESS] Database updated successfully")
        
        # If this is a backout, update the backed out commits
        if details['is_backout_changeset'] and details['backed_out_changesets']:
            repo_map = build_repo_commits_map(REPO_PATH)
            count = update_backed_out_commits_in_db(hash_id, details['backed_out_changesets'], repo_map)
            print(f"[SUCCESS] Updated {count} backed out commits")
    else:
        print("[ERROR] Failed to update database")


if __name__ == "__main__":
    # ========== CONFIGURATION ==========
    
    # MODE: "all" to process all commits, "single" to test one commit
    MODE = "single"  # "all" or "single"
    
    # For single mode, specify the commit hash
    # Example: a known backout commit for testing
    TEST_COMMIT = ""  # Replace with actual Git commit hash
    
    # ===================================
    
    if MODE == "all":
        process_all_commits()
    elif MODE == "single":
        process_single_commit(TEST_COMMIT)
    else:
        print(f"[ERROR] Invalid MODE: {MODE}")
        print("Valid options: 'all' or 'single'")
    
    print("\nScript completed. Exiting.")
