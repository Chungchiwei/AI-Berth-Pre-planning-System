"""
資料庫管理模組 - 整合修正版
版本: 3.0
修正: 
  1. 避免重複資料（UNIQUE 約束）
  2. 新增泊位占用計算
  3. 新增資料清理功能
  4. 保留原有 IFA 表格結構
  5. 簡化快取管理（移除獨立快取表）
"""
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import logging
import sys
from typing import Optional, List, Dict, Any  # ✅ 加入 Optional
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH, CACHE_TTL_MINUTES, TIMEZONE
import pytz
from pathlib import Path
# 設定日誌
logger = logging.getLogger(__name__)


def ensure_db_directory():
    """確保資料庫目錄存在"""
    db_path = Path(DB_PATH)
    
    # 如果是雲端環境，/tmp 已存在，不需建立
    if not os.getenv('STREAMLIT_SHARING_MODE'):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"✓ 資料庫目錄已確認: {db_path.parent}")
        
        
def get_db_connection():
    """
    取得資料庫連線
    
    Returns:
        sqlite3.Connection: 資料庫連線物件
    """
    # 確保目錄存在
    ensure_db_directory()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """初始化資料庫，建立所有必要的表格"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # ==================== IFA_D005: 船席現況及指泊表  ====================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ifa_d005 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- 基本資訊
            port_code TEXT NOT NULL,
            port_name TEXT NOT NULL,           
            
            -- Row1 欄位 (12 欄)
            wharf_code TEXT,            -- 碼頭編號
            alongside_status TEXT,       -- 現靠/接靠
            mooring_type TEXT,           -- 靠泊方式
            prev_wharf TEXT,             -- 移泊前碼頭
            vessel_no TEXT,              -- 船舶號數
            ship_type TEXT,              -- 船種
            vessel_ename TEXT,           -- 英文船名
            visa_no TEXT,                -- 簽證編號
            eta_berth TEXT,              -- 預定靠泊時間
            etd_berth TEXT,              -- 預定離泊時間
            prev_port TEXT,              -- 前一港
            isps_level TEXT,             -- 保全等級
            
            -- Row2 欄位 (11 欄，因 rowspan)
            wharf_name TEXT,             -- 碼頭名稱
            movement_status TEXT,        -- 動態
            via_port TEXT,               -- 通過港口
            gt REAL,                     -- 總噸
            arrival_purpose TEXT,        -- 到港目的
            vessel_cname TEXT,           -- 中文船名
            agent TEXT,                  -- 港口代理
            ata_berth TEXT,              -- 實際靠泊時間
            eta_pilot TEXT,              -- 預定引水時間
            next_port TEXT,              -- 次一港
            loa_m REAL,                  -- 船舶總長
            
            -- 額外欄位
            can_berth_container INTEGER DEFAULT 0,
            crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            saved_at TEXT,
            
            -- 🔥 唯一性約束：避免重複資料
            UNIQUE(port_code, wharf_code, vessel_ename, eta_berth, crawled_at)
        )
        """)

        # ==================== ifa_d003: 進港船舶表 (11+11 欄位) ====================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ifa_d003 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- 基本資訊
            port_code TEXT NOT NULL,
            port_name TEXT NOT NULL,
            
            -- Row1 欄位 (11 欄)
            call_sign TEXT,              -- 船舶呼號
            ship_type TEXT,              -- 船種
            vessel_ename TEXT,           -- 英文船名
            visa_no TEXT,                -- 簽證編號
            eta_report TEXT,             -- 預報進港時間
            eta_berth TEXT,              -- 預定靠泊時間
            berth TEXT,                  -- 靠泊碼頭
            prev_port TEXT,              -- 前一港
            vhf_report_time TEXT,        -- VHF報到時間
            loa_m REAL,                  -- 船長(M)
            anchor_time TEXT,            -- 下錨時間
            
            -- Row2 欄位 (11 欄)
            imo TEXT,                    -- IMO
            agent TEXT,                  -- 港口代理
            vessel_cname TEXT,           -- 中文船名
            arrival_purpose TEXT,        -- 到港目的
            inport_pass_time TEXT,       -- 進港通過港口時間
            etd_berth TEXT,              -- 預定離泊時間
            ata_berth TEXT,              -- 靠泊時間
            next_port TEXT,              -- 次一港
            captain_report_eta TEXT,     -- 船長報到ETA
            gt REAL,                     -- 總噸
            inport_5nm_time TEXT,        -- 進港通過5浬時間
            
            -- 額外欄位
            can_berth_container INTEGER DEFAULT 0,
            crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            saved_at TEXT,
            
            -- 🔥 唯一性約束：避免重複資料
            UNIQUE(port_code, vessel_ename, eta_berth, crawled_at)
        )
        """)

        # ==================== ifa_d004: 出港船舶表 (9+8 欄位) ====================
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ifa_d004 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            
            -- 基本資訊
            port_code TEXT NOT NULL,
            port_name TEXT NOT NULL,
            
            -- Row1 欄位 (9 欄)
            call_sign TEXT,              -- 船舶呼號
            ship_type TEXT,              -- 船種
            vessel_ename TEXT,           -- 英文船名
            visa_no TEXT,                -- 簽證編號
            etd_report TEXT,             -- 預報出港時間
            etd_berth TEXT,              -- 預定離泊時間 (rowspan)
            berth TEXT,                  -- 靠泊碼頭
            prev_port TEXT,              -- 前一港
            isps_level TEXT,             -- 保全等級
            
            -- Row2 欄位 (8 欄，因 rowspan)
            imo TEXT,                    -- IMO
            agent TEXT,                  -- 港口代理
            vessel_cname TEXT,           -- 中文船名
            arrival_purpose TEXT,        -- 到港目的
            outport_pass_time TEXT,      -- 出港通過港口時間
            atd_berth TEXT,              -- 離泊時間
            next_port TEXT,              -- 次一港
            loa_m REAL,                  -- 船長(M)
            
            -- 額外欄位
            can_berth_container INTEGER DEFAULT 0,
            crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            saved_at TEXT,
            
            -- 🔥 唯一性約束：避免重複資料
            UNIQUE(port_code, vessel_ename, etd_berth, crawled_at)
        )
        """)

        # ===== 建立索引 =====
        
        indexes = [
            # D005 索引
            "CREATE INDEX IF NOT EXISTS idx_d005_port ON ifa_d005(port_code, port_name)",
            "CREATE INDEX IF NOT EXISTS idx_d005_wharf ON ifa_d005(wharf_code, wharf_name)",
            "CREATE INDEX IF NOT EXISTS idx_d005_vessel ON ifa_d005(vessel_ename, vessel_cname)",
            "CREATE INDEX IF NOT EXISTS idx_d005_time ON ifa_d005(eta_berth, etd_berth)",
            "CREATE INDEX IF NOT EXISTS idx_d005_status ON ifa_d005(alongside_status, movement_status)",
            "CREATE INDEX IF NOT EXISTS idx_d005_container ON ifa_d005(can_berth_container)",
            "CREATE INDEX IF NOT EXISTS idx_d005_crawled_at ON ifa_d005(crawled_at)",
            "CREATE INDEX IF NOT EXISTS idx_d005_ship_type ON ifa_d005(ship_type)",
            
            # D003 索引
            "CREATE INDEX IF NOT EXISTS idx_d003_port ON ifa_d003(port_code, port_name)",
            "CREATE INDEX IF NOT EXISTS idx_d003_vessel ON ifa_d003(vessel_ename, vessel_cname)",
            "CREATE INDEX IF NOT EXISTS idx_d003_eta ON ifa_d003(eta_berth, eta_report)",
            "CREATE INDEX IF NOT EXISTS idx_d003_port_route ON ifa_d003(prev_port, next_port)",
            "CREATE INDEX IF NOT EXISTS idx_d003_container ON ifa_d003(can_berth_container)",
            "CREATE INDEX IF NOT EXISTS idx_d003_crawled_at ON ifa_d003(crawled_at)",
            "CREATE INDEX IF NOT EXISTS idx_d003_ship_type ON ifa_d003(ship_type)",
            "CREATE INDEX IF NOT EXISTS idx_d003_berth ON ifa_d003(berth)",
            
            # D004 索引
            "CREATE INDEX IF NOT EXISTS idx_d004_port ON ifa_d004(port_code, port_name)",
            "CREATE INDEX IF NOT EXISTS idx_d004_vessel ON ifa_d004(vessel_ename, vessel_cname)",
            "CREATE INDEX IF NOT EXISTS idx_d004_etd ON ifa_d004(etd_berth, etd_report)",
            "CREATE INDEX IF NOT EXISTS idx_d004_next_port ON ifa_d004(next_port)",
            "CREATE INDEX IF NOT EXISTS idx_d004_container ON ifa_d004(can_berth_container)",
            "CREATE INDEX IF NOT EXISTS idx_d004_crawled_at ON ifa_d004(crawled_at)",
            "CREATE INDEX IF NOT EXISTS idx_d004_ship_type ON ifa_d004(ship_type)",
            "CREATE INDEX IF NOT EXISTS idx_d004_berth ON ifa_d004(berth)",
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)

        conn.commit()
        logger.info("✓ 資料庫初始化完成")
        
    except sqlite3.Error as e:
        logger.error(f"✗ 資料庫初始化失敗: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def migrate_database():
    """
    資料庫遷移：新增缺失的欄位
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # ==================== D005 遷移 ====================
        d005_migrations = [
            ('port_code', 'TEXT NOT NULL DEFAULT ""'),
            ('port_name', 'TEXT NOT NULL DEFAULT ""'),
            ('can_berth_container', 'INTEGER DEFAULT 0'),
            ('alongside_status', 'TEXT'),
            ('mooring_type', 'TEXT'),
            ('prev_wharf', 'TEXT'),
            ('vessel_no', 'TEXT'),
            ('movement_status', 'TEXT'),
            ('via_port', 'TEXT'),
            ('isps_level', 'TEXT'),
            ('saved_at', 'TEXT'),
        ]
        
        # ==================== D003 遷移 ====================
        d003_migrations = [
            ('port_code', 'TEXT NOT NULL DEFAULT ""'),
            ('port_name', 'TEXT NOT NULL DEFAULT ""'),
            ('can_berth_container', 'INTEGER DEFAULT 0'),
            ('eta_report', 'TEXT'),
            ('vhf_report_time', 'TEXT'),
            ('anchor_time', 'TEXT'),
            ('inport_pass_time', 'TEXT'),
            ('captain_report_eta', 'TEXT'),
            ('inport_5nm_time', 'TEXT'),
            ('ata_berth', 'TEXT'),
            ('etd_berth', 'TEXT'),
            ('saved_at', 'TEXT'),
        ]
        
        # ==================== D004 遷移 ====================
        d004_migrations = [
            ('port_code', 'TEXT NOT NULL DEFAULT ""'),
            ('port_name', 'TEXT NOT NULL DEFAULT ""'),
            ('can_berth_container', 'INTEGER DEFAULT 0'),
            ('etd_report', 'TEXT'),
            ('outport_pass_time', 'TEXT'),
            ('atd_berth', 'TEXT'),
            ('saved_at', 'TEXT'),
        ]
        
        migrations = {
            'ifa_d005': d005_migrations,
            'ifa_d003': d003_migrations,
            'ifa_d004': d004_migrations,
        }
        
        for table, columns in migrations.items():
            # 檢查表格是否存在
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table,))
            
            if not cursor.fetchone():
                logger.warning(f"⚠ 表格 {table} 不存在，跳過遷移")
                continue
            
            # 取得現有欄位
            cursor.execute(f"PRAGMA table_info({table})")
            existing_columns = [row[1] for row in cursor.fetchall()]
            
            # 新增缺失的欄位
            for column_name, column_type in columns:
                if column_name not in existing_columns:
                    logger.info(f"正在為 {table} 新增 {column_name} 欄位...")
                    try:
                        cursor.execute(f"""
                            ALTER TABLE {table} 
                            ADD COLUMN {column_name} {column_type}
                        """)
                        conn.commit()
                        logger.info(f"✓ {table}: 已新增 {column_name} 欄位")
                    except sqlite3.Error as e:
                        logger.error(f"✗ {table}: 新增 {column_name} 失敗 - {e}")
                else:
                    logger.debug(f"✓ {table}: {column_name} 欄位已存在")
        
        logger.info("✓ 資料庫遷移完成")
        
    except sqlite3.Error as e:
        logger.error(f"✗ 資料庫遷移失敗: {e}")
        conn.rollback()
        raise
    
    finally:
        conn.close()

def save_to_database(df: pd.DataFrame, table_name: str, port_code: str = None) -> bool:
    """
    儲存 DataFrame 到 SQLite 資料庫
    
    Args:
        df: 要儲存的 DataFrame
        table_name: 資料表名稱 (例如: 'ifa_d005', 'ifa_d003', 'ifa_d004')
        port_code: 港口代碼 (例如: 'KEL', 'KHH')，可選參數
    
    Returns:
        bool: 儲存是否成功
    """
    if df is None or df.empty:
        print(f"⚠️  DataFrame 為空，跳過儲存")
        return False
    
    try:
        from pathlib import Path
        
        # 確保資料庫目錄存在
        db_path = Path(DB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 複製 DataFrame 避免修改原始資料
        df_to_save = df.copy()
        
        # ✅ 添加 port_code 欄位（如果提供且不存在）
        if port_code and 'port_code' not in df_to_save.columns:
            df_to_save['port_code'] = port_code
        
        # 添加時間戳記
        if 'saved_at' not in df_to_save.columns:
            df_to_save['saved_at'] = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        
        if 'crawled_at' not in df_to_save.columns:
            df_to_save['crawled_at'] = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        
        # 連接資料庫
        conn = sqlite3.connect(DB_PATH)
        
        # 儲存到資料庫（追加模式，忽略重複）
        try:
            df_to_save.to_sql(
                name=table_name,
                con=conn,
                if_exists='append',
                index=False
            )
            conn.commit()
            print(f"✅ 成功儲存 {len(df_to_save)} 筆資料到 {table_name}")
            return True
            
        except sqlite3.IntegrityError as e:
            # 如果有重複資料，逐筆插入並跳過重複
            print(f"⚠️  偵測到重複資料，正在逐筆插入...")
            
            cursor = conn.cursor()
            success_count = 0
            duplicate_count = 0
            
            for _, row in df_to_save.iterrows():
                try:
                    placeholders = ', '.join(['?' for _ in row])
                    columns = ', '.join(row.index)
                    sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
                    cursor.execute(sql, tuple(row))
                    success_count += 1
                except sqlite3.IntegrityError:
                    duplicate_count += 1
                    continue
            
            conn.commit()
            print(f"✅ 成功儲存 {success_count} 筆資料，跳過 {duplicate_count} 筆重複資料")
            return True
        
    except Exception as e:
        print(f"❌ 儲存失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if 'conn' in locals():
            conn.close()

def query_latest_data(table_name: str, port_code: str = None, limit: int = 100) -> pd.DataFrame:
    """
    查詢最新的資料
    
    Args:
        table_name: 表格名稱
        port_code: 港口代碼（可選）
        limit: 限制筆數
    
    Returns:
        pd.DataFrame: 查詢結果
    """
    conn = get_db_connection()
    
    try:
        if port_code:
            query = f"""
            SELECT * FROM {table_name}
            WHERE port_code = ?
            ORDER BY crawled_at DESC
            LIMIT ?
            """
            df = pd.read_sql_query(query, conn, params=(port_code, limit))
        else:
            query = f"""
            SELECT * FROM {table_name}
            ORDER BY crawled_at DESC
            LIMIT ?
            """
            df = pd.read_sql_query(query, conn, params=(limit,))
        
        logger.info(f"✓ {table_name}: 查詢到 {len(df)} 筆資料")
        return df
        
    except sqlite3.Error as e:
        logger.error(f"✗ {table_name}: 查詢失敗 - {e}")
        return pd.DataFrame()
    
    finally:
        conn.close()

def is_cache_valid(table_name: str, port_code: str, cache_hours: float = None) -> bool:
    """
    檢查快取是否有效
    
    Args:
        table_name: 表格名稱
        port_code: 港口代碼
        cache_hours: 快取有效時間（小時），若為 None 則使用 CACHE_TTL_MINUTES
    
    Returns:
        bool: 快取是否有效
    """
    conn = get_db_connection()
    
    try:
        query = f"""
        SELECT MAX(crawled_at) as latest_time
        FROM {table_name}
        WHERE port_code = ?
        """
        
        cursor = conn.cursor()
        cursor.execute(query, (port_code,))
        result = cursor.fetchone()
        
        if result and result['latest_time']:
            # 🔥 修正：統一使用帶時區的 datetime
            latest_time_str = result['latest_time']
            
            # 嘗試解析時間字串
            try:
                # 如果是 ISO 格式且包含時區資訊
                latest_time = datetime.fromisoformat(latest_time_str)
                
                # 如果是 naive datetime，加上時區
                if latest_time.tzinfo is None:
                    latest_time = pytz.timezone(TIMEZONE).localize(latest_time)
                
            except Exception as e:
                logger.warning(f"解析時間失敗: {latest_time_str}, 錯誤: {e}")
                return False
            
            # 使用帶時區的當前時間
            now = datetime.now(pytz.timezone(TIMEZONE))
            
            # 計算時間差
            age_minutes = (now - latest_time).total_seconds() / 60
            
            # 如果有指定 cache_hours，使用它；否則使用 CACHE_TTL_MINUTES
            if cache_hours is not None:
                threshold_minutes = cache_hours * 60
            else:
                threshold_minutes = CACHE_TTL_MINUTES
            
            is_valid = age_minutes < threshold_minutes
            
            logger.debug(
                f"快取檢查 - {table_name}@{port_code}: "
                f"年齡={age_minutes:.1f}分鐘, "
                f"閾值={threshold_minutes:.1f}分鐘, "
                f"有效={is_valid}"
            )
            
            return is_valid
        
        logger.debug(f"快取檢查 - {table_name}@{port_code}: 無資料")
        return False
        
    except sqlite3.Error as e:
        logger.error(f"✗ 檢查快取失敗: {e}")
        return False
    
    finally:
        conn.close()

def get_cache_age(table_name: str, port_code: str) -> Optional[float]:
    """
    取得快取年齡（分鐘）
    
    Args:
        table_name: 資料表名稱 (ifa_d005, ifa_d003, ifa_d004)
        port_code: 港口代碼
    
    Returns:
        快取年齡（分鐘），如果無資料則回傳 None
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ✅ 修正：使用 crawled_at 而非 crawl_time
        cursor.execute(f"""
            SELECT MAX(crawled_at) 
            FROM {table_name} 
            WHERE port_code = ?
        """, (port_code,))
        
        result = cursor.fetchone()
        latest_time = result[0] if result else None
        
        conn.close()
        
        # 檢查是否有資料
        if latest_time is None:
            print(f"[DEBUG] {table_name} 無快取資料")
            return None
        
        # 解析時間
        if isinstance(latest_time, str):
            # 處理可能的時區格式
            latest_time = latest_time.replace('Z', '+00:00')
            latest_dt = datetime.fromisoformat(latest_time)
        else:
            latest_dt = latest_time
        
        # 確保有時區
        if latest_dt.tzinfo is None:
            latest_dt = pytz.timezone(TIMEZONE).localize(latest_dt)
        
        # 計算時間差（分鐘）
        now = datetime.now(pytz.timezone(TIMEZONE))
        age_minutes = (now - latest_dt).total_seconds() / 60
        
        print(f"[DEBUG] {table_name} 快取年齡: {age_minutes:.1f} 分鐘")
        
        return age_minutes
        
    except Exception as e:
        print(f"[ERROR] 取得快取年齡失敗: {e}")
        import traceback
        traceback.print_exc()
        return None


def clear_old_data(table_name: str, days: int = 7) -> bool:
    """
    清除舊資料
    
    Args:
        table_name: 表格名稱
        days: 保留天數
    
    Returns:
        bool: 是否清除成功
    """
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        # 🔥 修正：使用帶時區的 datetime
        now = datetime.now(pytz.timezone(TIMEZONE))
        cutoff_date = now - timedelta(days=days)
        
        # 刪除舊資料
        cursor.execute(f"""
            DELETE FROM {table_name}
            WHERE crawled_at < ?
        """, (cutoff_date.isoformat(),))
        
        deleted_count = cursor.rowcount
        
        conn.commit()
        logger.info(f"✓ {table_name}: 已清除 {deleted_count} 筆超過 {days} 天的舊資料")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"✗ {table_name}: 清除舊資料失敗 - {e}")
        conn.rollback()
        return False
    
    finally:
        conn.close()

