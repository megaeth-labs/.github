"""Drive release-settle's "Ensure the settle PR" step, extracted from its
action.yml, against a real local remote. Only GitHub's PR and ref API is
faked; the settle branch, merges and pushes are real git."""

import json
import os
import pathlib
import re
import subprocess
import tempfile
import unittest

import yaml

import release_tools as rt

ACTIONS = pathlib.Path(__file__).resolve().parent.parent
VERSION = "1.1.0"
BRANCH = "release-v1.1.0"
HEAD = "chore/release-settle-v1.1.0"
AUTHOR = "mega-gutenberg[bot]"

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys

path = pathlib.Path(os.environ["PR_STATE"])
state = json.loads(path.read_text())
args = sys.argv[1:]
remote = os.environ["FAKE_REMOTE"]
def option(flag):
    return args[args.index(flag) + 1]
def save(event):
    state["events"].append(event)
    path.write_text(json.dumps(state))
def git(*cmd):
    who = {"GIT_AUTHOR_NAME": "rival", "GIT_AUTHOR_EMAIL": "rival@example.invalid",
           "GIT_COMMITTER_NAME": "rival", "GIT_COMMITTER_EMAIL": "rival@example.invalid"}
    return subprocess.run(["git", "-C", remote, *cmd], check=True, text=True,
                          capture_output=True, env={**os.environ, **who}).stdout.strip()
def add_pr(head, base, title, body, labels=()):
    number = len(state["pulls"]) + 1
    pr = {"number": number, "url": f"https://example.invalid/pull/{number}", "state": "open",
          "author": {"login": os.environ["PR_AUTHOR"]}, "headRefName": head, "baseRefName": base,
          "title": title, "body": body, "labels": list(labels)}
    state["pulls"].append(pr)
    return pr
def concurrent_settle(commit):
    # Another run pushes its own settle branch and opens its PR first.
    sha = git("commit-tree", f"{commit}^{{tree}}", "-p", commit, "-m", "chore(release): settle v1.1.0")
    git("update-ref", "refs/heads/" + os.environ["HEAD_BRANCH"], sha)
    add_pr(os.environ["HEAD_BRANCH"], os.environ["BRANCH"], "chore(release): settle v1.1.0",
           f"<!-- release-settle: v1.1.0 {commit} -->\n")

if args[:2] == ["pr", "list"]:
    fields = option("--json").split(",")
    pulls = [pr for pr in state["pulls"] if pr["state"] == "open"
             and pr["headRefName"] == option("--head") and pr["baseRefName"] == option("--base")]
    print(json.dumps([{key: pr[key] for key in fields} for pr in pulls]))
elif args[:2] == ["pr", "create"]:
    if state.pop("race_create", False):
        # The competitor's PR has the same head, created between our list and create.
        add_pr(option("--head"), option("--base"), "stale title", "")
        save("create-lost")
        sys.exit(f'a pull request for branch "{option("--head")}" into branch "{option("--base")}" '
                 f'already exists:\nhttps://example.invalid/pull/{len(state["pulls"])}')
    if any(pr["state"] == "open" and pr["headRefName"] == option("--head")
           and pr["baseRefName"] == option("--base") for pr in state["pulls"]):
        sys.exit("a pull request for this branch already exists")
    pr = add_pr(option("--head"), option("--base"), option("--title"),
                pathlib.Path(option("--body-file")).read_text(),
                [args[i + 1] for i, arg in enumerate(args) if arg == "--label"])
    save("create")
    print(pr["url"])
elif args[:2] == ["pr", "edit"]:
    pr = state["pulls"][int(args[2]) - 1]
    assert pr["state"] == "open"
    if "--title" in args:
        pr["title"] = option("--title")
    pr["body"] = pathlib.Path(option("--body-file")).read_text()
    save("edit")
    print(pr["url"])
elif args[:2] == ["pr", "close"]:
    pr = state["pulls"][int(args[2]) - 1]
    pr["state"] = "closed"
    save("close")
elif args[:3] == ["api", "-X", "DELETE"]:
    ref = args[3].split("/git/refs/", 1)[1]
    mode = state.pop("delete_mode", "")
    if mode != "concurrent-creator":
        subprocess.run(["git", "-C", remote, "update-ref", "-d", f"refs/{ref}"], check=True)
    if mode == "gone":
        save("delete-422")
        sys.exit("gh: Reference does not exist (HTTP 422)")
    if mode == "concurrent-creator":
        git("update-ref", "-d", f"refs/{ref}")
        concurrent_settle(state["commit"])
    save("delete")
else:
    sys.exit(f"unexpected gh command: {args}")
