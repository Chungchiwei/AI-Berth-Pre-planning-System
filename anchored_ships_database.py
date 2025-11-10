"""
船泊地資料庫管理模組
Version: 1.0
Date: 2025-11-06
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import os


class AnchoredShipsDatabase:
    """船泊地資料庫管理"""
    
    def __init__(self, db_path: str = 'data/berth_analysis.db'):
        """
        初始化資料庫
        
        Args:
            db_path: 資料庫路徑
        """
        self.db_path = db_path
        self._ensure_database()
    
    def _ensure_database(self):
        """確保資料庫和表格存在"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 建立船泊地資料表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS anchored_ships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                port_code TEXT NOT NULL,
                port_name TEXT NOT NULL,
                vessel_cname TEXT,
                vessel_ename TEXT,
                vessel_no TEXT,
                call_sign TEXT,
                imo TEXT,
                anchorage_area TEXT,
                anchorage_time TEXT,
                anchorage_date TEXT,
                ship_type TEXT,
                tonnage REAL,
                agent TEXT,
                agent_name TEXT,
                eta TEXT,
                etd TEXT,
                status TEXT,
                remark TEXT,
                crawl_time TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(port_code, vessel_no, anchorage_time)
            )
        ''')
        
        # 建立索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_anchored_port 
            ON anchored_ships(port_code, crawl_time)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_anchored_vessel 
            ON anchored_ships(vessel_ename, vessel_cname)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_anchored_imo 
            ON anchored_ships(imo)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_anchored_time 
            ON anchored_ships(crawl_time)
        ''')
        
        conn.commit()
        conn.close()
    
    def save_data(self, df: pd.DataFrame) -> int:
        """
        儲存資料到資料庫
        
        Args:
            df: 船泊地資料
            
        Returns:
            int: 儲存的筆數
        """
        if df.empty:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        
        # 使用 to_sql 方法
        df.to_sql('anchored_ships', conn, if_exists='append', index=False)
        
        saved_count = len(df)
        conn.close()
        
        return saved_count
    
    def query_latest(
        self,
        port_code: Optional[str] = None,
        hours: int = 24
    ) -> pd.DataFrame:
        """
        查詢最新資料
        
        Args:
            port_code: 港口代碼
            hours: 最近幾小時
            
        Returns:
            DataFrame: 查詢結果
        """
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT * FROM anchored_ships
            WHERE datetime(crawl_time) >= datetime('now', '-{} hours')
        '''.format(hours)
        
        params = []
        
        if port_code:
            query += ' AND port_code = ?'
            params.append(port_code)
        
        query += ' ORDER BY crawl_time DESC'
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return df
    
    def query_by_vessel(
        self,
        vessel_name: str,
        exact_match: bool = False
    ) -> pd.DataFrame:
        """
        根據船名查詢
        
        Args:
            vessel_name: 船名
            exact_match: 是否精確匹配
            
        Returns:
            DataFrame: 查詢結果
        """
        conn = sqlite3.connect(self.db_path)
        
        if exact_match:
            query = '''
                SELECT * FROM anchored_ships
                WHERE vessel_cname = ? OR vessel_ename = ?
                ORDER BY crawl_time DESC
            '''
            params = [vessel_name, vessel_name]
        else:
            query = '''
                SELECT * FROM anchored_ships
                WHERE vessel_cname LIKE ? OR vessel_ename LIKE ?
                ORDER BY crawl_time DESC
            '''
            params = [f'%{vessel_name}%', f'%{vessel_name}%']
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return df
    
    def get_statistics(self, port_code: Optional[str] = None) -> Dict:
        """
        取得統計資訊
        
        Args:
            port_code: 港口代碼
            
        Returns:
            Dict: 統計資訊
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if port_code:
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(DISTINCT vessel_no) as unique_vessels,
                    MIN(crawl_time) as earliest,
                    MAX(crawl_time) as latest
                FROM anchored_ships
                WHERE port_code = ?
            ''', (port_code,))
        else:
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(DISTINCT vessel_no) as unique_vessels,
                    COUNT(DISTINCT port_code) as ports,
                    MIN(crawl_time) as earliest,
                    MAX(crawl_time) as latest
                FROM anchored_ships
            ''')
        
        result = cursor.fetchone()
        conn.close()
        
        return {
            '總筆數': result[0],
            '不重複船舶數': result[1],
            '港口數': result[2] if not port_code else 1,
            '最早資料時間': result[-2],
            '最新資料時間': result[-1]
        }
    
    def clean_old_data(self, days: int = 30) -> int:
        """
        清理舊資料
        
        Args:
            days: 保留最近幾天的資料
            
        Returns:
            int: 刪除的筆數
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM anchored_ships
            WHERE datetime(crawl_time) < datetime('now', '-{} days')
        '''.format(days))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted_count


# 便捷函數
def get_latest_anchored_ships(port_code: str, hours: int = 24) -> pd.DataFrame:
    """快速查詢最新船泊地資料"""
    db = AnchoredShipsDatabase()
    return db.query_latest(port_code, hours)


def search_vessel_history(vessel_name: str) -> pd.DataFrame:
    """快速搜尋船舶歷史"""
    db = AnchoredShipsDatabase()
    return db.query_by_vessel(vessel_name)
