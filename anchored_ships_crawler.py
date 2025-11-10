"""
船泊地靠泊資料爬蟲模組（資料庫整合版）
Version: 2.0
Date: 2025-11-06
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import re
import os
from typing import Dict, Optional, List
import json
import logging


class AnchoredShipsCrawler:
    """船泊地靠泊資料爬蟲"""
    
    # 港口代碼對應
    PORT_CODES = {
        '基隆港': 'KEL',
        '臺北港': 'TPE',
        '臺中港': 'TXG',
        '高雄港': 'KHH',
        '花蓮港': 'HUN',
        '蘇澳港': 'SUO',
        '安平港': 'ANP'
    }
    
    # 欄位對應（中文化）
    COLUMN_MAPPING = {
        'vesselCname': '船名_中文',
        'vesselEname': '船名_英文',
        'vesselNo': '船舶編號',
        'callSign': '呼號',
        'registerNoI': '國際註冊號碼',
        'anchorageArea': '錨地區域',
        'anchorageTime': '錨泊時間',
        'anchorageDt': '錨泊日期',
        'shipType': '船舶類型',
        'tonnage': '噸位',
        'agent': '代理行',
        'agentName': '代理商名稱',
        'eta': '預計抵達時間',
        'etd': '預計離開時間',
        'status': '狀態',
        'remark': '備註'
    }
    
    def __init__(self, verbose: bool = True, db_path: str = 'data/berth_analysis.db'):
        """
        初始化爬蟲
        
        Args:
            verbose: 是否顯示詳細訊息
            db_path: 資料庫路徑
        """
        self.base_url = "https://tpnet.twport.com.tw"
        self.verbose = verbose
        self.session = requests.Session()
        self._setup_headers()
        self.token = None
        self.last_token_time = None
        self.db_path = db_path  # 🆕 資料庫路徑
        
        # 設定 logging
        self.logger = logging.getLogger(__name__)
        
        # 🆕 初始化資料庫
        self._init_database()
        
    def _init_database(self):
        """初始化資料庫表格"""
        import sqlite3
        
        try:
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
            
            conn.commit()
            conn.close()
            
            self._log("資料庫初始化完成", "SUCCESS")
            
        except Exception as e:
            self._log(f"資料庫初始化失敗: {str(e)}", "ERROR")
    
    def _setup_headers(self):
        """設定 HTTP Headers"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://tpnet.twport.com.tw',
            'Referer': 'https://tpnet.twport.com.tw/IFAWeb/Board/PortStatus',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin'
        })
    
    def _log(self, message: str, level: str = "INFO"):
        """輸出日誌"""
        if self.verbose:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            prefix = {
                "INFO": "ℹ️",
                "SUCCESS": "✅",
                "WARNING": "⚠️",
                "ERROR": "❌",
                "DEBUG": "🔍"
            }.get(level, "📝")
            print(f"[{timestamp}] {prefix} {message}")
            
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message)
    
    def _is_token_expired(self) -> bool:
        """檢查 Token 是否過期（15分鐘）"""
        if not self.token or not self.last_token_time:
            return True
        
        elapsed = (datetime.now() - self.last_token_time).total_seconds()
        return elapsed > 900
    
    def get_csrf_token(self, force_refresh: bool = False) -> bool:
        """取得 CSRF Token"""
        if not force_refresh and not self._is_token_expired():
            self._log("使用現有的 CSRF Token", "DEBUG")
            return True
        
        try:
            self._log("正在取得 CSRF Token...", "INFO")
            
            main_page_url = f"{self.base_url}/IFAWeb/Board/PortStatus"
            response = self.session.get(main_page_url, timeout=30)
            
            if response.status_code != 200:
                self._log(f"無法訪問主頁面，狀態碼: {response.status_code}", "ERROR")
                return False
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            token_input = soup.find('input', {'name': '__RequestVerificationToken'})
            if token_input:
                self.token = token_input.get('value')
            
            if not self.token:
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string and '__RequestVerificationToken' in script.string:
                        match = re.search(r'__RequestVerificationToken["\s:]+([A-Za-z0-9_-]+)', script.string)
                        if match:
                            self.token = match.group(1)
                            break
            
            if not self.token:
                meta_token = soup.find('meta', {'name': 'csrf-token'})
                if meta_token:
                    self.token = meta_token.get('content')
            
            if self.token:
                self.last_token_time = datetime.now()
                self._log(f"成功取得 CSRF Token: {self.token[:20]}...", "SUCCESS")
                return True
            else:
                self._log("無法取得 CSRF Token", "ERROR")
                return False
                
        except Exception as e:
            self._log(f"取得 Token 時發生錯誤: {str(e)}", "ERROR")
            return False
    
    def fetch_anchored_ships(
        self, 
        port_code: str = 'TPE',
        retry: int = 3,
        filters: Optional[Dict] = None,
        save_to_db: bool = True  # 🆕 是否儲存到資料庫
    ) -> pd.DataFrame:
        """
        爬取船泊地靠泊資料
        
        Args:
            port_code: 港口代碼
            retry: 重試次數
            filters: 篩選條件
            save_to_db: 是否儲存到資料庫
        
        Returns:
            DataFrame: 船泊地資料
        """
        
        if port_code not in self.PORT_CODES.values():
            self._log(f"無效的港口代碼: {port_code}", "ERROR")
            return pd.DataFrame()
        
        if not self.token or self._is_token_expired():
            if not self.get_csrf_token():
                self._log("無法取得 CSRF Token，爬取失敗", "ERROR")
                return pd.DataFrame()
        
        url = f"{self.base_url}/IFAWeb/Board/PortStatus/LoadAnchoredShips"
        
        payload = {
            'portId': port_code,
            'wharfType': '',
            'wharfCode': '',
            'shipGroup': '',
            'vesselNo': '',
            'vesselCname': '',
            'vesselEname': '',
            'registerNoI': '',
            'callSign': '',
            'startDt': '',
            '__RequestVerificationToken': self.token
        }
        
        if filters:
            payload.update(filters)
        
        for attempt in range(retry):
            try:
                self._log(f"嘗試爬取 {port_code} 港船泊地資料 (第 {attempt + 1}/{retry} 次)...", "INFO")
                
                response = self.session.post(url, data=payload, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    ships_data = self._extract_data(data)
                    
                    if ships_data:
                        df = pd.DataFrame(ships_data)
                        df = self._rename_columns(df)
                        
                        df['爬取時間'] = datetime.now()
                        df['港口代碼'] = port_code
                        df['港口名稱'] = self._get_port_name(port_code)
                        
                        df = self._clean_data(df)
                        
                        # 🆕 儲存到資料庫
                        if save_to_db:
                            self._save_to_database(df, port_code)
                        
                        self._log(f"成功爬取 {len(df)} 筆船泊地資料", "SUCCESS")
                        return df
                    else:
                        self._log(f"{port_code} 港目前無船泊地資料", "WARNING")
                        return pd.DataFrame()
                
                elif response.status_code == 403:
                    self._log("403 Forbidden - Token 可能過期，重新取得...", "WARNING")
                    if self.get_csrf_token(force_refresh=True):
                        payload['__RequestVerificationToken'] = self.token
                        continue
                    else:
                        break
                
                else:
                    self._log(f"請求失敗，狀態碼: {response.status_code}", "ERROR")
                
            except requests.exceptions.Timeout:
                self._log(f"請求超時 (第 {attempt + 1} 次)", "WARNING")
                if attempt < retry - 1:
                    time.sleep(2)
                    continue
            
            except Exception as e:
                self._log(f"爬取時發生錯誤: {str(e)}", "ERROR")
                if attempt < retry - 1:
                    time.sleep(2)
                    continue
        
        self._log(f"爬取失敗，已重試 {retry} 次", "ERROR")
        return pd.DataFrame()
    
    def _save_to_database(self, df: pd.DataFrame, port_code: str):
        """
        🆕 儲存資料到資料庫
        
        Args:
            df: 船泊地資料
            port_code: 港口代碼
        """
        import sqlite3
        
        if df.empty:
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            
            # 準備資料
            records = []
            for _, row in df.iterrows():
                record = (
                    port_code,
                    row.get('港口名稱', ''),
                    row.get('船名_中文', ''),
                    row.get('船名_英文', ''),
                    row.get('船舶編號', ''),
                    row.get('呼號', ''),
                    row.get('國際註冊號碼', ''),
                    row.get('錨地區域', ''),
                    str(row.get('錨泊時間', '')) if pd.notna(row.get('錨泊時間')) else None,
                    str(row.get('錨泊日期', '')) if pd.notna(row.get('錨泊日期')) else None,
                    row.get('船舶類型', ''),
                    float(row.get('噸位', 0)) if pd.notna(row.get('噸位')) else None,
                    row.get('代理行', ''),
                    row.get('代理商名稱', ''),
                    str(row.get('預計抵達時間', '')) if pd.notna(row.get('預計抵達時間')) else None,
                    str(row.get('預計離開時間', '')) if pd.notna(row.get('預計離開時間')) else None,
                    row.get('狀態', ''),
                    row.get('備註', ''),
                    str(row.get('爬取時間', datetime.now()))
                )
                records.append(record)
            
            # 插入資料（使用 REPLACE 避免重複）
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT OR REPLACE INTO anchored_ships (
                    port_code, port_name, vessel_cname, vessel_ename,
                    vessel_no, call_sign, imo, anchorage_area,
                    anchorage_time, anchorage_date, ship_type, tonnage,
                    agent, agent_name, eta, etd, status, remark, crawl_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', records)
            
            conn.commit()
            conn.close()
            
            self._log(f"成功儲存 {len(records)} 筆資料到資料庫", "SUCCESS")
            
        except Exception as e:
            self._log(f"儲存到資料庫時發生錯誤: {str(e)}", "ERROR")
    
    def query_from_database(
        self,
        port_code: Optional[str] = None,
        vessel_name: Optional[str] = None,
        hours: int = 24
    ) -> pd.DataFrame:
        """
        🆕 從資料庫查詢船泊地資料
        
        Args:
            port_code: 港口代碼（可選）
            vessel_name: 船名（可選）
            hours: 查詢最近幾小時的資料
        
        Returns:
            DataFrame: 查詢結果
        """
        import sqlite3
        
        try:
            conn = sqlite3.connect(self.db_path)
            
            query = '''
                SELECT * FROM anchored_ships
                WHERE datetime(crawl_time) >= datetime('now', '-{} hours')
            '''.format(hours)
            
            params = []
            
            if port_code:
                query += ' AND port_code = ?'
                params.append(port_code)
            
            if vessel_name:
                query += ' AND (vessel_cname LIKE ? OR vessel_ename LIKE ?)'
                params.extend([f'%{vessel_name}%', f'%{vessel_name}%'])
            
            query += ' ORDER BY crawl_time DESC'
            
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            
            self._log(f"從資料庫查詢到 {len(df)} 筆資料", "SUCCESS")
            return df
            
        except Exception as e:
            self._log(f"查詢資料庫時發生錯誤: {str(e)}", "ERROR")
            return pd.DataFrame()
    
    def _extract_data(self, response_data) -> List:
        """從回應中提取資料"""
        if isinstance(response_data, dict):
            for key in ['data', 'result', 'items', 'ships']:
                if key in response_data:
                    return response_data[key]
            return [response_data] if response_data else []
        elif isinstance(response_data, list):
            return response_data
        return []
    
    def _rename_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """重新命名欄位為中文"""
        return df.rename(columns=self.COLUMN_MAPPING)
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗資料"""
        if df.empty:
            return df
        
        time_columns = ['錨泊時間', '錨泊日期', '預計抵達時間', '預計離開時間']
        for col in time_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        if '噸位' in df.columns:
            df['噸位'] = pd.to_numeric(df['噸位'], errors='coerce')
        
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].str.strip() if df[col].dtype == 'object' else df[col]
        
        return df
    
    def _get_port_name(self, port_code: str) -> str:
        """根據港口代碼取得港口名稱"""
        for name, code in self.PORT_CODES.items():
            if code == port_code:
                return name
        return port_code
    
    def fetch_all_ports(self, delay: float = 1.0, save_to_db: bool = True) -> Dict[str, pd.DataFrame]:
        """
        爬取所有港口的船泊地資料
        
        Args:
            delay: 每次請求間隔秒數
            save_to_db: 是否儲存到資料庫
            
        Returns:
            Dict: {港口名稱: DataFrame}
        """
        all_data = {}
        
        self._log("="*60, "INFO")
        self._log("開始爬取所有港口船泊地資料", "INFO")
        self._log("="*60, "INFO")
        
        for port_name, port_code in self.PORT_CODES.items():
            self._log(f"\n正在爬取 {port_name} ({port_code})...", "INFO")
            
            df = self.fetch_anchored_ships(port_code, save_to_db=save_to_db)
            
            if not df.empty:
                all_data[port_name] = df
                self._log(f"{port_name} 完成，共 {len(df)} 筆資料", "SUCCESS")
            else:
                self._log(f"{port_name} 無資料或爬取失敗", "WARNING")
            
            time.sleep(delay)
        
        self._log(f"\n總計爬取 {len(all_data)} 個港口的資料", "SUCCESS")
        return all_data
    
    def save_to_csv(
        self, 
        data, 
        filename: Optional[str] = None,
        output_dir: str = 'data/anchored_ships'
    ) -> Optional[pd.DataFrame]:
        """儲存資料到 CSV"""
        os.makedirs(output_dir, exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'anchored_ships_{timestamp}.csv'
        
        filepath = os.path.join(output_dir, filename)
        
        try:
            if isinstance(data, dict):
                all_df = [df for df in data.values() if not df.empty]
                if all_df:
                    combined_df = pd.concat(all_df, ignore_index=True)
                    combined_df.to_csv(filepath, index=False, encoding='utf-8-sig')
                    self._log(f"資料已儲存至: {filepath}", "SUCCESS")
                    return combined_df
            
            elif isinstance(data, pd.DataFrame) and not data.empty:
                data.to_csv(filepath, index=False, encoding='utf-8-sig')
                self._log(f"資料已儲存至: {filepath}", "SUCCESS")
                return data
            
            self._log("無資料可儲存", "WARNING")
            return None
            
        except Exception as e:
            self._log(f"儲存檔案時發生錯誤: {str(e)}", "ERROR")
            return None
    
    def get_statistics(self, data) -> Dict:
        """取得資料統計"""
        stats = {
            '總筆數': 0,
            '港口數': 0,
            '各港口統計': {}
        }
        
        if isinstance(data, dict):
            stats['港口數'] = len(data)
            for port_name, df in data.items():
                if not df.empty:
                    stats['總筆數'] += len(df)
                    stats['各港口統計'][port_name] = {
                        '船舶數': len(df),
                        '欄位數': len(df.columns)
                    }
        
        elif isinstance(data, pd.DataFrame) and not data.empty:
            stats['總筆數'] = len(data)
            if '港口名稱' in data.columns:
                stats['港口數'] = data['港口名稱'].nunique()
        
        return stats


# 便捷函數
def quick_fetch(port_code: str = 'TPE', verbose: bool = True, save_to_db: bool = True) -> pd.DataFrame:
    """快速爬取單一港口資料"""
    crawler = AnchoredShipsCrawler(verbose=verbose)
    return crawler.fetch_anchored_ships(port_code, save_to_db=save_to_db)


def quick_fetch_all(verbose: bool = True, save_to_db: bool = True) -> Dict[str, pd.DataFrame]:
    """快速爬取所有港口資料"""
    crawler = AnchoredShipsCrawler(verbose=verbose)
    return crawler.fetch_all_ports(save_to_db=save_to_db)


def quick_query(port_code: Optional[str] = None, vessel_name: Optional[str] = None, hours: int = 24) -> pd.DataFrame:
    """🆕 快速查詢資料庫"""
    crawler = AnchoredShipsCrawler(verbose=True)
    return crawler.query_from_database(port_code, vessel_name, hours)
