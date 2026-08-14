import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import pandas as pd

from data_management import (
    DataManagementError,
    add_sales_record,
    delete_sales_records,
    list_sales_records,
    restore_sample_records,
)
from init_db import create_sample_database


class DataManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.sample_csv = self.root / "sample_data.csv"
        self.database_file = self.root / "sales.db"
        self.original_data = pd.DataFrame(
            {
                "商品": ["智能手环", "蓝牙耳机"],
                "品类": ["数码", "数码"],
                "月份": ["1月", "1月"],
                "地区": ["华东", "华南"],
                "销量": [120, 85],
                "销售额": [11880, 4250],
            }
        )
        self.original_data.to_csv(self.sample_csv, index=False)
        create_sample_database(self.sample_csv, self.database_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def count_rows(self):
        with closing(sqlite3.connect(self.database_file)) as connection:
            return connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0]

    def test_lists_records_with_stable_row_identifier(self):
        records = list_sales_records(self.database_file)

        self.assertEqual(records.columns.tolist()[0], "记录ID")
        self.assertEqual(records["记录ID"].tolist(), [1, 2])
        self.assertEqual(records["商品"].tolist(), ["智能手环", "蓝牙耳机"])

    def test_adds_trimmed_validated_record(self):
        record_id = add_sales_record(
            self.database_file,
            product=" 运动鞋 ",
            category="服饰",
            month="2月",
            region="华东",
            quantity=130,
            revenue=13000,
        )

        records = list_sales_records(self.database_file)
        added = records.loc[records["记录ID"] == record_id].iloc[0]
        self.assertEqual(added["商品"], "运动鞋")
        self.assertEqual(int(added["销售额"]), 13000)

    def test_rejects_invalid_record_before_writing(self):
        with self.assertRaisesRegex(DataManagementError, "商品不能为空"):
            add_sales_record(
                self.database_file,
                product="  ",
                category="服饰",
                month="2月",
                region="华东",
                quantity=130,
                revenue=13000,
            )

        with self.assertRaisesRegex(DataManagementError, "销量必须在"):
            add_sales_record(
                self.database_file,
                product="运动鞋",
                category="服饰",
                month="2月",
                region="华东",
                quantity=-1,
                revenue=13000,
            )
        self.assertEqual(self.count_rows(), 2)

    def test_deletes_selected_records(self):
        deleted = delete_sales_records(self.database_file, [2])

        self.assertEqual(deleted, 1)
        self.assertEqual(list_sales_records(self.database_file)["记录ID"].tolist(), [1])

    def test_delete_is_atomic_when_any_record_is_missing(self):
        with self.assertRaisesRegex(DataManagementError, "发生变化"):
            delete_sales_records(self.database_file, [1, 999])

        self.assertEqual(self.count_rows(), 2)

    def test_restores_repository_sample_data(self):
        delete_sales_records(self.database_file, [1])
        add_sales_record(
            self.database_file,
            product="运动鞋",
            category="服饰",
            month="2月",
            region="华东",
            quantity=130,
            revenue=13000,
        )

        restored = restore_sample_records(self.database_file, self.sample_csv)

        self.assertEqual(restored, 2)
        records = list_sales_records(self.database_file)
        self.assertEqual(records["商品"].tolist(), ["智能手环", "蓝牙耳机"])

    def test_management_limit_is_bounded(self):
        with self.assertRaisesRegex(ValueError, "1 到 1000"):
            list_sales_records(self.database_file, limit=1001)


if __name__ == "__main__":
    unittest.main()
