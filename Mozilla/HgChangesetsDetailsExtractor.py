r"""
Tip: You can use this command before to run in PowerShell to see all information about a specific changesets:
hg log -r {specific Hg Hash ID} --debug --cwd C:\Users\quocb\quocbui\Studies\research\GithubRepo\firefox_mercurial
"""

"""
Changeset Details Extractor for Mozilla Central - LOCAL MERCURIAL VERSION

Extracts detailed information from local Mercurial repository and updates:
1. Changesets table - Updates is_merge, backed_out, is_backout_changeset flags
2. Changeset_Properties table - Stores parent/child relationships and backout info

EXTRACTED INFORMATION:
- Parent changesets (merge commits have 2 parents, identified using p1node/p2node)
- Child changesets (using hg children() revset query)
- Merge status (is_merge flag when 2+ parents exist)
- Backout relationships (backed_out, is_backout_changeset flags)
- Backout changeset links (parsed from commit descriptions + metadata)

BACKOUT DETECTION IMPROVEMENTS:
- Checks Mercurial extras/metadata fields for backout information
- Enhanced regex patterns to catch various backout message formats
- Handles cases where changeset hash is not in description
- Supports both short (12-char) and full (40-char) hash matching
- Optional Mercurial search for higher accuracy (USE_HG_SEARCH_FOR_BACKOUTS flag)

BACKOUT PATTERNS DETECTED:
- "Backed out changeset abc123" 
- "Back out changeset abc123"
- "Backout abc123"
- "Backing out abc123"
- "Reverted changeset abc123"
- And more variations (case-insensitive)

REQUIREMENTS:
- Local clone of mozilla-central repository
- Mercurial installed  
- Changesets table already populated with basic info
"""

import subprocess
from unittest import result
import pyodbc
from time import strftime, localtime
import re
import sys
import requests
from time import sleep

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

# Batch size for database commits (commit after this many changesets)
BATCH_SIZE = 100

# Progress update frequency (print progress every N changesets)
PROGRESS_FREQUENCY = 10

# Use Mercurial search for more accurate backout detection (slower)
# Set to False for faster processing, relies on commit message parsing only
USE_HG_SEARCH_FOR_BACKOUTS = False
# ====================================

# Cache for resolving revision numbers to hashes
REV_TO_HASH_CACHE = {}
HASH_TO_REV_CACHE = {}

# Cache for Git/Hg hash mappings
GIT_TO_HG_CACHE = {}
HG_TO_GIT_CACHE = {}


def resolve_rev_to_hash(rev_number):
    """
    Resolve a Mercurial revision number to its full hash.

    Args:
        rev_number: Revision number as string or int

    Returns:
        str or None: Full 40-char hash if found
    """
    try:
        rev_key = str(rev_number).strip()
        if not rev_key:
            return None
        if rev_key in REV_TO_HASH_CACHE:
            return REV_TO_HASH_CACHE[rev_key]

        cmd = ['hg', 'log', '-r', rev_key, '--template', '{node}', '--cwd', REPO_PATH]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)
        node = result.stdout.strip()
        if node:
            REV_TO_HASH_CACHE[rev_key] = node
            return node
        return None
    except Exception:
        return None


def resolve_hash_to_rev(hash_id):
    """
    Resolve a Mercurial hash to its revision number.

    Args:
        hash_id: Full changeset hash

    Returns:
        str or None: Revision number as string if found
    """
    try:
        hash_key = hash_id.strip()
        if not hash_key:
            return None
        if hash_key in HASH_TO_REV_CACHE:
            return HASH_TO_REV_CACHE[hash_key]

        cmd = ['hg', 'log', '-r', hash_key, '--template', '{rev}', '--cwd', REPO_PATH]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)
        rev = result.stdout.strip()
        if rev:
            HASH_TO_REV_CACHE[hash_key] = rev
            return rev
        return None
    except Exception:
        return None


