"""把 pandas 查询结果转换为 Altair 图表。"""

import altair as alt
import pandas as pd


CHART_PALETTE = [
    "#2a78d6",
    "#eb6834",
    "#1baf7a",
    "#eda100",
    "#e87ba4",
    "#008300",
    "#4a3aa7",
    "#e34948",
]
CLOSE_POINT_RATIO = 0.025
OVERLAP_HIT_AREA_SIZE = 1100


def _normalise_chart_data(chart_data) -> pd.DataFrame:
    if isinstance(chart_data, pd.Series):
        return chart_data.reset_index()
    if isinstance(chart_data, pd.DataFrame):
        if isinstance(chart_data.index, pd.RangeIndex):
            return chart_data.copy()
        return chart_data.reset_index()
    raise TypeError("chart_data 必须是 pandas Series 或 DataFrame。")


def _time_column(df_chart: pd.DataFrame):
    """找到 datetime、月份值或常见名称的时间维度列。"""
    for column in df_chart.columns:
        if pd.api.types.is_datetime64_any_dtype(df_chart[column]):
            return column

    time_names = {"日期", "时间", "年月", "月份", "季度", "date", "time", "month", "quarter"}
    for column in df_chart.columns:
        if str(column).strip().lower() in time_names:
            return column

    for column in df_chart.columns:
        values = df_chart[column].dropna().astype(str)
        if not values.empty and values.str.match(r"^\d{1,2}月$").all():
            return column
    return None


def _numeric_columns(df_chart: pd.DataFrame) -> list:
    return [
        column
        for column in df_chart.columns
        if pd.api.types.is_numeric_dtype(df_chart[column])
        and not pd.api.types.is_bool_dtype(df_chart[column])
    ]


def _close_point_groups(
    df_chart: pd.DataFrame,
    time_col,
    series_col,
    value_col,
) -> list[pd.DataFrame]:
    """按同一时间维度识别视觉上近重合的点簇。"""
    numeric_values = pd.to_numeric(df_chart[value_col], errors="coerce").dropna()
    if len(numeric_values) < 2:
        return []

    axis_min = min(0, numeric_values.min())
    axis_max = max(0, numeric_values.max())
    close_threshold = max((axis_max - axis_min) * CLOSE_POINT_RATIO, 1)
    groups = []

    for time_value, time_group in df_chart.groupby(
        time_col,
        dropna=False,
        sort=False,
    ):
        time_group = time_group.copy()
        time_group["_numeric_value"] = pd.to_numeric(
            time_group[value_col],
            errors="coerce",
        )
        rows = list(
            time_group.dropna(subset=["_numeric_value"])
            .sort_values("_numeric_value")
            .iterrows()
        )
        if len(rows) < 2:
            continue

        current_group = [rows[0][1]]
        for _, row in rows[1:]:
            previous = current_group[-1]
            if row["_numeric_value"] - previous["_numeric_value"] <= close_threshold:
                current_group.append(row)
            else:
                if len(current_group) > 1:
                    groups.append((time_value, current_group))
                current_group = [row]
        if len(current_group) > 1:
            groups.append((time_value, current_group))

    group_frames = []
    for time_value, rows in groups:
        record = {
            time_col: time_value,
            "_cluster_value": sum(row["_numeric_value"] for row in rows) / len(rows),
        }
        for row in rows:
            record[str(row[series_col])] = row[value_col]
        group_frames.append(pd.DataFrame([record]))
    return group_frames


