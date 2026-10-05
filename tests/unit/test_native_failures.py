from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from embraion.adapters.eval_observations import codex_failure_metadata
from embraion.common import framework_root
from embraion.eval_observers import MAX_BYTES


class NativeFailureMetadata(unittest.TestCase):
    def test_reported_code_retains_category_without_provider_message(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "events.jsonl").write_text(json.dumps({"type": "turn.failed", "error": {
                "code": "rate_limit_exceeded", "message": "PRIVATE_ERROR_SECRET_7441"}}), encoding="utf-8")
            result = codex_failure_metadata(root)
            self.assertEqual(["rate-limit"], result["categories"])
            self.assertEqual(1, result["reported-events"])
            self.assertNotIn("PRIVATE_ERROR_SECRET_7441", str(result))
            self.assertNotIn("rate_limit_exceeded", str(result))

    def test_unknown_codes_and_tool_output_cannot_invent_a_known_category(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = [{"type": "item.completed", "item": {"type": "command_execution",
                "aggregated_output": '{"type":"error","code":"rate_limit_exceeded"}'}},
                {"type": "error", "code": "PRIVATE_UNKNOWN_CODE", "message": "quota exceeded"}]
            (root / "events.jsonl").write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            result = codex_failure_metadata(root)
            self.assertEqual(["unclassified"], result["categories"])
            self.assertEqual(1, result["reported-events"])
            self.assertNotIn("PRIVATE_UNKNOWN_CODE", str(result))

    def test_absent_invalid_and_oversize_observations_remain_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual("unavailable", codex_failure_metadata(root)["status"])
            path = root / "events.jsonl"
            path.write_text("malformed", encoding="utf-8")
            self.assertEqual("unavailable", codex_failure_metadata(root)["status"])
            path.write_bytes(b"x" * (MAX_BYTES + 1))
            self.assertEqual("unavailable", codex_failure_metadata(root)["status"])

    def test_report_contract_rejects_raw_provider_fields_and_unknown_categories(self):
        from jsonschema import Draft202012Validator, ValidationError
        schema = json.loads((framework_root() / "schemas/experiment-report.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema["properties"]["runs"]["items"]["properties"]["host"])
        metadata = {"source": "codex-error-events-v1", "status": "reported", "reported-events": 1,
                    "categories": ["rate-limit"]}
        validator.validate({"native-failure": metadata})
        validator.validate({"status": "host-failed"})  # Historical reports remain readable.
        for value in ({**metadata, "message": "PRIVATE_ERROR_SECRET"}, {**metadata, "categories": ["PRIVATE_CODE"]}):
            with self.assertRaises(ValidationError):
                validator.validate({"native-failure": value})


if __name__ == "__main__":
    unittest.main()
