#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import yaml

import app_token_lint
import copy_templates
from copy_templates import PLACEHOLDERS, RELEASE_TEMPLATES, TEMPLATES, RenderError, check, main, parse_args, render

MEGA_RETH = [
    "--repo", "mega-reth", "--default-branch", "develop",
    "--version-file", "Cargo.toml", "--version-pattern", "toml",
    "--bump-command", "cargo update --workspace",
    "--dependency-repositories", "rust-rocksdb,pstd,rocksdb",
]


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def steps(doc, job):
    return doc["jobs"][job]["steps"]


def shared(doc, job, action):
    return [s for s in steps(doc, job) if f"/.github/actions/{action}@" in str(s.get("uses", ""))]


class MegaRethRender(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "workflows"
        code, _, err = run(MEGA_RETH + ["--out", str(cls.out)])
        assert code == 0, err
        cls.text = {name: (cls.out / name).read_text() for name in RELEASE_TEMPLATES}
        cls.doc = {name: yaml.safe_load(text) for name, text in cls.text.items()}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_writes_exactly_the_release_templates(self):
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), sorted(RELEASE_TEMPLATES))

    def test_no_placeholder_is_left(self):
        for name, text in self.text.items():
            for placeholder in PLACEHOLDERS:
                self.assertNotIn(placeholder, text, f"{name} still has {placeholder}")
            self.assertNotIn("version_file: VERSION", text, name)
            self.assertNotIn("version_pattern: plain", text, name)

    def test_triggers_use_the_default_branch(self):
        self.assertEqual(self.doc["release-candidate.yml"][True]["push"]["branches"], ["develop"])
        self.assertEqual(self.doc["app-token-lint.yml"][True]["push"]["branches"], ["develop"])
        self.assertEqual(self.doc["release-settle.yml"][True]["push"]["branches"], ["release-v*"])

    def test_every_shared_action_call_is_valid(self):
        for name, text in self.text.items():
            self.assertEqual(check(name, text), [], name)

    def test_with_keys_are_inputs_of_the_called_action(self):
        # Independent of check(): walk every step and compare against action.yml directly.
        seen = 0
        for doc in self.doc.values():
            for job in doc["jobs"].values():
                for step in job.get("steps") or []:
                    match = copy_templates.SHARED_ACTION.fullmatch(str(step.get("uses", "")))
                    if not match:
                        continue
                    action = yaml.safe_load((copy_templates.ACTIONS / match["name"] / "action.yml").read_text())
                    self.assertLessEqual(set(step.get("with") or {}), set(action.get("inputs") or {}), step["uses"])
                    seen += 1
        # Candidate propose/refresh/route/cut, settle route/refresh/publish, lint.
        self.assertEqual(seen, 8)

    def test_release_tokens_are_scoped_to_the_repository(self):
        for name, jobs in (("release-candidate.yml", ("propose", "refresh", "cut")),
                           ("release-settle.yml", ("refresh", "publish"))):
            for job in jobs:
                if job == "publish":
                    self.assertEqual(self.doc[name]["jobs"][job]["environment"], "release", job)
                else:
                    self.assertNotIn("environment", self.doc[name]["jobs"][job], job)
                token = next(s for s in steps(self.doc[name], job) if s.get("id") == "release-token")
                self.assertEqual(token["with"]["client-id"], "${{ vars.MEGA_GUTENBERG_CLIENT_ID }}", job)
                self.assertEqual(token["with"]["private-key"], "${{ secrets.MEGA_GUTENBERG_PK }}", job)
                self.assertEqual(token["with"]["repositories"], "mega-reth", job)

    def test_bump_command_reads_dependencies_with_a_read_only_token(self):
        doc = self.doc["release-candidate.yml"]
        ids = [s.get("id") for s in steps(doc, "propose")]
        self.assertLess(ids.index("dependency-token"), len(ids) - 1)
        dependency = steps(doc, "propose")[ids.index("dependency-token")]["with"]
        self.assertEqual(dependency["client-id"], "${{ vars.MEGA_GUTENBERG_CLIENT_ID }}")
        self.assertEqual(dependency["private-key"], "${{ secrets.MEGA_GUTENBERG_PK }}")
        self.assertEqual(dependency["repositories"], "rust-rocksdb,pstd,rocksdb")
        self.assertEqual({k for k in dependency if k.startswith("permission-")}, {"permission-contents"})
        self.assertEqual(dependency["permission-contents"], "read")
        (propose,) = shared(doc, "propose", "release-candidate")
        self.assertEqual(propose["with"]["bump_command"], "cargo update --workspace")
        self.assertEqual(propose["with"]["dependency_token"], "${{ steps.dependency-token.outputs.token }}")
        self.assertEqual(propose["with"]["version_file"], "Cargo.toml")
        self.assertEqual(propose["with"]["version_pattern"], "toml")

    def test_pr_labels_are_left_empty(self):
        for name, text in self.text.items():
            self.assertNotIn("pr_labels", text, name)

    def test_rendered_files_lint_clean(self):
        for name, text in self.text.items():
            self.assertEqual(app_token_lint.lint_source(name, text, "mega-reth"), [], name)


