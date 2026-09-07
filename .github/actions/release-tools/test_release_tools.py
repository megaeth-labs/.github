import unittest

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
        "cccccccccccccccccccccccccccccccccccccccc\tchore(release): candidate v0.1.0 (#5)",
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

    def test_extract_missing(self):
        self.assertIsNone(rt.extract_changelog_section(self.OLD, "9.9.9"))


if __name__ == "__main__":
    unittest.main()
