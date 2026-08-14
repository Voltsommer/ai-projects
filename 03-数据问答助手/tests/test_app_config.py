import tempfile
import unittest
from pathlib import Path

from app_config import DEFAULT_MODEL, load_config


class AppConfigTests(unittest.TestCase):
    def test_defaults_are_absolute_and_ai_is_disabled_without_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_config(temp_dir, {})

        self.assertFalse(config.ai_enabled)
        self.assertEqual(config.model, DEFAULT_MODEL)
        self.assertTrue(config.chat_file.is_absolute())
        self.assertEqual(config.database_file.name, "sales.db")

    def test_trims_environment_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_config(
                temp_dir,
                {
                    "DEEPSEEK_API_KEY": "  secret  ",
                    "DEEPSEEK_MODEL": " deepseek-chat ",
                    "APP_ENV": " production ",
                },
            )

        self.assertTrue(config.ai_enabled)
        self.assertEqual(config.api_key, "secret")
        self.assertEqual(config.environment, "production")

    def test_rejects_unknown_environment(self):
        with self.assertRaisesRegex(ValueError, "APP_ENV"):
            load_config(Path.cwd(), {"APP_ENV": "staging"})


if __name__ == "__main__":
    unittest.main()
