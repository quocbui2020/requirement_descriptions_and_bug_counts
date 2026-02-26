"""
Git Modified Files + Functions Extractor for Mozilla Firefox repository data.

OVERVIEW
--------
This script reads commit IDs from SQL Server, analyzes each commit from a local
Firefox Git repository with PyDriller, and writes:

1) modified files -> Modified_Files table
2) modified functions -> Modified_Functions table (if present)

It is designed for parallel execution (for example 20 workers), where each worker
uses a different output shard and local repo path.


INPUT SOURCE
------------
- Source commit table is fixed: [dbo].[GitCommitList]
- Commits are filtered to exclude rows where:
        - [is_merge] = 1
        - [is_backout_commit] = 1
        - [backed_out] = 1
- Eligible commit IDs are loaded once at startup into an in-memory cache.


OUTPUT TABLES
-------------
For each --table-number N:
- Preferred file table: [dbo].[Modified_Files_N]
- Fallback file table:  [dbo].[Modified_Files]

- Preferred function table: [dbo].[Modified_Functions_N]
- Fallback function table:  [dbo].[Modified_Functions]

If a function table does not exist, function extraction still happens in memory,
but function rows are not inserted.


WHAT IS WRITTEN
---------------
Modified_Files columns written by this script:
- [Git_commit_ID]
- [Previous_File_Name]
- [Updated_File_Name]
- [File_Status]
- [File_Type] (only if this column exists in selected table)

Modified_Functions columns written by this script:
- [Modified_File_Unique_Hash]
- [Function_Name]
- [Function_Arguments] (only if this column exists)

Function extraction behavior:
- Default: PyDriller changed_methods only
- Optional: add regex-based extraction from diff lines with
    --enable-regex-function-fallback


STATUS/TYPE NORMALIZATION
-------------------------
File_Status values:
- new | modified | deleted | renamed | copied | renamed_modified |
    copied_modified | unknown

File_Type values:
- JavaScript | C++ | C | Python | Kotlin | Header | Markup | Style |
    Data | Config | Documentation | Asset/Binary | Other

Path handling:
- Previous/updated file names are stored from PyDriller paths as-is.


RUN MODES
---------
1) ALL mode (default when no start/end range and no single commit):
     processes all eligible commits in cache.

2) RANGE mode:
     pass start_git_commit_id and end_git_commit_id (inclusive).

3) SINGLE mode:
     pass --single-commit-id <hash>.
     This still checks source filters unless --single-bypass-filters is provided.

4) REPLAY FAILED mode:
    pass --replay-failed-file <path_to_failed_commits_txt>.
    Commits in that file are processed directly (one hash per line).


DEBUGGING CONVENIENCE
---------------------
For VS Code breakpoint debugging, you can set:
- USE_DEBUG_CLI_ARGS = True
- edit DEBUG_CLI_ARGS list

Then run with debugger (F5), and arguments will be taken from DEBUG_CLI_ARGS.


CLI USAGE EXAMPLES
------------------
All eligible commits (worker 4):
    python GitModifiedFilesFunctionsExtractor.py --table-number 4 --repo-path C:\path\to\firefox_worker_04

Single commit:
    python GitModifiedFilesFunctionsExtractor.py --table-number 4 --repo-path C:\path\to\firefox_worker_04 \
            --single-commit-id 0006c9b86c7c307de509cf383f29cec3d6f0e3e8

Single commit with regex fallback:
    python GitModifiedFilesFunctionsExtractor.py --table-number 4 --repo-path C:\path\to\firefox_worker_04 \
            --single-commit-id 0006c9b86c7c307de509cf383f29cec3d6f0e3e8 --enable-regex-function-fallback

Range mode with per-file changed_methods timeout (recommended for hang-prone files):
    python GitModifiedFilesFunctionsExtractor.py --table-number 4 --repo-path C:\path\to\firefox_worker_04 \
            --commit-file-extract-timeout-seconds 120 \
            265c42d16f47111316f6a79e5308a0d6ac5d9f71 334746cbcbd83d2bea6bf70ba1227f5a096182ad

Alias for typo-tolerant flag name:
    --commit-fie-extract-timeout-seconds 120

Range mode:
    python GitModifiedFilesFunctionsExtractor.py --table-number 4 --repo-path C:\path\to\firefox_worker_04 \
            265c42d16f47111316f6a79e5308a0d6ac5d9f71 334746cbcbd83d2bea6bf70ba1227f5a096182ad

Replay failed commits from previous run:
    python GitModifiedFilesFunctionsExtractor.py --table-number 4 --repo-path C:\path\to\firefox_worker_04 \
            --replay-failed-file failed_commits_table_4_20260220_141205.txt


OPERATIONAL NOTES
-----------------
- Inserts are duplicate-safe (integrity conflicts are skipped).
- Script uses retry windows/heartbeat logs for DB operations.
- During extraction, the script prints a live in-place status line:
    Process Git_Commit_ID: <hash>
  This line is overwritten as each commit changes (instead of appending a new line).
- While iterating files inside a commit, live status includes file path:
        Process Git_Commit_ID: <hash> - File: <path>
    This line is also overwritten in-place and truncated to terminal width.
- A periodic summary is still emitted every PROGRESS_LOG_INTERVAL commits, including
    batch position and a progress bar.
- Commit extraction intentionally uses a fresh PyDriller repository traversal per
    commit (Repository(..., single=<hash>).traverse_commits()) for safer behavior
    in multi-process scenarios sharing the same .git directory.
- Per-file timeout safety:
        --commit-file-extract-timeout-seconds <seconds>
    If changed_methods extraction for one file exceeds timeout, only that file's
    function extraction is skipped; the same commit and remaining files continue.
    Use 0 to disable timeout behavior.
- If SQL reports truncation (for example Function_Arguments too long), increase
    column size in DB schema or add truncation policy in code.
"""

import argparse
import multiprocessing
import os
import queue
import re
import shutil
import sys
import time
from time import localtime, sleep, strftime

import pyodbc
import pydriller


# ========== CONFIGURATION ==========
REPO_PATH = r"C:\Users\quocb\quocbui\Studies\research\GithubRepo\firefox"

CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost\\SQLEXPRESS;"
    "DATABASE=MozillaDataSet2026;"
    "Connection Timeout=300;"
    "Login Timeout=300;"
    "LongAsMax=yes;"
    "TrustServerCertificate=yes;"
    "Trusted_Connection=yes;"
)

BATCH_SIZE = 500
DEBUG_MODE = False
DEFAULT_PYTHON_RECURSION_LIMIT = 10000

LOCAL_RETRY_DELAY_SECONDS = 5
MAX_LOCAL_RETRY_WINDOW_SECONDS = 900
RETRY_HEARTBEAT_INTERVAL_SECONDS = 30

PROGRESS_LOG_INTERVAL = 5
PROGRESS_BAR_WIDTH = 24
LIVE_COMMIT_STATUS_PREFIX = "Process Git_Commit_ID: "
DEFAULT_COMMIT_FILE_EXTRACT_TIMEOUT_SECONDS = 0.0

