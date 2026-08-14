import json
import tempfile
import unittest
from pathlib import Path

from observability import write_analysis_event


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_file = Path(self.temp_dir.name) / "events.jsonl"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_writes_privacy_safe_success_event(self):
        event = write_analysis_event(
            self.log_file,
            request_id="request-1",
            status="success",
            source="database",
            duration_ms=120,
            result_rows=3,
        )
        stored = json.loads(self.log_file.read_text(encoding="utf-8"))

        self.assertEqual(stored, event)
        self.assertEqual(stored["result_rows"], 3)
        self.assertNotIn("question", stored)
        self.assertNotIn("sql", stored)
        self.assertNotIn("api_key", stored)

    def test_appends_error_event_with_type_only(self):
        write_analysis_event(
            self.log_file,
            request_id="request-1",
            status="error",
            source="file",
            duration_ms=20,
            error_type="PythonValidationError",
        )
        write_analysis_event(
            self.log_file,
            request_id="request-2",
            status="success",
            source="file",
            duration_ms=30,
            result_rows=1,
        )

        lines = self.log_file.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["error_type"], "PythonValidationError")

    def test_rejects_inconsistent_event(self):
        with self.assertRaisesRegex(ValueError, "必须包含 error_type"):
            write_analysis_event(
                self.log_file,
                request_id="request-1",
                status="error",
                source="file",
                duration_ms=10,
            )


if __name__ == "__main__":
    unittest.main()
