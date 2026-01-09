import argparse
import sys
import os
import glob
from .core import convert
from .utils import read_jsonl, scan_session_info, normalize_role

DEFAULT_SESSIONS_DIR = os.path.expanduser("~/.codex/sessions")


def find_sessions_in_date_tree(base_dir: str, target_date: str = None) -> tuple:
    """
    Find session files in the <year>/<month>/<day> folder structure.

    Args:
        base_dir: Base directory containing year/month/day folders
        target_date: Optional date in YYYYMMDD format. If None, finds the most recent date.

    Returns:
        (target_date, list of session file paths)
    """
    if target_date:
        # Parse YYYYMMDD into year/month/day path
        if len(target_date) == 8:
            year, month, day = target_date[:4], target_date[4:6], target_date[6:8]
            date_dir = os.path.join(base_dir, year, month, day)
            if os.path.isdir(date_dir):
                files = glob.glob(os.path.join(date_dir, "*.jsonl"))
                return target_date, files
        return target_date, []

    # No date specified: find the most recent date
    # Scan year/month/day folders in reverse order
    years = sorted(glob.glob(os.path.join(base_dir, "[0-9][0-9][0-9][0-9]")), reverse=True)
    for year_dir in years:
        months = sorted(glob.glob(os.path.join(year_dir, "[0-9][0-9]")), reverse=True)
        for month_dir in months:
            days = sorted(glob.glob(os.path.join(month_dir, "[0-9][0-9]")), reverse=True)
            for day_dir in days:
                files = glob.glob(os.path.join(day_dir, "*.jsonl"))
                if files:
                    # Extract date from path
                    year = os.path.basename(year_dir)
                    month = os.path.basename(month_dir)
                    day = os.path.basename(day_dir)
                    return f"{year}{month}{day}", files

    return None, []


def is_codex_sessions_dir(path: str) -> bool:
    """Check if path appears to be a Codex sessions directory with year/month/day structure."""
    if not os.path.isdir(path):
        return False
    # Check for year-like subdirectories
    years = glob.glob(os.path.join(path, "[0-9][0-9][0-9][0-9]"))
    return len(years) > 0


def main() -> None:
    p = argparse.ArgumentParser(description="Convert OpenAI Codex JSONL session logs to Markdown.")
    p.add_argument("input", nargs="?", default=DEFAULT_SESSIONS_DIR, help=f"Path to input .jsonl file or directory (default: {DEFAULT_SESSIONS_DIR}).")
    p.add_argument("-d", "--date", help="Filter sessions by date (YYYYMMDD). Defaults to the most recent date found.")
    p.add_argument("-o", "--output", help="Path to output .md (default: stdout).")
    p.add_argument("--include-raw", action="store_true", help="Include raw JSON blocks for each line.")
    p.add_argument(
        "--only",
        nargs="+",
        help="Only include these roles (e.g. user assistant tool system developer event).",
    )
    p.add_argument(
        "--collapse-tools",
        action="store_true",
        help="Wrap tool calls/results in <details> blocks.",
    )
    args = p.parse_args()

    # Determine input mode
    input_path = args.input
    target_file = None

    if os.path.isfile(input_path) and input_path.endswith(".jsonl"):
        target_file = input_path
    else:
        if not os.path.isdir(input_path):
            sys.stderr.write(f"Error: {input_path} is not a valid file or directory.\n")
            sys.exit(1)

        # Check if this is a Codex sessions directory with year/month/day structure
        is_date_tree = is_codex_sessions_dir(input_path)
        if is_date_tree:
            target_date, files = find_sessions_in_date_tree(input_path, args.date)
            if not files:
                if args.date:
                    sys.stderr.write(f"No sessions found for date {args.date} in {input_path}\n")
                else:
                    sys.stderr.write(f"No session files found in {input_path}\n")
                sys.exit(1)
        else:
            # Flat directory mode: Scan for jsonl files directly
            files = glob.glob(os.path.join(input_path, "*.jsonl"))
            if not files:
                sys.stderr.write(f"No .jsonl files found in {input_path}\n")
                sys.exit(1)
            target_date = args.date

        # Scan sessions for metadata
        sessions = [scan_session_info(f) for f in files]
        sessions = [s for s in sessions if s["timestamp"]]
        sessions.sort(key=lambda x: x["timestamp"] or "", reverse=True)

        if not sessions:
            sys.stderr.write("No valid session logs found (could not parse timestamps).\n")
            sys.exit(1)

        # For flat directories without date tree, filter by date if specified
        if target_date and not is_date_tree:
            sessions = [s for s in sessions if s["date_str"] == target_date]
            if not sessions:
                sys.stderr.write(f"No sessions found for date {target_date}.\n")
                sys.exit(1)
        
        # Interactive selection
        if target_date:
            sys.stderr.write(f"Found {len(sessions)} session(s) for {target_date}:\n")
        else:
            sys.stderr.write(f"Found {len(sessions)} session(s):\n")
        for idx, s in enumerate(sessions, 1):
            cwd = s["cwd"] or "(unknown)"
            date = s["date_str"]
            if date and len(date) == 8:
                date = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
            prompt = s["first_prompt"] or "(No user prompt found)"
            preview = (prompt[:50] + "...") if len(prompt) > 50 else prompt
            sys.stderr.write(f"[{idx}] {cwd} ({date}) - {preview}\n")

        sys.stderr.write("\nSelect a session number: ")
        try:
            choice = input()
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(sessions):
                target_file = sessions[choice_idx]["path"]
            else:
                sys.stderr.write("Invalid selection.\n")
                sys.exit(1)
        except (ValueError, KeyboardInterrupt, EOFError):
            sys.stderr.write("\nOperation cancelled.\n")
            sys.exit(1)

    # Proceed with conversion
    only_roles = None
    if args.only:
        only_roles = [normalize_role(r) or r.strip().lower() for r in args.only]

    md = convert(read_jsonl(target_file), args.include_raw, only_roles, args.collapse_tools)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
    else:
        sys.stdout.write(md)