# VS Code breakpoint-friendly run mode:
# - False: use normal command-line arguments
# - True: use DEBUG_CLI_ARGS below (as if typed in terminal)
USE_DEBUG_CLI_ARGS = False
DEBUG_CLI_ARGS = [
    "--table-number", "1",
    "--repo-path", r"C:\Users\quocb\quocbui\Studies\research\GithubRepo\firefox_workers\firefox-worker-01",
    "--single-commit-id", "dab7697ab91c048268b91bfa3616a0ea194ae983",
    # "--enable-regex-function-fallback",
]

# Dynamic table configuration
TABLE_NUMBER = 1
TABLE_SOURCE_COMMITS = None
TABLE_MODIFIED_FILES = None
TABLE_MODIFIED_FUNCTIONS = None
HAS_MODIFIED_FUNCTIONS_TABLE = False
HAS_FILE_TYPE_COLUMN = False
HAS_FUNCTION_ARGUMENTS_COLUMN = False
SOURCE_COMMITS_CACHE = []
SOURCE_COMMITS_CACHE_SET = set()
ENABLE_REGEX_FUNCTION_FALLBACK = False
LIVE_COMMIT_STATUS_LAST_LENGTH = 0
COMMIT_FILE_EXTRACT_TIMEOUT_SECONDS = DEFAULT_COMMIT_FILE_EXTRACT_TIMEOUT_SECONDS

GET_COMMITS_ALL_QUERY = None
GET_COMMITS_RANGE_QUERY = None
GET_SINGLE_COMMIT_ELIGIBILITY_QUERY = None
INSERT_MODIFIED_FILE_QUERY = None
INSERT_MODIFIED_FUNCTION_QUERY = None
GET_MODIFIED_FILE_UNIQUE_HASH_QUERY = None


def _retry_window_exhausted(start_time, max_window_seconds):
    if max_window_seconds is None or max_window_seconds <= 0:
        return False
    return (time.time() - start_time) >= max_window_seconds


def _should_emit_retry_heartbeat(last_heartbeat_time):
    return (time.time() - last_heartbeat_time) >= RETRY_HEARTBEAT_INTERVAL_SECONDS


def print_progress_bar(phase, current, total, indent="  "):
    if total <= 0:
        return

    ratio = current / total
    if ratio < 0:
        ratio = 0
    if ratio > 1:
        ratio = 1

    filled = int(PROGRESS_BAR_WIDTH * ratio)
    bar = ("#" * filled) + ("-" * (PROGRESS_BAR_WIDTH - filled))
    percent = ratio * 100
    print(
        f"{indent}[{strftime('%H:%M:%S', localtime())}] [{phase}] "
        f"|{bar}| {percent:6.2f}% ({current}/{total})"
    )


def print_live_commit_status(commit_hash):
    global LIVE_COMMIT_STATUS_LAST_LENGTH

    message = _truncate_live_status_message(f"{LIVE_COMMIT_STATUS_PREFIX}{commit_hash}")
    if LIVE_COMMIT_STATUS_LAST_LENGTH > len(message):
        message += " " * (LIVE_COMMIT_STATUS_LAST_LENGTH - len(message))

    print(f"\r{message}", end="", flush=True)
    LIVE_COMMIT_STATUS_LAST_LENGTH = len(message)


def print_live_commit_file_status(commit_hash, file_path):
    global LIVE_COMMIT_STATUS_LAST_LENGTH

    safe_file_path = file_path or "<unknown>"
    message = _truncate_live_status_message(
        f"{LIVE_COMMIT_STATUS_PREFIX}{commit_hash} - File: {safe_file_path}"
    )
    if LIVE_COMMIT_STATUS_LAST_LENGTH > len(message):
        message += " " * (LIVE_COMMIT_STATUS_LAST_LENGTH - len(message))

    print(f"\r{message}", end="", flush=True)
    LIVE_COMMIT_STATUS_LAST_LENGTH = len(message)


def _truncate_live_status_message(message):
    try:
        term_columns = shutil.get_terminal_size(fallback=(120, 20)).columns
    except Exception:
        term_columns = 120

    if term_columns is None or term_columns <= 10:
        term_columns = 120

    max_len = max(20, term_columns - 1)
    if len(message) <= max_len:
        return message

    ellipsis = "..."
    if max_len <= len(ellipsis):
        return message[:max_len]

    return message[: max_len - len(ellipsis)] + ellipsis


def clear_live_commit_status():
    global LIVE_COMMIT_STATUS_LAST_LENGTH

    if LIVE_COMMIT_STATUS_LAST_LENGTH <= 0:
        return

    print(f"\r{' ' * LIVE_COMMIT_STATUS_LAST_LENGTH}\r", end="", flush=True)
    LIVE_COMMIT_STATUS_LAST_LENGTH = 0


def parse_arguments(cli_args=None):
    parser = argparse.ArgumentParser(
        description="Extract modified files/functions from commits (parallel-safe)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "start_git_commit_id",
        type=str,
        nargs="?",
        default=None,
        help="Starting Git_Commit_ID string (inclusive)",
    )

    parser.add_argument(
        "end_git_commit_id",
        type=str,
        nargs="?",
        default=None,
        help="Ending Git_Commit_ID string (inclusive)",
    )

    parser.add_argument(
        "--table-number",
        type=int,
        default=1,
        help="Table shard number (1-20). Used for output table routing.",
    )

    parser.add_argument(
        "--repo-path",
        type=str,
        default=REPO_PATH,
        help="Path to local firefox Git repository for this process",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help="Batch size for processing (default: 500)",
    )

    parser.add_argument(
        "--single-commit-id",
        type=str,
        default=None,
        help="Process one commit hash only (testing mode). Skips commit queue lookup.",
    )

    parser.add_argument(
        "--replay-failed-file",
        type=str,
        default=None,
        help="Replay only commit hashes listed in a failed-commits text file (one hash per line).",
    )

    parser.add_argument(
        "--single-bypass-filters",
        action="store_true",
        help="In single mode, bypass is_merge/is_backout/backed_out filters and force processing.",
    )

    parser.add_argument(
        "--enable-regex-function-fallback",
        action="store_true",
        help="Enable regex fallback from diff lines for function extraction (default: disabled; PyDriller-only).",
    )

    parser.add_argument(
        "--python-recursion-limit",
        type=int,
        default=DEFAULT_PYTHON_RECURSION_LIMIT,
        help="Optional Python recursion limit (e.g., 10000) to reduce RecursionError in deep parser paths.",
    )

    parser.add_argument(
        "--commit-file-extract-timeout-seconds",
        "--commit-fie-extract-timeout-seconds",
        dest="commit_file_extract_timeout_seconds",
        type=float,
        default=DEFAULT_COMMIT_FILE_EXTRACT_TIMEOUT_SECONDS,
        help=(
            "Per-file timeout (seconds) for changed_methods extraction. "
            "If timeout is reached, only that file's function extraction is skipped and processing continues. "
            "0 disables timeout (default)."
        ),
    )

    args = parser.parse_args(cli_args)

    if (args.start_git_commit_id is None) != (args.end_git_commit_id is None):
        parser.error("Both start_git_commit_id and end_git_commit_id must be specified together")

    if args.start_git_commit_id is not None and args.end_git_commit_id is not None:
        if args.start_git_commit_id > args.end_git_commit_id:
            parser.error(
                f"start_git_commit_id ({args.start_git_commit_id}) must be <= end_git_commit_id ({args.end_git_commit_id})"
            )

    if args.table_number < 1 or args.table_number > 20:
        parser.error(f"table_number must be between 1 and 20 (got {args.table_number})")

    if args.batch_size <= 0:
        parser.error("batch-size must be > 0")

    if args.python_recursion_limit is not None and args.python_recursion_limit <= 0:
        parser.error("--python-recursion-limit must be > 0")

    if args.commit_file_extract_timeout_seconds is not None and args.commit_file_extract_timeout_seconds < 0:
        parser.error("--commit-file-extract-timeout-seconds must be >= 0")

    if args.single_commit_id is not None and (args.start_git_commit_id is not None or args.end_git_commit_id is not None):
        parser.error("--single-commit-id cannot be used together with start/end range arguments")

    if args.replay_failed_file is not None:
        if args.start_git_commit_id is not None or args.end_git_commit_id is not None:
            parser.error("--replay-failed-file cannot be used together with start/end range arguments")
        if args.single_commit_id is not None:
            parser.error("--replay-failed-file cannot be used together with --single-commit-id")

    return args


