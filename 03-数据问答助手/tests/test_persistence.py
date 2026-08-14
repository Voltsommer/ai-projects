import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from persistence import PersistenceError, load_messages, save_messages


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.chat_file = Path(self.temp_dir.name) / "chat_history.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_file_starts_empty_session(self):
        messages, warning = load_messages(self.chat_file)

        self.assertEqual(messages, [])
        self.assertIsNone(warning)

    def test_save_and_load_keep_audit_but_drop_runtime_chart(self):
        source = [
            {
                "role": "assistant",
                "content": "分析完成",
                "analysis": {"execution_type": "数据库查询"},
                "chart_data": pd.DataFrame({"销售额": [1, 2]}),
            }
        ]

        save_messages(self.chat_file, source)
        messages, warning = load_messages(self.chat_file)

        self.assertIsNone(warning)
        self.assertEqual(messages[0]["content"], "分析完成")
        self.assertIn("analysis", messages[0])
        self.assertNotIn("chart_data", messages[0])

    def test_corrupt_json_is_quarantined(self):
        self.chat_file.write_text("{not valid json", encoding="utf-8")

        messages, warning = load_messages(self.chat_file)

        self.assertEqual(messages, [])
        self.assertIn("已重新开始空会话", warning)
        self.assertFalse(self.chat_file.exists())
        backups = list(Path(self.temp_dir.name).glob("chat_history.corrupt-*.json"))
        self.assertEqual(len(backups), 1)

    def test_invalid_message_shape_is_quarantined(self):
        self.chat_file.write_text(
            json.dumps([{"role": "system", "content": "hidden"}]),
            encoding="utf-8",
        )

        messages, warning = load_messages(self.chat_file)

        self.assertEqual(messages, [])
        self.assertIsNotNone(warning)

    def test_rejects_invalid_messages_before_saving(self):
        with self.assertRaises(PersistenceError):
            save_messages(self.chat_file, [{"role": "user", "content": 123}])

    def test_save_leaves_no_temporary_file(self):
        save_messages(
            self.chat_file,
            [{"role": "user", "content": "哪个商品卖得最好？"}],
        )

        self.assertTrue(self.chat_file.exists())
        self.assertFalse((Path(self.temp_dir.name) / ".chat_history.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
