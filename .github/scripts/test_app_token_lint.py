#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import app_token_lint
from app_token_lint import lint_source

SCRIPT = Path(app_token_lint.__file__)
TOKEN_ACTION = "actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1 # v3"
APPS = {
    "maxwell": ("${{ vars.MEGA_MAXWELL_CLIENT_ID }}", "${{ secrets.MEGA_MAXWELL_PK }}"),
    "legacy": ("${{ secrets.CI_APP_ID }}", "${{ secrets.MEGA_CI_APP_PK }}"),
    "gutenberg": ("${{ vars.RELEASE_APP_CLIENT_ID }}", "${{ secrets.RELEASE_APP_PRIVATE_KEY }}"),
    "other": ("${{ vars.SOMETHING_ELSE_ID }}", "${{ secrets.SOMETHING_ELSE_KEY }}"),
}
LINE = re.compile(r"^::error file=(?P<file>[^:]*)::(?P<job>[^/]+)/(?P<step>.+?): (?P<rule>\w+): ")


def job(name="build", *, environment=None, app="maxwell", permissions=None, repositories=None,
        release_step=False, run=None, job_if=None):
    lines = [f"  {name}:", "    runs-on: ubuntu-24.04"]
    if job_if is not None:
        lines.append(f"    if: {job_if}")
    if environment is not None:
        lines.append(f"    environment: {environment}")
    lines.append("    steps:")
    if release_step:
        lines.append("      - uses: megaeth-labs/.github/.github/actions/release-settle@main")
    if app:
        client, key = APPS[app]
        lines += [f"      - uses: {TOKEN_ACTION}", "        id: token", "        with:",
                  f"          client-id: {client}", f"          private-key: {key}", "          owner: megaeth-labs"]
        if repositories:
            lines.append("          repositories: |")
            lines += [f"            {r}" for r in repositories]
        for permission, value in (permissions or {}).items():
            lines.append(f"          permission-{permission}: {value}")
    if run is not None:
        lines += ["      - run: |", f"          {run}"]
    return "\n".join(lines) + "\n"


def workflow(*jobs, top=""):
    return "name: t\non: push\n" + top + "jobs:\n" + "".join(jobs)


def lint(path, text, repo="my-repo"):
    return lint_source(path, text, repo)


def rules(lines):
    return [(m["rule"], m["job"]) for m in (LINE.match(line) for line in lines)]


class L1Maxwell(unittest.TestCase):
    def test_pull_requests_and_issues_write_and_contents_read_pass(self):
        text = workflow(job(permissions={"contents": "read", "pull-requests": "write", "issues": "write"}))
        self.assertEqual(lint("ci.yml", text), [])

    def test_contents_write_fails_with_the_documented_line(self):
        lines = lint("ci.yml", workflow(job(permissions={"contents": "write"})))
        self.assertEqual(rules(lines), [("L1", "build")])
        self.assertTrue(lines[0].startswith("::error file=ci.yml::build/token: L1: "))

    def test_older_app_names_are_maxwell_too(self):
        lines = lint("ci.yml", workflow(job(app="legacy", permissions={"workflows": "write"})))
        self.assertEqual(rules(lines), [("L1", "build")])

    def test_unverifiable_permission_fails(self):
        lines = lint("ci.yml", workflow(job(permissions={"contents": "${{ inputs.level }}"})))
        self.assertEqual(rules(lines), [("L1", "build")])

    def test_other_apps_are_not_checked(self):
        self.assertEqual(lint("ci.yml", workflow(job(app="other", permissions={"contents": "write"}))), [])


class L6ExplicitPermissions(unittest.TestCase):
    def test_maxwell_token_without_permissions_fails(self):
        # create-github-app-token without permission-* returns the
        # installation's full set, contents write included.
        for app in ("maxwell", "legacy"):
            with self.subTest(app=app):
                lines = lint("ci.yml", workflow(job(app=app)))
                self.assertEqual(rules(lines), [("L6", "build")])
                self.assertTrue(lines[0].startswith("::error file=ci.yml::build/token: L6: Maxwell token requests no permission-* inputs"))

    def test_gutenberg_token_without_permissions_fails_even_in_release(self):
        text = workflow(job(app="gutenberg", environment="release", release_step=True))
        self.assertEqual(rules(lint("release-settle.yml", text)), [("L6", "build")])

    def test_any_app_token_in_a_release_job_needs_permissions(self):
        self.assertEqual(rules(lint("ci.yml", workflow(job(app="other", release_step=True)))), [("L6", "build")])
        text = workflow(job(app="other", environment="release"))
        self.assertEqual(rules(lint("release-candidate.yml", text)), [("L6", "build")])

    def test_other_app_outside_release_jobs_is_not_checked(self):
        self.assertEqual(lint("ci.yml", workflow(job(app="other"))), [])

    def test_a_single_read_permission_is_enough(self):
        self.assertEqual(lint("ci.yml", workflow(job(permissions={"contents": "read"}))), [])


