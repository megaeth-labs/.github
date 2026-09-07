#!/usr/bin/env python3
"""Pure helpers shared by the release-* composite actions.

Everything git- or GitHub-facing stays in the actions' bash steps; this module
only transforms text so it can be unit-tested without a repository. stdlib only.

Subcommands (see `main`):
  normalize   VERSION                       -> X.Y.Z on stdout, exit 1 if invalid
  is-greater  VERSION LATEST_TAG_OR_EMPTY   -> exit 0 if VERSION > LATEST, else 1
  read-file   PATH PATTERN                  -> version found in the file
  bump-file   PATH PATTERN VERSION          -> rewrite in place, print old version
  notes       REPO VERSION DATE             -> stdin: "<sha>\t<subject>" lines; stdout: markdown
  changelog-insert PATH VERSION SECTION_MD  -> insert/replace the section, print "inserted"/"replaced"
  changelog-extract PATH VERSION            -> the section body on stdout, exit 1 if absent
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEMVER = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")

# Conventional Commits types, in the order they appear in the notes. Anything
# not listed (or without a type) lands under "Other".
NOTE_GROUPS: list[tuple[str, str]] = [
    ("feat", "Features"),
    ("fix", "Fixes"),
    ("perf", "Performance"),
    ("refactor", "Refactoring"),
    ("docs", "Documentation"),
    ("test", "Tests"),
    ("bench", "Benchmarks"),
    ("ci", "CI"),
    ("deps", "Dependencies"),
    ("chore", "Chores"),
    ("revert", "Reverts"),
]
SUBJECT = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?:\s*(?P<desc>.+)$")
PR_SUFFIX = re.compile(r"\s*\(#(?P<num>\d+)\)\s*$")

CHANGELOG_HEADER = "# Changelog\n"


# --- versions ---------------------------------------------------------------


def normalize_version(raw: str) -> str:
    """Return X.Y.Z for 'X.Y.Z' or 'vX.Y.Z'; raise ValueError otherwise."""
    m = SEMVER.match(raw.strip())
    if not m:
        raise ValueError(f"not a release version (X.Y.Z or vX.Y.Z): {raw!r}")
    return ".".join(m.groups())


def version_tuple(v: str) -> tuple[int, int, int]:
    a, b, c = normalize_version(v).split(".")
    return int(a), int(b), int(c)


def is_greater(version: str, latest: str) -> bool:
    """True when `version` is strictly newer than `latest` (empty latest = no
    prior release, always true)."""
    if not latest.strip():
        return True
    return version_tuple(version) > version_tuple(latest)


# --- version files ----------------------------------------------------------

# pattern -> (regex with a `v` group, description). `plain` is the whole file.
FILE_PATTERNS: dict[str, re.Pattern[str]] = {
    # Cargo.toml / pyproject.toml: first `version = "..."` at line start.
    "toml": re.compile(r'^(?P<pre>version\s*=\s*")(?P<v>[^"]*)(?P<post>")', re.M),
    # package.json: first `"version": "..."`.
    "json": re.compile(r'(?P<pre>"version"\s*:\s*")(?P<v>[^"]*)(?P<post>")'),
}


def read_version_file(text: str, pattern: str) -> str:
    if pattern == "plain":
        return text.strip()
    rx = FILE_PATTERNS.get(pattern)
    if rx is None:
        raise ValueError(f"unknown version_pattern {pattern!r}; use plain, toml or json")
    m = rx.search(text)
    if not m:
        raise ValueError(f"no version field matched pattern {pattern!r}")
    return m.group("v")


def bump_version_file(text: str, pattern: str, version: str) -> tuple[str, str]:
    """Return (new_text, old_version)."""
    old = read_version_file(text, pattern)
    if pattern == "plain":
        return version + "\n", old
    rx = FILE_PATTERNS[pattern]
    new = rx.sub(lambda m: m.group("pre") + version + m.group("post"), text, count=1)
    return new, old


# --- release notes ----------------------------------------------------------


def parse_subject(subject: str) -> tuple[str | None, str | None, bool, str, str | None]:
    """-> (type, scope, breaking, description, pr_number)."""
    pr = None
    m = PR_SUFFIX.search(subject)
    if m:
        pr = m.group("num")
        subject = subject[: m.start()]
    m = SUBJECT.match(subject.strip())
    if not m:
        return None, None, False, subject.strip(), pr
    return m.group("type"), m.group("scope"), bool(m.group("bang")), m.group("desc").strip(), pr


def generate_notes(repo: str, version: str, date: str, lines: list[str]) -> str:
    """Markdown section for one release from `<sha>\\t<subject>` lines (newest
    first, as `git log` prints them). Grouped by Conventional Commit type;
    breaking changes are listed first regardless of type."""
    groups: dict[str, list[str]] = {title: [] for _, title in NOTE_GROUPS}
    other: list[str] = []
    breaking: list[str] = []
    type_to_title = dict(NOTE_GROUPS)

    for line in lines:
        if not line.strip():
            continue
        sha, _, subject = line.partition("\t")
        ctype, scope, bang, desc, pr = parse_subject(subject)
        ref = f"[#{pr}](https://github.com/{repo}/pull/{pr})" if pr else f"`{sha[:10]}`"
        text = f"{scope}: {desc}" if scope else desc
        item = f"- {text} ({ref})"
        if bang:
            breaking.append(item)
        title = type_to_title.get(ctype or "")
        (groups[title] if title else other).append(item)

    out = [f"## v{version} ({date})", ""]
    if breaking:
        out += ["### Breaking changes", "", *breaking, ""]
    for _, title in NOTE_GROUPS:
        if groups[title]:
            out += [f"### {title}", "", *groups[title], ""]
    if other:
        out += ["### Other", "", *other, ""]
    if len(out) == 2:
        out += ["_No changes recorded since the previous release._", ""]
    return "\n".join(out)


# --- changelog --------------------------------------------------------------


def _section_span(text: str, version: str) -> tuple[int, int] | None:
    """(start, end) of the `## vX.Y.Z` section, end exclusive (next `## ` or EOF)."""
    heads = list(re.finditer(r"^## v?(\S+)", text, re.M))
    for i, h in enumerate(heads):
        if normalize_version(h.group(1)) == normalize_version(version) if SEMVER.match(h.group(1)) else False:
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            return h.start(), end
    return None


def insert_changelog_section(text: str, version: str, section: str) -> tuple[str, str]:
    """Insert `section` as the newest entry (or replace an existing entry for
    the same version). Returns (new_text, "inserted"|"replaced"). An empty or
    missing changelog gets the standard header."""
    section = section.rstrip("\n") + "\n\n"
    if not text.strip():
        return CHANGELOG_HEADER + "\n" + section, "inserted"
    span = _section_span(text, version)
    if span:
        s, e = span
        return text[:s] + section + text[e:].lstrip("\n"), "replaced"
    first = re.search(r"^## ", text, re.M)
    if first:
        return text[: first.start()] + section + text[first.start():], "inserted"
    return text.rstrip("\n") + "\n\n" + section, "inserted"


def extract_changelog_section(text: str, version: str) -> str | None:
    """Body of the section (without its `## ` heading), or None."""
    span = _section_span(text, version)
    if not span:
        return None
    s, e = span
    body = text[s:e].split("\n", 1)[1] if "\n" in text[s:e] else ""
    return body.strip("\n") + "\n"


# --- CLI --------------------------------------------------------------------


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="release_tools")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("normalize")
    s.add_argument("version")

    s = sub.add_parser("is-greater")
    s.add_argument("version")
    s.add_argument("latest")

    s = sub.add_parser("read-file")
    s.add_argument("path")
    s.add_argument("pattern")

    s = sub.add_parser("bump-file")
    s.add_argument("path")
    s.add_argument("pattern")
    s.add_argument("version")

    s = sub.add_parser("notes")
    s.add_argument("repo")
    s.add_argument("version")
    s.add_argument("date")

    s = sub.add_parser("changelog-insert")
    s.add_argument("path")
    s.add_argument("version")
    s.add_argument("section_file")

    s = sub.add_parser("changelog-extract")
    s.add_argument("path")
    s.add_argument("version")

    a = p.parse_args(argv)
    try:
        if a.cmd == "normalize":
            print(normalize_version(a.version))
        elif a.cmd == "is-greater":
            return 0 if is_greater(a.version, a.latest) else 1
        elif a.cmd == "read-file":
            print(read_version_file(Path(a.path).read_text(), a.pattern))
        elif a.cmd == "bump-file":
            path = Path(a.path)
            new, old = bump_version_file(path.read_text(), a.pattern, normalize_version(a.version))
            path.write_text(new)
            print(old)
        elif a.cmd == "notes":
            print(generate_notes(a.repo, normalize_version(a.version), a.date, sys.stdin.read().splitlines()), end="")
        elif a.cmd == "changelog-insert":
            path = Path(a.path)
            text = path.read_text() if path.exists() else ""
            new, what = insert_changelog_section(text, a.version, Path(a.section_file).read_text())
            path.write_text(new)
            print(what)
        elif a.cmd == "changelog-extract":
            body = extract_changelog_section(Path(a.path).read_text(), a.version)
            if body is None:
                print(f"no section for v{normalize_version(a.version)} in {a.path}", file=sys.stderr)
                return 1
            print(body, end="")
    except (ValueError, OSError) as e:
        print(f"release_tools: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
