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
import altair as alt
from openai import OpenAI

api_key = os.environ.get('DEEPSEEK_API_KEY')
if not api_key:
    st.error("请先设置 DEEPSEEK_API_KEY 环境变量")
    st.stop()

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# ---- 文件路径：都相对于 app.py 所在目录（不管从哪里启动 streamlit 都找得到）----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---- 本地持久化：刷新页面后仍能恢复对话和数据 ----
CHAT_FILE = os.path.join(BASE_DIR, "chat_history.json")   # 对话存档
DATA_FILE = os.path.join(BASE_DIR, "data.csv")            # 上次上传的数据

def save_messages():
    """把对话存到本地文件（图表数据不存，JSON 存不了 DataFrame）"""
    clean = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
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

def generate_code(question, df):
    schema = df.dtypes.to_string()   # 数据的"体检报告"：每列的列名和类型
    system_prompt = (f"你是数据分析专家。数据是 pandas DataFrame（变量名 df），每一行是一条销售记录，列名和类型：\n{schema}\n"
                        "请编写 pandas 代码回答用户问题。要求：\n"
                        "1. 只输出代码，不解释；结果存进 answer 变量；不要 import；df 已加载。\n"
                        "2. 问题里问'哪个商品/品类/地区…最高/最多/合计'这类，必须先按对应维度分组汇总再比较，不能直接对单行取最大。\n"
                        "3. 示例：'哪个商品销售额最高' → answer = df.groupby('商品')['销售额'].sum().idxmax()\n"
                        "4. 如果问题适合用图表展示（对比、分布、趋势），让 answer 是 pandas Series 或 DataFrame：索引是类别/时间，值是数值。")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        stream=False,
    )
    return response.choices[0].message.content


def run_code(code, df):
    local_vars = {"df": df}
    exec(code, {"__builtins__": {}}, local_vars)
    return local_vars.get("answer")


def generate_answer(question, result):
    system_prompt = "你是数据分析专家。根据用户的问题和执行结果生成自然语言回答，简洁、给出具体数字。"
    user_message = f"用户问题: {question}\n\nPython 执行结果: \n{result}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        stream=False,
    )
    return response.choices[0].message.content


def generate_sql(question, schema_text):
    """第 1 步（数据库模式）：让 AI 写 SQL，而不是直接回答"""
    system_prompt = (f"你是 SQL 专家。数据库模式如下：\n{schema_text}\n"
                     "请根据用户问题生成 SQL 查询语句。要求：\n"
                     "1. 只输出 SQL 语句本身（可直接执行的查询），不要解释，不要加任何 Python 前缀（如 answer = ）、引号或 markdown 代码块。\n"
                     "2. 问题里问'哪个商品/品类/地区…最高/最多/合计'这类，必须先按对应维度分组汇总再比较，不能直接对单行取最大。\n"
                     "3. 示例：'哪个商品销售额最高' → SELECT 商品, SUM(销售额) AS 总销售额 FROM sales GROUP BY 商品 ORDER BY 总销售额 DESC LIMIT 1\n"
                     "4. 如果问题适合用图表展示（对比、分布、趋势），让查询结果包含类别/时间列和数值列。")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        stream=False,
    )
    return response.choices[0].message.content


def run_sql(sql, conn):
    """第 2 步（数据库模式）：执行 SQL，结果转成 DataFrame"""
    return pd.read_sql_query(sql, conn)

# ---------- 3.5 图表美化 ----------
# 验证过的分类调色板（dataviz 规范）：按顺序取用，不循环
CHART_PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