def _table_exists(cursor, full_table_name):
    cursor.execute("SELECT OBJECT_ID(?, 'U')", full_table_name)
    return cursor.fetchone()[0] is not None


def _normalize_file_status(modified_file):
    change_type = str(getattr(modified_file, "change_type", "")).lower()

    added_lines = getattr(modified_file, "added_lines", 0) or 0
    deleted_lines = getattr(modified_file, "deleted_lines", 0) or 0
    has_content_change = (added_lines + deleted_lines) > 0

    if "add" in change_type:
        return "new"
    if "delete" in change_type:
        return "deleted"
    if "rename" in change_type:
        if has_content_change:
            return "renamed_modified"
        return "renamed"
    if "copy" in change_type:
        if has_content_change:
            return "copied_modified"
        return "copied"
    if "modify" in change_type:
        return "modified"

    old_path = getattr(modified_file, "old_path", None)
    new_path = getattr(modified_file, "new_path", None)

    if old_path in (None, "") and new_path not in (None, ""):
        return "new"
    if new_path in (None, "") and old_path not in (None, ""):
        return "deleted"
    if old_path not in (None, "") and new_path not in (None, "") and old_path != new_path:
        return "renamed"
    if old_path == new_path and old_path not in (None, ""):
        return "modified"

    return "unknown"


def _get_pydriller_paths(modified_file):
    old_path = getattr(modified_file, "old_path", None)
    new_path = getattr(modified_file, "new_path", None)

    prev_name = str(old_path).strip() if old_path is not None else ""
    updated_name = str(new_path).strip() if new_path is not None else ""

    return prev_name, updated_name


