import unittest

import crates_tools as ct


class Parse(unittest.TestCase):
    def test_newlines_commas_blanks_dups(self):
        self.assertEqual(
            ct.parse_crates("mega-system-contracts\n mega-evm , mega-state-test\n\nmega-evme,mega-evm\n"),
            ["mega-system-contracts", "mega-evm", "mega-state-test", "mega-evme"],
        )
        self.assertEqual(ct.parse_crates(""), [])


class Check(unittest.TestCase):
    META = {
        "packages": [
            {"name": "mega-evm", "version": "1.7.1", "publish": None},
            {"name": "mega-evme", "version": "1.7.1", "publish": None},
            {"name": "state-test", "version": "1.7.1", "publish": []},
            {"name": "mega-t8n", "version": "1.7.0", "publish": None},
        ]
    }

    def test_all_good(self):
        self.assertEqual(ct.check_versions(self.META, ["mega-evm", "mega-evme"], "1.7.1"), [])

    def test_problems_are_listed_not_raised(self):
        problems = ct.check_versions(self.META, ["mega-evm", "state-test", "mega-t8n", "nope"], "1.7.1")
        self.assertEqual(len(problems), 3)
        self.assertTrue(any("publish = false" in p and "state-test" in p for p in problems))
        self.assertTrue(any("mega-t8n" in p and "1.7.0" in p for p in problems))
        self.assertTrue(any("nope: not a workspace member" == p for p in problems))


class Partition(unittest.TestCase):
    def test_keeps_order_and_skips_published(self):
        out = ct.partition(["a", "b", "c", "d"], {"b", "d"})
        self.assertEqual(out, {"publish": ["a", "c"], "skip": ["b", "d"]})

    def test_nothing_published(self):
        self.assertEqual(ct.partition(["a"], set()), {"publish": ["a"], "skip": []})


if __name__ == "__main__":
    unittest.main()
