#!/usr/bin/env python3
"""Pure helpers shared by the release-* composite actions.

Everything git- or GitHub-facing stays in the actions' bash steps; this module
only transforms text so it can be unit-tested without a repository. stdlib only.

Subcommands (see `main`):
  route                                     -> stdin: routing JSON object; stdout: decision JSON object
  normalize   VERSION                       -> X.Y.Z on stdout, exit 1 if invalid
  is-greater  VERSION LATEST_TAG_OR_EMPTY   -> exit 0 if VERSION > LATEST, else 1
  read-file   PATH PATTERN                  -> version found in the file
  bump-file   PATH PATTERN VERSION          -> rewrite in place, print old version
  notes       REPO VERSION DATE             -> stdin: "<sha>\t<subject>" lines; stdout: markdown
                                               (DATE may be "" for a heading without a date)
  changelog-insert PATH VERSION SECTION_MD  -> insert/replace the section, print "inserted"/"replaced"
  changelog-extract PATH VERSION            -> the section body on stdout, exit 1 if absent
  changelog-copy   SRC DST VERSION          -> copy VERSION's section (with heading) from SRC into DST;
                                               prints inserted/replaced/unchanged/absent
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
# Commits the release flow itself makes (candidate bump, settle, changelog
# sync). They are bookkeeping, not changes, so they never appear in notes.
RELEASE_COMMIT = re.compile(r"^chore\(release\):")

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


# --- release routing --------------------------------------------------------


def _field(data: dict, key: str, default):
    """Return data[key], treating absent and JSON null alike; reject other types."""
    value = data.get(key)
    if value is None:
        return default
    if not isinstance(value, type(default)):
        raise ValueError(f"route field {key!r} must be {type(default).__name__}, got {value!r}")
    return value


def _items(data: dict, key: str) -> list[dict]:
    items = _field(data, key, [])
    if not all(isinstance(item, dict) for item in items):
        raise ValueError(f"route field {key!r} must be a list of objects")
    return items


def _branch_version(branch: str, prefix: str) -> str | None:
    """X.Y.Z for a release branch, None when the suffix is not a version."""
    try:
        return normalize_version(branch[len(prefix):])
    except ValueError:
        return None


def route(data: dict) -> dict:
    """Decide the next release action from an already collected snapshot."""
    if not isinstance(data, dict):
        raise ValueError("route input must be a JSON object")
    kind, event, ref = (_field(data, key, "") for key in ("kind", "event", "ref_name"))
    prefix = _field(data, "prefix", "release-v")
    sha = _field(data, "sha", "")
    result = {
        "action": "skip",
        "reason": f"no route for kind={kind}, event={event}, ref={ref}",
        "version": "",
        "release_branch": "",
        "commit": "",
        "pr_number": None,
        "targets": [],
    }
    if event == "push" and (
        (kind == "candidate" and ref == data.get("default_branch"))
        or (kind == "settle" and ref.startswith(prefix))
    ):
        candidate = kind == "candidate"
        head_prefix = "chore/release-candidate-"
        if not candidate:
            version = _branch_version(ref, prefix)
            if version is None:
                result["reason"] = (
                    f"{ref} is not a release branch: {ref[len(prefix):]!r} after {prefix!r} is not X.Y.Z"
                )
                return result
            result.update(version=version, release_branch=ref, commit=sha)
            if data.get("tag_exists") and data.get("release_exists"):
                result["reason"] = f"v{version} is already published"
                return result
        pr = next((
            pr for pr in _items(data, "pulls")
            if pr.get("merged_at") and pr.get("merge_commit_sha") == sha
            and (pr.get("base") or {}).get("ref") == ref
            and (
                str((pr.get("head") or {}).get("ref") or "").startswith(head_prefix)
                if candidate else (pr.get("head") or {}).get("ref") == f"chore/release-settle-v{version}"
            )
        ), None)
        fresh = False
        marker = None
        if pr and not candidate:
            match = re.search(
                rf"<!-- release-settle: v{re.escape(version)} ([0-9a-fA-F]{{40}}) -->",
                pr.get("body") or "",
            )
            marker = match.group(1) if match else None
            fresh = marker is not None and marker == data.get("first_parent")
        author = (pr.get("user") or {}).get("login") if pr else None
        expected_author = _field(data, "pr_author", "mega-gutenberg[bot]")
        if not candidate and data.get("tag_exists") and not (
            fresh and author == expected_author
        ):
            result["reason"] = (
                f"v{version} is tagged but has no Release: re-run the release-settle run "
                "for the settle PR's merge commit"
                f"{' ' + data['tag_commit'] if data.get('tag_commit') else ''} to finish publishing"
            )
            return result
        if pr:
            if author != expected_author:
                result["reason"] = f"PR #{pr['number']} author {author} does not match {expected_author}"
                return result
            result["pr_number"] = pr["number"]
            if candidate:
                version = normalize_version(pr["head"]["ref"][len(head_prefix):])
                result.update(
                    action="cut", reason=f"merged candidate PR #{pr['number']}",
                    version=version, release_branch=f"{prefix}{version}", commit=sha,
                )
                return result
            if fresh:
                result.update(action="publish", reason=f"merged fresh settle PR #{pr['number']}")
                return result
            settled = f"settled {marker}" if marker else "no release-settle marker"
            result["reason"] = (
                f"merged settle PR #{pr['number']} was stale ({settled}, "
                f"tip was {data.get('first_parent') or 'unknown'}); a fresh settle PR follows"
            )
        elif candidate:
            result["reason"] = "no merged candidate PR matches this push"
            return result
        elif data.get("version_at_sha") != version:
            result["reason"] = "the candidate has not landed on this branch yet"
            return result
        elif not is_greater(version, _field(data, "latest_tag", "")):
            result["reason"] = f"v{version} is not greater than latest tag {data.get('latest_tag')}"
            return result
        else:
            result["reason"] = f"refresh settle PR for v{version}"
        result.update(action="refresh", targets=[
            {"version": version, "release_branch": ref, "commit": sha},
        ])
    elif kind == "settle" and event == "workflow_dispatch":
        selected = _field(data, "dispatch_version", "")
        selected = normalize_version(selected) if selected else ""
        for branch in _items(data, "branches"):
            name = branch.get("name")
            if not isinstance(name, str) or not name.startswith(prefix) or branch.get("tag_exists"):
                continue
            version = _branch_version(name, prefix)
            if version is None:
                continue
            if (branch.get("version_at_tip") == version
                    and is_greater(version, _field(data, "latest_tag", ""))
                    and (not selected or version == selected)):
                result["targets"].append({
                    "version": version, "release_branch": name, "commit": branch.get("tip") or "",
                })
        result.update(
            action="refresh" if result["targets"] else "skip",
            reason="refresh eligible release branches" if result["targets"] else "no eligible release branches",
        )
    return result


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
        if RELEASE_COMMIT.match(subject.strip()):
            continue
        ctype, scope, bang, desc, pr = parse_subject(subject)
        ref = f"[#{pr}](https://github.com/{repo}/pull/{pr})" if pr else f"`{sha[:10]}`"
        text = f"{scope}: {desc}" if scope else desc
        item = f"- {text} ({ref})"
        if bang:
            breaking.append(item)
        title = type_to_title.get(ctype or "")
        (groups[title] if title else other).append(item)

    heading = f"## v{version}" + (f" ({date})" if date else "")
    out = [heading, ""]
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


def _tidy(text: str) -> str:
    """Exactly one blank line between blocks and one newline at EOF, so the
    result is stable under formatters like dprint/prettier."""
    return re.sub(r"\n{3,}", "\n\n", text).rstrip("\n") + "\n"


def insert_changelog_section(text: str, version: str, section: str) -> tuple[str, str]:
    """Insert `section` as the newest entry (or replace an existing entry for
    the same version). Returns (new_text, "inserted"|"replaced"). An empty or
    missing changelog gets the standard header."""
    section = section.rstrip("\n") + "\n\n"
    if not text.strip():
        return _tidy(CHANGELOG_HEADER + "\n" + section), "inserted"
    span = _section_span(text, version)
    if span:
        s, e = span
        return _tidy(text[:s] + section + text[e:].lstrip("\n")), "replaced"
    first = re.search(r"^## ", text, re.M)
    if first:
        return _tidy(text[: first.start()] + section + text[first.start():]), "inserted"
    return _tidy(text.rstrip("\n") + "\n\n" + section), "inserted"


def changelog_section_text(text: str, version: str) -> str | None:
    """The `## vX.Y.Z` section including its heading, or None."""
    span = _section_span(text, version)
    if not span:
        return None
    s, e = span
    return text[s:e].rstrip("\n") + "\n"


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

    sub.add_parser("route")

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

    s = sub.add_parser("changelog-copy")
    s.add_argument("src")
    s.add_argument("dst")
    s.add_argument("version")

    a = p.parse_args(argv)
    try:
        if a.cmd == "route":
            print(json.dumps(route(json.load(sys.stdin))))
        elif a.cmd == "normalize":
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
        elif a.cmd == "changelog-copy":
            section = changelog_section_text(Path(a.src).read_text(), a.version)
            if section is None:
                print("absent")
                return 0
            dst = Path(a.dst)
            text = dst.read_text() if dst.exists() else ""
            new, what = insert_changelog_section(text, a.version, section)
            if new == text:
                print("unchanged")
            else:
                dst.write_text(new)
                print(what)
        elif a.cmd == "changelog-extract":
            body = extract_changelog_section(Path(a.path).read_text(), a.version)
            if body is None:
                print(f"no section for v{normalize_version(a.version)} in {a.path}", file=sys.stderr)
                return 1
            print(body, end="")
    except (ValueError, OSError, TypeError, KeyError, AttributeError) as e:
        print(f"release_tools: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
