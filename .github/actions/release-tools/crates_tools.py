#!/usr/bin/env python3
"""Pure helpers for release-publish-rust-crates. No network, no cargo here —
the action's bash steps call cargo and crates.io and hand the results in.

Subcommands:
  parse       CRATES_TEXT                      -> one crate name per line
  check       METADATA_JSON EXPECTED CRATES... -> exit 1 listing crates whose
                                                  manifest version != EXPECTED
                                                  or that are not workspace
                                                  members / are publish=false
  partition   PUBLISHED_FILE CRATES...         -> JSON {"publish": [...],
                                                  "skip": [...]}; PUBLISHED_FILE
                                                  lists crates already at the
                                                  version, one per line
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_crates(text: str) -> list[str]:
    """Newline- or comma-separated names, order kept, blanks and dups dropped."""
    out: list[str] = []
    for chunk in text.replace(",", "\n").splitlines():
        name = chunk.strip()
        if name and name not in out:
            out.append(name)
    return out


def check_versions(metadata: dict, crates: list[str], expected: str) -> list[str]:
    """Problems (empty = fine) with the requested crates against
    `cargo metadata --no-deps` output: missing from the workspace, marked
    publish = false, or at a version other than `expected`."""
    by_name = {p["name"]: p for p in metadata.get("packages", [])}
    problems: list[str] = []
    for name in crates:
        pkg = by_name.get(name)
        if pkg is None:
            problems.append(f"{name}: not a workspace member")
            continue
        if pkg.get("publish") == []:
            problems.append(f"{name}: publish = false in its manifest")
        if pkg.get("version") != expected:
            problems.append(f"{name}: manifest version is {pkg.get('version')}, expected {expected}")
    return problems


def partition(crates: list[str], published: set[str]) -> dict[str, list[str]]:
    """Keep order; crates already on the registry at this version are skipped."""
    return {
        "publish": [c for c in crates if c not in published],
        "skip": [c for c in crates if c in published],
    }


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="crates_tools")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("parse")
    s.add_argument("text")
    s = sub.add_parser("check")
    s.add_argument("metadata_file")
    s.add_argument("expected")
    s.add_argument("crates", nargs="+")
    s = sub.add_parser("partition")
    s.add_argument("published_file")
    s.add_argument("crates", nargs="*")
    a = p.parse_args(argv)

    if a.cmd == "parse":
        print("\n".join(parse_crates(a.text)))
    elif a.cmd == "check":
        metadata = json.loads(Path(a.metadata_file).read_text())
        problems = check_versions(metadata, a.crates, a.expected)
        for line in problems:
            print(f"crates_tools: {line}", file=sys.stderr)
        return 1 if problems else 0
    elif a.cmd == "partition":
        text = Path(a.published_file).read_text() if Path(a.published_file).exists() else ""
        published = {line.strip() for line in text.splitlines() if line.strip()}
        print(json.dumps(partition(a.crates, published)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