def _normalize_file_type(previous_file_name, updated_file_name):
    candidate_path = None

    for path_value in (updated_file_name, previous_file_name):
        if not path_value:
            continue
        candidate_path = path_value
        break

    if not candidate_path:
        return "Other"

    extension = os.path.splitext(candidate_path)[1].lower()

    if extension in {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"}:
        return "JavaScript"
    if extension in {".cpp", ".cc", ".cxx", ".c++", ".cp"}:
        return "C++"
    if extension in {".h", ".hh", ".hpp", ".hxx", ".inc", ".inl"}:
        return "Header"
    if extension in {".java"}:
        return "Java"
    if extension in {".rs"}:
        return "Rust"
    if extension in {".go"}:
        return "Go"
    if extension in {".html", ".htm", ".xhtml", ".xht"}:
        return "Markup"
    if extension in {".xml", ".xul", ".svg"}:
        return "Markup"
    if extension in {".css", ".scss", ".sass", ".less"}:
        return "Style"
    if extension == ".c":
        return "C"
    if extension in {".py", ".pyw"}:
        return "Python"
    if extension in {".kt", ".kts"}:
        return "Kotlin"
    if extension in {".json", ".json5", ".yaml", ".yml", ".toml", ".csv", ".tsv"}:
        return "Data"
    if extension in {".ini", ".cfg", ".conf", ".properties"}:
        return "Config"
    if extension in {".md", ".markdown", ".rst", ".txt", ".adoc"}:
        return "Documentation"
    if extension in {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".avif",
        ".mp3", ".wav", ".ogg", ".flac", ".mp4", ".webm", ".mov",
        ".pdf", ".zip", ".gz", ".7z", ".rar", ".jar", ".class", ".dll", ".so", ".dylib", ".exe"
    }:
        return "Asset/Binary"

    return "Other"


def _extract_function_parts(method, anonymous_name="<anonymous>"):
    base_name = getattr(method, "name", None) or getattr(method, "long_name", None)
    if base_name is not None:
        base_name = str(base_name).strip()
    else:
        base_name = ""

    def _anonymous_location_arguments():
        start_line = getattr(method, "start_line", None)
        end_line = getattr(method, "end_line", None)

        if isinstance(start_line, int) and isinstance(end_line, int):
            return f"(line {start_line}-{end_line})"
        if isinstance(start_line, int):
            return f"(line {start_line})"
        return None

    parameters = getattr(method, "parameters", None)
    if parameters is not None:
        try:
            param_list = [str(param).strip() for param in parameters if str(param).strip()]
            function_arguments = f"({', '.join(param_list)})"
        except Exception:
            param_list = []
            function_arguments = None

        if not base_name:
            function_name = anonymous_name
        elif "(" in base_name and base_name.endswith(")"):
            function_name = base_name.split("(", 1)[0].rstrip()
        else:
            function_name = base_name

        if not function_name:
            function_name = anonymous_name

        function_name = re.sub(r"\s+", " ", function_name).strip()
        if function_name and (" " not in function_name or function_name.startswith("operator ")):
            return function_name, function_arguments
        return anonymous_name, function_arguments

    if not base_name:
        return anonymous_name, _anonymous_location_arguments()

    if "(" in base_name and base_name.endswith(")"):
        split_index = base_name.find("(")
        function_name = base_name[:split_index].rstrip()
        function_arguments = base_name[split_index:]
        function_name = re.sub(r"\s+", " ", function_name).strip()
        if not function_name or (" " in function_name and not function_name.startswith("operator ")):
            function_name = anonymous_name
            function_arguments = function_arguments or _anonymous_location_arguments()
        return function_name, function_arguments

    base_name = re.sub(r"\s+", " ", base_name).strip()
    if " " in base_name and not base_name.startswith("operator "):
        return anonymous_name, _anonymous_location_arguments()

    return base_name, None


def _extract_changed_methods_metadata_worker(repo_path, commit_hash, previous_file_name, updated_file_name, out_queue):
    try:
        commits = list(
            pydriller.Repository(
                repo_path,
                single=commit_hash,
            ).traverse_commits()
        )
        if not commits:
            out_queue.put({"ok": False, "error": "Commit not found", "methods": []})
            return

        commit = commits[0]
        target_file = None
        for modified_file in commit.modified_files:
            old_path = getattr(modified_file, "old_path", None)
            new_path = getattr(modified_file, "new_path", None)
            old_norm = str(old_path).strip() if old_path is not None else ""
            new_norm = str(new_path).strip() if new_path is not None else ""
            if old_norm == previous_file_name and new_norm == updated_file_name:
                target_file = modified_file
                break

        if target_file is None:
            out_queue.put({"ok": False, "error": "Target file not found in commit", "methods": []})
            return

        changed_methods = getattr(target_file, "changed_methods", None) or []
        method_payloads = []
        for method in changed_methods:
            parameters = getattr(method, "parameters", None)
            if parameters is not None:
                try:
                    parameters = [str(param) for param in parameters]
                except Exception:
                    parameters = []

            method_payloads.append(
                {
                    "name": getattr(method, "name", None),
                    "long_name": getattr(method, "long_name", None),
                    "parameters": parameters,
                    "start_line": getattr(method, "start_line", None),
                    "end_line": getattr(method, "end_line", None),
                }
            )

        out_queue.put({"ok": True, "error": None, "methods": method_payloads})
    except Exception as e:
        out_queue.put({"ok": False, "error": str(e), "methods": []})


class _MethodMetadata:
    def __init__(self, payload):
        self.name = payload.get("name")
        self.long_name = payload.get("long_name")
        self.parameters = payload.get("parameters")
        self.start_line = payload.get("start_line")
        self.end_line = payload.get("end_line")


def _get_changed_methods_with_timeout(modified_file, commit_hash, repo_path, previous_file_name, updated_file_name, timeout_seconds):
    if timeout_seconds is None or timeout_seconds <= 0:
        changed_methods = getattr(modified_file, "changed_methods", None)
        return changed_methods, False, None

    ctx = multiprocessing.get_context("spawn")
    out_queue = ctx.Queue()
    process = ctx.Process(
        target=_extract_changed_methods_metadata_worker,
        args=(repo_path, commit_hash, previous_file_name, updated_file_name, out_queue),
        daemon=True,
    )

    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join()
        return None, True, f"Timeout after {timeout_seconds}s"

    result = None
    try:
        result = out_queue.get_nowait()
    except queue.Empty:
        result = {"ok": False, "error": "No result returned from worker", "methods": []}
    finally:
        out_queue.close()
        out_queue.join_thread()

    if not result.get("ok"):
        return None, False, result.get("error")

    methods = [_MethodMetadata(payload) for payload in result.get("methods", [])]
    return methods, False, None


def _extract_function_records(modified_file, file_status, commit_hash=None, repo_path=None):
    records = []
    previous_file_name, updated_file_name = _get_pydriller_paths(modified_file)

    anonymous_context = updated_file_name
    if not anonymous_context:
        anonymous_context = previous_file_name

    if anonymous_context:
        anonymous_name = f"<anonymous>@{anonymous_context}"
    else:
        anonymous_name = "<anonymous>"

    changed_methods, timed_out, changed_methods_error = _get_changed_methods_with_timeout(
        modified_file,
        commit_hash,
        repo_path,
        previous_file_name,
        updated_file_name,
        COMMIT_FILE_EXTRACT_TIMEOUT_SECONDS,
    )

    if timed_out:
        clear_live_commit_status()
        target_file = updated_file_name or previous_file_name or "<unknown>"
        print(
            f"[{strftime('%H:%M:%S', localtime())}] [WARNING] changed_methods timeout for file '{target_file}' "
            f"in commit {str(commit_hash)[:7]} after {COMMIT_FILE_EXTRACT_TIMEOUT_SECONDS}s; "
            f"skipping function extraction for this file"
        )
        changed_methods = None
    elif changed_methods_error and DEBUG_MODE:
        clear_live_commit_status()
        target_file = updated_file_name or previous_file_name or "<unknown>"
        print(
            f"[{strftime('%H:%M:%S', localtime())}] [DEBUG] changed_methods extraction error for file '{target_file}' "
            f"in commit {str(commit_hash)[:7]}: {changed_methods_error}"
        )

    if changed_methods:
        for method in changed_methods:
            function_name, function_arguments = _extract_function_parts(method, anonymous_name=anonymous_name)
            if function_name:
                records.append(
                    {
                        "function_name": function_name,
                        "function_arguments": function_arguments,
                    }
                )

    if ENABLE_REGEX_FUNCTION_FALLBACK:
        records.extend(_extract_function_records_from_diff(modified_file, anonymous_name))

    seen = set()
    deduped = []
    for record in records:
        function_name = record.get("function_name")
        function_arguments = record.get("function_arguments")
        if not function_name:
            continue
        dedupe_key = (function_name, function_arguments)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduped.append(record)

    return deduped


def _extract_function_records_from_diff(modified_file, anonymous_name):
    records = []
    diff_parsed = getattr(modified_file, "diff_parsed", None) or {}

    changed_lines = []
    for section in ("added", "deleted"):
        entries = diff_parsed.get(section, []) or []
        for _, line_text in entries:
            if line_text:
                changed_lines.append(str(line_text))

    if not changed_lines:
        return records

    js_assignment_pattern = re.compile(
        r'^\s*([A-Za-z_$][\w$\.\[\]"\']*)\s*=\s*(?:async\s+)?function(?:\s+[A-Za-z_$][\w$]*)?\s*\(([^)]*)\)',
        re.IGNORECASE,
    )
    js_named_expression_pattern = re.compile(
        r'(?:^|[^A-Za-z0-9_$])(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)',
        re.IGNORECASE,
    )
    js_anonymous_pattern = re.compile(
        r'(?:^|[\s\(,])(?:async\s+)?function(?:\s+[A-Za-z_$][\w$]*)?\s*\(([^)]*)\)',
        re.IGNORECASE,
    )
    py_lambda_assignment_pattern = re.compile(
        r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*lambda\b([^:]*):',
        re.IGNORECASE,
    )

    for line_text in changed_lines:
        js_assignment_match = js_assignment_pattern.search(line_text)
        if js_assignment_match:
            function_name = js_assignment_match.group(1).strip()
            parameters_text = js_assignment_match.group(2).strip()
            function_arguments = f"({parameters_text})"
            records.append(
                {
                    "function_name": function_name,
                    "function_arguments": function_arguments,
                }
            )
            continue

        js_named_expression_match = js_named_expression_pattern.search(line_text)
        if js_named_expression_match:
            function_name = js_named_expression_match.group(1).strip()
            parameters_text = js_named_expression_match.group(2).strip()
            function_arguments = f"({parameters_text})"
            records.append(
                {
                    "function_name": function_name,
                    "function_arguments": function_arguments,
                }
            )
            continue

        py_lambda_match = py_lambda_assignment_pattern.search(line_text)
        if py_lambda_match:
            function_name = py_lambda_match.group(1).strip()
            parameters_text = py_lambda_match.group(2).strip()
            function_arguments = f"(lambda {parameters_text})" if parameters_text else "(lambda)"
            records.append(
                {
                    "function_name": function_name,
                    "function_arguments": function_arguments,
                }
            )
            continue

        js_anonymous_match = js_anonymous_pattern.search(line_text)
        if js_anonymous_match:
            parameters_text = js_anonymous_match.group(1).strip()
            function_arguments = f"({parameters_text})"
            records.append(
                {
                    "function_name": anonymous_name,
                    "function_arguments": function_arguments,
                }
            )

    return records


def configure_table_queries(table_number):
    global TABLE_NUMBER, TABLE_SOURCE_COMMITS, TABLE_MODIFIED_FILES, TABLE_MODIFIED_FUNCTIONS
    global HAS_MODIFIED_FUNCTIONS_TABLE, HAS_FILE_TYPE_COLUMN, HAS_FUNCTION_ARGUMENTS_COLUMN
    global GET_COMMITS_ALL_QUERY, GET_COMMITS_RANGE_QUERY, GET_SINGLE_COMMIT_ELIGIBILITY_QUERY, INSERT_MODIFIED_FILE_QUERY, INSERT_MODIFIED_FUNCTION_QUERY, GET_MODIFIED_FILE_UNIQUE_HASH_QUERY

    TABLE_NUMBER = table_number
    TABLE_SOURCE_COMMITS = "[dbo].[GitCommitList]"

    shard_modified_files = f"[dbo].[Modified_Files_{table_number}]"
    base_modified_files = "[dbo].[Modified_Files]"

    shard_modified_functions = f"[dbo].[Modified_Functions_{table_number}]"
    base_modified_functions = "[dbo].[Modified_Functions]"

    conn = None
    cursor = None
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()

        if not _table_exists(cursor, TABLE_SOURCE_COMMITS):
            raise RuntimeError(f"Input table not found: {TABLE_SOURCE_COMMITS}")

        if _table_exists(cursor, shard_modified_files):
            TABLE_MODIFIED_FILES = shard_modified_files
        elif _table_exists(cursor, base_modified_files):
            TABLE_MODIFIED_FILES = base_modified_files
        else:
            raise RuntimeError(
                f"No output table found for modified files. Checked {shard_modified_files} and {base_modified_files}"
            )

        cursor.execute(
            '''
                SELECT TOP 1 1
                FROM sys.columns
                WHERE object_id = OBJECT_ID(?)
                  AND name = 'File_Type'
            ''',
            TABLE_MODIFIED_FILES,
        )
        HAS_FILE_TYPE_COLUMN = cursor.fetchone() is not None

        if _table_exists(cursor, shard_modified_functions):
            TABLE_MODIFIED_FUNCTIONS = shard_modified_functions
            HAS_MODIFIED_FUNCTIONS_TABLE = True
        elif _table_exists(cursor, base_modified_functions):
            TABLE_MODIFIED_FUNCTIONS = base_modified_functions
            HAS_MODIFIED_FUNCTIONS_TABLE = True
        else:
            TABLE_MODIFIED_FUNCTIONS = None
            HAS_MODIFIED_FUNCTIONS_TABLE = False

        HAS_FUNCTION_ARGUMENTS_COLUMN = False
        if HAS_MODIFIED_FUNCTIONS_TABLE:
            cursor.execute(
                '''
                    SELECT TOP 1 1
                    FROM sys.columns
                    WHERE object_id = OBJECT_ID(?)
                      AND name = 'Function_Arguments'
                ''',
                TABLE_MODIFIED_FUNCTIONS,
            )
            HAS_FUNCTION_ARGUMENTS_COLUMN = cursor.fetchone() is not None

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    source_filters_for_src = """
          ISNULL(src.[is_merge], 0) = 0
      AND ISNULL(src.[is_backout_commit], 0) = 0
      AND ISNULL(src.[backed_out], 0) = 0
    """.strip()

    source_filters_for_c = """
          ISNULL(c.[is_merge], 0) = 0
      AND ISNULL(c.[is_backout_commit], 0) = 0
      AND ISNULL(c.[backed_out], 0) = 0
    """.strip()

    GET_COMMITS_ALL_QUERY = f'''
            SELECT src.[Git_commit_ID]
            FROM {TABLE_SOURCE_COMMITS} src
            WHERE {source_filters_for_src}
              AND NOT EXISTS (
                    SELECT 1
                    FROM {TABLE_MODIFIED_FILES} done
                    WHERE done.[Git_commit_ID] = src.[Git_commit_ID]
                      AND (
                            ISNULL(LTRIM(RTRIM(done.[Previous_File_Name])), '') <> ''
                         OR ISNULL(LTRIM(RTRIM(done.[Updated_File_Name])), '') <> ''
                         OR ISNULL(LTRIM(RTRIM(done.[File_Status])), '') <> ''
                      )
              )
            GROUP BY src.[Git_commit_ID]
            ORDER BY src.[Git_commit_ID]
    '''

    GET_SINGLE_COMMIT_ELIGIBILITY_QUERY = f'''
            SELECT c.[Git_commit_ID]
            FROM {TABLE_SOURCE_COMMITS} c
            WHERE {source_filters_for_c}
    '''

    GET_COMMITS_RANGE_QUERY = f'''
            SELECT src.[Git_commit_ID]
            FROM {TABLE_SOURCE_COMMITS} src
            WHERE src.[Git_commit_ID] >= ?
              AND src.[Git_commit_ID] <= ?
              AND {source_filters_for_src}
              AND NOT EXISTS (
                    SELECT 1
                    FROM {TABLE_MODIFIED_FILES} done
                    WHERE done.[Git_commit_ID] = src.[Git_commit_ID]
                      AND (
                            ISNULL(LTRIM(RTRIM(done.[Previous_File_Name])), '') <> ''
                         OR ISNULL(LTRIM(RTRIM(done.[Updated_File_Name])), '') <> ''
                         OR ISNULL(LTRIM(RTRIM(done.[File_Status])), '') <> ''
                      )
              )
            GROUP BY src.[Git_commit_ID]
            ORDER BY src.[Git_commit_ID]
    '''

    if HAS_FILE_TYPE_COLUMN:
        INSERT_MODIFIED_FILE_QUERY = f'''
            INSERT INTO {TABLE_MODIFIED_FILES}
                ([Git_commit_ID], [Previous_File_Name], [Updated_File_Name], [File_Status], [File_Type])
            VALUES (?, ?, ?, ?, ?)
        '''
    else:
        INSERT_MODIFIED_FILE_QUERY = f'''
            INSERT INTO {TABLE_MODIFIED_FILES}
                ([Git_commit_ID], [Previous_File_Name], [Updated_File_Name], [File_Status])
            VALUES (?, ?, ?, ?)
        '''

    GET_MODIFIED_FILE_UNIQUE_HASH_QUERY = f'''
        SELECT TOP 1 [Unique_Hash]
        FROM {TABLE_MODIFIED_FILES}
        WHERE [Git_commit_ID] = ?
          AND [Previous_File_Name] = ?
          AND [Updated_File_Name] = ?
          AND [File_Status] = ?
    '''

    if HAS_MODIFIED_FUNCTIONS_TABLE:
        if HAS_FUNCTION_ARGUMENTS_COLUMN:
            INSERT_MODIFIED_FUNCTION_QUERY = f'''
                INSERT INTO {TABLE_MODIFIED_FUNCTIONS}
                    ([Modified_File_Unique_Hash], [Function_Name], [Function_Arguments])
                VALUES (?, ?, ?)
            '''
        else:
            INSERT_MODIFIED_FUNCTION_QUERY = f'''
                INSERT INTO {TABLE_MODIFIED_FUNCTIONS}
                    ([Modified_File_Unique_Hash], [Function_Name])
                VALUES (?, ?)
            '''
    else:
        INSERT_MODIFIED_FUNCTION_QUERY = None


def get_commits_from_db(start_git_commit_id=None, end_git_commit_id=None):
    use_range = start_git_commit_id is not None and end_git_commit_id is not None

    if use_range:
        return [c for c in SOURCE_COMMITS_CACHE if start_git_commit_id <= c <= end_git_commit_id]

    return list(SOURCE_COMMITS_CACHE)


def load_source_commits_cache():
    global SOURCE_COMMITS_CACHE, SOURCE_COMMITS_CACHE_SET

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
            cursor.execute(GET_SINGLE_COMMIT_ELIGIBILITY_QUERY)

            SOURCE_COMMITS_CACHE = [row[0] for row in cursor.fetchall()]
            SOURCE_COMMITS_CACHE_SET = set(SOURCE_COMMITS_CACHE)

            cursor.close()
            conn.close()

            print(
                f"[{strftime('%H:%M:%S', localtime())}] [INFO] Loaded {len(SOURCE_COMMITS_CACHE)} eligible commits "
                f"from {TABLE_SOURCE_COMMITS} into memory cache"
            )
            return

        except Exception as e:
            print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Failed to load source commit cache (attempt {attempt}): {e}")
            if cursor:
                cursor.close()
            if conn:
                conn.close()

            if _retry_window_exhausted(retry_started, MAX_LOCAL_RETRY_WINDOW_SECONDS):
                raise RuntimeError("Database read retry window exceeded while loading source commit cache") from e

            if _should_emit_retry_heartbeat(last_heartbeat):
                elapsed = int(time.time() - retry_started)
                print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Still retrying source commit cache load... elapsed={elapsed}s attempts={attempt}")
                last_heartbeat = time.time()

            print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Retrying DB read in {LOCAL_RETRY_DELAY_SECONDS}s...")
            sleep(LOCAL_RETRY_DELAY_SECONDS)


def is_commit_allowed_by_filters(commit_hash):
    return commit_hash in SOURCE_COMMITS_CACHE_SET


def load_failed_commits_file(file_path):
    commits = []
    seen = set()

    with open(file_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            if line in seen:
                continue
            seen.add(line)
            commits.append(line)

    return commits


def write_failed_commits_file(failed_commits):
    if not failed_commits:
        return None

    timestamp = strftime("%Y%m%d_%H%M%S", localtime())
    output_name = f"failed_commits_table_{TABLE_NUMBER}_{timestamp}.txt"

    with open(output_name, "w", encoding="utf-8") as f:
        f.write(f"# Failed commits for table-number {TABLE_NUMBER}\n")
        f.write(f"# Generated at: {strftime('%Y-%m-%d %H:%M:%S', localtime())}\n")
        f.write("# One commit hash per line\n")
        for commit_hash in failed_commits:
            f.write(f"{commit_hash}\n")

    return os.path.abspath(output_name)


def get_commit_modified_data(commit_hash, repo_path):
    attempt = 0

    while True:
        attempt += 1
        try:
            commits = list(
                pydriller.Repository(
                    repo_path,
                    single=commit_hash,
                ).traverse_commits()
            )

            if not commits:
                clear_live_commit_status()
                print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] Commit {commit_hash[:7]} not found in repository")
                return None

            commit = commits[0]

            files = []
            recursion_skipped_files = 0

            for modified_file in commit.modified_files:
                file_status = _normalize_file_status(modified_file)
                prev_name, updated_name = _get_pydriller_paths(modified_file)
                target_file = updated_name or prev_name or "<unknown>"
                print_live_commit_file_status(commit_hash, target_file)
                file_type = _normalize_file_type(prev_name, updated_name)
                function_records = []
                try:
                    function_records = _extract_function_records(
                        modified_file,
                        file_status,
                        commit_hash=commit_hash,
                        repo_path=repo_path,
                    )
                except RecursionError as rec_err:
                    recursion_skipped_files += 1
                    clear_live_commit_status()
                    print(
                        f"[{strftime('%H:%M:%S', localtime())}] [WARNING] [skip] fail to process '{target_file}' "
                        f"with RecursionError - {rec_err}; file-level data kept, function rows skipped"
                    )

                files.append(
                    {
                        "previous_file_name": prev_name,
                        "updated_file_name": updated_name,
                        "file_status": file_status,
                        "file_type": file_type,
                        "functions": function_records,
                    }
                )

            return {
                "hash_id": commit.hash,
                "files": files,
                "recursion_skipped_files": recursion_skipped_files,
            }

        except Exception as e:
            text = str(e).lower()
            if ".git" in text and "config.lock" in text:
                clear_live_commit_status()
                print(
                    f"[{strftime('%H:%M:%S', localtime())}] [WARNING] Git config lock contention for {commit_hash[:7]} "
                    f"(attempt {attempt}), retrying in {LOCAL_RETRY_DELAY_SECONDS}s"
                )
                sleep(LOCAL_RETRY_DELAY_SECONDS)
                continue

            if "badname" in text or "unknown revision" in text or "not found" in text:
                clear_live_commit_status()
                print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] Commit {commit_hash[:7]} is not available in local repository")
                return None

            clear_live_commit_status()
            print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Failed to read commit {commit_hash[:7]}: {e}")
            return None