def resolve_git_to_hg(git_commit_id):
    """
    Resolve a Git commit ID to its Mercurial changeset hash.
    
    Args:
        git_commit_id: Git commit hash (40-char)
    
    Returns:
        str or None: Mercurial changeset hash if found
    """
    try:
        git_hash = git_commit_id.strip()
        if not git_hash or len(git_hash) < 40:
            return None
        
        print(f"[DEBUG] resolve_git_to_hg called for: {git_hash[:12]}...")
        
        # Check cache first
        if git_hash in GIT_TO_HG_CACHE:
            print(f"[DEBUG] Found in cache: {GIT_TO_HG_CACHE[git_hash][:12]}")
            return GIT_TO_HG_CACHE[git_hash]
        
        # Query database
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        
        print(f"[DEBUG] Querying database for Git hash: {git_hash[:12]}...")
        query = '''
            SELECT [Hg_Changeset_ID]
            FROM [dbo].[HgGit_Mappings]
            WHERE [Git_Commit_ID] = ?
        '''
        cursor.execute(query, git_hash)
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            hg_hash = row[0]
            print(f"[DEBUG] Found in database: {hg_hash[:12]}")
            GIT_TO_HG_CACHE[git_hash] = hg_hash
            HG_TO_GIT_CACHE[hg_hash] = git_hash
            return hg_hash
        
        print(f"[DEBUG] Not in database, calling Lando API...")
        # Fallback to Lando API
        try:
            url = f'https://lando.moz.tools/api/git2hg/firefox/{git_hash}'
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                hg_hash = data.get('hg_hash')  # API returns 'hg_hash', not 'hg_changeset_id'
                if hg_hash:
                    GIT_TO_HG_CACHE[git_hash] = hg_hash
                    HG_TO_GIT_CACHE[hg_hash] = git_hash
                    print(f"[Lando API] Git {git_hash[:12]} -> Hg {hg_hash[:12]}")
                    sleep(0.1)  # Rate limiting
                    return hg_hash
        except Exception as e:
            print(f"\n[WARNING] Lando API failed for {git_hash[:12]}: {e}")
        
        return None
        
    except Exception as e:
        print(f"\n[WARNING] Error resolving Git to Hg for {git_commit_id[:12]}: {e}")
        return None

def identify_and_convert_hash(hash_id):
    """
    Identify if a hash is Git or Hg, and convert to Hg if needed.
    
    Args:
        hash_id: Either a Git commit ID or Hg changeset hash
    
    Returns:
        tuple: (hg_hash, is_git_hash)
    """
    if not hash_id or len(hash_id) < 40:
        return (hash_id, False)
    
    print(f"[DEBUG] identify_and_convert_hash called for: {hash_id[:12]}...")
    
    try:
        # Query database to check both columns
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        
        query = '''
            SELECT [Hg_Changeset_ID], [Git_Commit_ID]
            FROM [dbo].[HgGit_Mappings]
            WHERE [Hg_Changeset_ID] = ? OR [Git_Commit_ID] = ?
        '''
        cursor.execute(query, hash_id, hash_id)
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if row:
            hg_hash, git_hash = row[0], row[1]
            
            print(f"[DEBUG] Found in HgGit_Mappings: hg={hg_hash[:12]}, git={git_hash[:12]}")
            
            # Cache both directions
            GIT_TO_HG_CACHE[git_hash] = hg_hash
            HG_TO_GIT_CACHE[hg_hash] = git_hash
            
            # If hash matches Git column, it's a Git hash
            if hash_id == git_hash:
                print(f"[DEBUG] Hash is Git, returning Hg: {hg_hash[:12]}")
                return (hg_hash, True)
            else:
                print(f"[DEBUG] Hash is Hg, returning as-is: {hg_hash[:12]}")
                return (hg_hash, False)
        
        print(f"[DEBUG] Not in HgGit_Mappings, trying API conversion...")
        # Not in database - try to determine type and resolve
        # If it starts with typical Git patterns or API succeeds, it's Git
        hg_from_git = resolve_git_to_hg(hash_id)
        if hg_from_git:
            print(f"[DEBUG] API conversion succeeded: {hash_id[:12]} -> {hg_from_git[:12]}")
            return (hg_from_git, True)
        
        print(f"[DEBUG] No conversion found, assuming Hg hash: {hash_id[:12]}")
        # Assume it's Hg if no conversion found
        return (hash_id, False)
        
    except Exception:
        return (hash_id, False)

