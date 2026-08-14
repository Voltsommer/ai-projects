"""企业数据问答助手的 Streamlit 页面入口。"""

import time
from contextlib import closing

import pandas as pd
import streamlit as st
from ai_service import DeepSeekService
from app_config import load_config
from analysis_audit import (
    build_analysis_record,
    result_preview_to_dataframe,
)
from analysis_service import analyse_database_question, analyse_dataframe_question
from chart_builder import build_chart
from data_quality import (
    DataQualityError,
    analyse_data_quality,
    load_tabular_data,
    validate_upload_metadata,
)
from database import (
    DatabaseAccessError,
    connect_read_only,
    get_schema_text,
    list_user_tables,
    preview_table,
)
from data_management import (
    DataManagementError,
    add_sales_record,
    delete_sales_records,
    list_sales_records,
    restore_sample_records,
)
from error_messages import user_error_message
from init_db import SampleDatabaseError, ensure_sample_database
from observability import EventLogError, new_request_id, write_analysis_event
from persistence import PersistenceError, load_messages, save_messages as persist_messages

config = load_config()
st.set_page_config(
    page_title="企业数据问答助手",
    page_icon="📊",
    layout="centered",
)

ai_service = (
    DeepSeekService(api_key=config.api_key, model=config.model)
    if config.ai_enabled
    else None
)

def save_messages():
    """把对话与分析审计记录存到本地文件。"""
    persist_messages(config.chat_file, st.session_state.messages)


def clear_chat():
    """清空对话：屏幕上的消息 + 本地存档一起清掉"""
    st.session_state.messages = []
    try:
        save_messages()
    except PersistenceError as exc:
        st.session_state.persistence_warning = str(exc)


@st.cache_data(show_spinner=False, max_entries=5)
def load_uploaded_data(file_bytes, extension):
    """按文件内容缓存读取结果，避免界面重跑时重复解析 Excel。"""
    return load_tabular_data(file_bytes, extension)


@st.cache_data(show_spinner=False, max_entries=5)
def build_quality_report(df):
    """数据不变时复用质量检查结果。"""
    return analyse_data_quality(df)


def render_data_quality(report):
    """用明确指标、问题清单和字段明细展示质量检查结果。"""
    st.subheader("数据质量概览", anchor=False)
    with st.container(horizontal=True):
        st.metric("数据行数", f"{report['row_count']:,}", border=True)
        st.metric("字段数量", f"{report['column_count']:,}", border=True)
        st.metric("缺失值", f"{report['missing_cells']:,}", border=True)
        st.metric("重复行", f"{report['duplicate_rows']:,}", border=True)

    if report["blockers"]:
        st.error("数据暂不可用于分析：" + "；".join(report["blockers"]))
    elif report["warnings"]:
        st.warning("数据可以分析，但建议先核对以下质量提醒。")
        for warning in report["warnings"]:
            st.markdown(f"- {warning}")
    else:
        st.success("质量检查通过，未发现影响当前分析的明显问题。")

    with st.expander("查看字段质量明细", icon=":material/fact_check:"):
        profile = pd.DataFrame(report["column_profiles"])
        st.dataframe(
            profile,
            column_config={
                "缺失率": st.column_config.ProgressColumn(
                    "缺失率",
                    min_value=0,
                    max_value=1,
                    format="percent",
                ),
            },
            hide_index=True,
        )