def render_chart(chart_data):
    """把 Series/DataFrame 画成好看的图表：类别 → 柱状图，月份/数值 → 折线图"""
    if isinstance(chart_data, pd.Series):
        # Series（如 groupby 结果）：索引是类别/时间，值在列里 → 摊平成两列
        df_chart = chart_data.reset_index()
    elif isinstance(chart_data.index, pd.RangeIndex):
        # DataFrame 且是默认数字索引（SQL 查询结果就是这种）→ 直接两列，别再插行号
        df_chart = chart_data.copy()
    else:
        # DataFrame 且索引有内容（比如按商品分组的 DataFrame）→ 把索引变成一列
        df_chart = chart_data.reset_index()
    # 第一列是类别/时间，最后一列是数值
    x_col, y_col = df_chart.columns[0], df_chart.columns[-1]
    df_chart = df_chart[[x_col, y_col]]
    n = len(df_chart)

    # 判断 x 适不适合画折线：是数字，或是"1月/2月"这类有序月份
    x_str = df_chart[x_col].astype(str)
    is_numeric = pd.api.types.is_numeric_dtype(df_chart[x_col])
    is_month = (len(df_chart) > 0 and x_str.str.match(r"^\d{1,2}月$").all())

    if is_numeric or is_month:
        # 折线图：单色用第一个槽位，带数据点
        if is_month:
            # "1月"按数字大小排序（否则 10月 会排到 2月 前面）
            months = sorted(x_str.unique(), key=lambda s: int(s.replace("月", "")))
            x_enc = alt.X(x_col, type="ordinal", sort=months,
                          axis=alt.Axis(labelAngle=0, title=None))
        else:
            x_enc = alt.X(x_col, type="quantitative",
                          axis=alt.Axis(labelAngle=0, title=None))
        chart = alt.Chart(df_chart).mark_line(point=True).encode(
            x=x_enc,
            y=alt.Y(y_col, type="quantitative", title=None),
            color=alt.value(CHART_PALETTE[0]),
            tooltip=[x_col, y_col],
        )
    else:
        # 类别索引 → 柱状图：按数值高到低排，柱子细一半，标签横着放
        x_scale = alt.Scale(paddingInner=0.5)   # 柱子占格子一半宽（细）
        x_axis = alt.Axis(labelAngle=0)          # 分类文字横着放
        chart = alt.Chart(df_chart).mark_bar().encode(
            x=alt.X(x_col, type="nominal", sort="-y", title=None,
                    axis=x_axis, scale=x_scale),
            y=alt.Y(y_col, type="quantitative", title=None),   # 柱顶有数字，去掉旋转的 Y 标题
            color=alt.Color(x_col, type="nominal",
                            scale=alt.Scale(range=CHART_PALETTE[:n]),
                            legend=None),
            tooltip=[x_col, y_col],
        )
        # 柱顶数值标签：用墨色文字，不用系列色（x 用同一个 scale，才能对齐柱子）
        labels = alt.Chart(df_chart).mark_text(dy=-8, size=12).encode(
            x=alt.X(x_col, type="nominal", sort="-y", scale=x_scale),
            y=alt.Y(y_col, type="quantitative"),
            text=alt.Text(y_col, format=","),
            color=alt.value("#52514e"),
        )
        chart = chart + labels

    st.altair_chart(chart, width="stretch")


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

# 判断当前有没有可用数据（数据库模式连上就算有）
has_data = (source == "数据库") or (df is not None)

if not has_data:
    st.info("👆 先上传数据文件，然后就能用自然语言提问了")

prompt = st.chat_input("比如：哪个商品卖得最好？", disabled=not has_data)
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    try:
        if source == "数据库":
            sql = generate_sql(prompt, schema_text)
            result = run_sql(sql, conn)
            debug_code, debug_lang = sql, "sql"
        else:
            code = generate_code(prompt, df)
            result = run_code(code, df)
            debug_code, debug_lang = code, "python"
        answer = generate_answer(prompt, result)
    except Exception as e:
        st.session_state.messages.pop()
        st.error(f"出错了：{e}")
    else:
        # 执行结果是 Series/DataFrame 且有多行（≥2 行）才有画图意义：
        # 比如"各品类总额"3 行 → 柱状图；"哪个最高"只有 1 行 → 不画图，否则一根孤零零的柱子像张空表
        chart_data = result if isinstance(result, (pd.Series, pd.DataFrame)) and len(result) > 1 else None
        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "chart_data": chart_data,
        })
        save_messages()   # 存盘：刷新后对话还在
        with st.chat_message("assistant"):
            st.write(answer)
            if chart_data is not None:
                render_chart(chart_data)
        with st.expander("🔍 调试：AI 生成的代码"):
            st.code(debug_code, language=debug_lang)
            st.write(f"执行结果：{result}")