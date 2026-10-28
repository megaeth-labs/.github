import contextlib
import io
import unittest

import release_tools as rt


CANDIDATE = "a" * 40
AHEAD = "b" * 40
OTHER = "c" * 40


class SettleState(unittest.TestCase):
    def test_settle_states(self):
        cases = [
            (CANDIDATE, True, False, False, False, "", "clean"),
            (AHEAD, True, False, False, False, "", "needs-settle-pr"),
            (CANDIDATE, True, True, False, False, "", "needs-settle-pr"),
            (CANDIDATE, True, False, True, False, CANDIDATE, "resume"),
            (CANDIDATE, True, False, True, True, CANDIDATE, "published"),
            (OTHER, False, False, False, False, "", "blocked"),
            (CANDIDATE, True, False, True, False, OTHER, "blocked"),
            (CANDIDATE, True, False, True, True, OTHER, "blocked"),
            (OTHER, False, True, True, True, CANDIDATE, "blocked"),
            (AHEAD, True, True, True, False, CANDIDATE, "resume"),
            (AHEAD, True, True, True, True, CANDIDATE, "published"),
            (CANDIDATE, True, False, True, False, "", "resume"),
            (CANDIDATE, True, False, True, True, "", "published"),
            (CANDIDATE, True, False, False, True, OTHER, "clean"),
        ]
        for tip, ancestor, open_pr, tag, release, tag_sha, expected in cases:
            with self.subTest(tip=tip, ancestor=ancestor, open_pr=open_pr,
                              tag=tag, release=release, tag_sha=tag_sha):
                state, reason = rt.settle_state(
                    "v1.2.3", tip, CANDIDATE, ancestor, open_pr, tag, release, tag_sha,
                )
                self.assertEqual(state, expected)
                self.assertTrue(reason)
                self.assertEqual(len(reason.splitlines()), 1)

                argv = [
                    "settle-state", "--version", "v1.2.3", "--branch-tip", tip,
                    "--candidate-merge-sha", CANDIDATE,
                    "--candidate-is-ancestor", str(ancestor).lower(),
                    "--open-settle-pr", str(open_pr).lower(),
                    "--published-tag-exists", str(tag).lower(),
                    "--release-exists", str(release).lower(),
                ]
                if tag_sha:
                    argv.extend(["--published-tag-sha", tag_sha])
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(rt.main(argv), 0)
                self.assertEqual(out.getvalue().splitlines(), [state, reason])

    def test_each_boolean_changes_state(self):
        cases = [
            (0, (True, False, False, False), "blocked", "clean"),
            (1, (True, False, False, False), "clean", "needs-settle-pr"),
            (2, (True, False, False, False), "clean", "resume"),
            (3, (True, False, True, False), "resume", "published"),
        ]
        for index, args, expected_false, expected_true in cases:
            for value, expected in ((False, expected_false), (True, expected_true)):
                with self.subTest(index=index, value=value):
                    changed = list(args)
                    changed[index] = value
                    self.assertEqual(
                        rt.settle_state("1.2.3", CANDIDATE, CANDIDATE, *changed)[0],
                        expected,
                    )

    def test_version_is_normalized(self):
        args = (CANDIDATE, CANDIDATE, True, False, True, False)
        self.assertEqual(rt.settle_state("v1.2.3", *args), rt.settle_state("1.2.3", *args))
        with self.assertRaises(ValueError):
            rt.settle_state("not-a-version", *args)

    def test_cli_rejects_non_boolean_values(self):
        for flag in ("candidate-is-ancestor", "open-settle-pr",
                     "published-tag-exists", "release-exists"):
            with self.subTest(flag=flag):
                argv = [
                    "settle-state", "--version", "1.2.3", "--branch-tip", CANDIDATE,
                    "--candidate-merge-sha", CANDIDATE,
                    "--candidate-is-ancestor", "true", "--open-settle-pr", "false",
                    "--published-tag-exists", "false", "--release-exists", "false",
                ]
                argv[argv.index(f"--{flag}") + 1] = "yes"
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                    rt.main(argv)
                self.assertEqual(exc.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
