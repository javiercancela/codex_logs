import json
from typing import Any, Dict, Iterable, List, Optional
from .utils import format_ts, pick_first, normalize_role
from .extractors import (
    extract_role_and_text,
    extract_tool_calls,
    extract_tool_result,
    event_label,
)
from .renderers import (
    render_block_header,
    render_tool_calls,
    render_tool_result,
)


def convert(
    items: Iterable[Dict[str, Any]],
    include_raw: bool,
    only_roles: Optional[List[str]],
    collapse_tools: bool,
) -> str:
    out_lines: List[str] = []
    out_lines.append("# Codex session transcript\n")

    for obj in items:
        ts = format_ts(pick_first(obj, ["timestamp", "time", "created_at", "created", "ts", "datetime"]))
        role, text = extract_role_and_text(obj)

        tool_calls = extract_tool_calls(obj)
        tool_result = extract_tool_result(obj)

        # Determine role fallback
        if role is None:
            # If it's some log event without role, label by event type
            role = event_label(obj)
            role = f"event:{role}"

        role = normalize_role(role) or "event"

        # Skip elements with no content (no text, no tool calls, no tool results)
        has_text = bool(text and text.strip())
        if not (has_text or tool_calls or tool_result is not None):
            continue

        # Filter by role
        if only_roles:
            is_event = role.startswith("event:")
            if is_event and "event" not in only_roles:
                continue
            if not is_event and role not in only_roles:
                continue

        # Render main block
        out_lines.append(render_block_header(role, ts))

        if has_text:
            out_lines.append(text.rstrip())
            out_lines.append("")  # blank line

        # Render tool calls/results (even if no text)
        if tool_calls:
            out_lines.append(render_tool_calls(tool_calls, collapse_tools).rstrip())
            out_lines.append("")
        if tool_result is not None:
            out_lines.append(render_tool_result(tool_result, collapse_tools).rstrip())
            out_lines.append("")

        # Optionally include raw JSON
        if include_raw:
            out_lines.append("```json")
            out_lines.append(json.dumps(obj, ensure_ascii=False, indent=2))
            out_lines.append("```")
            out_lines.append("")

    return "\n".join(out_lines).rstrip() + "\n"