# SQL Queries
UPDATE_CHANGESET_QUERY = '''
    UPDATE [dbo].[Changesets]
    SET [is_merge] = ?,
        [backed_out] = ?,
        [is_backout_changeset] = ?,
        [Description] = ?
    WHERE [Hash_Id] = ?
'''

INSERT_PROPERTY_QUERY = '''
    INSERT INTO [dbo].[Changeset_Properties]
        ([Hg_Changeset_ID], [Name], [Value])
    VALUES (?, ?, ?)
'''

DELETE_PROPERTIES_QUERY = '''
    DELETE FROM [dbo].[Changeset_Properties]
    WHERE [Hg_Changeset_ID] = ?
'''

GET_ALL_CHANGESETS_QUERY = '''
    SELECT [Hash_Id]
    FROM [dbo].[Changesets]
    WHERE [Description] IS NULL -- This condition helps to only process changesets that haven't been updated yet
    ORDER BY [Hash_Id]
'''

GET_CHANGESETS_BATCH_QUERY = '''
    SELECT [Hash_Id]
    FROM [dbo].[Changesets]
    WHERE [Hash_Id] > ?
    ORDER BY [Hash_Id]
    OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY
'''


def get_changeset_details(hash_id):
    """
    Extract detailed information about a changeset from local Mercurial repository.
    Uses stable template parts for reliable parsing and checks multiple backout indicators.
    
    Args:
        hash_id: Changeset hash
    
    Returns:
        dict: Detailed changeset info including parents, children, backout info
    """
    try:
        # Get basic info: node, parents, extras, description
        # Use unusual delimiter to avoid issues with descriptions containing |||
        template_parts = "{node}<<<DELIM>>>{p1node}<<<DELIM>>>{p2node}<<<DELIM>>>{extras}<<<DELIM>>>{desc}"
        cmd = ['hg', 'log', '-r', hash_id, '--template', template_parts, '--cwd', REPO_PATH]
        print(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)
        print(f"Raw output: {repr(result.stdout)}")  # Add this line
        print(f"Split parts: {result.stdout.strip().split('<<<DELIM>>>')}")  # See the split result
        
        if not result.stdout.strip():
            return None
        
        parts = result.stdout.strip().split('<<<DELIM>>>')
        if len(parts) < 5:
            return None
        
        node = parts[0].strip()
        p1_node = parts[1].strip()
        p2_node = parts[2].strip()
        extras = parts[3].strip()
        description = parts[4].strip() if len(parts) > 4 else ''
        
        # Parse parents
        parents = []
        if p1_node and p1_node != '0' * 40:  # Not null parent
            parents.append(p1_node)
        if p2_node and p2_node != '0' * 40:  # Not null parent (merge)
            parents.append(p2_node)
        
        # Get children using descendants query
        children = []
        try:
            child_cmd = ['hg', 'log', '-r', f'children({hash_id})',
                        '--template', '{node}\\n', '--cwd', REPO_PATH]
            child_result = subprocess.run(child_cmd, capture_output=True, text=True, timeout=30, check=True)
            if child_result.stdout.strip():
                children = [c.strip() for c in child_result.stdout.strip().split('\n') if c.strip()]
        except Exception:
            pass  # Children not critical
        
        # Determine if this is a merge commit (has more than 1 parent)
        is_merge = len(parents) > 1
        
        # Check for backout metadata in extras
        is_backout_from_extras = False
        backed_out_from_extras = []
        
        if extras:
            # Check for common backout-related metadata fields
            # Mozilla might use: backout=<hash> or backed_out=<hash>
            extra_pairs = extras.split('\0')  # Extras are null-separated
            for pair in extra_pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    if key.lower() in ['backout', 'backed_out', 'backouts']:
                        is_backout_from_extras = True
                        # Value might be a hash
                        if re.match(r'^[0-9a-f]{12,40}$', value):
                            backed_out_from_extras.append(value)
        
        # Parse description for backout patterns (enhanced regex)
        backed_out_hashes = []
        backed_out_revs = []
        is_backout_from_desc = False
        
        # Enhanced backout patterns - more comprehensive
        backout_patterns = [
            # Standard patterns with "changeset"
            r'[Bb]acked?\s+out\s+changeset\s+([0-9a-f]{12,40})',
            r'[Bb]ack(?:ing)?\s+out\s+changeset\s+([0-9a-f]{12,40})',
            r'[Bb]ackout\s+changeset\s+([0-9a-f]{12,40})',
            
            # Patterns without "changeset" but with clear context
            r'[Bb]acked?\s+out\s+(?:rev\s+)?([0-9a-f]{12,40})',
            r'[Bb]ackout(?:\s+of)?\s+([0-9a-f]{12,40})',
            r'[Bb]acking\s+out\s+([0-9a-f]{12,40})',
            
            # Multiple changesets
            r'[Bb]acked?\s+out\s+\d+\s+changesets.*?([0-9a-f]{12,40})',
            
            # Rev number style
            r'[Bb]ackout\s+rev\s+([0-9a-f]{12,40})',
            
            # Git-style revert patterns (GitHub workflow) - flexible with/without "commit"
            r'[Rr]everts?\s+commit\s+version\s+([0-9a-f]{40})',
            r'[Rr]everts?\s+(?:commit\s+)?([0-9a-f]{40})',
            r'[Tt]his\s+reverts\s+(?:commit\s+)?([0-9a-f]{40})',
            r'[Rr]evert(?:ed|ing)?\s+([0-9a-f]{40})',
        ]

        # Patterns for revision numbers (not hashes)
        backout_rev_patterns = [
            r'[Bb]acked?\s+out\s+changeset\s+(\d+)',
            r'[Bb]ack(?:ing)?\s+out\s+changeset\s+(\d+)',
            r'[Bb]ackout\s+changeset\s+(\d+)',
            r'[Bb]acked?\s+out\s+rev\s+(\d+)',
            r'[Bb]ackout\s+rev\s+(\d+)',
        ]
        
        # Also check for phrases that indicate backout intent
        backout_indicators = [
            r'[Bb]acked?\s+out',
            r'[Bb]ack(?:ing)?\s+out',
            r'[Bb]ackout',
            r'[Rr]evert(?:ing|ed)?',
        ]
        
        # Look for backout indicators
        for indicator in backout_indicators:
            if re.search(indicator, description):
                is_backout_from_desc = True
                break
        
        # Extract hashes using patterns
        for pattern in backout_patterns:
            matches = re.findall(pattern, description)
            if matches:
                print(f"[DEBUG] Pattern matched: {pattern} -> {matches}")
                backed_out_hashes.extend(matches)

        # Extract revision numbers and resolve to hashes
        for pattern in backout_rev_patterns:
            matches = re.findall(pattern, description)
            if matches:
                backed_out_revs.extend(matches)
        
        # Resolve revision numbers to hashes
        resolved_from_revs = []
        for rev in backed_out_revs:
            resolved = resolve_rev_to_hash(rev)
            if resolved:
                resolved_from_revs.append(resolved)

        # Combine results from extras and description
        is_backout = is_backout_from_extras or is_backout_from_desc
        all_backed_out = backed_out_from_extras + backed_out_hashes + resolved_from_revs
        
        print(f"[DEBUG] is_backout: {is_backout}, all_backed_out raw: {all_backed_out}")
        
        # Remove duplicates and invalid hashes
        # Normalize all hashes to full 40-char format to avoid redundancy
        unique_backed_out = []
        seen = set()
        for h in all_backed_out:
            if h and len(h) >= 12:
                # If short hash (12-20 chars), try to resolve to full hash
                if len(h) < 40:
                    full_hash = resolve_rev_to_hash(h) if h.isdigit() else None
                    # If not a rev number, try as short hash by querying repo
                    if not full_hash and len(h) >= 12:
                        try:
                            cmd = ['hg', 'log', '-r', h, '--template', '{node}', '--cwd', REPO_PATH]
                            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=True)
                            full_hash = result.stdout.strip()
                        except Exception:
                            full_hash = None
                    h = full_hash if full_hash else h
                
                # Now that we have a full 40-char hash, validate if it's Git or Hg
                if h and len(h) == 40:
                    print(f"[DEBUG] Validating hash: {h[:12]}...")
                    hg_hash, is_git = identify_and_convert_hash(h)
                    if is_git and hg_hash:
                        print(f"[Git->Hg] {h[:12]} -> {hg_hash[:12]}")
                        h = hg_hash
                    else:
                        print(f"[DEBUG] Hash is Hg (or already normalized): {h[:12]}")
                        h = hg_hash if hg_hash else h
                
                # Add only if not already seen (avoid duplicates)
                if h and h not in seen:
                    unique_backed_out.append(h)
                    seen.add(h)
        
        print(f"[DEBUG] Final unique_backed_out: {unique_backed_out}")
        
        # Extract bug IDs from description by regex
        bug_ids = []
        bug_id_pattern = r'[Bb]ug\s+([0-9]+)'
        bug_matches = re.findall(bug_id_pattern, description)
        if bug_matches:
            bug_ids = list(set(bug_matches))  # Remove duplicates
            print(f"[DEBUG] Found bug IDs: {bug_ids}")
        
        return {
            'hash_id': node,
            'parents': parents,
            'children': children,
            'is_merge': is_merge,
            'is_backout_changeset': is_backout,
            'backed_out_changesets': unique_backed_out,
            'description': description,
            'extras': extras,
            'bug_ids': bug_ids
        }
        
    except subprocess.TimeoutExpired:
        print(f"[WARNING] Timeout getting details for {hash_id}")
        return None
    except subprocess.CalledProcessError as e:
        print(f"[WARNING] Error getting details for {hash_id}: {e.stderr}")
        return None
    except Exception as e:
        print(f"[WARNING] Unexpected error for {hash_id}: {e}")
        import traceback
        traceback.print_exc()
        return None


