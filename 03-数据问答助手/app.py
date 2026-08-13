# ============================================================
# 企业数据问答助手（Streamlit）— 里程碑③b
# 升级点：不再把数据"全文"喂给 AI 心算，
#         而是让 AI 写 pandas 代码，Python 执行拿到准确结果。
# 流程：AI 写代码 → Python 执行 → AI 把结果翻译成人话
# 运行：python -m streamlit run app.py
# ============================================================

import os
import json
import sqlite3
import pandas as pd
import streamlit as st
from ai_service import DeepSeekService
from analysis_audit import (
    build_analysis_record,
    result_preview_to_dataframe,
    serialise_messages,
)
from chart_builder import build_chart
from python_executor import execute_pandas_code
from sql_executor import clean_sql_output, execute_read_only_query

api_key = os.environ.get('DEEPSEEK_API_KEY')
if not api_key:
    st.error("请先设置 DEEPSEEK_API_KEY 环境变量")
    st.stop()

ai_service = DeepSeekService(api_key=api_key)

# ---- 文件路径：都相对于 app.py 所在目录（不管从哪里启动 streamlit 都找得到）----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---- 本地持久化：刷新页面后仍能恢复对话和数据 ----
CHAT_FILE = os.path.join(BASE_DIR, "chat_history.json")   # 对话存档
DATA_FILE = os.path.join(BASE_DIR, "data.csv")            # 上次上传的数据

def save_messages():
    """把对话与分析审计记录存到本地文件。"""
    clean = serialise_messages(st.session_state.messages)
    with open(CHAT_FILE, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)


def clear_chat():
    """清空对话：屏幕上的消息 + 本地存档一起清掉"""
    st.session_state.messages = []
    save_messages()

# ---- 数据库连接 ----
DB_FILE = os.path.join(BASE_DIR, "sales.db")   # init_db.py 生成的数据库

def get_connection():
    # 只读模式连接：AI 写的 SQL 就算想删表、改数据，也执行不了（安全沙箱）
    db_uri = DB_FILE.replace("\\", "/")   # Windows 路径转正斜杠，file: URI 才认识
    return sqlite3.connect(f"file:{db_uri}?mode=ro", uri=True)

def list_tables(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return [r[0] for r in rows]

def get_schema_text(conn, table):
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    cols = ", ".join(f"{r[1]} {r[2]}" for r in rows)
    return f"表 {table} 的列：{cols}"

st.title("📊 企业数据问答助手")

# ---- 会话管理（侧边栏）：聊天记录存在本机 chat_history.json，可一键清空 ----
st.sidebar.header("⚙️ 会话管理")
st.sidebar.caption("聊天记录保存在本机 chat_history.json")
st.sidebar.button("🧹 清除对话", on_click=clear_chat)

# 数据来源切换：上传文件 或 SQLite 数据库
# 默认"数据库"：sales.db 自带示例数据，启动即可提问，不用先传文件
source = st.segmented_control("数据来源", ["上传文件", "数据库"], default="数据库")

df = None
conn = None
schema_text = None

if source == "数据库":
    if not os.path.exists(DB_FILE):
        st.error("找不到数据库文件 sales.db，请先运行：python init_db.py")
        st.stop()
    conn = get_connection()
    tables = list_tables(conn)
    table = st.selectbox("选择数据表", tables)
    schema_text = get_schema_text(conn, table)
    st.subheader("📋 表结构")
    st.code(schema_text)
    st.dataframe(pd.read_sql_query(f'SELECT * FROM "{table}" LIMIT 5', conn), hide_index=True)
else:
    uploaded = st.file_uploader("上传数据文件（CSV 或 Excel）", type=["csv", "xlsx"])
    if uploaded is not None:
        if uploaded.name.endswith(".csv"):
            df = pd.read_csv(uploaded)
        elif uploaded.name.endswith(".xlsx"):
            df = pd.read_excel(uploaded)
        df.to_csv(DATA_FILE, index=False)   # 存到本地，刷新后自动恢复
    elif os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)          # 没重新上传 → 用上次保存的数据
    if df is not None:
        st.subheader("📋 数据预览")
        st.dataframe(df, hide_index=True)

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


if "messages" not in st.session_state:
    # 刷新后从本地存档恢复对话（没有存档就空着）
    if os.path.exists(CHAT_FILE):
        with open(CHAT_FILE, "r", encoding="utf-8") as f:
            st.session_state.messages = json.load(f)
    else:
        st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        # 如果这条消息带了图表数据，就在文字下面画出来
        if msg.get("chart_data") is not None:
            render_chart(msg["chart_data"])
        render_analysis_record(msg.get("analysis"))

# 判断当前有没有可用数据（数据库模式连上就算有）
has_data = (source == "数据库") or (df is not None)

if not has_data:
    st.info(
        "支持 CSV 和 Excel 格式。上传完成后即可开始数据分析。",
        title="等待数据文件",
        icon=":material/upload_file:",
    )

prompt = st.chat_input("比如：哪个商品卖得最好？", disabled=not has_data)
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    try:
        if source == "数据库":
            sql = clean_sql_output(ai_service.generate_sql(prompt, schema_text))
            result = execute_read_only_query(sql, conn)
            debug_code, debug_lang = sql, "sql"
            execution_type = "数据库查询"
        else:
            code, result = execute_pandas_code(
                ai_service.generate_pandas_code(prompt, df),
                df,
            )
            debug_code, debug_lang = code, "python"
            execution_type = "Pandas 分析"
        answer = ai_service.generate_answer(prompt, result)
    except Exception as e:
        st.session_state.messages.pop()
        st.error(f"出错了：{e}")
    else:
        # 执行结果是 Series/DataFrame 且有多行（≥2 行）才有画图意义：
        # 比如"各品类总额"3 行 → 柱状图；"哪个最高"只有 1 行 → 不画图，否则一根孤零零的柱子像张空表
        chart_data = result if isinstance(result, (pd.Series, pd.DataFrame)) and len(result) > 1 else None
        analysis = build_analysis_record(
            execution_type,
            debug_code,
            debug_lang,
            result,
        )
        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "chart_data": chart_data,
            "analysis": analysis,
        })
        save_messages()   # 存盘：刷新后对话还在
        with st.chat_message("assistant"):
            st.write(answer)
            if isinstance(result, pd.DataFrame) and result.attrs.get("truncated"):
                st.info(f"查询结果较多，仅展示前 {result.attrs['max_rows']} 行。")
            if chart_data is not None:
                render_chart(chart_data)
            render_analysis_record(analysis)