class L2GutenbergEnvironment(unittest.TestCase):
    WRITE = {"contents": "write", "pull-requests": "write"}

    def test_release_environment_as_string_passes(self):
        self.assertEqual(lint("release-candidate.yml", workflow(job(app="gutenberg", environment="release", permissions=self.WRITE))), [])

    def test_release_environment_as_mapping_passes(self):
        text = workflow(job(app="gutenberg", environment="{ name: release }", permissions=self.WRITE))
        self.assertEqual(lint("release-settle.yml", text), [])

    def test_publish_environment_with_only_contents_read_passes(self):
        text = workflow(job(app="gutenberg", environment="publish", permissions={"contents": "read"}, repositories=["rust-rocksdb"]))
        self.assertEqual(lint("on-release.yml", text), [])

    def test_no_environment_fails(self):
        self.assertEqual(rules(lint("ci.yml", workflow(job(app="gutenberg", permissions=self.WRITE)))), [("L2", "build")])

    def test_other_environment_fails(self):
        text = workflow(job(app="gutenberg", environment="staging", permissions={"contents": "read"}))
        self.assertEqual(rules(lint("ci.yml", text)), [("L2", "build")])

    def test_publish_environment_with_write_fails(self):
        text = workflow(job(app="gutenberg", environment="publish", permissions={"contents": "write"}))
        self.assertEqual(rules(lint("on-release.yml", text)), [("L2", "build")])

    def test_publish_environment_with_more_than_contents_read_fails(self):
        text = workflow(job(app="gutenberg", environment="publish", permissions={"contents": "read", "pull-requests": "read"}))
        self.assertEqual(rules(lint("on-release.yml", text)), [("L2", "build")])


class L3ReleaseWorkflows(unittest.TestCase):
    def test_maxwell_token_in_a_workflow_using_a_release_action_fails(self):
        text = workflow(job(release_step=True, permissions={"contents": "read"}))
        self.assertEqual(rules(lint("ci.yml", text)), [("L3", "build")])

    def test_maxwell_token_in_on_release_fails_by_name(self):
        text = workflow(job(permissions={"contents": "read"}))
        self.assertEqual(rules(lint("on-release.yml", text)), [("L3", "build")])

    def test_read_only_maxwell_token_outside_release_workflows_passes(self):
        text = workflow(job(permissions={"contents": "read"}, repositories=["rust-rocksdb"]))
        self.assertEqual(lint("snapshot-publish.yml", text), [])

    def test_dependency_read_token_naming_the_repository_fails(self):
        text = workflow(job(app="gutenberg", environment="release", permissions={"contents": "read"}, repositories=["pstd", "My-Repo"]))
        self.assertEqual(rules(lint("on-release.yml", text)), [("L3", "build")])

    def test_owner_qualified_repository_name_is_still_the_repository(self):
        text = workflow(job(app="gutenberg", environment="release", permissions={"contents": "read"}, repositories=["megaeth-labs/my-repo"]))
        self.assertEqual(rules(lint("on-release.yml", text)), [("L3", "build")])

    def test_dependency_read_token_naming_only_dependencies_passes(self):
        text = workflow(job(app="gutenberg", environment="release", permissions={"contents": "read"}, repositories=["rust-rocksdb", "pstd"]))
        self.assertEqual(lint("on-release.yml", text), [])

    def test_write_token_for_the_repository_itself_passes(self):
        text = workflow(job(app="gutenberg", environment="release", release_step=True,
                            permissions={"contents": "write", "pull-requests": "write"}, repositories=["my-repo"]))
        self.assertEqual(lint("release-candidate.yml", text), [])

    def test_without_a_repository_name_the_own_repository_check_is_skipped(self):
        text = workflow(job(app="gutenberg", environment="release", permissions={"contents": "read"}, repositories=["my-repo"]))
        self.assertEqual(lint_source("on-release.yml", text, None), [])


class L4MaxwellIdentity(unittest.TestCase):
    def test_git_identity_in_a_release_step_fails(self):
        text = workflow(job(app=None, environment="release", release_step=True, run='git config user.name "mega-maxwell[bot]"'))
        self.assertEqual(rules(lint("release-settle.yml", text)), [("L4", "build")])

    def test_pr_author_filter_in_a_release_job_condition_fails(self):
        text = workflow(job(app=None, release_step=True, job_if="\"github.event.pull_request.user.login == 'mega-maxwell[bot]'\""))
        lines = lint("release-publish.yml", text)
        self.assertEqual(rules(lines), [("L4", "build")])
        self.assertIn("build/-: L4:", lines[0])

    def test_workflow_level_value_fails(self):
        text = workflow(job(app=None, release_step=True), top="env:\n  BOT: mega-maxwell[bot]\n")
        self.assertEqual(rules(lint("release-publish.yml", text)), [("L4", "(workflow)")])

    def test_same_identity_outside_a_release_workflow_passes(self):
        text = workflow(job(app=None, run='git config user.name "mega-maxwell[bot]"'))
        self.assertEqual(lint("ci.yml", text), [])

    def test_gutenberg_identity_in_a_release_workflow_passes(self):
        text = workflow(job(app=None, environment="release", release_step=True, run='git config user.name "mega-gutenberg[bot]"'))
        self.assertEqual(lint("release-settle.yml", text), [])