'''


def ensure_script() -> str:
    action = yaml.safe_load((ACTIONS / "release-settle" / "action.yml").read_text())
    [step] = [s for s in action["runs"]["steps"] if s.get("name") == "Ensure the settle PR"]
    return step["run"]


def publish_marker_pattern() -> re.Pattern:
    """The pattern release-publish greps the merged PR body with."""
    text = (ACTIONS / "release-publish" / "action.yml").read_text()
    return re.compile(re.search(r"grep -oE '(<!-- release-settle: [^']*)'", text)[1])


class EnsureSettlePR(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="settle-test-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.tmp)], check=True)
        self.remote = self.tmp / "remote.git"
        self.repo = self.tmp / "repo"
        self.state = self.tmp / "prs.json"
        self.out = self.tmp / "output"
        self.script = self.tmp / "ensure.sh"
        self.script.write_text(ensure_script())
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text(FAKE_GH)
        (bin_dir / "gh").chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
            "AUTH_WRAPPER": str(ACTIONS / "git-auth" / "with-github-auth.sh"),
            "GITHUB_AUTH_TOKEN": "fixture-token", "GH_TOKEN": "fixture-token",
            "VERSION": VERSION, "BRANCH": BRANCH, "HEAD_BRANCH": HEAD,
            "CHANGELOG": "CHANGELOG.md", "PR_LABELS": "release", "PR_AUTHOR": AUTHOR,
            "TOOLS": str(ACTIONS / "release-tools" / "release_tools.py"),
            "RUNNER_TEMP": str(self.tmp), "GITHUB_OUTPUT": str(self.out),
            "GITHUB_REPOSITORY": "megaeth-labs/fake", "PR_STATE": str(self.state),
            "FAKE_REMOTE": str(self.remote),
        }
        self.git("init", "--quiet", "--bare", "--initial-branch=main", str(self.remote), cwd=self.tmp)
        self.git("clone", "--quiet", str(self.remote), str(self.repo), cwd=self.tmp)
        self.git("config", "user.name", AUTHOR)
        self.git("config", "user.email", "bot@users.noreply.github.com")
        self.commit_file("VERSION", "1.0.0\n", "feat: initial release")
        self.commit_file("CHANGELOG.md", "# Changelog\n\n## v1.0.0 (2025-01-01)\n\n- shipped\n", "docs: changelog")
        self.git("push", "--quiet", "origin", "main")
        self.git("checkout", "--quiet", "-b", BRANCH)
        self.commit_file("VERSION", "1.1.0\n", "chore(release): candidate v1.1.0")
        self.git("push", "--quiet", "origin", BRANCH)
        self.state.write_text(json.dumps({"pulls": [], "events": []}))

    def git(self, *args, cwd=None):
        return subprocess.run(["git", *args], cwd=cwd or self.repo, env=self.env, check=True,
                              text=True, capture_output=True).stdout.strip()

    def commit_file(self, name, content, message):
        (self.repo / name).write_text(content)
        self.git("add", name)
        self.git("commit", "--quiet", "-m", message)

    def advance(self, line):
        self.git("checkout", "--quiet", "-B", BRANCH, f"origin/{BRANCH}")
        self.commit_file("fixes", line + "\n", f"fix: {line}")
        self.git("push", "--quiet", "origin", BRANCH)
        return self.git("rev-parse", "HEAD")

    def remote_head(self, branch):
        return self.git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", cwd=self.remote)

    def tip(self):
        return self.remote_head(BRANCH)

    def pulls(self):
        return json.loads(self.state.read_text())["pulls"]

    def events(self):
        return json.loads(self.state.read_text())["events"]

    def patch_state(self, **changes):
        state = json.loads(self.state.read_text())
        state.update(changes)
        self.state.write_text(json.dumps(state))

    def settle(self, commit, check=True):
        notes = self.tmp / "notes.md"
        notes.write_text(f"## v{VERSION} (2026-01-01)\n\n- fix: up to {commit[:10]}\n")
        self.out.write_text("")
        self.git("fetch", "--quiet", "origin")
        result = subprocess.run(["bash", str(self.script)], cwd=self.repo, text=True, capture_output=True,
                                env={**self.env, "COMMIT": commit, "NOTES": str(notes)})
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def assert_one_open_pr_settling(self, commit):
        open_prs = [pr for pr in self.pulls() if pr["state"] == "open"]
        self.assertEqual(len(open_prs), 1, open_prs)
        [pr] = open_prs
        body = pr["body"]
        self.assertEqual(re.findall(r"<!-- release-settle: v1\.1\.0 ([0-9a-f]{40}) -->", body), [commit])
        # The marker sits on its own line, outside any blockquote.
        self.assertIn(f"\n<!-- release-settle: v{VERSION} {commit} -->\n", body)
        # Both consumers of the marker read it back as this commit.
        self.assertEqual(re.findall(r"[0-9a-f]{40}", publish_marker_pattern().search(body)[0]), [commit])
        decision = rt.route({
            "kind": "settle", "event": "push", "sha": "f" * 40, "first_parent": commit,
            "ref_name": BRANCH, "default_branch": "main", "prefix": "release-v",
            "pr_author": AUTHOR, "tag_exists": False, "release_exists": False,
            "version_at_sha": VERSION, "latest_tag": "v1.0.0", "branches": [], "dispatch_version": "",
            "pulls": [{"number": pr["number"], "merged_at": "2026-01-01T00:00:00Z",
                       "merge_commit_sha": "f" * 40, "head": {"ref": HEAD}, "base": {"ref": BRANCH},
                       "user": {"login": AUTHOR}, "body": body}],
        })
        self.assertEqual(decision["action"], "publish", decision)
        self.assertEqual(decision["commit"], "f" * 40)
        self.assertIn(f"pr_url={pr['url']}", self.out.read_text().splitlines())
        return pr

    def test_title_is_conventional(self):
        tip = self.tip()
        self.settle(tip)
        [pr] = self.pulls()
        self.assertRegex(pr["title"], r"^chore\(release\): \S.*$")
        self.assertTrue(rt.RELEASE_COMMIT.match(pr["title"]))
        self.assertIn(f"v{VERSION}", pr["title"])

    def test_refresh_keeps_the_pr_and_moves_the_marker(self):
        first = self.tip()
        self.settle(first)
        pr = self.assert_one_open_pr_settling(first)
        old_head = self.remote_head(HEAD)
        second = self.advance("second fix")
        self.settle(second)
        refreshed = self.assert_one_open_pr_settling(second)
        self.assertEqual(refreshed["number"], pr["number"])
        self.assertEqual(len(self.pulls()), 1)
        new_head = self.remote_head(HEAD)
        self.git("merge-base", "--is-ancestor", old_head, new_head)
        self.git("merge-base", "--is-ancestor", second, new_head)
        self.assertEqual(self.events(), ["create", "edit"])

    def test_up_to_date_rerun_is_a_noop(self):
        tip = self.tip()
        self.settle(tip)
        head = self.remote_head(HEAD)
        state = self.state.read_text()
        result = self.settle(tip)
        self.assertIn("settle PR is up to date", result.stdout)
        self.assertEqual(self.state.read_text(), state)
        self.assertEqual(self.remote_head(HEAD), head)
        self.assert_one_open_pr_settling(tip)

    def test_old_title_is_refreshed_without_a_commit(self):
        tip = self.tip()
        self.settle(tip)
        head = self.remote_head(HEAD)
        state = json.loads(self.state.read_text())
        state["pulls"][0]["title"] = "chore(release): settle v1.1.0"
        self.state.write_text(json.dumps(state))
        self.settle(tip)
        self.assertEqual(self.remote_head(HEAD), head)
        self.assertEqual(self.events(), ["create", "edit"])
        self.assertNotEqual(self.pulls()[0]["title"], "chore(release): settle v1.1.0")

    def test_create_race_recovers_on_the_existing_pr(self):
        tip = self.tip()
        self.patch_state(race_create=True)
        result = self.settle(tip)
        self.assertIn("concurrent run opened the settle PR first", result.stdout)
        pr = self.assert_one_open_pr_settling(tip)
        self.assertEqual(pr["number"], 1)
        self.assertEqual(self.events(), ["create-lost", "edit"])

    def test_stale_ref_already_deleted(self):
        tip = self.tip()
        self.settle(tip)
        self.patch_state(pulls=[{**self.pulls()[0], "state": "closed"}])
        self.patch_state(delete_mode="gone")
        result = self.settle(tip)
        self.assertIn("already deleted", result.stdout)
        self.assert_one_open_pr_settling(tip)
        self.assertEqual(self.events()[-2:], ["delete-422", "create"])

    def test_concurrent_creator_after_delete(self):
        tip = self.tip()
        self.settle(tip)
        self.patch_state(pulls=[{**self.pulls()[0], "state": "closed"}])
        self.patch_state(delete_mode="concurrent-creator", commit=tip)
        result = self.settle(tip)
        self.assertIn("push of a fresh", result.stdout)
        pr = self.assert_one_open_pr_settling(tip)
        self.assertEqual(pr["number"], 2)
        self.assertEqual(len(self.pulls()), 2)
        self.assertEqual(self.events()[-2:], ["delete", "edit"])

    def test_failed_changelog_commit_pushes_nothing_and_a_rerun_recovers(self):
        first = self.tip()
        self.settle(first)
        head = self.remote_head(HEAD)
        second = self.advance("third fix")
        hooks = self.tmp / "hooks"
        hooks.mkdir()
        (hooks / "pre-commit").write_text("#!/bin/sh\nexit 1\n")
        (hooks / "pre-commit").chmod(0o755)
        self.git("config", "core.hooksPath", str(hooks))
        result = self.settle(second, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("nothing pushed", result.stdout)
        self.assertEqual(self.remote_head(HEAD), head)
        self.assertEqual(self.events(), ["create"])
        self.git("config", "--unset", "core.hooksPath")
        self.settle(second)
        self.assert_one_open_pr_settling(second)
        self.git("merge-base", "--is-ancestor", head, self.remote_head(HEAD))


if __name__ == "__main__":
    unittest.main()