def find_backed_out_by_changeset(hash_id, backout_changesets_map, use_hg_search=False):
    """
    Find if this changeset was backed out by another changeset.
    Uses both the backout map and optionally direct Mercurial search.
    
    Args:
        hash_id: The changeset to check (full 40-char hash)
        backout_changesets_map: Dict mapping backed_out_hash -> list of backout_hashes
        use_hg_search: If True, also search Mercurial history (slower but more accurate)
    
    Returns:
        list: List of changeset hashes that backed out this changeset
    """
    backed_out_by = []
    short_hash = hash_id[:12]
    rev_number = resolve_hash_to_rev(hash_id)
    
    # Method 1: Check the backout map we built from descriptions
    # Need to handle both short and full hashes
    for backed_out_hash, backout_hash_list in backout_changesets_map.items():
        backed_out_short = backed_out_hash[:12]
        
        # Match if either hash matches (full or short)
        if (hash_id == backed_out_hash or 
            short_hash == backed_out_short or
            hash_id[:20] == backed_out_hash[:20]):  # Match first 20 chars for safety
            backed_out_by.extend(backout_hash_list)
    
    # Method 2: Search Mercurial history (optional, slower)
    # Only use this for verification or specific changesets
    if use_hg_search:
        try:
            # Get all commits and check if they mention backing out this hash
            search_cmd = [
                'hg', 'log',
                '-r', 'all()',
                '--template', '{node}<<<DELIM>>>{desc}\n',
                '--cwd', REPO_PATH
            ]
            
            result = subprocess.run(search_cmd, capture_output=True, text=True,
                                   timeout=120, stderr=subprocess.DEVNULL)

            if result.returncode == 0 and result.stdout.strip():
                # Regex to detect backout keywords
                backout_regex = re.compile(r'(backed?\s+out|backout|back\s+out|revert)', re.IGNORECASE)
                
                for line in result.stdout.split('\n'):
                    if '<<<DELIM>>>' in line:
                        node, desc = line.split('<<<DELIM>>>', 1)
                        if node == hash_id:
                            continue
                        
                        # Check if description has backout keyword AND mentions this hash
                        if backout_regex.search(desc) and (short_hash in desc or hash_id in desc):
                            if node not in backed_out_by:
                                backed_out_by.append(node)
        except Exception:
            # Silently fail - map is good enough
            pass
    
    # Remove duplicates
    return list(set(backed_out_by))