def render_database_management(database_file, sample_csv_file):
    """将人工写入集中在显式的数据管理区，AI 查询连接仍保持只读。"""
    with st.expander("管理演示数据", icon=":material/database:"):
        st.caption(
            "这里的操作只影响本机 sales.db；AI 生成的 SQL 仍然只能查询数据。"
        )

        try:
            records = list_sales_records(database_file)
        except DataManagementError as exc:
            st.error(str(exc), icon=":material/error:")
            return

        st.markdown("**当前记录**")
        selection = st.dataframe(
            records,
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row",
            key="sales_management_table",
            column_config={
                "记录ID": st.column_config.NumberColumn("记录编号", disabled=True),
                "销量": st.column_config.NumberColumn("销量", format="%d"),
                "销售额": st.column_config.NumberColumn("销售额", format="%d 元"),
            },
        )
        selected_positions = list(selection.selection.rows)
        selected_ids = [
            int(records.iloc[position]["记录ID"])
            for position in selected_positions
            if 0 <= position < len(records)
        ]
        st.caption(f"已选择 {len(selected_ids)} 条记录。")

        confirm_delete = st.checkbox(
            "我确认删除所选记录",
            disabled=not selected_ids,
            key="confirm_sales_delete",
        )
        if st.button(
            "删除所选记录",
            disabled=not selected_ids,
            key="delete_sales_records",
            icon=":material/delete:",
        ):
            if not confirm_delete:
                st.warning("删除前请勾选确认项。")
            else:
                try:
                    deleted = delete_sales_records(database_file, selected_ids)
                except DataManagementError as exc:
                    st.error(str(exc), icon=":material/error:")
                else:
                    st.session_state.database_notice = f"已删除 {deleted} 条记录。"
                    st.rerun()

        st.divider()
        st.markdown("**新增记录**")
        with st.form("add_sales_record", clear_on_submit=True):
            first_row = st.columns(3)
            product = first_row[0].text_input("商品", max_chars=100)
            category = first_row[1].text_input("品类", max_chars=100)
            month = first_row[2].text_input("月份", placeholder="例如：4月", max_chars=100)

            second_row = st.columns(3)
            region = second_row[0].text_input("地区", max_chars=100)
            quantity = second_row[1].number_input(
                "销量",
                min_value=0,
                max_value=1_000_000_000,
                step=1,
            )
            revenue = second_row[2].number_input(
                "销售额",
                min_value=0,
                max_value=1_000_000_000_000,
                step=1,
            )
            add_submitted = st.form_submit_button("新增记录", type="primary")

        if add_submitted:
            try:
                record_id = add_sales_record(
                    database_file,
                    product=product,
                    category=category,
                    month=month,
                    region=region,
                    quantity=quantity,
                    revenue=revenue,
                )
            except DataManagementError as exc:
                st.error(str(exc), icon=":material/error:")
            else:
                st.session_state.database_notice = (
                    f"记录新增成功，记录编号为 {record_id}。"
                )
                st.rerun()

        st.divider()
        st.markdown("**恢复初始示例数据**")
        st.caption("此操作会清除当前 sales 表，并重新载入 sample_data.csv。")
        confirm_restore = st.checkbox(
            "我确认覆盖当前演示数据",
            key="confirm_sample_restore",
        )
        if st.button(
            "恢复示例数据",
            disabled=not confirm_restore,
            key="restore_sample_records",
            icon=":material/restore:",
        ):
            try:
                restored = restore_sample_records(database_file, sample_csv_file)
            except DataManagementError as exc:
                st.error(str(exc), icon=":material/error:")
            else:
                st.session_state.database_notice = (
                    f"已恢复初始示例数据，共 {restored} 条记录。"
                )
                st.rerun()


st.title("📊 企业数据问答助手")

st.session_state.setdefault("persistence_warning", None)
st.session_state.setdefault("database_notice", None)
if "messages" not in st.session_state:
    messages, persistence_warning = load_messages(config.chat_file)
    st.session_state.messages = messages
    st.session_state.persistence_warning = persistence_warning

if st.session_state.persistence_warning:
    st.warning(st.session_state.persistence_warning, icon=":material/warning:")
    st.session_state.persistence_warning = None

if st.session_state.database_notice:
    st.success(st.session_state.database_notice, icon=":material/check_circle:")
    st.session_state.database_notice = None

if not config.ai_enabled:
    st.info(
        "当前未配置 AI 服务。仍可浏览和管理本地演示数据；配置 "
        "DEEPSEEK_API_KEY 后即可使用自然语言提问。",
        icon=":material/key:",
    )

# ---- 会话管理（侧边栏）：聊天记录存在本机 chat_history.json，可一键清空 ----
st.sidebar.header("⚙️ 会话管理")
st.sidebar.caption("聊天记录保存在本机 chat_history.json")
st.sidebar.button("🧹 清除对话", on_click=clear_chat)

# 数据来源切换：上传文件 或 SQLite 数据库
# 默认“数据库”：缺少 sales.db 时从 sample_data.csv 自动创建
source = st.segmented_control("数据来源", ["上传文件", "数据库"], default="数据库")

df = None
schema_text = None
quality_report = None
table = None

if source == "数据库":
    try:
        ensure_sample_database(config.base_dir)
        with closing(connect_read_only(config.database_file)) as preview_connection:
            tables = list_user_tables(preview_connection)
            if not tables:
                raise DatabaseAccessError("数据库中没有可用的数据表。")
            table = st.selectbox("选择数据表", tables)
            schema_text = get_schema_text(preview_connection, table)
            table_preview = preview_table(preview_connection, table)
    except (DatabaseAccessError, SampleDatabaseError) as exc:
        st.error(user_error_message(exc), icon=":material/database_off:")
        st.stop()
    st.subheader("📋 表结构")
    st.code(schema_text)
    st.dataframe(table_preview, hide_index=True)
    if table == "sales":
        render_database_management(
            config.database_file,
            config.base_dir / "sample_data.csv",
        )
