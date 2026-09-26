from __future__ import annotations

import unittest

from embraion.failures import may_fallback, normalize_failure


class FailureTests(unittest.TestCase):
    def test_http_mapping_is_closed_and_unknown_terminal(self) -> None:
        self.assertEqual("authentication", normalize_failure(http_status=401))
        self.assertEqual("rate-limited", normalize_failure(http_status=429))
        self.assertEqual("unknown", normalize_failure("new-provider-code", http_status=418))
        self.assertFalse(may_fallback("unknown", termination_confirmed=True, mutation_confirmed=True))
        self.assertFalse(may_fallback("rate-limited", termination_confirmed=False, mutation_confirmed=True))
        self.assertTrue(may_fallback("rate-limited", termination_confirmed=True, mutation_confirmed=True))