def update_backed_out_changesets_in_db(backout_changeset_hash, backed_out_hashes):
    """
    Update the changesets that were backed out by marking them as backed_out=1
    and adding 'Backed Out By' properties.
    
    Args:
        backout_changeset_hash: The hash of the backout changeset
        backed_out_hashes: List of hashes that were backed out
    
    Returns:
        int: Number of changesets successfully updated
    """
    if not backed_out_hashes:
        return 0
    
    updated_count = 0
    
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        
        for backed_out_hash in backed_out_hashes:
            try:
                # Update the backed_out flag
                update_query = '''
                    UPDATE [dbo].[Changesets]
                    SET [backed_out] = 1
                    WHERE [Hash_Id] = ?
                '''
                cursor.execute(update_query, backed_out_hash)
                
                # Add 'Backed Out By' property (check if it already exists first)
                check_query = '''
                    SELECT COUNT(*)
                    FROM [dbo].[Changeset_Properties]
                    WHERE [Hg_Changeset_ID] = ? 
                      AND [Name] = 'Backed Out By'
                      AND [Value] = ?
                '''
                cursor.execute(check_query, backed_out_hash, backout_changeset_hash)
                exists = cursor.fetchone()[0] > 0
                
                if not exists:
                    cursor.execute(INSERT_PROPERTY_QUERY, backed_out_hash, 'Backed Out By', backout_changeset_hash)
                
                updated_count += 1
                
            except Exception as e:
                print(f"\n[WARNING] Failed to update backed-out changeset {backed_out_hash}: {e}")
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return updated_count
        
    except Exception as e:
        print(f"\n[ERROR] Database error in update_backed_out_changesets_in_db: {e}")
        try:
            conn.rollback()
            cursor.close()
            conn.close()
        except:
            pass
        return updated_count


