import unittest

import pandas as pd

from chart_builder import build_chart


class ChartBuilderTests(unittest.TestCase):
    def test_long_monthly_data_uses_multi_series_line_chart(self):
        chart_data = pd.DataFrame(
            {
                "商品": ["运动鞋", "运动鞋", "智能手环", "智能手环"],
                "月份": ["1月", "2月", "1月", "2月"],
                "销售额": [9500, 13000, 11880, 14850],
            }
        )

        spec = build_chart(chart_data).to_dict()

        self.assertEqual(spec["layer"][0]["mark"]["type"], "line")
        self.assertEqual(spec["layer"][0]["encoding"]["x"]["field"], "月份")
        self.assertEqual(spec["layer"][0]["encoding"]["y"]["field"], "销售额")
        self.assertEqual(spec["layer"][0]["encoding"]["color"]["field"], "商品")
        self.assertEqual(spec["layer"][1]["mark"]["type"], "point")
        self.assertNotIn("xOffset", spec["layer"][1]["encoding"])
        self.assertNotIn("shape", spec["layer"][1]["encoding"])
        self.assertTrue(spec["layer"][1]["mark"]["filled"])
        self.assertEqual(spec["layer"][1]["mark"]["shape"], "circle")
        self.assertEqual(spec["layer"][1]["mark"]["size"], 45)
        self.assertEqual(
            [tooltip["field"] for tooltip in spec["layer"][1]["encoding"]["tooltip"]],
            ["商品", "月份", "销售额"],
        )
        legend = spec["layer"][0]["encoding"]["color"]["legend"]
        self.assertEqual(legend["orient"], "top")
        self.assertEqual(legend["direction"], "horizontal")
        self.assertEqual(len(spec["layer"]), 2)
        self.assertNotIn("params", spec)

    def test_close_values_keep_true_positions_without_permanent_labels(self):
        chart_data = pd.DataFrame(
            {
                "商品": ["保温杯", "蓝牙耳机"],
                "月份": ["2月", "2月"],
                "销售额": [5400, 5500],
            }
        )

        spec = build_chart(chart_data).to_dict()

        self.assertNotIn("xOffset", spec["layer"][0]["encoding"])
        self.assertNotIn("xOffset", spec["layer"][1]["encoding"])
        tooltip_fields = spec["layer"][2]["encoding"]["tooltip"]
        self.assertEqual(tooltip_fields[0]["field"], "月份")
        self.assertEqual(
            [tooltip["field"] for tooltip in tooltip_fields[1:]],
            ["保温杯", "蓝牙耳机"],
        )
        self.assertEqual(len(spec["layer"]), 3)
        self.assertEqual(spec["layer"][2]["mark"]["type"], "point")
        self.assertEqual(spec["layer"][2]["mark"]["opacity"], 0)
        self.assertGreaterEqual(spec["layer"][2]["mark"]["size"], 900)
        self.assertNotIn("text", [layer["mark"]["type"] for layer in spec["layer"]])

    def test_values_far_apart_do_not_add_labels(self):
        chart_data = pd.DataFrame(
            {
                "商品": ["保温杯", "蓝牙耳机"],
                "月份": ["2月", "2月"],
                "销售额": [5400, 8500],
            }
        )

        spec = build_chart(chart_data).to_dict()

        self.assertEqual(len(spec["layer"]), 2)

    def test_category_totals_keep_bar_chart_with_labels(self):
        chart_data = pd.Series(
            [36500, 35640],
            index=pd.Index(["运动鞋", "智能手环"], name="商品"),
            name="销售额",
        )

        spec = build_chart(chart_data).to_dict()

        self.assertIn("layer", spec)
        self.assertEqual(spec["layer"][0]["mark"]["type"], "bar")
        self.assertEqual(spec["layer"][1]["mark"]["type"], "text")

    def test_single_month_series_keeps_line_chart(self):
        chart_data = pd.Series(
            [11880, 14850, 8910],
            index=pd.Index(["1月", "2月", "3月"], name="月份"),
            name="销售额",
        )

        spec = build_chart(chart_data).to_dict()

        self.assertEqual(spec["mark"]["type"], "line")
        self.assertEqual(spec["encoding"]["x"]["field"], "月份")
        self.assertEqual(spec["encoding"]["y"]["field"], "销售额")
        self.assertNotIn("field", spec["encoding"]["color"])

    def test_long_datetime_data_uses_temporal_multi_series_line_chart(self):
        chart_data = pd.DataFrame(
            {
                "地区": ["华东", "华东", "华南", "华南"],
                "日期": pd.to_datetime(["2026-01-01", "2026-02-01"] * 2),
                "销售额": [100, 120, 80, 110],
            }
        )

        spec = build_chart(chart_data).to_dict()

        self.assertEqual(spec["layer"][0]["mark"]["type"], "line")
        self.assertEqual(spec["layer"][0]["encoding"]["x"]["type"], "temporal")
        self.assertEqual(spec["layer"][0]["encoding"]["color"]["field"], "地区")


if __name__ == "__main__":
    unittest.main()
