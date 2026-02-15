import requests
from time import strftime, localtime
from datetime import datetime
import pyodbc
import time
import pydriller
import re

# Connection string
conn_str = 'DRIVER={ODBC Driver 18 for SQL Server};' \
           'SERVER=localhost\\SQLEXPRESS;' \
           'DATABASE=MozillaDataSet2026;' \
           'Connection Timeout=300;' \
           'Login Timeout=300;' \
           'LongAsMax=yes;' \
           'TrustServerCertificate=yes;' \
           'Trusted_Connection=yes;'


def detect_backout_info(commit_message):
    """
    Detect if a commit is a backout commit and extract the backed out commit hash(es).
    
    Mozilla commonly uses patterns like:
    - "Backed out changeset <hash>"
    - "Back out changeset <hash>"
    - "Backout <hash>"
    - "Backed out N changesets" (followed by hashes)
    
    Args:
        commit_message: The commit message to analyze
        
    Returns:
        dict with:
        - is_backout: Boolean indicating if this is a backout commit
        - backed_out_hashes: List of commit hashes that were backed out
        - backout_reason: Extracted reason for the backout (if available)
    """
    message_lower = commit_message.lower()
    
    # Common backout patterns
    backout_patterns = [
        r'back(?:ed)?\s*out\s+(?:changeset|change set|commit|revision)s?\s+([a-f0-9]{7,40})',
        r'backout\s+(?:changeset|change set|commit|revision)?\s*([a-f0-9]{7,40})',
        r'revert\s+(?:changeset|change set|commit|revision)?\s+([a-f0-9]{7,40})',
        r'revert\s+".*".*\s+([a-f0-9]{7,40})',
    ]
    
    is_backout = any([
        'backed out' in message_lower,
        'back out' in message_lower,
        message_lower.startswith('backout'),
        message_lower.startswith('revert'),
    ])
    
    backed_out_hashes = []
    
    if is_backout:
        # Try to extract commit hashes
        for pattern in backout_patterns:
            matches = re.finditer(pattern, commit_message, re.IGNORECASE)
            for match in matches:
                commit_hash = match.group(1)
                if len(commit_hash) >= 7:  # Valid hash length
                    backed_out_hashes.append(commit_hash)
        
        # Remove duplicates
        backed_out_hashes = list(set(backed_out_hashes))
    
    # Try to extract reason (text after "for" or "due to")
    backout_reason = None
    if is_backout:
        reason_patterns = [
            r'(?:for|due to|because of?)\s+(.+?)(?:\.|$)',
            r'(?:causing|causes)\s+(.+?)(?:\.|$)',
        ]
        for pattern in reason_patterns:
            match = re.search(pattern, commit_message, re.IGNORECASE)
            if match:
                backout_reason = match.group(1).strip()
                break
    
    return {
        'is_backout': is_backout,
        'backed_out_hashes': backed_out_hashes,
        'backout_reason': backout_reason
    }