def update_changeset_in_db(changeset_details, backed_out_by_list):
    """
    Update a single changeset and its properties in the database.
    
    Args:
        changeset_details: Dict with changeset details
        backed_out_by_list: List of changesets that backed out this one
    
    Returns:
        bool: Success status
    """
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        
        hash_id = changeset_details['hash_id']
        is_merge = changeset_details['is_merge']
        is_backout_changeset = changeset_details['is_backout_changeset']
        backed_out = len(backed_out_by_list) > 0
        description = changeset_details.get('description', '')
        
        # Update Changesets table
        cursor.execute(
            UPDATE_CHANGESET_QUERY,
            is_merge,
            backed_out,
            is_backout_changeset,
            description,
            hash_id
        )
        
        # Delete existing properties for this changeset (to avoid duplicates)
        cursor.execute(DELETE_PROPERTIES_QUERY, hash_id)
        
        # Insert parent changesets
        for parent_hash in changeset_details['parents']:
            cursor.execute(INSERT_PROPERTY_QUERY, hash_id, 'Parent Changeset', parent_hash)
        
        # Insert child changesets
        for child_hash in changeset_details['children']:
            cursor.execute(INSERT_PROPERTY_QUERY, hash_id, 'Child Changeset', child_hash)
        
        # Insert backed out changesets (if this is a backout changeset)
        for backed_out_hash in changeset_details['backed_out_changesets']:
            cursor.execute(INSERT_PROPERTY_QUERY, hash_id, 'Backout Changeset', backed_out_hash)
        
        # Insert backed out by changesets (if this was backed out)
        for backed_out_by_hash in backed_out_by_list:
            cursor.execute(INSERT_PROPERTY_QUERY, hash_id, 'Backed Out By', backed_out_by_hash)
        
        # Insert bug IDs mentioned in the description
        bug_ids = changeset_details.get('bug_ids', [])
        for bug_id in bug_ids:
            cursor.execute(INSERT_PROPERTY_QUERY, hash_id, 'Bug ID Mentioned', bug_id)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to update {hash_id}: {e}")
        try:
            conn.rollback()
            cursor.close()
            conn.close()
        except:
            pass
        return False


def get_changesets_from_db():
    """
    Get all changeset hashes from the database.
    
    Returns:
        list: List of changeset hashes
    """
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        
        cursor.execute(GET_ALL_CHANGESETS_QUERY)
        changesets = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return changesets
        
    except Exception as e:
        print(f"[ERROR] Failed to get changesets from database: {e}")
        return []