def insert_modified_file_skip_duplicate(cursor, git_commit_id, previous_file_name, updated_file_name, file_status, file_type):
    try:
        if HAS_FILE_TYPE_COLUMN:
            cursor.execute(
                INSERT_MODIFIED_FILE_QUERY,
                git_commit_id,
                previous_file_name,
                updated_file_name,
                file_status,
                file_type,
            )
        else:
            cursor.execute(
                INSERT_MODIFIED_FILE_QUERY,
                git_commit_id,
                previous_file_name,
                updated_file_name,
                file_status,
            )
        return True
    except pyodbc.IntegrityError:
        if DEBUG_MODE:
            print(
                f"  [DEBUG] Duplicate modified-file row skipped: "
                f"{git_commit_id[:7]} {file_status} {previous_file_name} -> {updated_file_name}"
            )
        return False


def insert_modified_function_skip_duplicate(
    cursor,
    modified_file_unique_hash,
    function_name,
    function_arguments,
):
    if not HAS_MODIFIED_FUNCTIONS_TABLE:
        return False

    try:
        if HAS_FUNCTION_ARGUMENTS_COLUMN:
            cursor.execute(
                INSERT_MODIFIED_FUNCTION_QUERY,
                modified_file_unique_hash,
                function_name,
                function_arguments,
            )
        else:
            cursor.execute(
                INSERT_MODIFIED_FUNCTION_QUERY,
                modified_file_unique_hash,
                function_name,
            )
        return True
    except pyodbc.IntegrityError:
        if DEBUG_MODE:
            print(
                f"  [DEBUG] Duplicate modified-function row skipped: "
                f"{function_name}"
            )
        return False


