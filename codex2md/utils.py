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


def scan_session_info(path: str, max_lines: int = 50) -> Dict[str, Any]:
    """
    Quickly scan a JSONL file to extract:
    - timestamp (from the first valid line with a timestamp)
    - first_prompt (the first user message found)
    """
    info = {"path": path, "timestamp": None, "first_prompt": None, "date_str": None}
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    
                    # specific extraction logic imports
                    # We avoid circular imports by simple dict lookups here or assume logic similar to extractors
                    
                    # Capture first timestamp
                    if not info["timestamp"]:
                        # try top level
                        ts = data.get("timestamp") or data.get("created_at")
                        if not ts and "payload" in data:
                            ts = data["payload"].get("timestamp")
                        
                        if ts:
                            info["timestamp"] = ts
                            # Try to make a sortable date string YYYYMMDD
                            # ts example: 2026-01-08T16:20:41.115Z
                            if isinstance(ts, str) and len(ts) >= 10:
                                info["date_str"] = ts[:10].replace("-", "")

                    # Capture first user prompt
                    if not info["first_prompt"]:
                        # Simplify detection for speed: look for role='user' or type='user_message'
                        text = None
                        
                        # Check payload style
                        payload = data.get("payload", {})
                        if isinstance(payload, dict):
                            if payload.get("type") == "user_message":
                                msg = payload.get("message")
                                if isinstance(msg, str):
                                    text = msg
                                elif isinstance(msg, dict):
                                    text = msg.get("content") or msg.get("text") # simplified
                            elif payload.get("role") == "user":
                                # handle content list/str
                                c = payload.get("content")
                                if isinstance(c, str):
                                    text = c
                                elif isinstance(c, list) and len(c) > 0 and isinstance(c[0], dict):
                                    text = c[0].get("text")
                        
                        # Check top level
                        if not text and data.get("role") == "user":
                             c = data.get("content")
                             if isinstance(c, str):
                                 text = c
                        
                        if text:
                            # Heuristic to skip injected system/context prompts
                            if "<INSTRUCTIONS>" in text or "<environment_context>" in text or "# AGENTS.md" in text:
                                continue
                            info["first_prompt"] = text

                    if info["timestamp"] and info["first_prompt"]:
                        break

                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    return info
