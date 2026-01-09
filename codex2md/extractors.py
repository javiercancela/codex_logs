import json
from typing import Any, Dict, List, Optional, Tuple
from .utils import normalize_role, pick_first


def extract_text_from_message_obj(msg: Dict[str, Any]) -> str:
    """
    Handle shapes like:
      {"role":"assistant","content":"..."}
      {"role":"assistant","content":[{"type":"text","text":"..."}, ...]}:
      {"message":{"role":...,"content":...}}
      {"data":{"message":...}}
    """
    content = msg.get("content")

    if isinstance(content, str):
        return content

    # content blocks
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                # common: {"type":"text","text":"..."}
                if "text" in block and isinstance(block["text"], str):
                    parts.append(block["text"])
                elif "content" in block and isinstance(block["content"], str):
                    parts.append(block["content"])
                else:
                    # last resort: dump block
                    parts.append(json.dumps(block, ensure_ascii=False))
            else:
                parts.append(str(block))
        return "\n".join([p for p in parts if p.strip()])

    # sometimes "text" is top-level
    if "text" in msg and isinstance(msg["text"], str):
        return msg["text"]

    # sometimes "delta" used for streaming; keep if present
    if "delta" in msg:
        delta = msg["delta"]
        if isinstance(delta, str):
            return delta
        if isinstance(delta, dict):
            return extract_text_from_message_obj(delta)

    # sometimes "summary" used for reasoning events
    if "summary" in msg and isinstance(msg["summary"], list):
        parts = []
        for block in msg["summary"]:
            if isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
        if parts:
            return "\n".join(parts)

    return ""


def extract_tool_calls(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Support common tool call shapes:
      {"tool_calls":[...]}
      {"message":{"tool_calls":[...]}}
      {"function_call": {...}}
      {"tool_call": {...}}
    """
    tool_calls = []
    for key in ("tool_calls", "tool_call", "function_call"):
        v = obj.get(key)
        if v:
            if isinstance(v, list):
                tool_calls.extend([x for x in v if isinstance(x, dict)])
            elif isinstance(v, dict):
                tool_calls.append(v)
    # nested message
    msg = obj.get("message")
    if isinstance(msg, dict) and msg.get("tool_calls"):
        v = msg["tool_calls"]
        if isinstance(v, list):
            tool_calls.extend([x for x in v if isinstance(x, dict)])
    return tool_calls


def extract_tool_result(obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Support common tool result shapes:
      {"tool_result": {...}}
      {"result": {...}} with tool-ish markers
      {"tool_output": "..."}
    """
    for k in ("tool_result", "tool_output", "toolResponse", "tool_response"):
        v = obj.get(k)
        if v is not None:
            if isinstance(v, dict):
                return v
            return {"output": v}
    # Some logs use {"type":"tool_result","name":...,"output":...}
    if obj.get("type") in ("tool_result", "tool_response") and (
        "output" in obj or "content" in obj or "result" in obj
    ):
        out = pick_first(obj, ["output", "content", "result"])
        return {"output": out, "name": obj.get("name")}
    return None


def event_label(obj: Dict[str, Any]) -> str:
    # Try a few common keys.
    return str(pick_first(obj, ["type", "event", "kind", "name"]) or "event")

def extract_role_and_text(obj: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """
    Attempt to map a JSONL line to (role, text).
    """
    # Parse error line
    if obj.get("_parse_error"):
        role = "error"
        text = f"JSON parse error on line {obj.get('_line_number')}: {obj.get('_error')}\n\nRaw:\n{obj.get('_raw_line')}"
        return role, text

    # Most direct: role/content
    role = normalize_role(obj.get("role"))
    if role:
        text = extract_text_from_message_obj(obj)
        return role, text

    # Nested message objects
    for path in ("message", "data", "payload"):
        nested = obj.get(path)
        if isinstance(nested, dict):
            role2 = normalize_role(nested.get("role"))
            if role2:
                return role2, extract_text_from_message_obj(nested)

            # Check for known types without explicit role
            msg_type = nested.get("type")

            if msg_type == "user_message":
                msg_content = nested.get("message")
                if isinstance(msg_content, str):
                    return "user", msg_content
                if isinstance(msg_content, dict):
                    return "user", extract_text_from_message_obj(msg_content)

            if msg_type == "agent_reasoning":
                return "reasoning", nested.get("text", "")

            if msg_type == "reasoning":
                return "reasoning", extract_text_from_message_obj(nested)

            # Sometimes: {"message": {"role":..., "content":...}}
            if "message" in nested and isinstance(nested["message"], dict):
                m = nested["message"]
                role3 = normalize_role(m.get("role"))
                if role3:
                    return role3, extract_text_from_message_obj(m)

    # Tool call lines: treat as tool
    if extract_tool_calls(obj):
        return "tool", ""  # tool calls will be rendered separately

    # Tool result lines
    if extract_tool_result(obj) is not None:
        return "tool", ""  # rendered separately

    # Fallback: check common "sender"/"source"
    for k in ("sender", "source", "actor"):
        if k in obj and obj[k]:
            r = normalize_role(str(obj[k]))
            if r in ("user", "assistant", "system", "developer", "tool"):
                # try to find text fields
                txt = pick_first(obj, ["content", "text", "message", "delta"])
                if isinstance(txt, str):
                    return r, txt

    # Unknown event type: treat as "event" with no direct text
    return None, ""