def get_modified_file_unique_hash(cursor, git_commit_id, previous_file_name, updated_file_name, file_status):
    cursor.execute(
        GET_MODIFIED_FILE_UNIQUE_HASH_QUERY,
        git_commit_id,
        previous_file_name,
        updated_file_name,
        file_status,
    )
    row = cursor.fetchone()
    if not row:
        return None
    return row[0]


def persist_commit_data(commit_data):
    hash_id = commit_data.get("hash_id", "UNKNOWN_HASH")
    files = commit_data.get("files", [])

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

            inserted_files = 0
            inserted_functions = 0

            for row in files:
                previous_file_name = row["previous_file_name"]
                updated_file_name = row["updated_file_name"]
                file_status = row["file_status"]
                file_type = row["file_type"]

                if insert_modified_file_skip_duplicate(
                    cursor,
                    hash_id,
                    previous_file_name,
                    updated_file_name,
                    file_status,
                    file_type,
                ):
                    inserted_files += 1

                if HAS_MODIFIED_FUNCTIONS_TABLE:
                    modified_file_unique_hash = get_modified_file_unique_hash(
                        cursor,
                        hash_id,
                        previous_file_name,
                        updated_file_name,
                        file_status,
                    )

                    if not modified_file_unique_hash:
                        if DEBUG_MODE:
                            print(
                                f"  [DEBUG] Could not resolve Modified_Files.Unique_Hash for "
                                f"{hash_id[:7]} {previous_file_name} -> {updated_file_name}"
                            )
                        continue

                    for function_row in row["functions"]:
                        function_name = function_row.get("function_name")
                        function_arguments = function_row.get("function_arguments")
                        if insert_modified_function_skip_duplicate(
                            cursor,
                            modified_file_unique_hash,
                            function_name,
                            function_arguments,
                        ):
                            inserted_functions += 1

            conn.commit()
            cursor.close()
            conn.close()

            return True, inserted_files, inserted_functions

        except Exception as e:
            print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Failed to persist commit {hash_id[:7]} (attempt {attempt}): {e}")
            if conn:
                conn.rollback()
            if cursor:
                cursor.close()
            if conn:
                conn.close()

            if _retry_window_exhausted(retry_started, MAX_LOCAL_RETRY_WINDOW_SECONDS):
                print(
                    f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Retry window exceeded for commit {hash_id[:7]}; "
                    f"marking as failure and continuing"
                )
                return False, 0, 0

            if _should_emit_retry_heartbeat(last_heartbeat):
                elapsed = int(time.time() - retry_started)
                print(
                    f"[{strftime('%H:%M:%S', localtime())}] [INFO] Still retrying DB write for commit {hash_id[:7]}... "
                    f"elapsed={elapsed}s attempts={attempt}"
                )
                last_heartbeat = time.time()

            print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Retrying DB write in {LOCAL_RETRY_DELAY_SECONDS}s...")
            sleep(LOCAL_RETRY_DELAY_SECONDS)


