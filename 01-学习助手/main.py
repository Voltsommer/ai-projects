# ============================================================
# 命令行 AI 学习助手（进阶版）
# 功能：
#   1. 连续对话（记住上下文）
#   2. 角色设定：AI 学习助手
#   3. /exit 退出程序
#   4. 报错不崩溃，还能继续聊
# ============================================================

import os
from openai import OpenAI

# ---------- 1. 配置（照你 DeepSeek调用测试.py 里那套） ----------
api_key = os.environ.get('DEEPSEEK_API_KEY')
if not api_key:
    raise ValueError("请设置 DEEPSEEK_API_KEY 环境变量")

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

# ---------- 2. 对话历史 ----------
# 这一个列表，装着我们和 AI 说过的每一句话。
# 模型是无记忆的，每次调用都要把"全部历史"发过去，它才知道上下文。
messages = [
    {"role": "system", "content": "你是一个耐心且知识渊博的 AI 学习助手，擅长解答各种学习相关的问题。"},

]

# ---------- 3. 开场白 ----------
print("你好！我是你的 AI 学习助手。输入问题开始，输入 /exit 退出。")

# ---------- 4. 对话主循环 ----------
while True:
    # 读取用户输入
    user_input = input("你 > ")

    # TODO-2: 用户输入 /exit 就退出程序
    # 提示：if 判断 → break 跳出循环
    if user_input.strip() == "/exit":
        break

    # TODO-3: 把用户这句话加入对话历史（这是"记住上下文"的关键）
    messages.append({"role": "user", "content": user_input})

    # 调用模型（这里照搬你测试脚本里的写法，只是把 messages 换成完整历史）
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=False,
        )
    
        # 取出模型的回复文本
        assistant_reply = response.choices[0].message.content


    except Exception as e:
        # 报错不崩：打印错误信息，程序继续跑
        messages.pop()  # 把刚才用户的输入从对话历史里删掉（否则历史里会留一条没人回答的问题）
        print(f"\n[出错了] {e}\n我们继续聊~")
    else:
        messages.append({"role": "assistant", "content": assistant_reply})
        print(f"\nAI > {assistant_reply}\n")