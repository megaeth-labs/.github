#!/usr/bin/env python3
"""Nothing this repository ships may force-push a branch.

The release pipeline is built so that no branch is ever rewritten: settle and
candidate re-runs supersede (close the PR, delete the branch, push a new ref)
instead. Consumers run it under rulesets that ban force pushes on every
branch, so one forced push anywhere breaks a release. This scans every file
under the shipped actions and workflow templates and fails on any push that
could rewrite a ref. `git fetch --force` of a tag refspec only updates the
runner's local copy and is allowed, explicitly, below.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHIPPED = [ROOT / ".github" / "actions", ROOT / "workflow-templates"]

# `git [global options] push ...`, up to the end of that command.
GIT_PUSH = re.compile(r"\bgit\b(?:\s+(?:-C\s+\S+|-c\s+\S+|--[\w-]+(?:=\S+)?))*\s+push\b(?P<args>[^;&|)\n]*)")
GIT_FETCH = re.compile(r"\bgit\b(?:\s+(?:-C\s+\S+|-c\s+\S+|--[\w-]+(?:=\S+)?))*\s+fetch\b(?P<args>[^;&|)\n]*)")
FORCING_ARG = re.compile(
    r"""(?:^|\s)["']?(?:
        --force(?:-with-lease|-if-includes)?(?:=\S*)?   # --force, --force-with-lease[=...]
      | --mirror                                        # mirror pushes force every ref
      | -[a-zA-Z]*f[a-zA-Z]*                            # -f, -fq, -uf ...
      | \+\S+                                           # +refspec
    )(?=\s|["']|$)""",
    re.X,
)
# Other ways to rewrite a ref: the action that force-pushes its branch when
# it updates a PR, and a forced ref update through the API.
OTHER = [
    (re.compile(r"peter-evans/create-pull-request"), "create-pull-request force-pushes the PR branch it updates"),
    (re.compile(r"(?:-[fF]|--(?:raw-)?field)\s+force=true"), "a ref update through the API with force=true"),
]


def logical_lines(text: str):
    """(line number, line) with backslash continuations joined."""
    start, buf = None, []
    for n, line in enumerate(text.splitlines(), 1):
        if start is None:
            start = n
        if line.rstrip().endswith("\\"):
            buf.append(line.rstrip()[:-1])
            continue
        buf.append(line)
        yield start, " ".join(buf)
        start, buf = None, []
    if buf:
        yield start, " ".join(buf)


def violations(text: str):
    """(line, reason, source) for every ref rewrite in `text`."""
    found = []
    for n, line in logical_lines(text):
        for m in GIT_PUSH.finditer(line):
            arg = FORCING_ARG.search(m["args"])
            if arg:
                found.append((n, f"git push with {arg.group().strip()!r}", line.strip()))
        for pattern, reason in OTHER:
            if pattern.search(line):
                found.append((n, reason, line.strip()))
    return found


def forced_fetches(text: str):
    """`git fetch --force` lines. (A `+` refspec into refs/remotes/ is the
    ordinary way to refresh a remote-tracking ref and is not listed.)"""
    return [line.strip() for _, line in logical_lines(text)
            if any(re.search(r"(?:^|\s)(?:--force|-[a-zA-Z]*f[a-zA-Z]*)(?=\s|$)", m["args"])
                   for m in GIT_FETCH.finditer(line))]


def shipped_files():
    for top in SHIPPED:
        for path in sorted(top.rglob("*")):
            if path.is_file() and path.name != Path(__file__).name:
                try:
                    yield path, path.read_text()
                except UnicodeDecodeError:
                    continue


class NothingShippedForcePushes(unittest.TestCase):
    def test_no_shipped_file_rewrites_a_ref(self):
        found = [f"{path.relative_to(ROOT)}:{n}: {reason}: {src}"
                 for path, text in shipped_files() for n, reason, src in violations(text)]
        self.assertEqual(found, [], "a shipped file can rewrite a branch:\n" + "\n".join(found))

    def test_the_scan_sees_the_shipped_pushes(self):
        # A scan that matches nothing proves nothing: the candidate and settle
        # pushes must be in view.
        pushing = {path.parent.name for path, text in shipped_files()
                   if any(GIT_PUSH.search(line) for _, line in logical_lines(text))}
        self.assertLessEqual({"release-candidate", "release-settle"}, pushing)

    def test_forced_tag_fetches_are_allowed_explicitly(self):
        # release-publish re-reads the tag it is about to verify with
        # `git fetch --force` on a refs/tags refspec: that only replaces the
        # runner's local tag. Every forced fetch shipped must be exactly that.
        fetches = [line for _, text in shipped_files() for line in forced_fetches(text)]
        self.assertTrue(fetches, "expected release-publish's forced tag fetches to be in view")
        for line in fetches:
            self.assertRegex(line, r'"refs/tags/[^"]+:refs/tags/[^"]+"', line)
            self.assertEqual(violations(line), [], line)


class TheScanner(unittest.TestCase):
    def assertFlags(self, text):
        self.assertTrue(violations(text), f"not flagged: {text}")

    def assertClean(self, text):
        self.assertEqual(violations(text), [], text)

    def test_forced_pushes_are_flagged(self):
        for text in [
            'git push --force origin "$head"',
            'git push --quiet --force-with-lease origin "$head"',
            'git push --force-with-lease=refs/heads/x: origin HEAD:refs/heads/x',
            'git push --force-if-includes origin x',
            'git push -f origin x',
            'git push -qf origin x',
            'git -C "$D" push --quiet origin "+HEAD:refs/heads/x"',
            "git push origin +refs/heads/a:refs/heads/a",
            "git push --mirror origin",
            'git -c http.extraHeader=x push --quiet \\\n  --force origin "$head"',
            "if git push --force origin x; then :; fi",
            "  uses: peter-evans/create-pull-request@5f6978faf089d4d20b00c7766989d076bb2fc7f1 # v8",
            'gh api -X PATCH "repos/$R/git/refs/heads/x" -f sha="$s" -F force=true',
        ]:
            with self.subTest(text=text):
                self.assertFlags(text)

    def test_plain_pushes_deletes_and_fetches_are_clean(self):
        for text in [
            'git push --quiet origin "$candidate:refs/heads/$head"',
            'git push --quiet origin "$head"',
            'git push --quiet origin ":$ref"',
            "git push --quiet -u origin main",
            'git fetch --quiet --force origin "refs/tags/$tag:refs/tags/$tag"',
            'git fetch --quiet origin "+refs/heads/$b:refs/remotes/origin/$b"',
            'echo "never force-pushed"; git push origin x',
            'gh api -X DELETE "repos/$R/git/refs/heads/$head"',
        ]:
            with self.subTest(text=text):
                self.assertClean(text)


if __name__ == "__main__":
    unittest.main()