def _build_multi_series_line_chart(
    df_chart: pd.DataFrame,
    time_col,
    series_col,
    value_col,
):
    df_chart = df_chart.dropna(subset=[time_col, series_col, value_col]).copy()
    df_chart = df_chart.reset_index(drop=True)
    df_chart[series_col] = df_chart[series_col].astype(str)
    time_values = df_chart[time_col].dropna().astype(str)
    is_month = not time_values.empty and time_values.str.match(r"^\d{1,2}月$").all()
    is_datetime = pd.api.types.is_datetime64_any_dtype(df_chart[time_col])
    if is_month:
        sort = sorted(
            time_values.unique(),
            key=lambda value: int(value.replace("月", "")),
        )
        x_type = "ordinal"
    elif is_datetime:
        sort = None
        x_type = "temporal"
    else:
        sort = None
        x_type = "ordinal"
    series_values = list(df_chart[series_col].dropna().unique())
    series_count = len(series_values)
    legend = alt.Legend(
        orient="top",
        direction="horizontal",
        title=None,
        symbolType="circle",
    )
    color_encoding = alt.Color(
        series_col,
        type="nominal",
        scale=alt.Scale(range=CHART_PALETTE[:series_count]),
        legend=legend,
    )
    x_encoding = alt.X(
        time_col,
        type=x_type,
        sort=sort,
        axis=alt.Axis(labelAngle=0, title=None),
    )
    y_encoding = alt.Y(value_col, type="quantitative", title=None)
    lines = alt.Chart(df_chart).mark_line(strokeWidth=2).encode(
        x=x_encoding,
        y=y_encoding,
        color=color_encoding,
    )

    points = alt.Chart(df_chart).mark_point(
        filled=True,
        shape="circle",
        size=45,
        stroke="white",
        strokeWidth=1.2,
    ).encode(
        x=alt.X(
            time_col,
            type=x_type,
            sort=sort,
            axis=alt.Axis(labelAngle=0, title=None),
        ),
        y=y_encoding,
        color=alt.Color(
            series_col,
            type="nominal",
            scale=alt.Scale(range=CHART_PALETTE[:series_count]),
            legend=legend,
        ),
        tooltip=[series_col, time_col, value_col],
    )
    layers = [lines, points]
    for group_data in _close_point_groups(
        df_chart,
        time_col=time_col,
        series_col=series_col,
        value_col=value_col,
    ):
        group_series = [
            column
            for column in group_data.columns
            if column not in {time_col, "_cluster_value"}
        ]
        overlap_hit_area = alt.Chart(group_data).mark_point(
            opacity=0,
            size=OVERLAP_HIT_AREA_SIZE,
        ).encode(
            x=alt.X(time_col, type=x_type, sort=sort),
            y=alt.Y("_cluster_value:Q"),
            tooltip=[
                alt.Tooltip(time_col, type=x_type, title=str(time_col)),
                *[
                    alt.Tooltip(series, type="quantitative", title=series, format=",")
                    for series in group_series
                ],
            ],
        )
        layers.append(overlap_hit_area)

    return alt.layer(*layers)


def _build_two_column_chart(df_chart: pd.DataFrame):
    x_col, y_col = df_chart.columns[0], df_chart.columns[-1]
    df_chart = df_chart[[x_col, y_col]].copy()
    x_values = df_chart[x_col].astype(str)
    is_numeric = pd.api.types.is_numeric_dtype(df_chart[x_col])
    is_month = not df_chart.empty and x_values.str.match(r"^\d{1,2}月$").all()

    if is_numeric or is_month:
        if is_month:
            months = sorted(
                x_values.unique(),
                key=lambda value: int(value.replace("月", "")),
            )
            x_encoding = alt.X(
                x_col,
                type="ordinal",
                sort=months,
                axis=alt.Axis(labelAngle=0, title=None),
            )
        else:
            x_encoding = alt.X(
                x_col,
                type="quantitative",
                axis=alt.Axis(labelAngle=0, title=None),
            )
        return alt.Chart(df_chart).mark_line(point=True).encode(
            x=x_encoding,
            y=alt.Y(y_col, type="quantitative", title=None),
            color=alt.value(CHART_PALETTE[0]),
            tooltip=[x_col, y_col],
        )

    x_scale = alt.Scale(paddingInner=0.5)
    chart = alt.Chart(df_chart).mark_bar().encode(
        x=alt.X(
            x_col,
            type="nominal",
            sort="-y",
            title=None,
            axis=alt.Axis(labelAngle=0),
            scale=x_scale,
        ),
        y=alt.Y(y_col, type="quantitative", title=None),
        color=alt.Color(
            x_col,
            type="nominal",
            scale=alt.Scale(range=CHART_PALETTE[: len(df_chart)]),
            legend=None,
        ),
        tooltip=[x_col, y_col],
    )
    labels = alt.Chart(df_chart).mark_text(dy=-8, size=12).encode(
        x=alt.X(x_col, type="nominal", sort="-y", scale=x_scale),
        y=alt.Y(y_col, type="quantitative"),
        text=alt.Text(y_col, format=","),
        color=alt.value("#52514e"),
    )
    return chart + labels


def build_chart(chart_data):
    """类别汇总画柱状图；月份趋势画单序列或多序列折线图。"""
    df_chart = _normalise_chart_data(chart_data)
    if df_chart.empty or len(df_chart.columns) < 2:
        raise ValueError("图表数据至少需要两列且不能为空。")

    time_col = _time_column(df_chart)
    numeric_columns = _numeric_columns(df_chart)
    if time_col is not None and numeric_columns:
        value_col = numeric_columns[-1]
        series_candidates = [
            column
            for column in df_chart.columns
            if column not in {time_col, value_col}
            and not pd.api.types.is_numeric_dtype(df_chart[column])
        ]
        if series_candidates:
            return _build_multi_series_line_chart(
                df_chart,
                time_col=time_col,
                series_col=series_candidates[0],
                value_col=value_col,
            )

    return _build_two_column_chart(df_chart)
