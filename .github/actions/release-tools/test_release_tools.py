import contextlib
import io
import json
import unittest
from unittest.mock import patch

import release_tools as rt


class Versions(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(rt.normalize_version("v1.2.3"), "1.2.3")
        self.assertEqual(rt.normalize_version(" 0.1.0\n"), "0.1.0")
        for bad in ("1.2", "v1.2.3-rc.1", "01.2.3", "1.2.3.4", "latest", ""):
            with self.assertRaises(ValueError, msg=bad):
                rt.normalize_version(bad)

    def test_is_greater(self):
        self.assertTrue(rt.is_greater("0.1.0", ""))
        self.assertTrue(rt.is_greater("1.10.0", "v1.9.9"))
        self.assertFalse(rt.is_greater("1.9.9", "v1.10.0"))
        self.assertFalse(rt.is_greater("2.2.0", "2.2.0"))

    def test_latest_tag_ignores_tags_that_are_not_plain_releases(self):
        # git's -v:refname puts v1.2.0-rc1 above v1.2.0; it is not a release.
        tags = ["v1.2.0-rc1", "v1.2.0", "v1.10.0-beta", "vnext", "v1.9.0", "1.99.0", "v01.0.0", ""]
        self.assertEqual(rt.latest_release_tag(tags),
                         ("v1.9.0", ["v1.2.0-rc1", "v1.10.0-beta", "vnext", "1.99.0", "v01.0.0"]))
        self.assertEqual(rt.latest_release_tag(["v1.2.0-rc1"]), ("", ["v1.2.0-rc1"]))
        self.assertEqual(rt.latest_release_tag([]), ("", []))

    def test_latest_tag_can_leave_out_the_version_being_published(self):
        tags = ["v1.2.0", "v1.3.0", "v1.1.0"]
        self.assertEqual(rt.latest_release_tag(tags, "1.3.0")[0], "v1.2.0")
        self.assertEqual(rt.latest_release_tag(tags, "v1.2.0")[0], "v1.3.0")

    def test_latest_tag_cli(self):
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.stdin", io.StringIO("v1.2.0\nv1.3.0-rc1\nv1.1.0\n")), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(rt.main(["latest-tag"]), 0)
        self.assertEqual(out.getvalue(), "v1.2.0\n")
        self.assertIn("ignoring tag 'v1.3.0-rc1'", err.getvalue())
        out = io.StringIO()
        with patch("sys.stdin", io.StringIO("v1.2.0\n")), contextlib.redirect_stdout(out):
            self.assertEqual(rt.main(["latest-tag", "--exclude", "1.2.0"]), 0)
        self.assertEqual(out.getvalue(), "\n")

    def test_order_refusal_names_both_versions_and_the_rule(self):
        self.assertIsNone(rt.order_refusal("1.3.0", "v1.2.0"))
        self.assertIsNone(rt.order_refusal("1.3.0", ""))
        for latest in ("v1.3.0", "v1.10.0"):
            refusal = rt.order_refusal("1.3.0", latest)
            self.assertIn("v1.3.0 is not newer than the latest published tag " + latest, refusal)
            self.assertIn(rt.ORDER_RULE, refusal)
        self.assertIn("'v1.4.0-rc1' is not vX.Y.Z", rt.order_refusal("1.3.0", "v1.4.0-rc1"))

    def test_check_order_cli(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(rt.main(["check-order", "v1.2.1", "v1.3.0"]), 1)
            self.assertEqual(rt.main(["check-order", "1.3.1", "v1.3.0"]), 0)
            self.assertEqual(rt.main(["check-order", "1.0.0", ""]), 0)
        self.assertEqual(out.getvalue().strip(),
                         f"v1.2.1 is not newer than the latest published tag v1.3.0 ({rt.ORDER_RULE})")


class Route(unittest.TestCase):
    SHA = "a" * 40
    PARENT = "b" * 40

    def fixture(self, kind="settle"):
        candidate = kind == "candidate"
        ref = "main" if candidate else "release-v1.2.0"
        return {
            "kind": kind, "event": "push", "sha": self.SHA,
            "first_parent": self.PARENT, "ref_name": ref, "default_branch": "main",
            "pr_author": "mega-gutenberg[bot]", "tag_exists": False,
            "release_exists": False, "version_at_sha": "1.2.0", "latest_tag": "v1.1.0",
            "pulls": [{
                "number": 42, "merged_at": "2026-10-27T00:00:00Z",
                "merge_commit_sha": self.SHA, "base": {"ref": ref},
                "head": {"ref": "chore/release-candidate-1.2.0" if candidate
                         else "chore/release-settle-v1.2.0"},
                "user": {"login": "mega-gutenberg[bot]"},
                "body": f"<!-- release-settle: v1.2.0 {self.PARENT} -->",
            }],
        }

    def decision(self, data, action):
        result = rt.route(data)
        self.assertEqual(result["action"], action)
        self.assertTrue(result["reason"])
        self.assertEqual(set(result), {
            "action", "reason", "version", "release_branch", "commit", "pr_number", "targets",
        })
        if action != "refresh":
            self.assertEqual(result["targets"], [])
        return result

    def test_candidate_push_cuts_normalized_version(self):
        data = self.fixture("candidate")
        for suffix in ("v1.2.0", "1.2.0"):
            with self.subTest(suffix=suffix):
                data["pulls"][0]["head"]["ref"] = "chore/release-candidate-" + suffix
                result = self.decision(data, "cut")
                self.assertEqual(
                    (result["version"], result["release_branch"], result["commit"], result["pr_number"]),
                    ("1.2.0", "release-v1.2.0", self.SHA, 42),
                )

    def test_author_mismatch_never_cuts_publishes_or_refreshes(self):
        for kind in ("candidate", "settle"):
            with self.subTest(kind=kind):
                data = self.fixture(kind)
                data["pulls"][0]["user"]["login"] = "mega-maxwell[bot]"
                result = self.decision(data, "skip")
                self.assertIn("mega-maxwell[bot]", result["reason"])

    def test_unmerged_pr_is_not_selected(self):
        self.assert_unmatched_pr("merged_at", None)

    def test_merge_commit_sha_mismatch_is_not_selected(self):
        self.assert_unmatched_pr("merge_commit_sha", "c" * 40)

    def test_base_mismatch_is_not_selected(self):
        self.assert_unmatched_pr("base", {"ref": "other"})

    def test_head_mismatch_is_not_selected(self):
        self.assert_unmatched_pr("head", {"ref": "chore/other"})

    def assert_unmatched_pr(self, field, value):
        for kind in ("candidate", "settle"):
            with self.subTest(kind=kind):
                data = self.fixture(kind)
                data["pulls"][0][field] = value
                self.decision(data, "skip" if kind == "candidate" else "refresh")

    def test_selects_matching_pr_among_unrelated_pulls(self):
        data = self.fixture("candidate")
        data["pulls"].insert(0, dict(data["pulls"][0], merge_commit_sha="c" * 40))
        self.decision(data, "cut")

    def test_settle_push_publishes_fresh_merge(self):
        result = self.decision(self.fixture(), "publish")
        self.assertEqual(
            (result["version"], result["release_branch"], result["commit"], result["pr_number"]),
            ("1.2.0", "release-v1.2.0", self.SHA, 42),
        )

    def test_stale_marker_refreshes_even_before_version_checks(self):
        data = self.fixture()
        data["pulls"][0]["body"] = f"<!-- release-settle: v1.2.0 {'c' * 40} -->"
        data.update(version_at_sha=None, latest_tag="v9.0.0")
        result = self.decision(data, "refresh")
        self.assertIn("was stale", result["reason"])
        self.assertIn(self.PARENT, result["reason"])
        self.assertEqual(result["targets"], [{
            "version": "1.2.0", "release_branch": "release-v1.2.0", "commit": self.SHA,
        }])

    def test_missing_or_invalid_marker_is_stale(self):
        for body in (None, "", "no marker", f"<!-- release-settle: v1.1.0 {self.PARENT} -->",
                     "<!-- release-settle: v1.2.0 bad-sha -->"):
            with self.subTest(body=body):
                data = self.fixture()
                data["pulls"][0]["body"] = body
                result = self.decision(data, "refresh")
                self.assertIn("was stale", result["reason"])
                self.assertNotIn("None", result["reason"])

    def test_tag_and_release_exist_skips_before_pr_checks(self):
        data = self.fixture()
        data.update(tag_exists=True, release_exists=True, pulls=[])
        result = self.decision(data, "skip")
        self.assertIn("v1.2.0 is already published", result["reason"])

    def test_fresh_merge_of_an_older_version_is_not_published(self):
        # release-v1.2.1 (a hotfix line) is merged after v1.3.0 was published.
        data = self.fixture()
        data.update(latest_tag="v1.3.0")
        for tag_exists in (False, True):
            with self.subTest(tag_exists=tag_exists):
                data["tag_exists"] = tag_exists
                result = self.decision(data, "skip")
                self.assertIn("refusing to publish settle PR #42", result["reason"])
                self.assertIn("v1.2.0 is not newer than the latest published tag v1.3.0", result["reason"])
                self.assertIn(rt.ORDER_RULE, result["reason"])

    def test_fresh_merge_of_the_same_version_as_latest_is_not_published(self):
        data = self.fixture()
        data.update(latest_tag="v1.2.0")
        self.assertIn("not newer than the latest published tag v1.2.0", self.decision(data, "skip")["reason"])

    def test_unparsable_latest_tag_skips_instead_of_failing(self):
        for pulls in ("fresh", "none"):
            with self.subTest(pulls=pulls):
                data = self.fixture()
                data["latest_tag"] = "v1.3.0-rc1"
                if pulls == "none":
                    data["pulls"] = []
                result = self.decision(data, "skip")
                self.assertIn("'v1.3.0-rc1' is not vX.Y.Z", result["reason"])
        data = self.dispatch_fixture()
        data["latest_tag"] = "v1.3.0-rc1"
        self.decision(data, "skip")

    def test_tag_without_release_fresh_merge_resumes_publish(self):
        data = self.fixture()
        data["tag_exists"] = True
        self.decision(data, "publish")

    def test_tag_without_release_other_push_requires_rerun(self):
        for state in ("no-pr", "stale", "missing", "wrong-author", "unmerged"):
            with self.subTest(state=state):
                data = self.fixture()
                data["tag_exists"] = True
                if state == "no-pr":
                    data["pulls"] = []
                elif state == "stale":
                    data["first_parent"] = "c" * 40
                elif state == "missing":
                    data["pulls"][0]["body"] = None
                elif state == "wrong-author":
                    data["pulls"][0]["user"]["login"] = "mega-maxwell[bot]"
                else:
                    data["pulls"][0]["merged_at"] = None
                result = self.decision(data, "skip")
                self.assertIn("v1.2.0 is tagged but has no Release", result["reason"])
                self.assertIn("re-run the release-settle run", result["reason"])
                self.assertIn("merge commit to finish publishing", result["reason"])
                self.assertNotIn("<", result["reason"])

    def test_tag_without_release_reason_names_existing_tag_commit(self):
        data = self.fixture()
        data.update(tag_exists=True, pulls=[], tag_commit="c" * 40)
        result = self.decision(data, "skip")
        self.assertIn(f"merge commit {'c' * 40} to finish publishing", result["reason"])
        data["tag_commit"] = None
        self.assertIn("merge commit to finish publishing", self.decision(data, "skip")["reason"])

    def test_unpublished_branch_refreshes_without_matching_pr(self):
        data = self.fixture()
        data["pulls"] = []
        result = self.decision(data, "refresh")
        self.assertEqual(result["targets"], [{
            "version": "1.2.0", "release_branch": "release-v1.2.0", "commit": self.SHA,
        }])

    def test_version_file_not_yet_bumped_skips(self):
        for version in (None, "1.1.0"):
            with self.subTest(version=version):
                data = self.fixture()
                data.update(pulls=[], version_at_sha=version)
                result = self.decision(data, "skip")
                self.assertIn("candidate has not landed", result["reason"])

    def test_old_or_equal_version_skips(self):
        for latest in ("v1.2.0", "v1.10.0"):
            with self.subTest(latest=latest):
                data = self.fixture()
                data.update(pulls=[], latest_tag=latest)
                self.decision(data, "skip")

    def test_no_latest_tag_refreshes(self):
        data = self.fixture()
        data.update(pulls=[], latest_tag="")
        self.decision(data, "refresh")

    def dispatch_fixture(self):
        data = self.fixture()
        data.update(event="workflow_dispatch", branches=[
            {"name": "release-v1.2.0", "tip": self.SHA, "version_at_tip": "1.2.0", "tag_exists": False},
            {"name": "release-v1.3.0", "tip": self.PARENT, "version_at_tip": "1.3.0",
             "tag_exists": True, "release_exists": True},
        ])
        data.update(candidate_merge_sha="c" * 40, candidate_is_ancestor=True)
        return data

    def test_dispatch_two_branches_excludes_tagged_branch(self):
        result = self.decision(self.dispatch_fixture(), "refresh")
        self.assertEqual(result["targets"], [{
            "version": "1.2.0", "release_branch": "release-v1.2.0", "commit": self.SHA,
        }])

    def test_dispatch_version_filter(self):
        data = self.dispatch_fixture()
        data["branches"][1]["tag_exists"] = False
        data["dispatch_version"] = "v1.3.0"
        result = self.decision(data, "refresh")
        self.assertEqual(result["targets"], [{
            "version": "1.3.0", "release_branch": "release-v1.3.0", "commit": self.PARENT,
        }])
        data["dispatch_version"] = "9.9.9"
        self.decision(data, "skip")

    def test_dispatch_excludes_unbumped_old_and_unrelated_branches(self):
        data = self.dispatch_fixture()
        data["branches"] = [
            {"name": "main", "tip": self.SHA, "version_at_tip": "1.2.0", "tag_exists": False},
            {"name": "release-v1.2.0", "tip": self.SHA, "version_at_tip": None, "tag_exists": False},
            {"name": "release-v1.1.0", "tip": self.SHA, "version_at_tip": "1.1.0", "tag_exists": False},
        ]
        self.decision(data, "skip")
        data["branches"] = []
        self.decision(data, "skip")

    def test_custom_branch_prefix(self):
        data = self.fixture()
        data.update(prefix="stable-", ref_name="stable-1.2.0", pulls=[])
        result = self.decision(data, "refresh")
        self.assertEqual(result["targets"][0]["release_branch"], "stable-1.2.0")
        data = self.dispatch_fixture()
        data.update(prefix="stable-")
        data["branches"][0]["name"] = "stable-1.2.0"
        self.decision(data, "refresh")

    def test_other_kind_event_or_ref_skips_with_context(self):
        for kind, event, ref in (
            ("unknown", "push", "main"), ("candidate", "push", "other"),
            ("settle", "push", "main"), ("candidate", "workflow_dispatch", "main"),
            ("settle", "schedule", "release-v1.2.0"),
        ):
            with self.subTest(kind=kind, event=event, ref=ref):
                data = self.fixture()
                data.update(kind=kind, event=event, ref_name=ref)
                result = self.decision(data, "skip")
                for value in (kind, event, ref):
                    self.assertIn(value, result["reason"])

    def test_unparsable_release_branch_push_skips_naming_branch(self):
        for ref in ("release-vnext", "release-v1.2", "release-v"):
            with self.subTest(ref=ref):
                data = self.fixture()
                data.update(ref_name=ref, version_at_sha=None)
                result = self.decision(data, "skip")
                self.assertIn(ref, result["reason"])
                self.assertEqual(result["version"], "")

    def test_dispatch_ignores_unparsable_release_branch(self):
        data = self.dispatch_fixture()
        data["branches"].insert(0, {
            "name": "release-vnext", "tip": self.PARENT, "version_at_tip": None, "tag_exists": False,
        })
        result = self.decision(data, "refresh")
        self.assertEqual([t["release_branch"] for t in result["targets"]], ["release-v1.2.0"])

    def test_null_fields_behave_like_absent(self):
        data = self.fixture()
        data.update(pulls=None, latest_tag=None, prefix=None, pr_author=None, first_parent=None)
        self.assertEqual(self.decision(data, "refresh")["targets"][0]["release_branch"], "release-v1.2.0")
        data = self.dispatch_fixture()
        data.update(latest_tag=None, dispatch_version=None)
        self.decision(data, "refresh")
        data.update(branches=None)
        self.decision(data, "skip")
        for key in ("ref_name", "kind", "event"):
            with self.subTest(key=key):
                data = self.fixture()
                data[key] = None
                self.decision(data, "skip")

    def test_route_cli_rejects_wrong_types_without_traceback(self):
        for data in (
            {"kind": "settle", "event": "push", "ref_name": 7},
            {**self.fixture(), "pulls": {"number": 1}},
            {**self.fixture(), "pulls": ["x"]},
            {**self.dispatch_fixture(), "branches": [None]},
        ):
            with self.subTest(data=data):
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch("sys.stdin", io.StringIO(json.dumps(data))), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    self.assertEqual(rt.main(["route"]), 1)
                self.assertEqual(stdout.getvalue(), "")
                self.assertTrue(stderr.getvalue().startswith("release_tools: "))
                self.assertEqual(len(stderr.getvalue().splitlines()), 1)

    def test_route_cli_json_and_invalid_input(self):
        for raw, code in ((json.dumps(self.fixture()), 0), ("not json", 1), ("[]", 1)):
            with self.subTest(raw=raw):
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch("sys.stdin", io.StringIO(raw)), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    self.assertEqual(rt.main(["route"]), code)
                if code == 0:
                    self.assertEqual(json.loads(stdout.getvalue())["action"], "publish")
                    self.assertEqual(stderr.getvalue(), "")
                else:
                    self.assertEqual(stdout.getvalue(), "")
                    self.assertIn("release_tools:", stderr.getvalue())
                    self.assertNotIn("Traceback", stderr.getvalue())


class VersionFiles(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(rt.read_version_file("0.0.0\n", "plain"), "0.0.0")
        new, old = rt.bump_version_file("0.0.0\n", "plain", "0.1.0")
        self.assertEqual((new, old), ("0.1.0\n", "0.0.0"))

    def test_toml_first_only(self):
        text = '[package]\nname = "x"\nversion = "2.1.0"\n\n[dependencies]\nfoo = { version = "1.0" }\n'
        self.assertEqual(rt.read_version_file(text, "toml"), "2.1.0")
        new, old = rt.bump_version_file(text, "toml", "2.2.0")
        self.assertEqual(old, "2.1.0")
        self.assertIn('version = "2.2.0"', new)
        self.assertIn('foo = { version = "1.0" }', new)  # dependency untouched

    def test_json(self):
        text = '{\n  "name": "x",\n  "version": "1.0.0",\n  "dependencies": {"a": "2.0.0"}\n}\n'
        new, old = rt.bump_version_file(text, "json", "1.1.0")
        self.assertEqual(old, "1.0.0")
        self.assertIn('"version": "1.1.0"', new)
        self.assertIn('"a": "2.0.0"', new)

    def test_unknown_pattern_and_missing_field(self):
        with self.assertRaises(ValueError):
            rt.read_version_file("x", "yaml")
        with self.assertRaises(ValueError):
            rt.read_version_file("name = 'x'\n", "toml")


class Notes(unittest.TestCase):
    LINES = [
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\tfeat(replay): windowed witness pipeline (#2320)",
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\tfix: validate receipt fallback ranges (#2301)",
        "cccccccccccccccccccccccccccccccccccccccc\tchore(deps): bump alloy (#5)",
        "dddddddddddddddddddddddddddddddddddddddd\tfeat!: drop legacy RPC (#2299)",
        "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee\tMerge branch 'x' into y",
    ]

    def test_grouping_and_links(self):
        md = rt.generate_notes("megaeth-labs/mega-agents", "0.1.0", "2026-09-07", self.LINES)
        self.assertTrue(md.startswith("## v0.1.0 (2026-09-07)\n"))
        # breaking first, then groups in NOTE_GROUPS order, then Other
        order = [md.index(h) for h in ("### Breaking changes", "### Features", "### Fixes", "### Chores", "### Other")]
        self.assertEqual(order, sorted(order))
        self.assertIn("- replay: windowed witness pipeline ([#2320](https://github.com/megaeth-labs/mega-agents/pull/2320))", md)
        self.assertIn("- Merge branch 'x' into y (`eeeeeeeeee`)", md)
        # the breaking item is listed under Breaking *and* under its type
        self.assertEqual(md.count("drop legacy RPC"), 2)

    def test_release_bookkeeping_commits_are_dropped(self):
        lines = [
            "1111111111111111111111111111111111111111\tchore(release): candidate v0.1.0 (#291)",
            "2222222222222222222222222222222222222222\tchore(release): settle v0.1.0",
            "3333333333333333333333333333333333333333\tchore(release): changelog for v0.1.0 (#293)",
            "4444444444444444444444444444444444444444\tchore(deps): bump foo (#5)",
        ]
        md = rt.generate_notes("o/r", "0.2.0", "", lines)
        self.assertTrue(md.startswith("## v0.2.0\n\n"))  # no date until settle stamps one
        self.assertNotIn("candidate v0.1.0", md)
        self.assertNotIn("settle v0.1.0", md)
        self.assertNotIn("changelog for v0.1.0", md)
        self.assertIn("deps: bump foo", md)

    def test_empty(self):
        md = rt.generate_notes("o/r", "1.0.0", "2026-01-01", [])
        self.assertIn("_No changes recorded", md)


class Changelog(unittest.TestCase):
    SEC = "## v0.2.0 (2026-09-07)\n\n### Fixes\n\n- b (`bbbbbbbbbb`)\n"
    OLD = "# Changelog\n\n## v0.1.0 (2026-08-01)\n\n### Features\n\n- a (`aaaaaaaaaa`)\n"

    def test_insert_into_empty(self):
        new, what = rt.insert_changelog_section("", "0.2.0", self.SEC)
        self.assertEqual(what, "inserted")
        self.assertTrue(new.startswith("# Changelog\n\n## v0.2.0"))

    def test_insert_newest_first(self):
        new, what = rt.insert_changelog_section(self.OLD, "0.2.0", self.SEC)
        self.assertEqual(what, "inserted")
        self.assertLess(new.index("## v0.2.0"), new.index("## v0.1.0"))
        self.assertEqual(rt.extract_changelog_section(new, "v0.1.0"), "### Features\n\n- a (`aaaaaaaaaa`)\n")

    def test_replace_same_version(self):
        once, _ = rt.insert_changelog_section(self.OLD, "0.2.0", self.SEC)
        twice, what = rt.insert_changelog_section(once, "0.2.0", self.SEC.replace("- b", "- b2"))
        self.assertEqual(what, "replaced")
        self.assertEqual(twice.count("## v0.2.0"), 1)
        self.assertIn("- b2", twice)
        self.assertNotIn("- b (", twice)
        self.assertIn("## v0.1.0", twice)

    def test_spacing_is_formatter_stable(self):
        # One blank line between blocks, one newline at EOF — whether the
        # section lands at the end (no prior entries), at the top, or replaces.
        for text in ("", "# Changelog\n\nIntro line.\n", self.OLD):
            new, _ = rt.insert_changelog_section(text, "0.2.0", self.SEC)
            self.assertFalse(new.endswith("\n\n"), repr(new[-10:]))
            self.assertTrue(new.endswith("\n"))
            self.assertNotIn("\n\n\n", new)
        twice, _ = rt.insert_changelog_section(new, "0.2.0", self.SEC)
        self.assertNotIn("\n\n\n", twice)
        self.assertFalse(twice.endswith("\n\n"))

    def test_section_text_and_copy_between_files(self):
        # main has the candidate's "(unreleased)" entry; the tag has the settled
        # one with a date and a drift line. Copying the tag's section over
        # main's replaces it in place and keeps everything else.
        main = "# Changelog\n\n## v0.2.0\n\n### Fixes\n\n- b (`bbbbbbbbbb`)\n\n## v0.1.0 (2026-08-01)\n\n- a\n"
        tagged = "# Changelog\n\n## v0.2.0 (2026-09-07)\n\n### Fixes\n\n- b (`bbbbbbbbbb`)\n- drift fix (`dddddddddd`)\n\n## v0.1.0 (2026-08-01)\n\n- a\n"
        section = rt.changelog_section_text(tagged, "v0.2.0")
        self.assertTrue(section.startswith("## v0.2.0 (2026-09-07)\n"))
        self.assertIn("- drift fix", section)
        self.assertNotIn("## v0.1.0", section)
        new, what = rt.insert_changelog_section(main, "0.2.0", section)
        self.assertEqual(what, "replaced")
        self.assertIn("## v0.2.0 (2026-09-07)", new)
        self.assertIn("- drift fix", new)
        self.assertIn("## v0.1.0 (2026-08-01)\n\n- a\n", new)
        self.assertEqual(new.count("## v0.2.0"), 1)
        self.assertIsNone(rt.changelog_section_text(main, "9.9.9"))

    def test_extract_missing(self):
        self.assertIsNone(rt.extract_changelog_section(self.OLD, "9.9.9"))

    def test_generated_undated_section_round_trip_is_unchanged(self):
        text = "# Changelog\n\n## v0.2.0\n\n### Fixes\n\n- b (`bbbbbbbbbb`)\n\n" + self.OLD.split("\n\n", 1)[1]
        lines = ["b" * 40 + "\tfix: b"]
        section = rt.generate_notes("o/r", "0.2.0", "", lines)

        new, what = rt.insert_changelog_section(text, "0.2.0", section)

        self.assertEqual((new, what), (text, "replaced"))

    def test_generated_undated_section_replaces_dated_heading(self):
        text = "# Changelog\n\n" + self.SEC
        section = rt.generate_notes("o/r", "0.2.0", "", ["b" * 40 + "\tfix: b"])

        new, what = rt.insert_changelog_section(text, "0.2.0", section)

        self.assertEqual(what, "replaced")
        self.assertNotEqual(new, text)
        self.assertEqual(new, "# Changelog\n\n" + section)

    def test_extract_cli_can_include_heading(self):
        for flags, expected in (
            ([], "### Fixes\n\n- b (`bbbbbbbbbb`)\n"),
            (["--include-heading"], self.SEC),
        ):
            with self.subTest(flags=flags):
                stdout = io.StringIO()
                with patch.object(rt.Path, "read_text", return_value=self.SEC), contextlib.redirect_stdout(stdout):
                    code = rt.main(["changelog-extract", "CHANGELOG.md", "0.2.0", *flags])
                self.assertEqual(code, 0)
                self.assertEqual(stdout.getvalue(), expected)


class SettlementSections(unittest.TestCase):
    def test_matching_section_keeps_candidate_merge_clean(self):
        for facts in ({}, {"section_matches": True}):
            with self.subTest(facts=facts):
                state, _ = rt.settle_state("1.2.0", "a" * 40, "a" * 40, True, False, False, False, **facts)
                self.assertEqual(state, "clean")

    def test_stale_section_at_candidate_merge_needs_settle_pr(self):
        state, reason = rt.settle_state(
            "1.2.0", "a" * 40, "a" * 40, True, False, False, False,
            section_matches=False,
        )
        self.assertEqual(state, "needs-settle-pr")
        self.assertIn("stale changelog section", reason)

    def test_cli_section_matches_defaults_true_and_accepts_false(self):
        args = [
            "settle-state", "--version", "1.2.0", "--branch-tip", "a" * 40,
            "--candidate-merge-sha", "a" * 40, "--candidate-is-ancestor", "true",
            "--open-settle-pr", "false", "--published-tag-exists", "false",
            "--release-exists", "false",
        ]
        for flags, expected in (
            ([], "clean"),
            (["--section-matches", "true"], "clean"),
            (["--section-matches", "false"], "needs-settle-pr"),
        ):
            with self.subTest(flags=flags):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    code = rt.main([*args, *flags])
                self.assertEqual(code, 0)
                self.assertEqual(stdout.getvalue().splitlines()[0], expected)


class DispatchSettlement(unittest.TestCase):
    def fixture(self, **facts):
        branch = {
            "name": "release-v1.2.0", "tip": "a" * 40, "version_at_tip": "1.2.0",
            "candidate_merge_sha": "a" * 40, "candidate_is_ancestor": True,
            "open_settle_pr": False, "tag_exists": False, "release_exists": False,
        }
        branch.update(facts)
        return {
            "kind": "settle", "event": "workflow_dispatch", "dispatch_version": "v1.2.0",
            "latest_tag": "v9.0.0", "branches": [branch],
        }

    def test_predicate_states_map_to_dispatch_actions_and_reasons(self):
        cases = [
            ("clean", {}, "publish"),
            ("needs-settle-pr", {"tip": "b" * 40}, "refresh"),
            ("resume", {"tag_exists": True}, "publish"),
            ("published", {"tag_exists": True, "release_exists": True}, "skip"),
            ("blocked", {"candidate_is_ancestor": False}, "skip"),
        ]
        for expected_state, facts, action in cases:
            with self.subTest(state=expected_state):
                data = self.fixture(**facts)
                branch = data["branches"][0]
                state, reason = rt.settle_state(
                    "1.2.0", branch["tip"], branch["candidate_merge_sha"],
                    branch["candidate_is_ancestor"], branch["open_settle_pr"],
                    branch["tag_exists"], branch["release_exists"],
                )
                self.assertEqual(state, expected_state)
                result = rt.route(data)
                self.assertEqual((result["action"], result["reason"]), (action, reason))
                self.assertEqual(result.get("settle_source"), "dispatch" if action == "publish" else None)
                self.assertEqual((result["version"], result["release_branch"], result["commit"]),
                                 ("1.2.0", branch["name"], branch["tip"]))
                self.assertEqual(result["targets"], [
                    {"version": "1.2.0", "release_branch": branch["name"], "commit": branch["tip"]},
                ] if action == "refresh" else [])

    def test_candidate_pr_number_is_optional(self):
        self.assertIsNone(rt.route(self.fixture())["pr_number"])
        for key in ("candidate_pr_number", "candidatePRNumber", "pr_number"):
            with self.subTest(key=key):
                self.assertEqual(rt.route(self.fixture(**{key: 42}))["pr_number"], 42)

    def test_resume_publishes_tagged_commit_when_tip_is_ahead(self):
        for key in ("published_tag_sha", "tag_commit", None):
            with self.subTest(tag_sha_key=key):
                facts = {"tip": "b" * 40, "tag_exists": True}
                if key:
                    facts[key] = "a" * 40
                result = rt.route(self.fixture(**facts))
                self.assertEqual(result["action"], "publish")
                self.assertEqual(result["settle_source"], "dispatch")
                self.assertEqual(result["commit"], "a" * 40 if key else "b" * 40)

    def test_selected_version_always_reaches_predicate(self):
        for facts in (
            {"version_at_tip": None},
            {"tag_exists": True, "release_exists": True},
        ):
            with self.subTest(facts=facts):
                with patch.object(rt, "settle_state", return_value=("blocked", "blocked")) as predicate:
                    result = rt.route(self.fixture(**facts))
                predicate.assert_called_once()
                self.assertEqual((result["action"], result["reason"]), ("skip", "blocked"))

    def test_missing_branch_facts_cannot_publish(self):
        data = self.fixture()
        data["branches"] = []
        result = rt.route(data)
        self.assertEqual(result["action"], "skip")
        self.assertIn("release-v1.2.0 does not exist", result["reason"])

    def test_push_without_merged_settle_pr_cannot_publish(self):
        data = self.fixture()
        data.update(event="push", ref_name="release-v1.2.0", sha="a" * 40,
                    version_at_sha="1.2.0", latest_tag="", pulls=[])
        with patch.object(rt, "settle_state", side_effect=AssertionError("dispatch only")):
            result = rt.route(data)
        self.assertEqual(result["action"], "refresh")
        self.assertNotIn("settle_source", result)

    def test_sweep_keeps_tag_without_release_and_summarizes_published_branch(self):
        data = self.fixture(tag_exists=True, version_at_tip=None)
        data["dispatch_version"] = ""
        data["branches"].append({
            "name": "release-v1.3.0", "tip": "b" * 40, "version_at_tip": "1.3.0",
            "tag_exists": True, "release_exists": True,
        })
        summary = io.StringIO()
        with contextlib.redirect_stderr(summary):
            result = rt.route(data)
        self.assertEqual(result["action"], "refresh")
        self.assertEqual(result["targets"], [
            {"version": "1.2.0", "release_branch": "release-v1.2.0", "commit": "a" * 40},
        ])
        self.assertEqual(len(summary.getvalue().splitlines()), 1)
        self.assertIn("release-v1.3.0 (v1.3.0)", summary.getvalue())
        self.assertIn("published tag and Release", summary.getvalue())


class DispatchSettlementFacts(unittest.TestCase):
    def fixture(self):
        return {
            "kind": "settle", "event": "workflow_dispatch", "dispatch_version": "v1.2.0",
            "branches": [{
                "name": "release-v1.2.0", "tip": "a" * 40,
                "version_at_tip": "1.2.0", "tag_exists": False,
            }],
        }

    def test_without_facts_raises(self):
        for facts, missing in (
            ({}, ["candidate_merge_sha", "candidate_is_ancestor"]),
            ({"candidate_merge_sha": "", "candidate_is_ancestor": True},
             ["candidate_merge_sha"]),
            ({"candidate_merge_sha": "a" * 40}, ["candidate_is_ancestor"]),
        ):
            with self.subTest(facts=facts):
                data = self.fixture()
                data["branches"][0].update(facts)
                with self.assertRaises(ValueError) as raised:
                    rt.route(data)
                self.assertIn("v1.2.0", str(raised.exception))
                for key in missing:
                    self.assertIn(key, str(raised.exception))

    def test_with_facts_publishes(self):
        data = self.fixture()
        data["branches"][0].update(
            candidate_merge_sha="a" * 40, candidate_is_ancestor=True, open_settle_pr=False,
        )
        result = rt.route(data)
        self.assertEqual(result["action"], "publish")
        self.assertEqual(result["settle_source"], "dispatch")

    def test_missing_branch_still_skips(self):
        data = self.fixture()
        data["branches"] = []
        result = rt.route(data)
        self.assertEqual(result["action"], "skip")
        self.assertIn("release-v1.2.0", result["reason"])
        self.assertIn("does not exist", result["reason"])


if __name__ == "__main__":
    unittest.main()
