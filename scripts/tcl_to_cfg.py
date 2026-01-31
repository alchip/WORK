#!/usr/bin/env python3
"""Convert simple Tcl list-style variable definitions into .cfg format.

Input pattern (example):

  set liblist(LEF_STD) [list \
      /path/a \
      /path/b] ;

Output pattern:

  LEF_STD       = /path/a
                  /path/b

Notes:
- This is intentionally conservative: it only converts `set <array>(<KEY>) [list ...]` blocks.
- Paths are assumed to have no spaces.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

# Defaults requested
DEFAULT_AUTHOR = "sunnyy@alchip.com"
DEFAULT_SECTION = "liblist"


BLOCK_RE = re.compile(
    # Supports both multi-line list with line-continuation backslashes and single-line list:
    #   set liblist(KEY) [list \
    #       /a \
    #       /b] ;
    #   set liblist(KEY) [list /a /b];
    r"set\s+\w+\((?P<key>[^)]+)\)\s+\[list(?P<body>.*?)\]\s*;?",
    re.DOTALL,
)


def _extract_paths(body: str) -> list[str]:
    # Remove Tcl line-continuation backslashes at EOL and normalize whitespace.
    # Example body lines often look like:
    #   /path/a \
    #   /path/b
    lines = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Drop trailing backslash if present (line continuation)
        if line.endswith("\\"):
            line = line[:-1].rstrip()
        # Drop trailing ';' if present on same line
        if line.endswith(";"):
            line = line[:-1].rstrip()
        if not line:
            continue
        lines.append(line)

    # Now split remaining by whitespace (paths are assumed whitespace-free)
    paths: list[str] = []
    for line in lines:
        paths.extend([tok for tok in line.split() if tok])
    return paths


def tcl_to_cfg(
    tcl_text: str,
    *,
    name_width: int = 12,
    indent_width: int = 16,
    author: str = DEFAULT_AUTHOR,
    created_date: str | None = None,
    section: str = DEFAULT_SECTION,
) -> str:
    """Convert Tcl to cfg.

    Rules:
    - Tcl lines starting with `#` are comments and ignored.
    - Output begins with `[liblist]` (or the provided section name).
    - Adds an author + created date comment block.
    """

    # Drop comment lines that start with # (ignoring leading whitespace)
    cleaned_lines: list[str] = []
    for line in tcl_text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)

    if created_date is None:
        # ISO date in local timezone
        from datetime import datetime

        created_date = datetime.now().astimezone().date().isoformat()

    out_lines: list[str] = []

    # Section header must be the first line
    out_lines.append(f"[{section}]")
    out_lines.append(f"# Author: {author}")
    out_lines.append(f"# Created: {created_date}")
    out_lines.append("")

    for m in BLOCK_RE.finditer(cleaned):
        key = m.group("key").strip()
        body = m.group("body")
        paths = _extract_paths(body)
        if not paths:
            continue

        lhs = key.ljust(name_width)
        out_lines.append(f"{lhs} = {paths[0]}")
        pad = " " * indent_width
        for p in paths[1:]:
            out_lines.append(f"{pad}{p}")
        out_lines.append("")  # blank line between variables

    # Trim trailing blank lines
    while out_lines and out_lines[-1] == "":
        out_lines.pop()

    return "\n".join(out_lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert Tcl [list] var definitions to .cfg format")
    ap.add_argument("input", type=Path, help="Input .tcl file")
    ap.add_argument("-o", "--output", type=Path, help="Output .cfg file (default: stdout)")
    ap.add_argument("--name-width", type=int, default=12, help="Width for variable name column")
    ap.add_argument("--indent-width", type=int, default=16, help="Indent for continuation lines")
    ap.add_argument("--author", type=str, default=DEFAULT_AUTHOR, help="Author comment")
    ap.add_argument("--created", type=str, default=None, help="Created date (YYYY-MM-DD). Defaults to today")
    ap.add_argument("--section", type=str, default=DEFAULT_SECTION, help="CFG section header name")
    args = ap.parse_args()

    tcl_text = args.input.read_text(encoding="utf-8", errors="replace")
    cfg_text = tcl_to_cfg(
        tcl_text,
        name_width=args.name_width,
        indent_width=args.indent_width,
        author=args.author,
        created_date=args.created,
        section=args.section,
    )

    if args.output:
        args.output.write_text(cfg_text, encoding="utf-8")
    else:
        print(cfg_text, end="")


if __name__ == "__main__":
    main()
