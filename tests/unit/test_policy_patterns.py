from __future__ import annotations

import unittest
from fnmatch import fnmatchcase

from embraion.policy import path_matches


class PolicyPatternTests(unittest.TestCase):
    def test_recursive_protected_patterns_match_immediate_and_nested_files(self) -> None:
        cases = (
            ("Assets/Project/Pressure/Sensor/Wireless/SDK/**/*.cs",
             "Assets/Project/Pressure/Sensor/Wireless/SDK/Adapter.cs"),
            ("Assets/Project/Pressure/Sensor/Wired/MeasureX/**/*.dll",
             "Assets/Project/Pressure/Sensor/Wired/MeasureX/driver.dll"),
            ("Assets/StreamingAssets/Pressure/Sensor/Wired/Sensors/**/*.mxd",
             "Assets/StreamingAssets/Pressure/Sensor/Wired/Sensors/device.mxd"),
        )
        for pattern, immediate in cases:
            with self.subTest(pattern=pattern):
                self.assertTrue(path_matches(immediate, [pattern]))
                parent, name = immediate.rsplit("/", 1)
                self.assertTrue(path_matches(f"{parent}/nested/deeper/{name}", [pattern]))
                self.assertFalse(path_matches(f"{parent}/sibling.txt", [pattern]))

    def test_multiple_recursive_segments_can_each_match_zero_levels(self) -> None:
        pattern = "root/**/middle/**/file.cs"
        for path in ("root/middle/file.cs", "root/one/middle/file.cs",
                     "root/middle/two/file.cs", "root/one/middle/two/file.cs"):
            with self.subTest(path=path):
                self.assertTrue(path_matches(path, [pattern]))

    def test_legacy_cross_slash_star_and_non_whole_recursive_text_remain(self) -> None:
        for path, pattern in (("foo/a/b.txt", "foo/*.txt"),
                              ("foo/a/bar", "foo**/bar"),
                              ("prefix/sub/item.cs", "prefix*/item.cs")):
            with self.subTest(path=path, pattern=pattern):
                self.assertEqual(fnmatchcase(path, pattern), path_matches(path, [pattern]))
        self.assertTrue(path_matches("root\\direct\\file.cs", ["root\\**\\file.cs"]))

    def test_complexity_limits_apply_before_legacy_fast_match(self) -> None:
        too_many = "**/" * 9 + "file.cs"
        for path, patterns in (("file.cs", [too_many]),
                               ("safe.txt", ["safe.txt", too_many]),
                               ("x", ["x" * 4097])):
            with self.subTest(patterns=patterns), self.assertRaises(RuntimeError):
                path_matches(path, patterns)


if __name__ == "__main__":
    unittest.main()
