import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from init_db import (
    SampleDatabaseError,
    create_sample_database,
    ensure_sample_database,
    load_sample_dataframe,
)


class SampleDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.csv_file = self.root / "sample_data.csv"
        self.database_file = self.root / "sales.db"
        pd.DataFrame(
            {
                "商品": ["智能手环", "蓝牙耳机"],
                "品类": ["数码", "数码"],
                "月份": ["1月", "1月"],
                "地区": ["华东", "华南"],
                "销量": [120, 85],
                "销售额": [11880, 4250],
            }
        ).to_csv(self.csv_file, index=False)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_creates_database_from_csv(self):
        row_count = create_sample_database(self.csv_file, self.database_file)

        self.assertEqual(row_count, 2)
        connection = sqlite3.connect(self.database_file)
        try:
            stored = connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(stored, 2)

    def test_missing_required_column_is_rejected(self):
        pd.DataFrame({"商品": ["智能手环"]}).to_csv(self.csv_file, index=False)

        with self.assertRaisesRegex(SampleDatabaseError, "缺少字段"):
            create_sample_database(self.csv_file, self.database_file)

    def test_load_sample_dataframe_returns_only_supported_columns(self):
        dataframe = pd.read_csv(self.csv_file)
        dataframe["测试备注"] = "不会写入数据库"
        dataframe.to_csv(self.csv_file, index=False)

        loaded = load_sample_dataframe(self.csv_file)

        self.assertEqual(
            loaded.columns.tolist(),
            ["商品", "品类", "月份", "地区", "销量", "销售额"],
        )

    def test_ensure_does_not_replace_existing_database(self):
        self.database_file.write_bytes(b"existing")

        result = ensure_sample_database(self.root)

        self.assertEqual(result, self.database_file)
        self.assertEqual(self.database_file.read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main()
