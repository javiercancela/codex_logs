# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python CLI tool that converts OpenAI Codex JSONL session logs into readable Markdown format. It parses various JSONL log formats from Codex sessions and renders them as structured Markdown with role headers, timestamps, tool calls, and tool results.

## Running the Tool

```bash
# Run directly
python main.py [input] [-d DATE] [-o OUTPUT] [--include-raw] [--only ROLES...] [--collapse-tools]

# Examples
python main.py                           # Interactive selection from ~/.codex/sessions (default)
python main.py -d 20260108               # Sessions from specific date
python main.py session.jsonl             # Convert specific file to stdout
python main.py session.jsonl -o out.md   # Write to file
python main.py session.jsonl --only user assistant  # Filter roles
python main.py session.jsonl --collapse-tools       # Wrap tool blocks in <details>
```

The default input path is `~/.codex/sessions`, which uses the `<year>/<month>/<day>` folder structure from OpenAI Codex.

## Architecture

The codebase follows a pipeline pattern for JSONL-to-Markdown conversion:

```
cli.py → core.py → extractors.py + renderers.py
           ↓
        utils.py + constants.py
```

- **cli.py**: Entry point. Handles argument parsing, directory scanning for session files, date filtering, and interactive session selection
- **core.py**: Main `convert()` function that orchestrates the conversion pipeline
- **extractors.py**: Functions to extract structured data (role, text, tool calls, tool results) from various JSONL line formats
- **renderers.py**: Functions to render extracted data as Markdown (headers, tool call blocks, tool results)
- **utils.py**: Shared utilities for JSONL reading, timestamp formatting, role normalization, and session scanning
- **constants.py**: Role alias mappings (e.g., "human" → "user", "function" → "tool")

## Key Design Patterns

- **Flexible JSONL parsing**: The extractors handle multiple log format variations (nested messages, different key names like `content`/`text`/`delta`, various tool call structures)
- **Role normalization**: All roles are normalized through `ROLE_ALIASES` in constants.py
- **Timestamp handling**: Supports ISO8601 strings, epoch seconds/milliseconds, and `{seconds, nanos}` objects

## Dependencies

Standard library only (json, argparse, datetime, re, glob, sys, os). No external packages required.
