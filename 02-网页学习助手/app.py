# ============================================================
# 网页版 AI 学习助手（Streamlit）
# 功能：
#   1. 浏览器里的连续对话界面
#   2. 角色设定：企业数据管家
#   3. 报错不崩，错误在界面里提示
# 运行：streamlit run app.py
# ============================================================

import os
import streamlit as st
from openai import OpenAI

# ---------- 1. 配置 ----------
api_key = os.environ.get('DEEPSEEK_API_KEY')
if not api_key:
    st.error("请先设置 DEEPSEEK_API_KEY 环境变量")
    st.stop()          # 停止往下执行

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# ---------- 2. 初始化对话历史 ----------
# Streamlit 每次交互都会重跑整个脚本，普通变量会归零。
# st.session_state 是"存档"：存进去的东西跨重跑保留。
# 所以对话历史必须放在这里，否则每句话都会被冲掉。
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "企业数据管家\n理解订单、商品、SKU、店铺、仓库、采购、库存、物流、成本、\n退款、利润等实体及其关系。\n所有指标必须遵循企业指标字典，不得自行创造统计口径。"},
        # ===== 你的代码 =====

    ]

# ---------- 3. 页面标题 ----------
st.title("💬 AI 学习助手")

# ---------- 4. 把历史消息画成对话气泡 ----------
# 每次重跑，这里都会把存档里的所有消息重新画一遍
for msg in st.session_state.messages:
    if msg["role"] == "system":
        continue          # system 人设不显示，只发给 API 用
    # TODO-2: 用 st.chat_message 画气泡
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# ---------- 5. 聊天输入框 ----------
# st.chat_input 是页面底部的输入框：用户一提交就返回文字，没提交返回 None
prompt = st.chat_input("问点什么吧...")
if prompt:
    # 用户说了句话 → 存进历史 + 立刻显示
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # 调 API（思路和命令行版一模一样，只是把 print 换成 st 显示）
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=st.session_state.messages,
            stream=False,
        )
        assistant_reply = response.choices[0].message.content

    except Exception as e:
        # TODO-3: 报错时撤掉刚进历史的那条用户消息，并在界面里提示错误
        st.session_state.messages.pop()  # 撤掉最后一条消息
        st.error(f"请求出错：{e}")

    else:
        # 成功：存进历史 + 在界面里画气泡
        st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
        with st.chat_message("assistant"):
            st.write(assistant_reply)