import argparse
import sys
from .core import convert
from .utils import read_jsonl
from .constants import ROLE_ALIASES


def main() -> None:
    p = argparse.ArgumentParser(description="Convert OpenAI Codex JSONL session logs to Markdown.")
    p.add_argument("input", help="Path to input .jsonl (use '-' for stdin).")
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

    only_roles = None
    if args.only:
        norm = []
        for r in args.only:
            r = r.strip().lower()
            r = ROLE_ALIASES.get(r, r)
            if r == "event":
                # we use event:* labels; allow 'event' as a special token
                norm.append("event")
            else:
                norm.append(r)
        # The filter checks exact role; we also support 'event' token manually in convert()
        only_roles = norm

    md = convert(read_jsonl(args.input), args.include_raw, only_roles, args.collapse_tools)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
    else:
        sys.stdout.write(md)
