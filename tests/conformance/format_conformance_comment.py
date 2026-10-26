#!/usr/bin/env python3

import argparse
import json
from pathlib import Path


def _fmt_list(items: list[str]) -> str:
    return ", ".join(f"`{x}`" for x in items)


def _fmt_section(diff: dict, name: str) -> str:
    section = diff.get(name, {}) if isinstance(diff, dict) else {}
    if not isinstance(section, dict):
        section = {}
    added = section.get("added", []) or []
    removed = section.get("removed", []) or []

    lines: list[str] = []
    if added:
        lines.append(f"- **{name} added**: {_fmt_list(added)}")
    if removed:
        lines.append(f"- **{name} removed**: {_fmt_list(removed)}")
    return "\n".join(lines)


def build_comment(exit_code: int, diff: dict | None) -> str:
    header = "✅ Conformance improved" if exit_code == 1 else "❌ Conformance regressed"
    hint = "(baseline auto-updated in this PR)" if exit_code == 1 else "(please investigate failures)"

    diff = diff or {}
    parts = [
        _fmt_section(diff, "passed"),
        _fmt_section(diff, "failed"),
        _fmt_section(diff, "skipped"),
    ]
    body = "\n".join([p for p in parts if p]).strip()
    if not body:
        body = "_No per-test changes detected (counts changed or diff unavailable)._"

    return f"{header} {hint}\n\n{body}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exit-code", type=int, required=True, help="Exit code from parse_report.py (0/1/2)")
    parser.add_argument(
        "--diff-json",
        default=None,
        help="Path to conformance-diff.json written by parse_report.py",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional path to write the formatted comment to a file (prints to stdout if omitted)",
    )
    args = parser.parse_args()

    diff: dict | None = None
    if args.diff_json:
        p = Path(args.diff_json)
        if p.exists():
            diff = json.loads(p.read_text())

    comment = build_comment(args.exit_code, diff)
    if args.out:
        Path(args.out).write_text(comment + "\n")
    else:
        print(comment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
