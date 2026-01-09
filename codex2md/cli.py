import argparse
import sys
import os
import glob
from .core import convert
from .utils import read_jsonl, scan_session_info
from .constants import ROLE_ALIASES


def main() -> None:
    p = argparse.ArgumentParser(description="Convert OpenAI Codex JSONL session logs to Markdown.")
    p.add_argument("input", nargs="?", default=".", help="Path to input .jsonl file or directory (default: current dir).")
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
        # Directory mode: Scan for jsonl files
        if os.path.isdir(input_path):
            search_path = os.path.join(input_path, "*.jsonl")
        else:
            # Fallback if user passed something that isn't a dir but might be a glob pattern or partial path
            # But specific requirement says: directory or file.
            sys.stderr.write(f"Error: {input_path} is not a valid file or directory.\n")
            sys.exit(1)
        
        files = glob.glob(search_path)
        if not files:
            sys.stderr.write(f"No .jsonl files found in {input_path}\n")
            sys.exit(1)

        # Scan sessions
        sessions = []
        for f in files:
            info = scan_session_info(f)
            if info["date_str"]:
                sessions.append(info)
        
        # Sort by timestamp desc
        sessions.sort(key=lambda x: x["timestamp"] or "", reverse=True)

        if not sessions:
            sys.stderr.write("No valid session logs found (could not parse timestamps).\n")
            sys.exit(1)

        # Filter by date
        target_date = args.date
        if not target_date:
            # Default to latest date available
            target_date = sessions[0]["date_str"]
        
        filtered_sessions = [s for s in sessions if s["date_str"] == target_date]
        
        if not filtered_sessions:
            sys.stderr.write(f"No sessions found for date {target_date}.\n")
            sys.exit(1)
        
        # Interactive selection
        sys.stderr.write(f"Found {len(filtered_sessions)} session(s) for {target_date}:\n")
        for idx, s in enumerate(filtered_sessions, 1):
            ts = s["timestamp"]
            prompt = s["first_prompt"] or "(No user prompt found)"
            preview = (prompt[:50] + "...") if len(prompt) > 50 else prompt
            # Print to stderr to keep stdout clean for piping if needed (though selection implies interactivity)
            sys.stderr.write(f"[{idx}] {ts} - {preview}\n")
        
        sys.stderr.write("\nSelect a session number: ")
        try:
            choice = input()
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(filtered_sessions):
                target_file = filtered_sessions[choice_idx]["path"]
            else:
                sys.stderr.write("Invalid selection.\n")
                sys.exit(1)
        except (ValueError, KeyboardInterrupt, EOFError):
            sys.stderr.write("\nOperation cancelled.\n")
            sys.exit(1)

    # Proceed with conversion
    only_roles = None
    if args.only:
        norm = []
        for r in args.only:
            r = r.strip().lower()
            r = ROLE_ALIASES.get(r, r)
            if r == "event":
                norm.append("event")
            else:
                norm.append(r)
        only_roles = norm

    md = convert(read_jsonl(target_file), args.include_raw, only_roles, args.collapse_tools)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
    else:
        sys.stdout.write(md)