def process_all_changesets():
    """
    Process all changesets from the database and extract detailed information.
    Uses incremental batch processing to handle large datasets (800K+ changesets).
    """
    print("=" * 80)
    print("CHANGESET DETAILS EXTRACTOR - LOCAL MERCURIAL VERSION (BATCH MODE)")
    print("=" * 80)
    print(f"Repository:       {REPO_PATH}")
    print(f"Batch size:       {BATCH_SIZE} (commits to DB after each batch)")
    print(f"Progress updates: Every {PROGRESS_FREQUENCY} changesets")
    print(f"Start time:       {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    print("=" * 80)
    
    # Get all changesets from database that haven't been processed
    print("\n[LOADING] Getting unprocessed changesets from database...")
    changesets = get_changesets_from_db()
    
    if not changesets:
        print("[INFO] No unprocessed changesets found (all have Description populated)")
        return
    
    print(f"[INFO] Found {len(changesets):,} changesets to process")
    print(f"[INFO] Estimated time: {len(changesets) * 3 / 3600:.1f} - {len(changesets) * 5 / 3600:.1f} hours")
    print(f"[INFO] Processing in batches of {BATCH_SIZE}, committing to DB incrementally\n")
    
    # Batch tracking
    backout_map_global = {}  # Track backout relationships across all batches
    
    # Statistics
    total_processed = 0
    total_failed = 0
    total_updated = 0
    total_backed_out_updates = 0
    batch_num = 0
    
    # Process in batches
    for batch_start in range(0, len(changesets), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(changesets))
        batch = changesets[batch_start:batch_end]
        batch_num += 1
        
        print(f"\n{'=' * 80}")
        print(f"[BATCH {batch_num}] Processing {batch_start + 1}-{batch_end} of {len(changesets):,}")
        print(f"[{strftime('%H:%M:%S', localtime())}] Started batch {batch_num}")
        print(f"{'=' * 80}")
        
        batch_details = {}
        batch_backout_map = {}
        batch_processed = 0
        batch_failed = 0
        
        # Extract details for this batch
        for idx, hash_id in enumerate(batch, 1):
            global_idx = batch_start + idx
            
            if idx % PROGRESS_FREQUENCY == 0 or idx == 1:
                print(f"  [{strftime('%H:%M:%S', localtime())}] Extracting {idx}/{len(batch)} "
                      f"(Global: {global_idx:,}/{len(changesets):,}) - "
                      f"OK: {batch_processed}, Failed: {batch_failed}",
                      end='\r', flush=True)
            
            details = get_changeset_details(hash_id)
            
            if details:
                batch_details[hash_id] = details
                batch_processed += 1
                
                # Build backout map for this batch
                if details['is_backout_changeset']:
                    for backed_out_hash in details['backed_out_changesets']:
                        if backed_out_hash not in batch_backout_map:
                            batch_backout_map[backed_out_hash] = []
                        batch_backout_map[backed_out_hash].append(hash_id)
                        
                        # Also add to global map
                        if backed_out_hash not in backout_map_global:
                            backout_map_global[backed_out_hash] = []
                        backout_map_global[backed_out_hash].append(hash_id)
            else:
                batch_failed += 1
        
        print()  # New line after progress
        
        # Update database for this batch
        if batch_details:
            print(f"  [DB UPDATE] Committing {len(batch_details)} changesets to database...")
            
            batch_updated = 0
            batch_update_failed = 0
            batch_backed_out_updates = 0
            
            for hash_id, details in batch_details.items():
                # Find if this changeset was backed out (check global map)
                backed_out_by = find_backed_out_by_changeset(hash_id, backout_map_global, False)
                
                # Update database
                success = update_changeset_in_db(details, backed_out_by)
                
                if success:
                    batch_updated += 1
                    
                    # If this is a backout changeset, update the backed out changesets
                    if details['is_backout_changeset'] and details['backed_out_changesets']:
                        count = update_backed_out_changesets_in_db(hash_id, details['backed_out_changesets'])
                        batch_backed_out_updates += count
                else:
                    batch_update_failed += 1
            
            print(f"  [BATCH {batch_num} COMPLETE] Updated: {batch_updated}, "
                  f"Failed: {batch_update_failed}, Backout links: {batch_backed_out_updates}")
            
            # Update totals
            total_processed += batch_processed
            total_failed += batch_failed
            total_updated += batch_updated
            total_backed_out_updates += batch_backed_out_updates
            
            # Progress summary
            pct_complete = (batch_end / len(changesets)) * 100
            print(f"  [OVERALL PROGRESS] {batch_end:,}/{len(changesets):,} ({pct_complete:.1f}%) - "
                  f"Processed: {total_processed:,}, Updated: {total_updated:,}")
        
        # Clear batch details from memory
        batch_details.clear()
    
    # Final summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)
    print(f"Total changesets:              {len(changesets):,}")
    print(f"Details extracted:             {total_processed:,}")
    print(f"Extraction failed:             {total_failed:,}")
    print(f"Database updates successful:   {total_updated:,}")
    print(f"Backout relationships found:   {len(backout_map_global):,}")
    print(f"Backed-out changesets updated: {total_backed_out_updates:,}")
    print(f"Batches processed:             {batch_num}")
    print(f"End time:                      {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    print("=" * 80)
    print("\n[SUCCESS] All batches committed to database.")
    print("[INFO] You can re-run this script anytime - it will skip already processed changesets.")
    print("=" * 80)


def process_single_changeset(hash_id):
    """
    Process a single changeset for testing purposes.
    
    Args:
        hash_id: Changeset hash to process
    """
    print(f"Processing single changeset: {hash_id}")
    print("=" * 80)
    
    details = get_changeset_details(hash_id)
    
    if not details:
        print("[ERROR] Failed to get changeset details")
        return
    
    print(f"Hash ID:              {details['hash_id']}")
    print(f"Is Merge:             {details['is_merge']}")
    print(f"Is Backout:           {details['is_backout_changeset']}")
    print(f"Parents:              {len(details['parents'])}")
    for parent in details['parents']:
        print(f"  - {parent}")
    print(f"Children:             {len(details['children'])}")
    for child in details['children']:
        print(f"  - {child}")
    print(f"Backed Out Changes:   {len(details['backed_out_changesets'])}")
    for backed_out in details['backed_out_changesets']:
        print(f"  - {backed_out}")
    
    if details.get('extras'):
        print(f"\nExtras (metadata):    {details['extras'][:200]}")
    
    print(f"\nDescription: {details['description'][:200]}")
    print("=" * 80)
    
    # Build a small backout map for testing
    backout_map = {}
    if details['is_backout_changeset']:
        for backed_out_hash in details['backed_out_changesets']:
            backout_map[backed_out_hash] = [hash_id]
    
    # Check if this was backed out (using HG search for testing)
    backed_out_by = find_backed_out_by_changeset(hash_id, backout_map, use_hg_search=True)
    
    if backed_out_by:
        print(f"\nBacked Out By:        {len(backed_out_by)} changesets")
        for backout_hash in backed_out_by:
            print(f"  - {backout_hash}")
    
    # Update database
    print("\nUpdating database...")
    success = update_changeset_in_db(details, backed_out_by)
    
    if success:
        print("[SUCCESS] Database updated")
        
        # If this is a backout changeset, also update the changesets it backed out
        if details['is_backout_changeset'] and details['backed_out_changesets']:
            print(f"\nUpdating {len(details['backed_out_changesets'])} backed-out changesets...")
            count = update_backed_out_changesets_in_db(hash_id, details['backed_out_changesets'])
            print(f"[SUCCESS] Updated {count} backed-out changesets")
    else:
        print("[ERROR] Database update failed")


if __name__ == "__main__":
    # ========== CONFIGURATION ==========
    
    # MODE: "all" to process all changesets, "single" to test one changeset
    MODE = "all"  # "all" or "single"
    
    # For single mode, specify the changeset hash
    # Example: changeset that was backed out (from web interface example)
    # TEST_CHANGESET = "ce76fa05c90f3f24f8db09950eadd4a8cdec9088" # Test case: Backout changeset with Hg changeset hashes in description
    # TEST_CHANGESET = "002359e80ee7f1e64555104fb9cb53b13cb10951" # Test case: Backout commit with Git commit hashes in description
    TEST_CHANGESET = ""

    # ===================================
    
    if MODE == "all":
        process_all_changesets()
    elif MODE == "single":
        process_single_changeset(TEST_CHANGESET)
    else:
        print(f"[ERROR] Invalid MODE: {MODE}")
        print("Valid modes: 'all' or 'single'")
        sys.exit(1)
    
    print("\nScript completed. Exiting.")
