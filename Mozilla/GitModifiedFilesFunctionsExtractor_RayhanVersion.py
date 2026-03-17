from pydriller import Repository
import os


# ==============================
# Editable run configuration
# ==============================
REPO_PATH = r"C:\Users\quocb\quocbui\Studies\research\GithubRepo\firefox"

# If set to a commit hash, script runs SINGLE mode.
# If None, script runs LIST mode using COMMIT_HASH_LIST below.
SINGLE_COMMIT_ID = '503e5b33874c8ede68f9a3d910c9381a502fb032'

# Used only when SINGLE_COMMIT_ID is None
# Add one or more commit hashes here to run list mode.
COMMIT_HASH_LIST = [
    # "dab7697ab91c048268b91bfa3616a0ea194ae983",
]


#repo_path = os.path.join("C:", "Users", "rohan", "mozilla-central")  # Change this path accordingly

def print_results(results):
    """Print extracted commit/file/function data to console."""
    if not results:
        print("No commit data extracted.")
        return

    total_files = 0
    total_functions = 0

    print("=" * 80)
    print("Modified Files + Functions (Console Output)")
    print("=" * 80)

    for commit, files in results.items():
        print(f"\nCommit: {commit}")

        if not files:
            print("  No modified files found.")
            continue

        for file_path, functions in files.items():
            total_files += 1
            print(f"  File: {file_path}")

            if not functions:
                print("    Functions: (none detected)")
                continue

            total_functions += len(functions)
            print(f"    Functions ({len(functions)}):")
            for function in functions:
                print(f"      - {function}")

    print("\n" + "=" * 80)
    print(f"Total commits:   {len(results)}")
    print(f"Total files:     {total_files}")
    print(f"Total functions: {total_functions}")
    print("=" * 80)

def get_modified_files_and_functions(repo_path, commit_hashes):
    """Extract modified files and functions for given commit hashes."""
    modified_data = {}

    if not os.path.exists(repo_path):
        print(f"Error: Repository path '{repo_path}' does not exist!")
        return modified_data

    print(f"Analyzing repository: {repo_path}")
    
    for commit in Repository(repo_path, only_commits=commit_hashes).traverse_commits():
        print(f"Processing commit: {commit.hash}")
        modified_data[commit.hash] = {}

        for modified_file in commit.modified_files:
            file_path = modified_file.new_path or modified_file.old_path
            if file_path:
                print(f"Commit: {commit.hash[:7]} | File: {file_path}...", flush=True)
                modified_data[commit.hash][file_path] = [
                    method.name for method in modified_file.changed_methods
                ]

    return modified_data


if __name__ == "__main__":
    repo_path = REPO_PATH

    if SINGLE_COMMIT_ID:
        commit_hashes = [SINGLE_COMMIT_ID]
        print("Running in SINGLE mode")
        print(f"Commit hash: {SINGLE_COMMIT_ID}")
    else:
        commit_hashes = [h for h in COMMIT_HASH_LIST if h]
        if not commit_hashes:
            print("No commit hashes found in COMMIT_HASH_LIST.")
            raise SystemExit(0)

        print("Running in LIST mode")
        print(f"Loaded {len(commit_hashes)} commit hashes from COMMIT_HASH_LIST.")

    # Analyze the repository for modifications
    results = get_modified_files_and_functions(repo_path, commit_hashes)

    # Print results to console
    if results:
        print_results(results)
    else:
        print("No modifications found in the provided commits.")