class L5ReleaseEnvironment(unittest.TestCase):
    def test_release_environment_in_another_file_fails(self):
        self.assertEqual(rules(lint("ci.yml", workflow(job(app=None, environment="release")))), [("L5", "build")])

    def test_release_environment_as_mapping_in_another_file_fails(self):
        text = workflow(job(app=None, environment="{ name: release }"))
        self.assertEqual(rules(lint("release-publish.yml", text)), [("L5", "build")])

    def test_release_environment_in_the_three_allowed_files_passes(self):
        text = workflow(job(app=None, environment="release"))
        for name in ("release-candidate.yml", "release-settle.yml", "on-release.yml"):
            with self.subTest(name):
                self.assertEqual(lint(name, text), [])

    def test_other_environments_are_free(self):
        self.assertEqual(lint("ci.yml", workflow(job(app=None, environment="publish"))), [])


class MalformedInput(unittest.TestCase):
    def assert_parse_error(self, text, where="-/-"):
        lines = lint("bad.yml", text)
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith(f"::error file=bad.yml::{where}: parse: "), lines[0])

    def test_broken_yaml_is_an_error_line_not_a_traceback(self):
        self.assert_parse_error("jobs:\n  a: [unclosed\n")

    def test_empty_file_is_an_error(self):
        self.assert_parse_error("")

    def test_scalar_document_is_an_error(self):
        self.assert_parse_error("just a string\n")

    def test_jobs_that_is_a_list_is_an_error(self):
        self.assert_parse_error("jobs:\n  - a\n")

    def test_a_job_that_is_not_a_mapping_is_an_error(self):
        self.assert_parse_error("jobs:\n  build: nope\n", "build/-")

    def test_a_step_that_is_not_a_mapping_is_an_error(self):
        self.assert_parse_error("jobs:\n  build:\n    steps:\n      - just-a-string\n", "build/#1")

    def test_token_step_without_with_is_ignored(self):
        text = ("jobs:\n  build:\n    runs-on: x\n    steps:\n"
                "      - uses: actions/create-github-app-token@v3\n"
                "      - uses: actions/create-github-app-token@v3\n        with:\n"
                "      - run: echo\n")
        self.assertEqual(lint("ci.yml", text), [])


class CommandLine(unittest.TestCase):
    def run_cli(self, *args, repository=None):
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_REPOSITORY"}
        if repository:
            env["GITHUB_REPOSITORY"] = repository
        return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], capture_output=True, text=True, env=env)

    def directory(self, files):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for name, text in files.items():
            Path(tmp.name, name).write_text(text)
        return tmp.name

    def test_clean_directory_exits_zero(self):
        directory = self.directory({"release-settle.yml": workflow(job(app="gutenberg", environment="release", release_step=True, permissions={"contents": "write"})),
                                    "release-settle.properties.json": "{not yaml"})
        result = self.run_cli("--repo", "my-repo", directory)
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertIn("1 file(s) clean", result.stdout)

    def test_violations_exit_one_with_error_lines_naming_the_file(self):
        directory = self.directory({"ci.yml": workflow(job(permissions={"contents": "write"}))})
        result = self.run_cli("--repo", "my-repo", directory)
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"::error file={directory}/ci.yml::build/token: L1: ", result.stdout)

    def test_malformed_file_exits_one_without_a_traceback(self):
        directory = self.directory({"bad.yml": "jobs:\n  a: [unclosed\n"})
        result = self.run_cli("--repo", "my-repo", directory)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("::error file=", result.stdout)

    def test_missing_path_and_empty_directory_exit_one(self):
        empty = self.directory({})
        for target in (empty + "/nope.yml", empty):
            with self.subTest(target):
                result = self.run_cli("--repo", "my-repo", target)
                self.assertEqual(result.returncode, 1)
                self.assertIn("::error file=", result.stdout)

    def test_repository_defaults_to_github_repository(self):
        directory = self.directory({"on-release.yml": workflow(job(app="gutenberg", environment="release", permissions={"contents": "read"}, repositories=["my-repo"]))})
        self.assertEqual(self.run_cli(directory, repository="megaeth-labs/my-repo").returncode, 1)
        unknown = self.run_cli(directory)
        self.assertEqual(unknown.returncode, 0)
        self.assertIn("::warning::", unknown.stdout)


if __name__ == "__main__":
    unittest.main()