def process_all_commits(
    repo_path,
    start_git_commit_id=None,
    end_git_commit_id=None,
    batch_size=BATCH_SIZE,
    explicit_commits=None,
    mode_label_override=None,
):
    use_range = start_git_commit_id is not None and end_git_commit_id is not None

    print("=" * 80)
    if mode_label_override:
        print(f"[{strftime('%H:%M:%S', localtime())}] MODIFIED FILES/FUNCTIONS EXTRACTOR [{mode_label_override}]")
    elif use_range:
        print(f"[{strftime('%H:%M:%S', localtime())}] MODIFIED FILES/FUNCTIONS EXTRACTOR [RANGE MODE]")
        print(f"Processing Git_Commit_ID range: {start_git_commit_id} to {end_git_commit_id}")
    else:
        print(f"[{strftime('%H:%M:%S', localtime())}] MODIFIED FILES/FUNCTIONS EXTRACTOR [ALL RECORDS]")
    print("=" * 80)
    print(f"[{strftime('%H:%M:%S', localtime())}] Input commits table:   {TABLE_SOURCE_COMMITS} (excluding merge/backout/backed_out)")
    print(f"[{strftime('%H:%M:%S', localtime())}] Output files table:    {TABLE_MODIFIED_FILES}")
    if HAS_MODIFIED_FUNCTIONS_TABLE:
        print(f"[{strftime('%H:%M:%S', localtime())}] Output functions table:{TABLE_MODIFIED_FUNCTIONS}")
    else:
        print(f"[{strftime('%H:%M:%S', localtime())}] Output functions table:NOT FOUND (function insert skipped)")
    print(f"[{strftime('%H:%M:%S', localtime())}] Repository:            {repo_path}")
    print(f"[{strftime('%H:%M:%S', localtime())}] Batch size:            {batch_size}")
    print(f"[{strftime('%H:%M:%S', localtime())}] Start time:            {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    print("=" * 80)

    print(f"\n[{strftime('%H:%M:%S', localtime())}] [STEP 1/3] Fetching commits to process...")
    if explicit_commits is not None:
        commits = list(explicit_commits)
    else:
        commits = get_commits_from_db(start_git_commit_id, end_git_commit_id)

    if not commits:
        print(f"[{strftime('%H:%M:%S', localtime())}] [WARNING] No commits found to process")
        return

    total_commits = len(commits)
    print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Found {total_commits} commits")

    total_extracted = 0
    total_extract_failed = 0
    total_db_success = 0
    total_db_failed = 0
    total_files_inserted = 0
    total_functions_inserted = 0
    total_recursion_skipped_files = 0
    failed_commits = []

    print(f"\n[{strftime('%H:%M:%S', localtime())}] [STEP 2/3] Processing commits...")

    batch_num = 0
    for start_idx in range(0, total_commits, batch_size):
        batch_num += 1
        end_idx = min(start_idx + batch_size, total_commits)
        batch = commits[start_idx:end_idx]

        print(f"\n[{strftime('%H:%M:%S', localtime())}] [BATCH {batch_num}] Commits {start_idx + 1}-{end_idx} / {total_commits}")
        print_progress_bar("Extract", 0, len(batch))

        extracted_batch = []
        for i, commit_hash in enumerate(batch, 1):
            print_live_commit_status(commit_hash)

            data = get_commit_modified_data(commit_hash, repo_path)
            if data is None:
                total_extract_failed += 1
                failed_commits.append(commit_hash)
            else:
                extracted_batch.append(data)
                total_extracted += 1

            if i % PROGRESS_LOG_INTERVAL == 0 or i == len(batch):
                clear_live_commit_status()
                print(
                    f"[{strftime('%H:%M:%S', localtime())}] [INFO] Extracting commit {i}/{len(batch)} "
                    f"({commit_hash[:12]}...)"
                )
                print_progress_bar("Extract", i, len(batch))

        clear_live_commit_status()
        print_progress_bar("DB Update", 0, len(extracted_batch) if extracted_batch else 1)
        batch_recursion_skipped_files = 0

        for j, commit_data in enumerate(extracted_batch, 1):
            commit_recursion_skips = int(commit_data.get("recursion_skipped_files", 0) or 0)
            batch_recursion_skipped_files += commit_recursion_skips
            total_recursion_skipped_files += commit_recursion_skips
            success, inserted_files, inserted_functions = persist_commit_data(commit_data)
            if success:
                total_db_success += 1
                total_files_inserted += inserted_files
                total_functions_inserted += inserted_functions
            else:
                total_db_failed += 1
                if commit_data.get("hash_id"):
                    failed_commits.append(commit_data["hash_id"])

            if j % PROGRESS_LOG_INTERVAL == 0 or j == len(extracted_batch):
                print_progress_bar("DB Update", j, len(extracted_batch))

        print(
            f"[{strftime('%H:%M:%S', localtime())}] [BATCH {batch_num}] Complete: "
            f"extracted={len(extracted_batch)} db_success={total_db_success} "
            f"files_inserted={total_files_inserted} functions_inserted={total_functions_inserted} "
            f"batch_recursion_skips={batch_recursion_skipped_files} "
            f"total_recursion_skips={total_recursion_skipped_files}"
        )

    print(f"\n[{strftime('%H:%M:%S', localtime())}] [STEP 3/3] Final Summary")
    print("=" * 80)
    print(f"Total commits selected:        {total_commits}")
    print(f"Extracted successfully:        {total_extracted}")
    print(f"Extraction failed:             {total_extract_failed}")
    print(f"DB updates successful:         {total_db_success}")
    print(f"DB updates failed:             {total_db_failed}")
    print(f"Modified_Files inserted:       {total_files_inserted}")
    print(f"Modified_Functions inserted:   {total_functions_inserted}")
    print(f"Function parse skips (recursion): {total_recursion_skipped_files}")
    print(f"Failed commits to replay:      {len(failed_commits)}")

    failed_file_path = write_failed_commits_file(failed_commits)
    if failed_file_path:
        print(f"Failed commits file:           {failed_file_path}")
    else:
        print("Failed commits file:           (none)")

    print(f"End time:                      {strftime('%Y-%m-%d %H:%M:%S', localtime())}")
    print("=" * 80)


def process_single_commit(repo_path, commit_hash, bypass_filters=False):
    print("=" * 80)
    print(f"[{strftime('%H:%M:%S', localtime())}] MODIFIED FILES/FUNCTIONS EXTRACTOR [SINGLE MODE]")
    print(f"Commit:                        {commit_hash}")
    print(f"[{strftime('%H:%M:%S', localtime())}] Output files table:    {TABLE_MODIFIED_FILES}")
    if HAS_MODIFIED_FUNCTIONS_TABLE:
        print(f"[{strftime('%H:%M:%S', localtime())}] Output functions table:{TABLE_MODIFIED_FUNCTIONS}")
    else:
        print(f"[{strftime('%H:%M:%S', localtime())}] Output functions table:NOT FOUND (function insert skipped)")
    print(f"[{strftime('%H:%M:%S', localtime())}] Repository:            {repo_path}")
    print("=" * 80)

    if not bypass_filters:
        allowed = is_commit_allowed_by_filters(commit_hash)
        if not allowed:
            print(
                f"[{strftime('%H:%M:%S', localtime())}] [INFO] Single commit skipped by source filters "
                f"(is_merge/is_backout_commit/backed_out) or not found in {TABLE_SOURCE_COMMITS}: {commit_hash}"
            )
            return
    else:
        print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] --single-bypass-filters enabled; processing commit regardless of source filters")

    details = get_commit_modified_data(commit_hash, repo_path)
    if details is None:
        print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Failed to extract commit: {commit_hash}")
        return

    success, inserted_files, inserted_functions = persist_commit_data(details)
    recursion_skipped_files = int(details.get("recursion_skipped_files", 0) or 0)
    if success:
        print(f"[{strftime('%H:%M:%S', localtime())}] [SUCCESS] Single commit processed")
        print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Modified_Files inserted: {inserted_files}")
        print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Modified_Functions inserted: {inserted_functions}")
        print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Function parse skips (recursion): {recursion_skipped_files}")
    else:
        print(f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Failed to persist single commit: {commit_hash}")


def main():
    if USE_DEBUG_CLI_ARGS:
        print(f"[{strftime('%H:%M:%S', localtime())}] [INFO] Using DEBUG_CLI_ARGS: {' '.join(DEBUG_CLI_ARGS)}")
        args = parse_arguments(DEBUG_CLI_ARGS)
    else:
        args = parse_arguments()

    r"""
    Test cases:
        - is_merge case: cd2683690c3d1d9194c8cba991f2517611c29b4e
        - is_backout_commit case:
            - revert: e6f25a8d314a64ce7e2ad887513e32b998588463
            - backout 3 changesets: e6f4355ff38f30bbed3aed88559df57c9b004f39
        - backed_out case: aac35e5a890f22bc341808d838d8efa48154fca7
        - regular cases:
            - 041774db08880cca1ab10e807d0d71718964dffe
                - modifed, deleted
            - 12eb0a9f99614a06ad17524ba9ecf4b5974c94a2
                - modified, new
                - (anonymous) function
            - dab7697ab91c048268b91bfa3616a0ea194ae983
                renamed_modified
                modified
                new
                new
                renamed_modified
                new
                deleted
                new
                modified
                modified
                deleted
            - 80254c44d838624cddfcd1210b3d3f36c133c23b
                copied_modified
        - Failed cases:
            - 33a2f45d217026304d7fe883df3b5e68506f61e5
                Save into the function name a long messages.
    """

    global REPO_PATH, BATCH_SIZE, ENABLE_REGEX_FUNCTION_FALLBACK, COMMIT_FILE_EXTRACT_TIMEOUT_SECONDS
    REPO_PATH = args.repo_path
    BATCH_SIZE = args.batch_size
    ENABLE_REGEX_FUNCTION_FALLBACK = args.enable_regex_function_fallback
    COMMIT_FILE_EXTRACT_TIMEOUT_SECONDS = args.commit_file_extract_timeout_seconds

    if args.python_recursion_limit is not None:
        old_limit = sys.getrecursionlimit()
        try:
            sys.setrecursionlimit(args.python_recursion_limit)
            print(
                f"[{strftime('%H:%M:%S', localtime())}] [INFO] Python recursion limit set: "
                f"{old_limit} -> {sys.getrecursionlimit()}"
            )
        except Exception as e:
            print(
                f"[{strftime('%H:%M:%S', localtime())}] [WARNING] Failed to set recursion limit "
                f"to {args.python_recursion_limit}: {e}"
            )

    configure_table_queries(args.table_number)

    replay_commits = None
    if args.replay_failed_file:
        try:
            replay_commits = load_failed_commits_file(args.replay_failed_file)
        except Exception as e:
            print(
                f"[{strftime('%H:%M:%S', localtime())}] [ERROR] Failed to read --replay-failed-file "
                f"{args.replay_failed_file}: {e}"
            )
            return

        print(
            f"[{strftime('%H:%M:%S', localtime())}] [INFO] Loaded {len(replay_commits)} commit hashes "
            f"from failed-commits file"
        )
    else:
        load_source_commits_cache()

    if args.replay_failed_file:
        process_all_commits(
            repo_path=REPO_PATH,
            batch_size=BATCH_SIZE,
            explicit_commits=replay_commits,
            mode_label_override="REPLAY FAILED MODE",
        )
    elif args.single_commit_id:
        process_single_commit(
            repo_path=REPO_PATH,
            commit_hash=args.single_commit_id,
            bypass_filters=args.single_bypass_filters,
        )
    else:
        process_all_commits(
            repo_path=REPO_PATH,
            start_git_commit_id=args.start_git_commit_id,
            end_git_commit_id=args.end_git_commit_id,
            batch_size=BATCH_SIZE,
        )


if __name__ == "__main__":
    # EXAMPLE OF RANGE MODE: cls; cd C:\Users\quocb\quocbui\Studies\research\GithubRepo\requirement_descriptions_and_bug_counts\Mozilla; ..\venv311\Scripts\Activate.ps1; python .\GitModifiedFilesFunctionsExtractor.py --table-number 1 --repo-path C:\Users\quocb\quocbui\Studies\research\GithubRepo\firefox_workers\firefox-worker-01 --commit-fie-extract-timeout-seconds 900 00000163a890eb9f05f98c4084cd07846aa7cbf0 0cc73f8e55a9781a93769b17be8a0571064430b7
    main()