def clear_all_data(table_name: str = None) -> bool:
    """
    清空指定表格或所有表格
    
    Args:
        table_name: 表格名稱（若為 None 則清空所有表格）
    
    Returns:
        bool: 是否清除成功
    """
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        if table_name:
            tables = [table_name]
        else:
            tables = ['ifa_d005', 'ifa_d003', 'ifa_d004']
        
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
            deleted_count = cursor.rowcount
            logger.info(f"✓ {table}: 已清空 {deleted_count} 筆資料")
        
        conn.commit()
        return True
        
    except sqlite3.Error as e:
        logger.error(f"✗ 清空資料失敗: {e}")
        conn.rollback()
        return False
    
    finally:
        conn.close()

def remove_duplicate_records(table_name: str = None) -> dict:
    """
    🔥 移除重複記錄（保留最新）
    
    Args:
        table_name: 表格名稱（若為 None 則處理所有表格）
    
    Returns:
        dict: 各表格刪除的記錄數
    """
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        if table_name:
            tables = [table_name]
        else:
            tables = ['ifa_d005', 'ifa_d003', 'ifa_d004']
        
        results = {}
        
        for table in tables:
            # 根據不同表格使用不同的唯一性條件
            if table == 'ifa_d005':
                unique_cols = 'port_code, wharf_code, vessel_ename, eta_berth'
            elif table == 'ifa_d003':
                unique_cols = 'port_code, vessel_ename, eta_berth'
            elif table == 'ifa_d004':
                unique_cols = 'port_code, vessel_ename, etd_berth'
            else:
                continue
            
            # 刪除重複記錄（保留最新的 id）
            cursor.execute(f"""
                DELETE FROM {table}
                WHERE id NOT IN (
                    SELECT MAX(id)
                    FROM {table}
                    GROUP BY {unique_cols}
                )
            """)
            
            deleted_count = cursor.rowcount
            results[table] = deleted_count
            
            logger.info(f"✓ {table}: 已移除 {deleted_count} 筆重複記錄")
        
        conn.commit()
        return results
        
    except sqlite3.Error as e:
        logger.error(f"✗ 移除重複記錄失敗: {e}")
        conn.rollback()
        return {}
    
    finally:
        conn.close()

