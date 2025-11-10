import os
import sqlite3
import pandas as pd
from pathlib import Path

# 參數區
base_dir = r"C:\Users\M3188\Desktop\AI 船期管理系統\data"
excel_filename = "台灣碼頭泊位資訊.xlsx"
db_name = "TaiwanPort_wharf_information.db"  # 這裡改成 .db
table_name = "wharf_information"

excel_path = Path(base_dir) / excel_filename
db_path = Path(base_dir) / db_name

# 建立目錄（如不存在）
os.makedirs(base_dir, exist_ok=True)

# 讀取 Excel（若實際是 CSV，改用 read_csv）
df = pd.read_excel(excel_path, dtype=str)

# 欄位標題（確保與提供資料一致）
expected_cols = [
    "PortName_en","PortName_cn","wharf_code","wharf_name", "basinName","wharf_length",
    "wharf_depth","wharf_type","wharf_area","bollard_count","bollard_code"
]

# 標準化欄位名稱
df.columns = [str(c).strip() for c in df.columns]

# 確認欄位存在
missing = [c for c in expected_cols if c not in df.columns]
if missing:
    raise ValueError(f"Excel 欄位缺少: {missing}. 目前欄位: {list(df.columns)}")

# 僅取所需欄位並依序排列
df = df[expected_cols]

# 清理資料
def normalize_null(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    if s.lower() in {"null", "none", ""}:
        return None
    return s

for c in df.columns:
    df[c] = df[c].map(normalize_null)

def to_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except:
        return None

def to_int(v):
    if v is None:
        return None
    try:
        return int(float(v))
    except:
        return None

df["wharf_length"] = df["wharf_length"].map(to_float)
df["wharf_depth"]  = df["wharf_depth"].map(to_float)
df["bollard_count"] = df["bollard_count"].map(to_int)

# 建立/連線 SQLite
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

# 重建資料表
cur.execute(f"DROP TABLE IF EXISTS {table_name}")
cur.execute(f"""
CREATE TABLE {table_name} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    PortName_en TEXT,
    PortName_cn TEXT,
    wharf_code TEXT,
    wharf_name TEXT,
    basinName TEXT,
    wharf_length REAL,
    wharf_depth REAL,
    wharf_type TEXT,
    wharf_area TEXT,
    bollard_count INTEGER,
    bollard_code TEXT
);
""")

# 寫入資料
insert_sql = f"""
INSERT INTO {table_name} (
    PortName_en, PortName_cn, wharf_code, wharf_name, basinName, wharf_length,
    wharf_depth, wharf_type, wharf_area, bollard_count, bollard_code
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
records = df.where(pd.notnull(df), None).to_records(index=False)
cur.executemany(insert_sql, list(records))

# 索引
cur.execute(f"CREATE INDEX idx_{table_name}_wharf_code ON {table_name}(wharf_code)")
cur.execute(f"CREATE INDEX idx_{table_name}_port_en ON {table_name}(PortName_en)")
cur.execute(f"CREATE INDEX idx_{table_name}_port_cn ON {table_name}(PortName_cn)")

conn.commit()
conn.close()

print(f"資料已寫入：{db_path}")