def verify_and_cleanup_commits(repo_url, conn_str, sample_size=1000):
    """
    Verify that commits in the database still exist in the repository.
    Removes orphaned commits caused by rebases, force pushes, etc.
    
    Args:
        repo_url: The URL or local path of the repository
        conn_str: Database connection string
        sample_size: Number of recent commits to verify (None = verify all)
        
    Returns:
        Number of orphaned commits removed
    """
    print("\n" + "=" * 100)
    print("VERIFYING DATABASE INTEGRITY")
    print("=" * 100)
    print("Checking for orphaned commits (from rebases, force pushes, etc.)\n")
    
    try:
        # Get all commit hashes from the repository
        print("Reading all commits from repository...")
        repo_commits = set()
        for commit in pydriller.Repository(repo_url).traverse_commits():
            repo_commits.add(commit.hash)
        print(f"Found {len(repo_commits)} commits in repository\n")
        
        # Get commits from database
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        if sample_size:
            # Only check recent commits
            cursor.execute(
                """
                SELECT TOP (?) Git_Commit_ID 
                FROM GitCommitList 
                ORDER BY Date DESC
                """,
                sample_size
            )
        else:
            # Check all commits
            cursor.execute("SELECT Git_Commit_ID FROM GitCommitList")
        
        db_commits = [row[0] for row in cursor.fetchall()]
        print(f"Checking {len(db_commits)} commits from database...\n")
        
        # Find orphaned commits
        orphaned_commits = []
        for db_commit in db_commits:
            if db_commit not in repo_commits:
                orphaned_commits.append(db_commit)
        
        if orphaned_commits:
            print(f"Found {len(orphaned_commits)} orphaned commits (no longer in repository)")
            print("These commits were likely removed due to rebases, force pushes, or branch deletions")
            print("\nRemoving orphaned commits from database...")
            
            # Remove orphaned commits
            for commit_hash in orphaned_commits:
                # Remove from parent relationships
                cursor.execute(
                    "DELETE FROM GitCommitParents WHERE Git_Commit_ID = ? OR Parent_ID = ?",
                    commit_hash, commit_hash
                )
                # Remove from commit list
                cursor.execute(
                    "DELETE FROM GitCommitList WHERE Git_Commit_ID = ?",
                    commit_hash
                )
            
            conn.commit()
            print(f"Removed {len(orphaned_commits)} orphaned commits")
        else:
            print("No orphaned commits found. Database is clean!")
        
        cursor.close()
        conn.close()
        
        print("=" * 100)
        return len(orphaned_commits)
        
    except Exception as e:
        print(f"Error during verification: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return 0


def get_latest_commit_date(conn_str):
    """
    Get the most recent commit date from the database.
    
    Args:
        conn_str: Database connection string
        
    Returns:
        datetime object of the most recent commit, or None if table is empty
    """
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT MAX(Date) FROM GitCommitList
            """
        )
        result = cursor.fetchone()
        latest_date = result[0] if result and result[0] else None
        
        cursor.close()
        conn.close()
        
        return latest_date
    except Exception as e:
        print(f"Error getting latest commit date: {str(e)}")
        return None


def collect_commits_list(repo_url, max_commits=None, since_date=None, to_date=None):
    """
    Collect basic commit list from a GitHub repository using PyDriller.
    Similar to what you see on GitHub's commits page.
    
    Args:
        repo_url: The URL or local path of the repository
        max_commits: Maximum number of commits to process (None = all commits)
        since_date: Only commits after this date (datetime object or None)
        to_date: Only commits before this date (datetime object or None)
    """
    print(f"Collecting commits from: {repo_url}")
    if since_date:
        print(f"Since date: {since_date.strftime('%Y-%m-%d %H:%M:%S')}")
    if to_date:
        print(f"To date: {to_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Start time: {strftime('%Y-%m-%d %H:%M:%S', localtime())}\n")
    
    commits = []
    commit_count = 0
    
    try:
        # Traverse the repository commits
        # Note: If using a GitHub URL, PyDriller will clone the repo first (can take 10-30+ minutes for large repos)
        # PyDriller traverses commits in REVERSE CHRONOLOGICAL ORDER (newest first)
        print("Initializing repository (this may take a while if cloning from GitHub)...\n")
        
        # Create repository object with optional date filtering
        repo_params = {'path_to_repo': repo_url}
        if since_date:
            repo_params['since'] = since_date
        if to_date:
            repo_params['to'] = to_date
        
        for commit in pydriller.Repository(**repo_params).traverse_commits():
            commit_count += 1
            
            # Detect backout information
            backout_info = detect_backout_info(commit.msg)
            
            # Store basic commit info
            commit_info = {
                'hash': commit.hash,
                'short_hash': commit.hash[:7],
                'author': commit.author.name,
                'author_email': commit.author.email,
                'date': commit.author_date,
                'message': commit.msg.strip(),
                'parents': commit.parents,  # List of parent commit hashes (commits that came BEFORE this one)
                'is_merge': commit.merge,  # True if this commit has multiple parents (merge commit)
                'is_backout': backout_info['is_backout'],  # True if this commit backs out other commits
                'backed_out_hashes': backout_info['backed_out_hashes'],  # List of commit hashes that were backed out
                'backout_reason': backout_info['backout_reason']  # Reason for the backout (if available)
            }
            commits.append(commit_info)
            
            # Print progress every 100 commits
            if commit_count % 100 == 0:
                backout_indicator = " [BACKOUT]" if commit_info['is_backout'] else ""
                print(f"Processed {commit_count} commits... (Latest: {commit_info['short_hash']} - {commit_info['date'].strftime('%Y-%m-%d')}{backout_indicator})")
            
            # Limit for testing purposes
            if max_commits and commit_count >= max_commits:
                print(f"\nReached maximum commits limit ({max_commits})\n")
                break
    
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        print(f"Commits processed before error: {commit_count}\n")
    
    print("=" * 100)
    print(f"Total commits collected: {commit_count}")
    print(f"End time: {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    print("\nCommit Order Information:")
    print("- Commits are traversed in REVERSE CHRONOLOGICAL ORDER (newest to oldest)")
    print("- Each commit's 'parents' field contains the hash(es) of commits that came BEFORE it")
    print("- Normal commits have 1 parent, merge commits have 2+ parents, initial commit has 0 parents")
    print("- Git doesn't store 'children' (commits that came after), but you can build this by mapping parents")
    
    return commits


def save_commits_to_database(commits, conn_str, batch_size=1000):
    """
    Save commits to the database tables GitCommitList and GitCommitParents.
    Uses batch inserts for efficiency.
    
    Args:
        commits: List of commit dictionaries
        conn_str: Database connection string
        batch_size: Number of records to insert per batch
    """
    print("\n" + "=" * 100)
    print("SAVING COMMITS TO DATABASE")
    print("=" * 100)
    print(f"Total commits to save: {len(commits)}")
    print(f"Batch size: {batch_size}")
    print(f"Start time: {strftime('%Y-%m-%d %H:%M:%S', localtime())}\n")
    
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Counters
        commits_inserted = 0
        commits_skipped = 0
        parents_inserted = 0
        parents_skipped = 0
        backouts_inserted = 0
        backouts_skipped = 0
        
        # Process commits in batches
        for i in range(0, len(commits), batch_size):
            batch = commits[i:i + batch_size]
            
            # Insert commits
            for commit in batch:
                try:
                    # Check if commit exists
                    cursor.execute(
                        "SELECT COUNT(*) FROM GitCommitList WHERE Git_Commit_ID = ?",
                        commit['hash']
                    )
                    exists = cursor.fetchone()[0] > 0
                    
                    if not exists:
                        cursor.execute(
                            """
                            INSERT INTO GitCommitList (Git_Commit_ID, Date, Message, is_merge)
                            VALUES (?, ?, ?, ?)
                            """,
                            commit['hash'],
                            commit['date'],
                            commit['message'],
                            1 if commit['is_merge'] else 0
                        )
                        commits_inserted += 1
                    else:
                        commits_skipped += 1
                        
                except Exception as e:
                    print(f"Error inserting commit {commit['hash'][:7]}: {str(e)}")
            
            # Insert parent relationships
            for commit in batch:
                for parent_hash in commit['parents']:
                    try:
                        # Check if relationship exists
                        cursor.execute(
                            "SELECT COUNT(*) FROM GitCommitParents WHERE Git_Commit_ID = ? AND Parent_ID = ?",
                            commit['hash'], parent_hash
                        )
                        exists = cursor.fetchone()[0] > 0
                        
                        if not exists:
                            cursor.execute(
                                """
                                INSERT INTO GitCommitParents (Git_Commit_ID, Parent_ID)
                                VALUES (?, ?)
                                """,
                                commit['hash'],
                                parent_hash
                            )
                            parents_inserted += 1
                        else:
                            parents_skipped += 1
                            
                    except Exception as e:
                        print(f"Error inserting parent relationship {commit['hash'][:7]} -> {parent_hash[:7]}: {str(e)}")
            
            # Commit the batch
            conn.commit()
            print(f"Progress: {min(i + batch_size, len(commits))}/{len(commits)} commits processed "
                  f"(Inserted: {commits_inserted}, Parents: {parents_inserted}, Backouts: {backouts_inserted})")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 100)
        print("DATABASE SAVE COMPLETED")
        print("=" * 100)
        print(f"Commits inserted: {commits_inserted}")
        print(f"Commits skipped (already exist): {commits_skipped}")
        print(f"Parent relationships inserted: {parents_inserted}")
        print(f"Parent relationships skipped (already exist): {parents_skipped}")
        print(f"Backout relationships inserted: {backouts_inserted}")
        print(f"Backout relationships skipped (already exist): {backouts_skipped}")
        print(f"End time: {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
        print("=" * 100)
        
        return {
            'commits_inserted': commits_inserted,
            'commits_skipped': commits_skipped,
            'parents_inserted': parents_inserted,
            'parents_skipped': parents_skipped
        }
        
    except Exception as e:
        print(f"\nDatabase error: {str(e)}")
        print("Rolling back any uncommitted changes...")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise


def build_parent_child_mapping(commits):
    """
    Build a mapping of parent commits to their children.
    
    Args:
        commits: List of commit dictionaries with 'hash' and 'parents' fields
        
    Returns:
        Dictionary mapping commit hash to list of child commit hashes
    """
    children_map = {}
    
    # Initialize all commits in the map
    for commit in commits:
        if commit['hash'] not in children_map:
            children_map[commit['hash']] = []
    
    # Build the parent→child relationships
    for commit in commits:
        for parent_hash in commit['parents']:
            if parent_hash not in children_map:
                children_map[parent_hash] = []
            children_map[parent_hash].append(commit['hash'])
    
    return children_map


def print_commit_relationships(commits, max_display=10):
    """
    Print parent-child relationships for commits.
    
    Args:
        commits: List of commit dictionaries
        max_display: Maximum number of commits to display relationships for
    """
    print("\n" + "=" * 100)
    print("PARENT-CHILD RELATIONSHIP ANALYSIS")
    print("=" * 100)
    
    children_map = build_parent_child_mapping(commits)
    
    print(f"\nShowing relationships for first {min(max_display, len(commits))} commits:\n")
    
    for idx, commit in enumerate(commits[:max_display], 1):
        print(f"Commit #{idx}: {commit['short_hash']} - {commit['message'][:60]}")
        
        # Show parents (commits that came BEFORE)
        if commit['parents']:
            parent_short = [p[:7] for p in commit['parents']]
            print(f"  ← Parents (came BEFORE): {', '.join(parent_short)}")
        else:
            print(f"  ← No parents (initial commit)")
        
        # Show children (commits that came AFTER)
        children = children_map.get(commit['hash'], [])
        if children:
            children_short = [c[:7] for c in children]
            print(f"  → Children (came AFTER): {', '.join(children_short)}")
        else:
            print(f"  → No children in this dataset")
        
        print()
    
    # Summary statistics
    merge_commits = sum(1 for c in commits if c['is_merge'])
    commits_with_multiple_children = sum(1 for children in children_map.values() if len(children) > 1)
    
    print("=" * 100)
    print("STATISTICS:")
    print(f"Total commits analyzed: {len(commits)}")
    print(f"Merge commits (multiple parents): {merge_commits}")
    print(f"Commits with multiple children (branch points): {commits_with_multiple_children}")
    print("=" * 100)


if __name__ == "__main__":
    # Local Firefox repository path
    repo_url = "C:/Users/quocb/quocbui/Studies/research/GithubRepo/firefox"
    
    # SYNC MODE SELECTION
    # Options:
    # 1. "incremental" - Only fetch new commits since the last sync (RECOMMENDED for updates)
    # 2. "full" - Fetch all commits (use for first run or to rebuild)
    # 3. "date_range" - Fetch commits within a specific date range
    
    # FIRST RUN: Use "full" to populate the database
    # SUBSEQUENT RUNS: Use "incremental" to only get new commits
    sync_mode = "full"  # Change to "incremental" after first successful run
    
    # VERIFICATION SETTINGS (for incremental mode)
    # Set to True to verify existing commits and remove orphaned ones (from rebases, force pushes)
    # This handles history rewrites but is slower
    verify_on_incremental = True  # Recommended: True
    verify_sample_size = 1000  # Number of recent commits to verify (None = all commits)
    
    # Optional: Set max_commits for testing (None = all commits)
    max_commits = None
    
    # Optional: For "date_range" mode, set these dates
    custom_since_date = None  # e.g., datetime(2025, 1, 1)
    custom_to_date = None     # e.g., datetime(2026, 1, 1)
    
    print("=" * 100)
    print("GitCommitListScraper - Mozilla Firefox Repository")
    print("=" * 100)
    print(f"Sync Mode: {sync_mode.upper()}")
    print()
    
    since_date = None
    to_date = None
    
    if sync_mode == "incremental":
        # Get the latest commit date from the database
        print("Checking database for latest commit date...")
        latest_date = get_latest_commit_date(conn_str)
        
        if latest_date:
            since_date = latest_date
            print(f"Latest commit in database: {latest_date.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Will fetch commits AFTER this date (incremental sync)\n")
            
            # Optional: Verify and cleanup orphaned commits
            if verify_on_incremental:
                orphaned_count = verify_and_cleanup_commits(repo_url, conn_str, verify_sample_size)
                if orphaned_count > 0:
                    print(f"\nCleaned up {orphaned_count} orphaned commits from history rewrites\n")
        else:
            print("No commits found in database. Switching to FULL sync mode.\n")
            sync_mode = "full"
    
    elif sync_mode == "date_range":
        since_date = custom_since_date
        to_date = custom_to_date
        print(f"Date range mode: {since_date} to {to_date}\n")
    
    else:  # full mode
        print("Full sync mode: Fetching ALL commits from repository\n")
    
    # Collect commits
    print("Starting commit collection...")
    commits = collect_commits_list(repo_url, max_commits, since_date, to_date)
    
    if commits:
        # Save to database
        save_commits_to_database(commits, conn_str, batch_size=1000)
        
        print(f"\n{'=' * 100}")
        print("PROCESS COMPLETED SUCCESSFULLY")
        print(f"{'=' * 100}")
        print(f"Sync mode: {sync_mode}")
        print(f"Total commits collected: {len(commits)}")
        print(f"Data saved to tables: GitCommitList, GitCommitParents")
        print(f"{'=' * 100}")
        print("\nUSAGE TIPS:")
        print("- For future updates: Change sync_mode to 'incremental'")
        print("- Incremental mode only fetches new commits (much faster)")
        print("- With verify_on_incremental=True, it also handles rebases/force pushes")
        print("- Run periodically to keep your database in sync with the repository")
        print(f"{'=' * 100}")
    else:
        print("\n" + "=" * 100)
        print("No new commits found. Database is already up to date!")
        print("=" * 100)