def calculate_berth_occupancy(port_code: str, wharf_code: str = None) -> dict:
    """
    🔥 計算泊位占用情況（修正版）
    
    Args:
        port_code: 港口代碼
        wharf_code: 碼頭代碼（可選，若為 None 則計算所有碼頭）
    
    Returns:
        dict: 占用情況統計
    """
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        # 查詢條件
        if wharf_code:
            where_clause = "WHERE port_code = ? AND wharf_code = ?"
            params = (port_code, wharf_code)
        else:
            where_clause = "WHERE port_code = ?"
            params = (port_code,)
        
        # 查詢當前停泊船舶（去重）
        query = f"""
        SELECT DISTINCT 
            wharf_code,
            wharf_name,
            vessel_ename,
            loa_m,
            alongside_status
        FROM ifa_d005
        {where_clause}
        AND alongside_status IN ('現靠', '接靠')
        AND (etd_berth IS NULL OR etd_berth > datetime('now'))
        ORDER BY wharf_code, eta_berth
        """
        
        cursor.execute(query, params)
        ships = cursor.fetchall()
        
        # 按碼頭分組計算
        berth_stats = {}
        
        for ship in ships:
            wharf = ship['wharf_code']
            
            if wharf not in berth_stats:
                berth_stats[wharf] = {
                    'wharf_name': ship['wharf_name'],
                    'ships': [],
                    'total_ship_length': 0,
                    'ship_count': 0
                }
            
            ship_length = ship['loa_m'] or 0
            
            berth_stats[wharf]['ships'].append({
                'vessel_ename': ship['vessel_ename'],
                'loa_m': ship_length,
                'status': ship['alongside_status']
            })
            
            berth_stats[wharf]['total_ship_length'] += ship_length
            berth_stats[wharf]['ship_count'] += 1
        
        # 計算占用長度（加入安全距離）
        for wharf, stats in berth_stats.items():
            ship_count = stats['ship_count']
            
            # 占用長度 = 船長總和 + 船間距（每艘船前後各 10m）
            if ship_count > 0:
                occupied_length = stats['total_ship_length'] + (ship_count * 20) - 10
            else:
                occupied_length = 0
            
            stats['occupied_length'] = round(occupied_length, 1)
        
        return berth_stats
        
    except sqlite3.Error as e:
        logger.error(f"✗ 計算泊位占用失敗: {e}")
        return {}
    
    finally:
        conn.close()
