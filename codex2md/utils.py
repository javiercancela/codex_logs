import datetime as dt
import json
import re
import sys
from typing import Any, Dict, Iterable, List, Optional
from .constants import ROLE_ALIASES


def read_jsonl(path: str) -> Iterable[Dict[str, Any]]:
    with (sys.stdin if path == "-" else open(path, "r", encoding="utf-8")) as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                yield {
                    "_parse_error": True,
                    "_line_number": i,
                    "_raw_line": line,
                    "_error": str(e),
                }


def looks_like_iso8601(s: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}T", s))


def format_ts(value: Any) -> Optional[str]:
    """
    Try to format timestamps commonly seen in logs:
    - ISO8601 strings
    - epoch seconds / ms
    - nested {"seconds":..., "nanos":...}
    """
    if value is None:
        return None

    # Nested {seconds, nanos}
    if isinstance(value, dict) and "seconds" in value:
        try:
            seconds = float(value["seconds"])
            nanos = float(value.get("nanos", 0))
            t = dt.datetime.fromtimestamp(seconds + nanos / 1e9, tz=dt.timezone.utc)
            return t.isoformat().replace("+00:00", "Z")
        except Exception:
            return None

    # ISO string
    if isinstance(value, str) and looks_like_iso8601(value):
        return value

    # Epoch numeric (seconds or ms)
    if isinstance(value, (int, float)):
        try:
            x = float(value)
            # Heuristic: ms if too large
            if x > 1e12:
                x /= 1000.0
            t = dt.datetime.fromtimestamp(x, tz=dt.timezone.utc)
            return t.isoformat().replace("+00:00", "Z")
        except Exception:
            return None

    return None


def pick_first(d: Dict[str, Any], keys: List[str]) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def normalize_role(role: Optional[str]) -> Optional[str]:
    if not role:
        return None
    r = str(role).strip().lower()
    return ROLE_ALIASES.get(r, r)
