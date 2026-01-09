import json
from typing import Any, Dict, List, Optional


def md_escape_heading(s: str) -> str:
    return s.replace("\n", " ").strip()


def render_block_header(role: str, ts: Optional[str]) -> str:
    # Example: ### user (2026-01-07T21:10:00Z)
    if ts:
        return f"### {md_escape_heading(role)} ({ts})"
    return f"### {md_escape_heading(role)}"


def render_tool_calls(tool_calls: List[Dict[str, Any]], collapse: bool) -> str:
    if not tool_calls:
        return ""

    lines: List[str] = []
    if collapse:
        lines.append("<details><summary>Tool calls</summary>\n")

    for tc in tool_calls:
        name = tc.get("name") or tc.get("tool_name") or tc.get("function", {}).get("name")
        args = tc.get("arguments") or tc.get("args") or tc.get("input") or tc.get("function", {}).get("arguments")
        call_id = tc.get("id") or tc.get("call_id")
        title = "Tool call"
        if name:
            title += f": {name}"
        if call_id:
            title += f" (id={call_id})"

        lines.append(f"**{title}**")
        if args is not None:
            try:
                args_json = json.dumps(args if not isinstance(args, str) else json.loads(args), ensure_ascii=False, indent=2)
            except Exception:
                args_json = args if isinstance(args, str) else json.dumps(args, ensure_ascii=False, indent=2)
            lines.append("```json")
            lines.append(args_json)
            lines.append("```")
        lines.append("")

    if collapse:
        lines.append("</details>\n")

    return "\n".join(lines).rstrip() + "\n"


def render_tool_result(tool_result: Dict[str, Any], collapse: bool) -> str:
    if tool_result is None:
        return ""

    name = tool_result.get("name")
    out = tool_result.get("output", tool_result)
    header = "**Tool result**" + (f": {name}" if name else "")

    if collapse:
        pre = "<details><summary>Tool result</summary>\n\n"
        post = "\n</details>\n"
    else:
        pre = ""
        post = ""

    # Render as json if structured; else as text
    if isinstance(out, (dict, list)):
        body = "```json\n" + json.dumps(out, ensure_ascii=False, indent=2) + "\n```"
    else:
        body = "```text\n" + str(out) + "\n```"

    return f"{pre}{header}\n{body}{post}\n"