class Render(unittest.TestCase):
    def args(self, *extra):
        return parse_args(["--repo", "r", "--default-branch", "main", "--version-file", "VERSION",
                           "--version-pattern", "plain", *extra])

    def test_refuses_an_existing_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "release-candidate.yml"
            stale.write_text("old render\n")
            code, out, err = run(MEGA_RETH + ["--out", tmp])
            self.assertEqual(code, 1)
            self.assertIn("already exists", err)
            self.assertEqual(out, "")
            self.assertEqual(stale.read_text(), "old render\n")

    def test_without_out_each_render_gets_a_new_directory(self):
        dirs = []
        for _ in range(2):
            code, out, err = run(MEGA_RETH)
            self.assertEqual(code, 0, err)
            dirs.append(Path(out.splitlines()[0]).parent)
        try:
            self.assertNotEqual(dirs[0], dirs[1])
        finally:
            for d in dirs:
                for f in d.iterdir():
                    f.unlink()
                d.rmdir()

    def test_without_bump_command_the_example_stays_a_comment(self):
        text = render("release-candidate.yml", (TEMPLATES / "release-candidate.yml").read_text(), self.args())
        (propose,) = shared(yaml.safe_load(text), "propose", "release-candidate")
        self.assertNotIn("bump_command", propose["with"])
        self.assertNotIn("dependency_token", propose["with"])
        self.assertIn("#   bump_command: cargo update --workspace", text)

    def test_bump_command_without_dependencies_uses_the_job_token(self):
        text = render("release-candidate.yml", (TEMPLATES / "release-candidate.yml").read_text(),
                      self.args("--bump-command", "make bump"))
        (propose,) = shared(yaml.safe_load(text), "propose", "release-candidate")
        self.assertEqual(propose["with"]["dependency_token"], "${{ github.token }}")
        self.assertNotIn("dependency-token", text)

    def test_bump_command_with_a_hash_is_kept_whole(self):
        # Unquoted, ` # regenerate lock` would be a YAML comment and vanish.
        for command in ("make bump # regenerate lock", "make bump: all", "'quoted' && echo \"x\"",
                        "[ -f x ] || make", "@scripts/bump", "true", "123", "*glob"):
            with self.subTest(command=command):
                text = render("release-candidate.yml", (TEMPLATES / "release-candidate.yml").read_text(),
                              self.args("--bump-command", command))
                (propose,) = shared(yaml.safe_load(text), "propose", "release-candidate")
                self.assertEqual(propose["with"]["bump_command"], command)
                self.assertEqual(check("release-candidate.yml", text, {"bump_command": command}), [])

    def test_plain_values_stay_plain(self):
        text = render("release-candidate.yml", (TEMPLATES / "release-candidate.yml").read_text(),
                      self.args("--bump-command", "cargo update --workspace"))
        self.assertIn("          bump_command: cargo update --workspace\n", text)

    def test_other_substituted_values_read_back_exactly(self):
        args = self.args("--version-file", "crates/a #b/Cargo.toml", "--changelog-file", "docs/CHANGES: all.md",
                         "--default-branch", "dev,next", "--bump-command", "x",
                         "--dependency-repositories", "pstd #1")
        for name in RELEASE_TEMPLATES:
            text = render(name, (TEMPLATES / name).read_text(), args)
            doc = yaml.safe_load(text)
            self.assertEqual(check(name, text, copy_templates.expected_inputs(args)), [], name)
            if name != "release-settle.yml":
                self.assertEqual(doc[True]["push"]["branches"], ["dev,next"], name)
        text = render("release-candidate.yml", (TEMPLATES / "release-candidate.yml").read_text(), args)
        (token,) = [s for s in steps(yaml.safe_load(text), "propose") if s.get("id") == "dependency-token"]
        self.assertEqual(token["with"]["repositories"], "pstd #1")

    def test_check_reports_a_value_that_reads_back_differently(self):
        text = render("release-candidate.yml", (TEMPLATES / "release-candidate.yml").read_text(),
                      self.args("--bump-command", "make bump"))
        problems = check("release-candidate.yml", text, {"bump_command": "make bump # regenerate lock"})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("bump_command reads back as 'make bump', not 'make bump # regenerate lock'", problems[0])

    def test_refuses_an_actions_ref_that_cannot_sit_in_uses(self):
        for ref in ("main # v3", "a b", ""):
            with self.subTest(ref=ref), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.args("--actions-ref", ref)

    def test_actions_ref_pins_every_shared_action(self):
        sha = "0" * 40
        for name in RELEASE_TEMPLATES:
            text = render(name, (TEMPLATES / name).read_text(), self.args("--actions-ref", sha))
            refs = {m["ref"] for m in copy_templates.SHARED_ACTION.finditer(text)}
            self.assertEqual(refs, {sha}, name)

    def test_template_drift_is_an_error(self):
        text = (TEMPLATES / "release-candidate.yml").read_text().replace("version_file: VERSION", "version_file: X")
        with self.assertRaisesRegex(RenderError, "version file"):
            render("release-candidate.yml", text, self.args())

    def test_check_reports_an_unfilled_placeholder(self):
        text = (TEMPLATES / "app-token-lint.yml").read_text()
        self.assertEqual(check("app-token-lint.yml", text), ["app-token-lint.yml: unfilled placeholder '$default-branch'"])

    def test_check_reports_an_unknown_and_a_missing_input(self):
        text = render("release-settle.yml", (TEMPLATES / "release-settle.yml").read_text(), self.args())
        text = text.replace("          release_branch: ${{ matrix.target.release_branch }}",
                            "          release_brnach: ${{ matrix.target.release_branch }}")
        text = text.replace("          pr_number: ${{ needs.route.outputs.pr_number }}\n", "")
        problems = check("release-settle.yml", text)
        self.assertIn("release-settle.yml: refresh/2 (release-settle): 'release_brnach' is not an input", problems)
        self.assertIn("release-settle.yml: publish/2 (release-publish): required input 'pr_number' missing", problems)

    def test_templates_call_only_known_inputs(self):
        for name in RELEASE_TEMPLATES:
            problems = check(name, (TEMPLATES / name).read_text())
            self.assertEqual([p for p in problems if "placeholder" not in p], [], name)

    def test_refuses_dependencies_naming_the_repository(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.args("--bump-command", "x", "--dependency-repositories", "pstd,r")

    def test_refuses_dependencies_without_a_bump_command(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.args("--dependency-repositories", "pstd")


if __name__ == "__main__":
    unittest.main()
