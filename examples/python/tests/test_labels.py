from __future__ import annotations

import unittest

from reference_app import normalize_label


class LabelTests(unittest.TestCase):
    def test_normalizes_spacing_and_case(self) -> None:
        self.assertEqual("Reference Project", normalize_label("  reference   project "))

    def test_rejects_empty_label(self) -> None:
        with self.assertRaises(ValueError):
            normalize_label("   ")


if __name__ == "__main__":
    unittest.main()
