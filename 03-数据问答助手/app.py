# ============================================================
# 企业数据问答助手（Streamlit）— 里程碑③b
# 升级点：不再把数据"全文"喂给 AI 心算，
#         而是让 AI 写 pandas 代码，Python 执行拿到准确结果。
# 流程：AI 写代码 → Python 执行 → AI 把结果翻译成人话
# 运行：python -m streamlit run app.py
# ============================================================

import os
import pandas as pd
import streamlit as st
from openai import OpenAI

api_key = os.environ.get('DEEPSEEK_API_KEY')
if not api_key:
    st.error("请先设置 DEEPSEEK_API_KEY 环境变量")
    st.stop()

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

st.title("📊 企业数据问答助手")

uploaded = st.file_uploader("上传数据文件（CSV 或 Excel）", type=["csv", "xlsx"])

df = None
if uploaded is not None:
    if uploaded.name.endswith(".csv"):
        df = pd.read_csv(uploaded)
    elif uploaded.name.endswith(".xlsx"):
        df = pd.read_excel(uploaded)

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


if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        # 如果这条消息带了图表数据，就在文字下面画出来
        if msg.get("chart_data") is not None:
            st.bar_chart(msg["chart_data"])

if uploaded is None:
    st.info("👆 先上传数据文件，然后就能用自然语言提问了")

prompt = st.chat_input("比如：哪个商品卖得最好？", disabled=uploaded is None)
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    try:
        code = generate_code(prompt, df)
        result = run_code(code, df)
        answer = generate_answer(prompt, result)
    except Exception as e:
        st.session_state.messages.pop()
        st.error(f"出错了：{e}")
    else:
        # 执行结果是 Series/DataFrame（如"各品类总额"）→ 存成图表数据，随消息一起保存
        chart_data = result if isinstance(result, (pd.Series, pd.DataFrame)) else None
        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "chart_data": chart_data,
        })
        with st.chat_message("assistant"):
            st.write(answer)
            if chart_data is not None:
                st.bar_chart(chart_data)
        with st.expander("🔍 调试：AI 生成的代码"):
            st.code(code, language="python")
            st.write(f"Python 执行结果：{result}")