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

# Debug mode - set to False to reduce log verbosity (only show progress/timing)
DEBUG_MODE = True

# Cache for Hg to Git conversions
HG_TO_GIT_CACHE = {}

# Cache for resolving short Git hashes to full hashes
GIT_HASH_CACHE = {}
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
    WHERE [Description] IS NULL -- This filter ensure we only process commits that haven't been updated yet (i.e., details not extracted)
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
            git_hash = row[0]
            HG_TO_GIT_CACHE[hg_hash] = git_hash
            cursor.close()
            conn.close()
            if DEBUG_MODE:
                print(f"[{strftime('%H:%M:%S', localtime())}] [DEBUG] Converted Hg {hg_hash[:12]} -> Git {git_hash[:7]} (from HgGit_Mappings)")
            return git_hash
        
        # HgGit_Mappings doesn't have it, try resolving full Hg hash from Changesets
        full_hg_hash = hg_hash
        if len(hg_hash) < 40:
            query = '''
                SELECT [Hash_Id]
                FROM [dbo].[Changesets]
                WHERE [Hash_Id] LIKE ?
            '''
            cursor.execute(query, hg_hash + '%')
            row = cursor.fetchone()
            if row:
                full_hg_hash = row[0]
                if DEBUG_MODE:
                    print(f"[{strftime('%H:%M:%S', localtime())}] [DEBUG] Resolved short Hg {hg_hash[:12]} -> {full_hg_hash[:12]}... (from Changesets)")
                
                # Check HgGit_Mappings again with the full hash
                query = '''
                    SELECT [Git_Commit_ID]
                    FROM [dbo].[HgGit_Mappings]
                    WHERE [Hg_Changeset_ID] = ?
                '''
                cursor.execute(query, full_hg_hash)
                row = cursor.fetchone()
                if row:
                    git_hash = row[0]
                    HG_TO_GIT_CACHE[hg_hash] = git_hash
                    HG_TO_GIT_CACHE[full_hg_hash] = git_hash
                    cursor.close()
                    conn.close()
                    if DEBUG_MODE:
                        print(f"[{strftime('%H:%M:%S', localtime())}] [DEBUG] Converted Hg {full_hg_hash[:12]} -> Git {git_hash[:7]} (from HgGit_Mappings with full hash)")
                    return git_hash
        
        cursor.close()
        conn.close()
        
        # Fallback to Lando API with full hash
        print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Hg hash {full_hg_hash[:12]} not in HgGit_Mappings, trying Lando API...")
        api_url = f'https://lando.moz.tools/api/hg2git/firefox/{full_hg_hash}'
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            git_hash = data.get('git_hash')  # API returns 'git_hash', not 'git_commit_id'
            if git_hash:
                HG_TO_GIT_CACHE[hg_hash] = git_hash
                if full_hg_hash != hg_hash:
                    HG_TO_GIT_CACHE[full_hg_hash] = git_hash  # Cache both short and full
                print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Converted Hg {full_hg_hash[:12]} -> Git {git_hash[:7]} (from Lando API)")
                return git_hash
        
        print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] Could not convert Hg hash {full_hg_hash[:12]} to Git, keeping original")
        return hg_hash
        
    except Exception as e:
        print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] Error converting Hg to Git for {hg_hash[:12]}: {e}")
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
            is_hg_in_mappings = cursor.fetchone()[0] > 0
            
            if is_hg_in_mappings:
                cursor.close()
                conn.close()
                return True
            
            # Check if it's in HgGit_Mappings as Git
            cursor.execute(
                "SELECT COUNT(*) FROM [dbo].[HgGit_Mappings] WHERE [Git_Commit_ID] = ?",
                hash_str
            )
            is_git_in_mappings = cursor.fetchone()[0] > 0
            
            if is_git_in_mappings:
                cursor.close()
                conn.close()
                return False
            
            # Not in HgGit_Mappings, fallback to Changesets table
            cursor.execute(
                "SELECT COUNT(*) FROM [dbo].[Changesets] WHERE [Hash_Id] = ?",
                hash_str
            )
            is_hg = cursor.fetchone()[0] > 0
            
            if is_hg:
                cursor.close()
                conn.close()
                return True
            
            # Fallback to GitCommitList table
            cursor.execute(
                "SELECT COUNT(*) FROM [dbo].[GitCommitList] WHERE [Git_Commit_ID] = ?",
                hash_str
            )
            is_git = cursor.fetchone()[0] > 0
            
            cursor.close()
            conn.close()
            
            return not is_git  # If it's Git, return False (not Hg)
        except:
            pass
    
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
            full_hash = row[0]
            GIT_HASH_CACHE[short_hash] = full_hash
            cursor.close()
            conn.close()
            if DEBUG_MODE:
                print(f"[{strftime('%H:%M:%S', localtime())}] [DEBUG] Resolved short Git {short_hash[:7]} -> {full_hash[:12]}... (from HgGit_Mappings)")
            return full_hash
        
        # Fallback: Check GitCommitList table
        query = '''
            SELECT [Git_Commit_ID]
            FROM [dbo].[GitCommitList]
            WHERE [Git_Commit_ID] LIKE ?
        '''
        cursor.execute(query, short_hash + '%')
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            full_hash = row[0]
            GIT_HASH_CACHE[short_hash] = full_hash
            if DEBUG_MODE:
                print(f"[{strftime('%H:%M:%S', localtime())}] [DEBUG] Resolved short Git {short_hash[:7]} -> {full_hash[:12]}... (from GitCommitList)")
            return full_hash
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
    
    updated_count = 0
    
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
                "SELECT [backed_out] FROM [dbo].[GitCommitList] WHERE [Git_Commit_ID] = ?",
                full_hash
            )
            result = cursor.fetchone()
            
            if result is not None:
                if DEBUG_MODE:
                    current_value = result[0]
                    print(f"  [DEBUG]   Current backed_out value: {current_value}")
                
                # Update backed_out flag
                cursor.execute(
                    "UPDATE [dbo].[GitCommitList] SET [backed_out] = 1 WHERE [Git_Commit_ID] = ?",
                    full_hash
                )
                
                if DEBUG_MODE:
                    rows_affected = cursor.rowcount
                    print(f"  [DEBUG]   UPDATE affected {rows_affected} row(s)")
                    
                    # Verify the update
                    cursor.execute(
                        "SELECT [backed_out] FROM [dbo].[GitCommitList] WHERE [Git_Commit_ID] = ?",
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
        
    except Exception as e:
        print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Failed to update backed out commits: {e}")
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
        
        # Insert backout properties (convert Hg to Git if needed, then normalize to full hash)
        full_backed_out_hashes = []  # Collect full hashes for later use
        if commit_details['backed_out_changesets']:
            for backed_out_hash in commit_details['backed_out_changesets']:
                original_hash = backed_out_hash
                
                # Check if this is an Hg hash and convert to Git
                if is_likely_hg_hash(backed_out_hash):
                    backed_out_hash = convert_hg_to_git(backed_out_hash)
                    
                    # Check if conversion failed (returned same hash)
                    if backed_out_hash == original_hash:
                        print(f"  [{strftime('%H:%M:%S', localtime())}] [WARNING] Could not convert Hg hash {original_hash[:12]} to Git, storing original Hg hash")
                        # Store the original Hg hash as-is
                        cursor.execute(INSERT_PROPERTY_QUERY,
                                     hash_id,
                                     'Backout Commit',
                                     original_hash)
                        # Don't add to full_backed_out_hashes since we can't update it in GitCommitList
                        continue
                
                # Resolve short Git hash to full 40-char hash
                full_backed_out_hash = resolve_commit_hash(backed_out_hash)
                full_backed_out_hashes.append(full_backed_out_hash)
                
                cursor.execute(INSERT_PROPERTY_QUERY,
                             hash_id,
                             'Backout Commit',
                             full_backed_out_hash)
            
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
                cursor.execute(INSERT_PROPERTY_QUERY,
                             hash_id,
                             'Backed Out By',
                             backout_hash)
        
        # Insert bug ID properties
        if commit_details['bug_ids']:
            for bug_id in commit_details['bug_ids']:
                cursor.execute(INSERT_PROPERTY_QUERY,
                             hash_id,
                             'Bug ID Mentioned',
                             bug_id)
        
        # Commit all remaining changes (if not already committed)
        if conn:
            conn.commit()
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Failed to update commit {hash_id[:7]}: {e}")
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
        print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Failed to get commits from database: {e}")
        return []


def process_all_commits():
    """
    Process all commits from the database and extract detailed information.
    Uses batch processing with incremental database saves for crash recovery.
    """
    print("=" * 80)
    print(f"[{strftime('%H:%M:%S', localtime())}] GIT COMMIT DETAILS EXTRACTOR - PYDRILLER VERSION")
    print("=" * 80)
    print(f"[{strftime('%H:%M:%S', localtime())}] Repository:  {REPO_PATH}")
    print(f"[{strftime('%H:%M:%S', localtime())}] Batch size:  {BATCH_SIZE}")
    print(f"[{strftime('%H:%M:%S', localtime())}] Start time:  {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    print("=" * 80)
    
    # Count total commits to process
    print(f"\n[{strftime('%H:%M:%S', localtime())}] [STEP 1/3] Counting commits to process...")
    commits = get_commits_from_db()
    
    if not commits:
        print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] No commits found to process")
        return
    
    total_commits = len(commits)
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
        batch_commits = get_commits_from_db()
        
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
            
            # Progress within batch
            if idx % 100 == 0:
                print(f"  [{strftime('%H:%M:%S', localtime())}] [{idx}/{len(batch_commits)}] Extracted details...")
        
        # Normalize backed-out hashes for this batch
        normalized_backout_map = {}
        for backed_out_hash, backout_list in batch_backout_map.items():
            full_hash = resolve_commit_hash(backed_out_hash)
            
            if full_hash not in normalized_backout_map:
                normalized_backout_map[full_hash] = []
            
            for backout_hash in backout_list:
                if backout_hash not in normalized_backout_map[full_hash]:
                    normalized_backout_map[full_hash].append(backout_hash)
        
        # Update database for this batch
        batch_updated = 0
        batch_failed = 0
        
        for hash_id, details in batch_details.items():
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
        
        # Batch complete - data is already saved to database
        print(f"[{strftime('%H:%M:%S', localtime())}] [BATCH {batch_num}] Complete: {batch_updated} commits saved to database ({total_updated}/{total_commits} total)")
        
        # Safety check: if batch size was less than BATCH_SIZE, we're done
        if len(batch_commits) < BATCH_SIZE:
            break
    
    # Final summary
    print(f"\n[{strftime('%H:%M:%S', localtime())}] [STEP 3/3] Final Summary")
    print("=" * 80)
    print("EXTRACTION SUMMARY")
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
    
    # MODE: "all" to process all commits, "single" to test one commit
    MODE = "all"  # "all" or "single"
    
    # Debug mode - set to False to reduce log verbosity (only show progress/timing)
    DEBUG_MODE = False
    
    # For single mode, specify the commit hash
    # Example: a known backout commit for testing
    # TEST_COMMIT = "a929f957f0e89b88bfc47ab9024224b4765443fb" # Test case: Backout changeset with Hg changeset hashes in description (https://hg-edge.mozilla.org/mozilla-central/rev/ce76fa05c90f3f24f8db09950eadd4a8cdec9088)
    # TEST_COMMIT = "becded629c7a6ae23a793035bc7d35eeb267f0a3" # Test case: regular (https://hg-edge.mozilla.org/mozilla-central/rev/0df381e9da8fa9bad1881075bbf25f2e5c0b413a)
    TEST_COMMIT = "55b2aa39f52c75f74351f056ec1c2e76bf5a88d9" # Test case: Backout commit with Git commit hashes in description (https://hg-edge.mozilla.org/mozilla-central/rev/01064dcdd2abd69e53837af1b41d6d6a0c8ac30e)
    # ===================================
    
    if MODE == "all":
        process_all_commits()
    elif MODE == "single":
        process_single_commit(TEST_COMMIT)
    else:
        print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Invalid MODE: {MODE}")
        print(f"[{strftime('%H:%M:%S', localtime())}] Valid options: 'all' or 'single'")
    
    print(f"\n[{strftime('%H:%M:%S', localtime())}] Script completed. Exiting.")
