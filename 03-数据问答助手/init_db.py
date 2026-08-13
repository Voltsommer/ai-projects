# ============================================================
# init_db.py：把 sample_data.csv 灌进 SQLite 数据库
# 运行一次即可：python init_db.py
# ============================================================

import sqlite3
import pandas as pd

DB_FILE = "sales.db"

# 1. 用 pandas 读示例数据
df = pd.read_csv("sample_data.csv")

# 2. 连接数据库（文件不存在会自动创建）
conn = sqlite3.connect(DB_FILE)

# 3. 建表（先删旧的再重建，保证可重复运行）
conn.execute("DROP TABLE IF EXISTS sales")
conn.execute("""
    CREATE TABLE sales (
        商品  TEXT,
        品类  TEXT,
        月份  TEXT,
        地区  TEXT,
        销量  INTEGER,
        销售额 INTEGER
    )
""")

# 4. 把 CSV 每一行插进数据库（? 是占位符，防止 SQL 注入）
for _, row in df.iterrows():
    conn.execute(
        "INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?)",
        (row["商品"], row["品类"], row["月份"], row["地区"], row["销量"], row["销售额"]),
    )

# 5. 提交事务，关闭连接
conn.commit()
conn.close()

print(f"✅ 已创建 {DB_FILE}，表 sales，共 {len(df)} 行")