def load_data_from_db(table_name: str, port_code: str) -> pd.DataFrame:
    """
    從資料庫載入資料
    
    Args:
        table_name: 資料表名稱 (ifa_d005, ifa_d003, ifa_d004)
        port_code: 港口代碼
    
    Returns:
        DataFrame
    """
    try:
        conn = get_db_connection()
        
        # ✅ 修正：使用 crawled_at 而非 crawl_time
        query = f"""
            SELECT * FROM {table_name}
            WHERE port_code = ?
            ORDER BY crawled_at DESC
        """
        
        df = pd.read_sql_query(query, conn, params=(port_code,))
        conn.close()
        
        print(f"[INFO] 從資料庫載入 {len(df)} 筆 {table_name} 資料")
        
        return df
        
    except Exception as e:
        print(f"[ERROR] 載入資料失敗: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()
    
    
def get_database_stats() -> dict:
    """
    取得資料庫統計資訊
    
    Returns:
        dict: 統計資訊
    """
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        stats = {}
        
        # 取得各表格的記錄數
        tables = ['ifa_d005', 'ifa_d003', 'ifa_d004']
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            result = cursor.fetchone()
            stats[f'{table}_count'] = result['count'] if result else 0
            
            # 取得各港口的記錄數
            cursor.execute(f"""
                SELECT port_code, COUNT(*) as count 
                FROM {table} 
                GROUP BY port_code
            """)
            port_stats = cursor.fetchall()
            stats[f'{table}_by_port'] = {row['port_code']: row['count'] for row in port_stats}
            
            # 取得貨櫃輪記錄數
            cursor.execute(f"""
                SELECT COUNT(*) as count 
                FROM {table} 
                WHERE can_berth_container = 1
            """)
            result = cursor.fetchone()
            stats[f'{table}_container_count'] = result['count'] if result else 0
            
            # 🔥 檢查重複記錄數
            if table == 'ifa_d005':
                unique_cols = 'port_code, wharf_code, vessel_ename, eta_berth'
            elif table == 'ifa_d003':
                unique_cols = 'port_code, vessel_ename, eta_berth'
            elif table == 'ifa_d004':
                unique_cols = 'port_code, vessel_ename, etd_berth'
            else:
                continue
            
            cursor.execute(f"""
                SELECT COUNT(*) - COUNT(DISTINCT {unique_cols}) as duplicate_count
                FROM {table}
            """)
            result = cursor.fetchone()
            stats[f'{table}_duplicate_count'] = result['duplicate_count'] if result else 0
        
        # 取得資料庫檔案大小
        if os.path.exists(DB_PATH):
            stats['db_size_mb'] = round(os.path.getsize(DB_PATH) / (1024 * 1024), 2)
        else:
            stats['db_size_mb'] = 0
        
        return stats
        
    except Exception as e:
        logger.error(f"✗ 取得資料庫統計失敗: {e}")
        return {}
    
    finally:
        conn.close()

def get_table_columns(table_name: str) -> list:
    """
    取得表格的所有欄位名稱
    
    Args:
        table_name: 表格名稱
    
    Returns:
        list: 欄位名稱列表
    """
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        return columns
        
    except sqlite3.Error as e:
        logger.error(f"✗ 取得表格欄位失敗: {e}")
        return []
    
    finally:
        conn.close()


# ==================== 測試程式 ====================

if __name__ == "__main__":
    print("=== 測試資料庫模組（整合修正版 v3.0）===\n")
    
    # 初始化資料庫
    print("1. 初始化資料庫...")
    init_database()
    
    # 執行遷移
    print("\n2. 執行資料庫遷移...")
    migrate_database()
    
    # 顯示表格欄位
    print("\n3. 顯示表格欄位:")
    for table in ['ifa_d005', 'ifa_d003', 'ifa_d004']:
        columns = get_table_columns(table)
        print(f"\n{table} ({len(columns)} 欄位):")
        for i, col in enumerate(columns, 1):
            print(f"  {i:2d}. {col}")
    
    # 顯示統計資訊
    print("\n4. 資料庫統計:")
    stats = get_database_stats()
    for key, value in stats.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    - {k}: {v}")
        else:
            print(f"  {key}: {value}")
    
    # 測試重複記錄移除
    print("\n5. 測試重複記錄移除:")
    results = remove_duplicate_records()
    for table, count in results.items():
        print(f"  {table}: 移除 {count} 筆重複記錄")
    
    print("\n✓ 測試完成")