else:
    uploaded = st.file_uploader(
        "上传数据文件（CSV 或 Excel）",
        type=["csv", "xlsx"],
        help="单个文件不超过 10 MB，最多 100,000 行、100 个字段。",
    )
    if uploaded is not None:
        try:
            file_bytes = uploaded.getvalue()
            extension = validate_upload_metadata(uploaded.name, len(file_bytes))
            df = load_uploaded_data(file_bytes, extension)
            quality_report = build_quality_report(df)
        except DataQualityError as exc:
            st.error(str(exc), icon=":material/error:")
            df = None
        else:
            if quality_report["is_usable"]:
                df.to_csv(config.data_file, index=False)  # 仅保存通过接入检查的数据
    elif config.data_file.exists():
        try:
            df = pd.read_csv(config.data_file)
            quality_report = build_quality_report(df)
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            st.error(f"上次保存的数据无法恢复：{exc}")
            df = None
    if df is not None:
        render_data_quality(quality_report)
        st.subheader("数据预览", anchor=False)
        st.dataframe(df.head(100), hide_index=True)
        if len(df) > 100:
            st.caption(f"当前展示前 100 行，完整数据共 {len(df):,} 行。")


def render_chart(chart_data):
    """把查询结果转换为合适的 Altair 图表并显示。"""
    st.altair_chart(build_chart(chart_data), width="stretch")


def render_analysis_record(analysis):
    """默认折叠展示生成逻辑与执行结果，供用户追溯答案。"""
    if not analysis:
        return

    with st.expander("分析过程", icon=":material/account_tree:"):
        st.caption(f"执行方式：{analysis['execution_type']}")
        st.markdown("**生成的查询逻辑**")
        st.code(analysis["code"], language=analysis["language"])
        st.markdown("**执行结果**")

        preview = analysis.get("result_preview", {})
        table = result_preview_to_dataframe(preview)
        if table is not None:
            st.dataframe(table, hide_index=True)
            if preview.get("truncated"):
                st.caption(
                    f"结果共 {preview['total_rows']} 行，"
                    f"当前展示前 {preview['shown_rows']} 行。"
                )
        else:
            st.code(preview.get("value", ""), language="text")
            if preview.get("truncated"):
                st.caption("结果内容较长，当前仅展示部分内容。")


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        # 如果这条消息带了图表数据，就在文字下面画出来
        if msg.get("chart_data") is not None:
            render_chart(msg["chart_data"])
        render_analysis_record(msg.get("analysis"))

# 判断当前有没有可用数据（数据库模式连上就算有）
has_data = (source == "数据库" and table is not None) or (
    df is not None
    and quality_report is not None
    and quality_report["is_usable"]
)

if not has_data:
    st.info(
        "支持 CSV 和 Excel 格式。上传完成后即可开始数据分析。",
        title="等待数据文件",
        icon=":material/upload_file:",
    )

prompt = st.chat_input(
    "比如：哪个商品卖得最好？",
    disabled=not has_data or ai_service is None,
    submit_mode="disable",
)
if prompt:
    request_id = new_request_id()
    started_at = time.monotonic()
    event_source = "database" if source == "数据库" else "file"
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    try:
        if source == "数据库":
            with closing(connect_read_only(config.database_file)) as query_connection:
                outcome = analyse_database_question(
                    prompt,
                    schema_text,
                    table,
                    query_connection,
                    ai_service,
                )
        else:
            outcome = analyse_dataframe_question(
                prompt,
                df,
                ai_service,
            )
        result = outcome.result
        answer = outcome.answer
    except Exception as error:
        st.session_state.messages.pop()
        try:
            write_analysis_event(
                config.event_log_file,
                request_id=request_id,
                status="error",
                source=event_source,
                duration_ms=int((time.monotonic() - started_at) * 1000),
                error_type=type(error).__name__,
            )
        except EventLogError:
            pass
        st.error(user_error_message(error, request_id))
    else:
        # 执行结果是 Series/DataFrame 且有多行（≥2 行）才有画图意义：
        # 比如"各品类总额"3 行 → 柱状图；"哪个最高"只有 1 行 → 不画图，否则一根孤零零的柱子像张空表
        chart_data = result if isinstance(result, (pd.Series, pd.DataFrame)) and len(result) > 1 else None
        analysis = build_analysis_record(
            outcome.execution_type,
            outcome.generated_code,
            outcome.language,
            result,
        )
        result_rows = len(result) if isinstance(result, (pd.Series, pd.DataFrame)) else 1
        try:
            write_analysis_event(
                config.event_log_file,
                request_id=request_id,
                status="success",
                source=event_source,
                duration_ms=int((time.monotonic() - started_at) * 1000),
                result_rows=result_rows,
            )
        except EventLogError:
            pass
        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "chart_data": chart_data,
            "analysis": analysis,
        })
        try:
            save_messages()  # 存盘：刷新后对话还在
        except PersistenceError as exc:
            st.warning(f"回答已生成，但{exc}")
        with st.chat_message("assistant"):
            st.write(answer)
            if isinstance(result, pd.DataFrame) and result.attrs.get("truncated"):
                st.info(f"查询结果较多，仅展示前 {result.attrs['max_rows']} 行。")
            if chart_data is not None:
                render_chart(chart_data)
            render_analysis_record(analysis)
