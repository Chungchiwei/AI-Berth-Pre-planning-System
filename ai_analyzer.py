"""
Perplexity AI 分析模組（整合資料庫版 v3.5 - 最終修正版）
✅ 修正所有縮排和結構問題
✅ 完整的資料庫整合
✅ 正確的欄位對應
"""
import requests
import json
import sqlite3
from datetime import datetime, timedelta
from textwrap import dedent
import time
from typing import Dict, List, Any, Optional, Tuple
import sys
import os

try:
    from config import PERPLEXITY_API_URL, PERPLEXITY_MODEL, TIMEZONE, DB_PATH, Port_DB_Path
except ImportError:
    PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
    PERPLEXITY_MODEL = "sonar"
    TIMEZONE = "Asia/Taipei"
    DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'berth_management_Data.db')
    Port_DB_Path = os.path.join(os.path.dirname(__file__), 'data', 'TaiwanPort_wharf_information.db')

# ✅ API Key
PERPLEXITY_API_KEY = "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"

# ✅ 模型配置
MODEL_CONFIG = {
    'berth_analysis': {
        'model': 'sonar-reasoning',
        'max_tokens': 20000,
        'temperature': 0.3,
        'description': '泊位動態綜合分析'
    },
    'quick_analysis': {
        'model': 'sonar',
        'max_tokens': 10000,
        'temperature': 0.3,
        'description': '快速泊位評估'
    },
    'deep_research': {
        'model': 'sonar-research',
        'max_tokens': 20000,
        'temperature': 0.2,
        'description': '深度泊位研究'
    }
}


# ==================== 安全轉換函數 ====================

def _safe_int_convert(value: Any, default: int = 0) -> int:
    """
    安全轉換為整數（處理 BLOB 和各種格式）
    
    Args:
        value: 要轉換的值
        default: 預設值
    
    Returns:
        整數值
    """
    if value is None:
        return default
    
    # 如果是 bytes 類型
    if isinstance(value, bytes):
        try:
            # 嘗試解碼為字串
            value_str = value.decode('utf-8', errors='ignore').strip()
            if value_str:
                return int(float(value_str))
        except (ValueError, UnicodeDecodeError):
            pass
        
        try:
            # 嘗試作為整數 bytes 解析（小端序）
            if len(value) >= 4:
                import struct
                return struct.unpack('<i', value[:4])[0]
        except struct.error:
            pass
        
        return default
    
    # 如果是字串
    if isinstance(value, str):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default
    
    # 如果是數字
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_float_convert(value: Any, default: float = 0.0) -> float:
    """
    安全轉換為浮點數（處理 BLOB 和各種格式）
    
    Args:
        value: 要轉換的值
        default: 預設值
    
    Returns:
        浮點數值
    """
    if value is None:
        return default
    
    # 如果是 bytes 類型
    if isinstance(value, bytes):
        try:
            # 嘗試解碼為字串
            value_str = value.decode('utf-8', errors='ignore').strip()
            if value_str:
                return float(value_str)
        except (ValueError, UnicodeDecodeError):
            pass
        
        try:
            # 嘗試作為浮點數 bytes 解析（小端序）
            if len(value) >= 8:
                import struct
                return struct.unpack('<d', value[:8])[0]
        except struct.error:
            pass
        
        return default
    
    # 如果是字串
    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    # 如果是數字
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_str_convert(value: Any, default: str = 'N/A') -> str:
    """
    安全轉換為字串（處理 BLOB 和各種格式）
    
    Args:
        value: 要轉換的值
        default: 預設值
    
    Returns:
        字串值
    """
    if value is None:
        return default
    
    # 如果是 bytes 類型
    if isinstance(value, bytes):
        try:
            decoded = value.decode('utf-8', errors='ignore').strip()
            return decoded if decoded else default
        except UnicodeDecodeError:
            return default
    
    # 如果已經是字串
    if isinstance(value, str):
        return value.strip() if value.strip() else default
    
    # 其他類型轉為字串
    try:
        return str(value)
    except:
        return default


# ==================== 資料庫查詢模組 ====================

class BerthDatabase:
    """碼頭資料庫管理類別（最終版）"""
    
    def __init__(self, berth_db_path: str = None, wharf_db_path: str = None):
        """
        初始化資料庫連線
        
        Args:
            berth_db_path: 船舶管理資料庫路徑
            wharf_db_path: 碼頭資訊資料庫路徑
        """
        # ✅ 使用傳入的路徑或預設路徑
        self.berth_db_path = berth_db_path if berth_db_path else DB_PATH
        self.wharf_db_path = wharf_db_path if wharf_db_path else Port_DB_Path
        
        # 檢查資料庫是否存在
        if not os.path.exists(self.berth_db_path):
            print(f"⚠️ 找不到船舶管理資料庫: {self.berth_db_path}")
        else:
            print(f"✅ 船舶管理資料庫: {self.berth_db_path}")
        
        if not os.path.exists(self.wharf_db_path):
            print(f"⚠️ 找不到碼頭資訊資料庫: {self.wharf_db_path}")
        else:
            print(f"✅ 碼頭資訊資料庫: {self.wharf_db_path}")
    
    def _get_connection(self, db_type: str = 'berth'):
        """獲取資料庫連線"""
        db_path = self.berth_db_path if db_type == 'berth' else self.wharf_db_path
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_wharf_info(self, port_name: str = None) -> List[Dict]:
        """
        獲取碼頭資訊
        
        Args:
            port_name: 港口名稱（中文或英文）
        
        Returns:
            碼頭資訊列表
        """
        try:
            conn = self._get_connection('wharf')
            cursor = conn.cursor()
            
            if port_name:
                query = """
                    SELECT * FROM wharf_information 
                    WHERE PortName_cn = ? OR PortName_en = ?
                """
                cursor.execute(query, (port_name, port_name))
            else:
                query = "SELECT * FROM wharf_information"
                cursor.execute(query)
            
            results = []
            for row in cursor.fetchall():
                wharf_dict = dict(row)
                # ✅ 統一欄位名稱
                wharf_dict['港口名稱'] = _safe_str_convert(wharf_dict.get('PortName_cn'))
                wharf_dict['碼頭代碼'] = _safe_str_convert(wharf_dict.get('wharf_code'))
                wharf_dict['碼頭名稱'] = _safe_str_convert(wharf_dict.get('wharf_name'))
                wharf_dict['碼頭長度'] = _safe_float_convert(wharf_dict.get('wharf_length'))
                wharf_dict['水深'] = _safe_float_convert(wharf_dict.get('wharf_depth'))
                wharf_dict['碼頭類型'] = _safe_str_convert(wharf_dict.get('wharf_type'))
                wharf_dict['泊位區域'] = _safe_str_convert(wharf_dict.get('wharf_area'))
                wharf_dict['繫船柱數量'] = _safe_int_convert(wharf_dict.get('bollard_count'))
                results.append(wharf_dict)
            
            conn.close()
            
            print(f"✅ 查詢到 {len(results)} 個碼頭資訊")
            return results
            
        except Exception as e:
            print(f"❌ 查詢碼頭資訊失敗: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_candidate_berths(
        self, 
        port_name: str, 
        required_length: float,
        ship_type: str = None
    ) -> List[Dict]:
        """
        獲取候選泊位（完全修正版 - 處理 BLOB 資料）
        
        Args:
            port_name: 港口名稱
            required_length: 所需泊位長度
            ship_type: 船舶類型
        
        Returns:
            候選泊位列表
        """
        try:
            conn = self._get_connection('wharf')
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM wharf_information 
                WHERE (PortName_cn = ? OR PortName_en = ?)
                AND wharf_length >= ?
                ORDER BY wharf_length ASC
            """
            
            cursor.execute(query, (port_name, port_name, required_length))
            
            results = []
            for row in cursor.fetchall():
                berth_dict = dict(row)
                
                # ✅ 使用安全轉換函數處理所有欄位
                berth_dict['泊位代碼'] = _safe_str_convert(berth_dict.get('wharf_code'))
                berth_dict['泊位名稱'] = _safe_str_convert(berth_dict.get('wharf_name'))
                berth_dict['泊位長度'] = _safe_float_convert(berth_dict.get('wharf_length'))
                berth_dict['水深'] = _safe_float_convert(berth_dict.get('wharf_depth'))
                berth_dict['碼頭類型'] = _safe_str_convert(berth_dict.get('wharf_type'))
                berth_dict['泊位區域'] = _safe_str_convert(berth_dict.get('wharf_area'))
                berth_dict['繫船柱數量'] = _safe_int_convert(berth_dict.get('bollard_count'))
                berth_dict['港口名稱'] = _safe_str_convert(berth_dict.get('PortName_cn'))
                
                # ✅ 計算適配度
                length_diff = berth_dict['泊位長度'] - required_length
                if length_diff >= 50:
                    berth_dict['適配度'] = '✅ 優良'
                elif length_diff >= 0:
                    berth_dict['適配度'] = '✅ 適配'
                else:
                    berth_dict['適配度'] = f'⚠️ 短缺 {abs(length_diff):.1f}m'
                
                results.append(berth_dict)
            
            conn.close()
            
            print(f"✅ 查詢到 {len(results)} 個候選泊位")
            if results:
                example = results[0]
                print(f"   範例: {example.get('泊位代碼')} - {example.get('泊位名稱')} "
                      f"({example.get('泊位長度'):.1f}m) {example.get('適配度')}")
            
            return results
            
        except Exception as e:
            print(f"❌ 查詢候選泊位失敗: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_in_berth_ships(self, port_name: str = None) -> List[Dict]:
        """
        獲取在泊船舶列表（完全修正版 - 處理 BLOB 資料）
        
        Args:
            port_name: 港口名稱
        
        Returns:
            在泊船舶列表
        """
        try:
            conn = self._get_connection('berth')
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM ifa_d005 
                WHERE 1=1
            """
            
            params = []
            if port_name:
                query += " AND port_name = ?"
                params.append(port_name)
            
            query += " ORDER BY eta_berth DESC LIMIT 50"
            
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                ship_dict = dict(row)
                
                # ✅ 使用安全轉換函數
                vessel_cname = _safe_str_convert(ship_dict.get('vessel_cname'), '')
                vessel_ename = _safe_str_convert(ship_dict.get('vessel_ename'), '')
                ship_name = vessel_cname if vessel_cname and vessel_cname != 'N/A' else vessel_ename
                if not ship_name or ship_name == 'N/A':
                    ship_name = '萬海船舶'
                
                # ✅ 統一欄位名稱（使用安全轉換）
                ship_dict['船名'] = ship_name
                ship_dict['泊位'] = _safe_str_convert(ship_dict.get('wharf_code'))
                ship_dict['泊位名稱'] = _safe_str_convert(ship_dict.get('wharf_name'))
                ship_dict['ETA'] = _safe_str_convert(ship_dict.get('eta_berth'))
                ship_dict['ETD'] = _safe_str_convert(ship_dict.get('etd_berth'))
                ship_dict['ATA'] = _safe_str_convert(ship_dict.get('ata_berth'))
                ship_dict['船長'] = _safe_float_convert(ship_dict.get('loa_m'))
                ship_dict['船舶類型'] = _safe_str_convert(ship_dict.get('ship_type'))
                ship_dict['靠泊狀態'] = _safe_str_convert(ship_dict.get('alongside_status'))
                ship_dict['總噸位'] = _safe_float_convert(ship_dict.get('gt'))
                ship_dict['代理'] = _safe_str_convert(ship_dict.get('agent'))
                
                results.append(ship_dict)
            
            conn.close()
            
            print(f"✅ 查詢到 {len(results)} 艘在泊船舶")
            if results:
                print(f"   範例: {results[0].get('船名')} @ {results[0].get('泊位')}")
            
            return results
            
        except Exception as e:
            print(f"❌ 查詢在泊船舶失敗: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_inbound_ships(self, port_name: str = None, time_window_hours: int = 48) -> List[Dict]:
        """
        獲取進港船舶列表（完全修正版 - 處理 BLOB 資料）
        
        Args:
            port_name: 港口名稱
            time_window_hours: 時間窗口（小時）
        
        Returns:
            進港船舶列表
        """
        try:
            conn = self._get_connection('berth')
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM ifa_d003 
                WHERE eta_berth IS NOT NULL
                AND eta_berth != ''
            """
            
            params = []
            if port_name:
                query += " AND port_name = ?"
                params.append(port_name)
            
            query += " ORDER BY eta_berth ASC LIMIT 50"
            
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                ship_dict = dict(row)
                
                # ✅ 使用安全轉換函數
                vessel_cname = _safe_str_convert(ship_dict.get('vessel_cname'), '')
                vessel_ename = _safe_str_convert(ship_dict.get('vessel_ename'), '')
                ship_name = vessel_cname if vessel_cname and vessel_cname != 'N/A' else vessel_ename
                if not ship_name or ship_name == 'N/A':
                    ship_name = '萬海船舶'
                
                # ✅ 統一欄位名稱（使用安全轉換）
                ship_dict['船名'] = ship_name
                ship_dict['泊位'] = _safe_str_convert(ship_dict.get('berth'))
                ship_dict['ETA'] = _safe_str_convert(ship_dict.get('eta_berth'))
                ship_dict['ETD'] = _safe_str_convert(ship_dict.get('etd_berth'))
                ship_dict['ATA'] = _safe_str_convert(ship_dict.get('ata_berth'))
                ship_dict['船長'] = _safe_float_convert(ship_dict.get('loa_m'))
                ship_dict['船舶類型'] = _safe_str_convert(ship_dict.get('ship_type'))
                ship_dict['總噸位'] = _safe_float_convert(ship_dict.get('gt'))
                ship_dict['前港'] = _safe_str_convert(ship_dict.get('prev_port'))
                ship_dict['下港'] = _safe_str_convert(ship_dict.get('next_port'))
                ship_dict['代理'] = _safe_str_convert(ship_dict.get('agent'))
                
                results.append(ship_dict)
            
            conn.close()
            
            print(f"✅ 查詢到 {len(results)} 艘進港船舶")
            if results:
                print(f"   範例: {results[0].get('船名')} ETA: {results[0].get('ETA')}")
            
            return results
            
        except Exception as e:
            print(f"❌ 查詢進港船舶失敗: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_outbound_ships(self, port_name: str = None, time_window_hours: int = 48) -> List[Dict]:
        """
        獲取出港船舶列表（完全修正版 - 處理 BLOB 資料）
        
        Args:
            port_name: 港口名稱
            time_window_hours: 時間窗口（小時）
        
        Returns:
            出港船舶列表
        """
        try:
            conn = self._get_connection('berth')
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM ifa_d004 
                WHERE etd_berth IS NOT NULL
                AND etd_berth != ''
            """
            
            params = []
            if port_name:
                query += " AND port_name = ?"
                params.append(port_name)
            
            query += " ORDER BY etd_berth ASC LIMIT 50"
            
            cursor.execute(query, params)
            
            results = []
            for row in cursor.fetchall():
                ship_dict = dict(row)
                
                # ✅ 使用安全轉換函數
                vessel_cname = _safe_str_convert(ship_dict.get('vessel_cname'), '')
                vessel_ename = _safe_str_convert(ship_dict.get('vessel_ename'), '')
                ship_name = vessel_cname if vessel_cname and vessel_cname != 'N/A' else vessel_ename
                if not ship_name or ship_name == 'N/A':
                    ship_name = '萬海船舶'
                
                # ✅ 統一欄位名稱（使用安全轉換）
                ship_dict['船名'] = ship_name
                ship_dict['泊位'] = _safe_str_convert(ship_dict.get('berth'))
                ship_dict['ETD'] = _safe_str_convert(ship_dict.get('etd_berth'))
                ship_dict['ATD'] = _safe_str_convert(ship_dict.get('atd_berth'))
                ship_dict['船長'] = _safe_float_convert(ship_dict.get('loa_m'))
                ship_dict['船舶類型'] = _safe_str_convert(ship_dict.get('ship_type'))
                ship_dict['前港'] = _safe_str_convert(ship_dict.get('prev_port'))
                ship_dict['下港'] = _safe_str_convert(ship_dict.get('next_port'))
                ship_dict['代理'] = _safe_str_convert(ship_dict.get('agent'))
                
                results.append(ship_dict)
            
            conn.close()
            
            print(f"✅ 查詢到 {len(results)} 艘出港船舶")
            if results:
                print(f"   範例: {results[0].get('船名')} ETD: {results[0].get('ETD')}")
            
            return results
            
        except Exception as e:
            print(f"❌ 查詢出港船舶失敗: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_port_statistics(self, port_name: str = None) -> Dict[str, Any]:
        """
        獲取港口統計資訊
        
        Args:
            port_name: 港口名稱
        
        Returns:
            統計資訊字典
        """
        stats = {
            '在泊船舶數': len(self.get_in_berth_ships(port_name)),
            '進港船舶數': len(self.get_inbound_ships(port_name)),
            '出港船舶數': len(self.get_outbound_ships(port_name)),
            '可用泊位數': len(self.get_wharf_info(port_name))
        }
        
        return stats


# ==================== 原有的輔助函數 ====================

def _safe_strptime(dt: Any) -> str:
    """將 datetime 或字串安全轉為顯示用字串"""
    if isinstance(dt, datetime):
        return dt.strftime('%Y-%m-%d %H:%M')
    elif isinstance(dt, str):
        return dt
    else:
        return str(dt)


def _summarize_ship_list(ship_list: List[Dict], max_items: int = 5) -> str:
    """摘要船舶列表（完全修正版）"""
    if not ship_list:
        return "*目前無資料*"
    
    total = len(ship_list)
    items_to_show = ship_list[:max_items]
    
    summary = []
    for i, ship in enumerate(items_to_show, 1):
        # ✅ 嘗試多種可能的欄位名稱
        vessel_name = (
            ship.get('船名') or 
            ship.get('vessel_cname') or 
            ship.get('vessel_ename') or 
            ship.get('vessel_name') or 
            'N/A'
        )
        
        berth = (
            ship.get('泊位') or 
            ship.get('wharf_code') or 
            ship.get('berth') or 
            'N/A'
        )
        
        berth_name = (
            ship.get('泊位名稱') or 
            ship.get('wharf_name') or 
            ''
        )
        
        # 組合泊位顯示
        if berth_name and berth_name != 'N/A' and berth_name != berth:
            berth_display = f"{berth} ({berth_name})"
        else:
            berth_display = berth
        
        # 時間資訊
        eta = ship.get('ETA') or ship.get('eta_berth') or 'N/A'
        etd = ship.get('ETD') or ship.get('etd_berth') or 'N/A'
        ata = ship.get('ATA') or ship.get('ata_berth') or ''
        atd = ship.get('ATD') or ship.get('atd_berth') or ''
        
        # 船舶資訊
        loa = float(ship.get('船長') or ship.get('loa_m') or 0)
        ship_type = ship.get('船舶類型') or ship.get('ship_type') or 'N/A'
        gt = ship.get('總噸位') or ship.get('gt') or 0
        
        # ✅ 格式化輸出（確保船名顯示）
        line = f"{i}. **{vessel_name}**"
        
        if ship_type != 'N/A':
            line += f" | 類型: {ship_type}"
        
        if loa > 0:
            line += f" | 船長: {loa:.1f}m"
        
        if gt > 0:
            line += f" | 噸位: {gt:,.0f} GT"
        
        if berth_display != 'N/A':
            line += f" | 泊位: {berth_display}"
        
        # 時間資訊
        time_info = []
        if ata and ata != 'N/A':
            time_info.append(f"ATA: {ata}")
        elif eta and eta != 'N/A':
            time_info.append(f"ETA: {eta}")
        
        if atd and atd != 'N/A':
            time_info.append(f"ATD: {atd}")
        elif etd and etd != 'N/A':
            time_info.append(f"ETD: {etd}")
        
        if time_info:
            line += f" | {' | '.join(time_info)}"
        
        summary.append(line)
    
    if total > max_items:
        summary.append(f"\n*... 及其他 {total - max_items} 艘船舶*")
    
    return "\n".join(summary)


def _build_system_prompt() -> str:
    """建立 System Prompt（增強版 - 完整航運決策分析）"""
    return dedent("""
        你是**港口靠泊調度與航運經濟 AI 專家**，專精於：
        1. 泊位可用性與競合風險評估
        2. 航速調整策略（加俥/慢俥）與成本效益分析
        3. 天氣風險與錨泊策略評估
        4. 運價與油價對航運決策的影響
        
        ## 🎯 核心分析任務
        
        ### 1️⃣ 泊位動態分析
        - 評估候選泊位可用性與適配度
        - 識別時間衝突與空間競合
        - 計算最佳到達時窗
        
        ### 2️⃣ 航速策略分析
        **加俥（增速）考量**：
        - 當前運價水平是否支持額外燃油成本
        - 準時到達的商業價值（避免滯期費、搶佔泊位）
        - 油價對加俥成本的影響
        - 船期緊迫性評估
        
        **慢俥（減速）考量**：
        - 泊位擁擠時的經濟慢速策略
        - 油價高企時的成本節約
        - 避免錨泊等待的燃油浪費
        - 最佳巡航速度建議
        
        ### 3️⃣ 天氣風險評估
        **錨泊風險分析**：
        - 查詢目標港口當前與未來 48 小時天氣預報
        - 評估風浪對錨泊作業的影響（風力、浪高、能見度）
        - 颱風/強對流天氣警報
        - 錨地安全性評估
        
        **天氣對靠泊的影響**：
        - 惡劣天氣導致的靠泊延遲風險
        - 引水作業限制條件
        - 建議的天氣窗口
        
        ### 4️⃣ 經濟決策分析
        **成本效益計算**：
        - 加俥額外燃油成本 vs 準時到達收益
        - 慢俥節省成本 vs 可能的滯期損失
        - 錨泊等待成本（燃油、時間、機會成本）
        - 最優經濟速度建議
        
        ## 📋 輸出格式（必須嚴格遵守）
        
        ```
        # 🎯 綜合分析摘要
        
        【泊位可用性】: ✅ 充足 / ⚠️ 緊張 / ❌ 嚴重擁擠
        【競合程度】: 🟢 低競爭 / 🟡 中度競爭 / 🔴 高度競爭
        【建議到達時間】: YYYY-MM-DD HH:MM
        【風險等級】: 🟢 低風險 / 🟡 中風險 / 🔴 高風險
        【天氣狀況】: ☀️ 良好 / ⛅ 普通 / 🌧️ 不佳 / ⛈️ 惡劣
        【經濟建議】: 💰 加俥 / 🐢 慢俥 / ⚓ 錨泊等待 / ⏱️ 維持航速
        
        ---
        
        # 🌊 天氣與海況分析
        
        ## 當前天氣狀況
        - **風力**: [查詢實時數據] 級 ([方向])
        - **浪高**: [查詢實時數據] 米
        - **能見度**: [查詢實時數據] 公里
        - **氣溫**: [查詢實時數據] °C
        
        ## 未來 48 小時預報
        - **天氣趨勢**: [描述]
        - **惡劣天氣警報**: ⚠️ [有/無]
        - **對靠泊影響**: [分析]
        
        ## 錨泊風險評估
        - **錨地安全性**: ✅ 安全 / ⚠️ 需謹慎 / ❌ 不建議
        - **錨泊時長預估**: [X] 小時
        - **錨泊成本**: 燃油 [X] 噸 ≈ $[X] USD
        - **風險因素**: [列舉]
        
        ---
        
        # ⛽ 航速策略與經濟分析
        
        ## 當前市場狀況
        - **國際油價**: [查詢 Brent/WTI 最新價格] USD/桶
        - **船用燃油價**: [估算 VLSFO/MGO 價格] USD/噸
        - **運價指數**: [查詢相關航線運價，如 SCFI/BDI]
        - **市場評估**: 🔴 高運價高油價 / 🟡 運價油價分化 / 🟢 低油價利好
        
        ## 航速調整方案
        
        ### 方案 A：加俥策略 🚀
        - **建議航速**: [X] 節 (較正常航速 +[X] 節)
        - **額外燃油消耗**: [X] 噸/天
        - **額外成本**: $[X] USD
        - **提前到達時間**: [X] 小時
        - **適用情境**:
          * ✅ 運價高企，準時到達價值大
          * ✅ 泊位競爭激烈，搶佔先機
          * ✅ 避免滯期費或合約罰款
          * ✅ 天氣窗口緊迫
        - **成本效益**: [正面/中性/負面]
        
        ### 方案 B：慢俥策略 🐢
        - **建議航速**: [X] 節 (較正常航速 -[X] 節)
        - **節省燃油**: [X] 噸/天
        - **節省成本**: $[X] USD
        - **延後到達時間**: [X] 小時
        - **適用情境**:
          * ✅ 油價高企，成本壓力大
          * ✅ 泊位擁擠，提前到達需錨泊
          * ✅ 運價低迷，時間價值低
          * ✅ 避開惡劣天氣窗口
        - **成本效益**: [正面/中性/負面]
        
        ### 方案 C：維持航速 ⏱️
        - **建議航速**: [X] 節 (經濟航速)
        - **燃油消耗**: [X] 噸/天
        - **預計到達**: [ETA]
        - **適用情境**:
          * ✅ 泊位時窗充裕
          * ✅ 運價油價平衡
          * ✅ 無特殊時間壓力
        
        ---
        
        # 📍 候選泊位詳細分析
        
        ## 🥇 泊位 A: [代碼] ([名稱])
        - **適配度**: ✅ 優良 / ⚠️ 適配 / ❌ 勉強
        - **泊位長度**: [X] m (餘裕 [X] m)
        - **水深**: [X] m
        - **可用時窗**: YYYY-MM-DD HH:MM ~ HH:MM
        - **競合船舶**: [X] 艘
        - **優勢**: [列舉]
        - **風險**: [列舉]
        - **推薦指數**: ⭐⭐⭐⭐⭐
        
        ## 🥈 泊位 B: [代碼] ([名稱])
        - **適配度**: ✅ 優良 / ⚠️ 適配 / ❌ 勉強
        - **泊位長度**: [X] m (餘裕 [X] m)
        - **水深**: [X] m
        - **可用時窗**: YYYY-MM-DD HH:MM ~ HH:MM
        - **競合船舶**: [X] 艘
        - **優勢**: [列舉]
        - **風險**: [列舉]
        - **推薦指數**: ⭐⭐⭐⭐
        
        [其他泊位...]
        
        ---
        
        # ⚠️ 風險警告與注意事項
        
        ## 🔴 高風險因素
        1. **[風險類型]**: [詳細描述]
        2. **[風險類型]**: [詳細描述]
        
        ## 🟡 中風險因素
        1. **[風險類型]**: [詳細描述]
        2. **[風險類型]**: [詳細描述]
        
        ## 🟢 低風險因素
        1. **[風險類型]**: [詳細描述]
        
        ---
        
        # 💡 綜合策略建議
        
        ## 🏆 最佳方案（推薦）
        
        ### 航速策略
        - **建議**: [加俥/慢俥/維持]
        - **目標航速**: [X] 節
        - **預計到達**: YYYY-MM-DD HH:MM
        - **理由**: 
          1. [經濟因素考量]
          2. [泊位競合考量]
          3. [天氣風險考量]
          4. [成本效益分析]
        
        ### 靠泊安排
        - **首選泊位**: [代碼] ([名稱])
        - **備選泊位**: [代碼] ([名稱])
        - **到達時窗**: YYYY-MM-DD HH:MM ~ HH:MM
        - **預計靠泊時間**: YYYY-MM-DD HH:MM
        
        ### 應變措施
        - **Plan A**: [正常情境]
        - **Plan B**: [泊位延遲情境]
        - **Plan C**: [天氣惡化情境]
        
        ## 📊 成本效益總結
        
        | 方案 | 航速 | 燃油成本 | 時間成本 | 風險成本 | 總評 |
        |------|------|----------|----------|----------|------|
        | 加俥 | [X]節 | $[X] | $[X] | $[X] | [評分] |
        | 慢俥 | [X]節 | $[X] | $[X] | $[X] | [評分] |
        | 維持 | [X]節 | $[X] | $[X] | $[X] | [評分] |
        
        ---
        
        # ✅ 最終結論
        
        **綜合評估**: [1-2 句話總結]
        
        **最佳策略**: [具體建議]
        
        **關鍵決策點**:
        1. [決策點 1]
        2. [決策點 2]
        3. [決策點 3]
        
        **預期效益**:
        - 💰 成本節約/增加: $[X] USD
        - ⏱️ 時間優化: [X] 小時
        - 🎯 風險降低: [X]%
        
        ```
        
        ## 📐 分析規範
        
        ### 數據查詢要求
        - **必須查詢**: 目標港口實時天氣、未來 48 小時預報
        - **必須查詢**: 當前國際油價（Brent/WTI）
        - **建議查詢**: 相關航線運價指數
        - **建議查詢**: 港口歷史擁擠數據
        
        ### 計算標準
        - **燃油消耗**: 使用標準海事公式（功率 ∝ 速度³）
        - **成本估算**: 基於實時油價與市場數據
        - **時間計算**: 考慮航行距離、天氣、引水等待
        
        ### 輸出要求
        - **語言**: 繁體中文
        - **時間格式**: YYYY-MM-DD HH:MM (Asia/Taipei)
        - **長度單位**: 公尺 (m)
        - **重量單位**: 公噸 (MT)
        - **貨幣單位**: 美元 (USD)
        - **輸出長度**: 2500-3500 字
        
        ### 專業術語
        - 加俥 = 增速航行
        - 慢俥 = 減速航行（Slow Steaming）
        - 錨泊 = 拋錨等待
        - 滯期費 = Demurrage
        - 經濟航速 = Economical Speed
        
        ## ⚖️ 免責聲明
        
        本分析基於當前可得資訊與市場數據，僅供決策參考。實際操作應：
        1. 遵循港務局與海事法規
        2. 聽從專業引水人指示
        3. 考慮船東/租家具體要求
        4. 依據實時天氣與海況調整
        5. 諮詢船舶經紀與代理意見
    """).strip()


def _build_user_prompt(
    port_name: str,
    ship_type: str,
    vessel_name: str,  # ✅ 這是使用者輸入的船名
    eta_str: str,
    ship_length: float,  # ✅ 這是使用者輸入的船長
    safety_buffer_each_side: float,
    required_length: float,
    competition_window_minutes: int,
    in_berth_list: List[Dict],
    inbound_list: List[Dict],
    outbound_list: List[Dict],
    candidate_berths: List[Dict],
    current_speed: float = None,
    distance_to_port: float = None,
    vessel_dwt: float = None,
    main_engine_power: float = None
) -> str:
    """
    建立 User Prompt（v3.6 - 明確標示分析目標船舶）
    """
    
    # ✅ 使用傳入的 vessel_name（來自使用者輸入）
    ship_name = vessel_name if vessel_name else '萬海船舶'
    
    # ✅ 統計資訊
    stats = {
        "在泊": int(len(in_berth_list)) if in_berth_list else 0,
        "進港": int(len(inbound_list)) if inbound_list else 0,
        "出港": int(len(outbound_list)) if outbound_list else 0,
        "候選泊位": int(len(candidate_berths)) if candidate_berths else 0
    }
    
    print(f"\n📊 AI 分析統計資訊:")
    print(f"   目標船舶: {ship_name} ({ship_length}m)")
    print(f"   在泊船舶: {stats['在泊']} 艘")
    print(f"   進港船舶: {stats['進港']} 艘")
    print(f"   出港船舶: {stats['出港']} 艘")
    print(f"   候選泊位: {stats['候選泊位']} 個")
    
    # ✅ 摘要船舶資料
    in_berth_summary = _summarize_ship_list(in_berth_list, max_items=5)
    inbound_summary = _summarize_ship_list(inbound_list, max_items=5)
    outbound_summary = _summarize_ship_list(outbound_list, max_items=5)
    
    # ✅ 候選泊位摘要
    berth_summary = []
    for i, berth in enumerate(candidate_berths[:8], 1):
        berth_code = (
            berth.get('泊位代碼') or 
            berth.get('碼頭代碼') or 
            berth.get('wharf_code') or 
            'N/A'
        )
        
        berth_name = (
            berth.get('泊位名稱') or 
            berth.get('碼頭名稱') or 
            berth.get('wharf_name') or 
            ''
        )
        
        berth_length = float(
            berth.get('泊位長度') or 
            berth.get('碼頭長度') or 
            berth.get('wharf_length') or 
            0
        )
        
        water_depth = float(
            berth.get('水深') or 
            berth.get('wharf_depth') or 
            0
        )
        
        berth_type = (
            berth.get('碼頭類型') or 
            berth.get('wharf_type') or 
            'N/A'
        )
        
        berth_area = (
            berth.get('泊位區域') or 
            berth.get('wharf_area') or 
            'N/A'
        )
        
        display_name = f"{berth_code}"
        if berth_name and berth_name != 'N/A' and berth_name != berth_code:
            display_name += f" ({berth_name})"
        
        fit_status = "✅ 適配" if berth_length >= required_length else f"⚠️ 短缺 {required_length - berth_length:.1f}m"
        
        berth_summary.append(
            f"{i}. {display_name} | 長度: {berth_length:.1f}m | 水深: {water_depth:.1f}m | "
            f"類型: {berth_type} | 區域: {berth_area} | {fit_status}"
        )
    
    if len(candidate_berths) > 8:
        berth_summary.append(f"... 及其他 {len(candidate_berths) - 8} 個泊位")
    
    # ✅ 建立 Prompt（明確標示這是使用者要分析的船舶）
    prompt = dedent(f"""
        請進行**完整的靠泊動態與航運經濟綜合評估**：
        
        ## 🚢 【分析目標】船舶基本資訊
        
        ⚠️ **重要**: 以下是使用者要分析的目標船舶資訊（不是資料庫中的其他船舶）
        
        - **港口**: {port_name}
        - **船種**: {ship_type}
        - **船名**: {ship_name} ⭐（這是要分析的目標船舶）
        - **預計到達時間 (ETA)**: {eta_str} ({TIMEZONE})
        - **船長 (LOA)**: {ship_length:.1f} m ⭐（使用者輸入）
        - **單側安全距離**: {safety_buffer_each_side:.1f} m
        - **所需泊位長度**: {required_length:.1f} m
        - **競合時窗**: ±{competition_window_minutes} 分鐘
    """).strip()
    
    # ✅ 新增：航行參數（如果有提供）
    if current_speed or distance_to_port or vessel_dwt or main_engine_power:
        prompt += "\n\n## 🚢 航行參數\n\n"
        if current_speed:
            prompt += f"- **當前航速**: {current_speed:.1f} 節\n"
        if distance_to_port:
            prompt += f"- **距離港口**: {distance_to_port:.1f} 海浬\n"
        if vessel_dwt:
            prompt += f"- **載重噸位 (DWT)**: {vessel_dwt:,.0f} 噸\n"
        if main_engine_power:
            prompt += f"- **主機功率**: {main_engine_power:,.0f} kW\n"
    
    prompt += dedent(f"""
        
        ## 📊 港口動態統計（參考資料）
        
        以下是港口中其他船舶的資料，用於評估競爭情況：
        
        - **在泊船舶**: {stats['在泊']} 艘
        - **進港船舶**: {stats['進港']} 艘
        - **出港船舶**: {stats['出港']} 艘
        - **候選泊位**: {stats['候選泊位']} 個
        
        ## 📋 在泊船舶（前 5 筆）
        
        {in_berth_summary}
        
        ## 📋 進港船舶（前 5 筆）
        
        {inbound_summary}
        
        ## 📋 出港船舶（前 5 筆）
        
        {outbound_summary}
        
        ## 📋 候選泊位（前 8 個）
        
    """).strip()
    
    # 加入泊位列表
    if berth_summary:
        prompt += "\n\n" + "\n".join(berth_summary)
    else:
        prompt += "\n\n*目前無候選泊位*"
    
    prompt += dedent(f"""
        
        ---
        
        ## 🎯 分析要求（請務必完整執行）
        
        ⚠️ **重要提醒**: 
        - 分析目標是 **{ship_name}** (船長 {ship_length:.1f}m, ETA: {eta_str})
        - 請針對這艘船舶進行泊位適配性、競爭分析、航速建議
        - 其他船舶資料僅作為參考，用於評估港口擁擠程度
        
        ### 1️⃣ 實時數據查詢（必須執行）
        - ✅ 查詢 **{port_name}** 當前天氣與未來 48 小時預報
        - ✅ 查詢當前國際油價（Brent 原油、船用燃油價格）
        - ✅ 查詢相關航線運價指數（如適用）
        - ✅ 評估錨地安全性與錨泊風險
        
        ### 2️⃣ 航速策略分析（必須提供）
        請針對 **{ship_name}** 提供以下三種方案的**詳細成本效益分析**：
        
        #### 方案 A：加俥策略 🚀
        - 計算增速後的燃油消耗與成本
        - 評估提前到達的商業價值
        - 分析在當前油價與運價下是否划算
        - 說明適用情境與決策理由
        
        #### 方案 B：慢俥策略 🐢
        - 計算減速後的燃油節省與成本
        - 評估延後到達的風險與損失
        - 分析是否能避免錨泊等待
        - 說明適用情境與決策理由
        
        #### 方案 C：維持航速 ⏱️
        - 評估當前航速的合理性
        - 分析是否為最優經濟方案
        - 說明適用情境與決策理由
        
        ### 3️⃣ 天氣風險評估（必須提供）
        - 評估天氣對 **{ship_name}** 靠泊作業的影響
        - 分析錨泊等待的風險與成本
        - 提供天氣窗口建議
        - 說明惡劣天氣應變措施
        
        ### 4️⃣ 泊位競合分析（必須提供）
        - 識別 **{ship_name}** 與其他船舶的時間衝突與空間競合
        - 評估各候選泊位對 **{ship_name}** 的適配度
        - 提供 2-3 個可行靠泊方案
        - 標註風險因素與應變措施
        
        ### 5️⃣ 綜合決策建議（必須提供）
        - 基於經濟、天氣、泊位等多維度分析
        - 提供明確的最佳方案與理由
        - 包含成本效益總結表格
        - 提供應變計畫（Plan A/B/C）
        
        ---
        
        ## ⚠️ 重要提醒
        
        1. **分析目標**: **{ship_name}** (LOA: {ship_length:.1f}m)
        2. **必須查詢實時數據**：天氣、油價、運價等
        3. **必須提供具體數字**：燃油消耗、成本、時間等
        4. **必須說明決策理由**：為什麼建議加俥/慢俥/維持
        5. **必須考慮經濟因素**：油價高低、運價水平、成本效益
        6. **必須評估天氣風險**：錨泊安全性、惡劣天氣影響
        7. **必須提供應變方案**：不同情境下的備選計畫
        
        請按照指定格式輸出完整的分析報告（2500-3500 字）。
    """).strip()
    
    return prompt


def _call_api(
    messages: List[Dict],
    task_type: str = 'berth_analysis',
    api_key: str = None,
    max_retries: int = 2,
    timeout: int = 180
) -> Optional[Dict]:
    """呼叫 Perplexity API"""
    if not api_key:
        api_key = PERPLEXITY_API_KEY
    
    if not api_key:
        print("❌ 未設定 PERPLEXITY_API_KEY")
        return None
    
    config = MODEL_CONFIG.get(task_type, MODEL_CONFIG['berth_analysis'])
    model_name = config['model']
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": config['temperature'],
        "max_tokens": config['max_tokens'],
        "stream": False
    }
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                wait_time = 3 ** attempt
                print(f"🔄 重試第 {attempt} 次（等待 {wait_time} 秒）...")
                time.sleep(wait_time)
            
            print(f"🤖 正在呼叫 Perplexity AI...")
            print(f"   📋 任務: {config['description']}")
            print(f"   🤖 使用模型: {model_name}")
            print(f"   📊 Max Tokens: {config['max_tokens']:,}")
            
            start_time = time.time()
            
            response = requests.post(
                PERPLEXITY_API_URL,
                headers=headers,
                json=payload,
                timeout=timeout
            )
            
            elapsed_time = time.time() - start_time
            print(f"⏱️ 請求耗時: {elapsed_time:.2f} 秒")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    print("❌ API 回應無法解析為 JSON")
                    return None
                
                choices = result.get('choices', [])
                if choices and isinstance(choices, list) and len(choices) > 0:
                    message = choices[0].get('message', {})
                    content = message.get('content', '')
                    
                    if content:
                        usage = result.get('usage', {})
                        if usage:
                            print(f"💰 Token 使用: {usage.get('total_tokens', 0):,} "
                                  f"(Prompt: {usage.get('prompt_tokens', 0):,}, "
                                  f"Completion: {usage.get('completion_tokens', 0):,})")
                        
                        print("✅ AI 分析完成")
                        
                        return {
                            'content': content,
                            'usage': usage,
                            'model': model_name,
                            'elapsed_time': elapsed_time
                        }
                
                print("❌ API 回應格式異常或無內容")
                return None
            
            elif response.status_code == 401:
                print("❌ API Key 認證失敗")
                return None
            
            elif response.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = 10 * (attempt + 1)
                    print(f"⚠️ API 請求頻率限制，等待 {wait_time} 秒後重試...")
                    time.sleep(wait_time)
                    continue
                else:
                    print("❌ API 請求頻率限制，請稍後再試")
                    return None
            
            elif response.status_code == 500:
                if attempt < max_retries - 1:
                    print("⚠️ 伺服器錯誤，嘗試重試...")
                    continue
                else:
                    print("❌ Perplexity 伺服器錯誤")
                    return None
            
            else:
                print(f"❌ API 請求失敗: HTTP {response.status_code}")
                print(f"   回應內容: {response.text[:500]}")
                return None
        
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print(f"⚠️ 請求超時（{timeout}秒），嘗試重試...")
                continue
            else:
                print(f"❌ API 請求超時（{timeout}秒）")
                return None
        
        except requests.exceptions.ConnectionError:
            print("❌ 無法連線到 Perplexity API")
            return None
        
        except Exception as e:
            print(f"❌ 未預期的錯誤: {str(e)}")
            return None
    
    print(f"❌ 經過 {max_retries} 次重試後仍然失敗")
    return None


# ==================== 主要 API 函數 ====================

def generate_berth_ai_analysis_from_db(
    port_name: str,
    ship_type: str,
    vessel_name: str,
    eta: Any,
    ship_length: float,
    safety_buffer_each_side: float = 10.0,
    competition_window_minutes: int = 120,
    perplexity_api_key: str = None,
    analysis_mode: str = 'normal',
    max_retries: int = 2,
    timeout: int = 180,
    berth_db_path: str = None,
    wharf_db_path: str = None,
    # ✅ 新增：接收使用者輸入的資料
    user_input_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    ✅ 使用 Perplexity AI 進行靠泊動態綜合評估（v3.6 修正版）
    
    Args:
        user_input_data: 使用者輸入的資料，包含：
            - vessel_name: 船名
            - ship_length: 船長
            - eta: ETA 時間
            - ship_type: 船型
    """
    # ✅ 優先使用 user_input_data 的資料
    if user_input_data:
        vessel_name = user_input_data.get('vessel_name', vessel_name)
        ship_length = user_input_data.get('ship_length', ship_length)
        eta = user_input_data.get('eta', eta)
        ship_type = user_input_data.get('ship_type', ship_type)
        
        print(f"\n✅ 使用使用者輸入的資料:")
        print(f"   船名: {vessel_name}")
        print(f"   船長: {ship_length}m")
        print(f"   ETA: {_safe_strptime(eta)}")
        print(f"   船型: {ship_type}")
    
    # ✅ 確保船名不為空
    if not vessel_name or vessel_name.strip() == '':
        vessel_name = '萬海船舶'
        print("⚠️ 船名為空，使用預設值: 萬海船舶")
    
    print(f"\n{'='*60}")
    print(f"🚢 開始分析靠泊動態")
    print(f"{'='*60}")
    print(f"港口: {port_name}")
    print(f"船舶: {vessel_name} ({ship_type})")
    print(f"船長: {ship_length} m")
    print(f"ETA: {_safe_strptime(eta)}")
    print(f"{'='*60}\n")
    
    # ✅ 初始化資料庫
    db = BerthDatabase(berth_db_path, wharf_db_path)
    
    # ✅ 計算所需泊位長度
    required_length = ship_length + (2 * safety_buffer_each_side)
    print(f"📏 所需泊位長度: {required_length:.1f} m "
          f"(船長 {ship_length:.1f} m + 安全距離 {safety_buffer_each_side*2:.1f} m)")
    
    # ✅ 從資料庫查詢港口資料（不是查詢船舶）
    print(f"\n🔍 正在從資料庫查詢港口資料...")
    
    in_berth_list = db.get_in_berth_ships(port_name)
    inbound_list = db.get_inbound_ships(port_name, time_window_hours=48)
    outbound_list = db.get_outbound_ships(port_name, time_window_hours=48)
    candidate_berths = db.get_candidate_berths(port_name, required_length, ship_type)
    
    # ✅ 檢查是否有足夠資料
    if not candidate_berths:
        return {
            'success': False,
            'error': f'❌ 在 {port_name} 找不到符合長度要求 ({required_length:.1f}m) 的泊位'
        }
    
    print(f"\n📊 港口資料統計:")
    print(f"  - 在泊船舶: {len(in_berth_list)} 艘")
    print(f"  - 進港船舶: {len(inbound_list)} 艘")
    print(f"  - 出港船舶: {len(outbound_list)} 艘")
    print(f"  - 候選泊位: {len(candidate_berths)} 個")
    
    # ✅ 調用 AI 分析（使用使用者輸入的船舶資料）
    return generate_berth_ai_analysis(
        port_name=port_name,
        ship_type=ship_type,
        vessel_name=vessel_name,  # ✅ 使用使用者輸入的船名
        eta=eta,  # ✅ 使用使用者輸入的 ETA
        ship_length=ship_length,  # ✅ 使用使用者輸入的船長
        safety_buffer_each_side=safety_buffer_each_side,
        required_length=required_length,
        in_berth_list=in_berth_list,  # 港口其他船舶資料
        inbound_list=inbound_list,
        outbound_list=outbound_list,
        candidate_berths=candidate_berths,
        competition_window_minutes=competition_window_minutes,
        perplexity_api_key=perplexity_api_key,
        analysis_mode=analysis_mode,
        max_retries=max_retries,
        timeout=timeout
    )


def generate_berth_ai_analysis(
    port_name: str,
    ship_type: str,
    vessel_name: str,
    eta: Any,
    ship_length: float,
    safety_buffer_each_side: float,
    required_length: float,
    in_berth_list: List[Dict],
    inbound_list: List[Dict],
    outbound_list: List[Dict],
    candidate_berths: List[Dict],
    competition_window_minutes: int,
    perplexity_api_key: str = None,
    analysis_mode: str = 'normal',
    max_retries: int = 2,
    timeout: int = 180
) -> Dict[str, Any]:
    """原有的 AI 分析函數（保持向後兼容）"""
    
    if not perplexity_api_key:
        perplexity_api_key = PERPLEXITY_API_KEY
    
    if not perplexity_api_key:
        return {
            'success': False,
            'error': '❌ 請提供 Perplexity API Key'
        }
    
    eta_str = _safe_strptime(eta)
    
    system_message = _build_system_prompt()
    user_message = _build_user_prompt(
        port_name=port_name,
        ship_type=ship_type,
        vessel_name=vessel_name,
        eta_str=eta_str,
        ship_length=ship_length,
        safety_buffer_each_side=safety_buffer_each_side,
        required_length=required_length,
        competition_window_minutes=competition_window_minutes,
        in_berth_list=in_berth_list,
        inbound_list=inbound_list,
        outbound_list=outbound_list,
        candidate_berths=candidate_berths
    )
    
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]
    
    task_type_map = {
        'quick': 'quick_analysis',
        'normal': 'berth_analysis',
        'deep': 'deep_research'
    }
    task_type = task_type_map.get(analysis_mode, 'berth_analysis')
    
    print(f"🎯 分析模式: {analysis_mode}")
    
    result = _call_api(
        messages=messages,
        task_type=task_type,
        api_key=perplexity_api_key,
        max_retries=max_retries,
        timeout=timeout
    )
    
    if result:
        return {
            'success': True,
            'analysis': result['content'],
            'raw_response': result,
            'usage': result.get('usage', {}),
            'model': result.get('model', PERPLEXITY_MODEL),
            'elapsed_time': result.get('elapsed_time', 0)
        }
    else:
        return {
            'success': False,
            'error': '❌ API 調用失敗，請檢查網路連線或 API Key'
        }


def format_ai_analysis(result: Dict[str, Any]) -> str:
    """格式化 AI 分析結果"""
    if not result.get('success'):
        error_msg = result.get('error', '未知錯誤')
        error_display = f"## ❌ AI 分析失敗\n\n**錯誤訊息**: {error_msg}"
        
        if "API Key" in error_msg:
            error_display += "\n\n### 💡 解決建議\n\n1. 檢查 API Key 是否正確\n2. 確認 API Key 是否已啟用\n3. 檢查 API Key 權限設定"
        elif "超時" in error_msg or "Timeout" in error_msg:
            error_display += "\n\n### 💡 解決建議\n\n1. 檢查網路連線速度\n2. 減少輸入資料量\n3. 稍後再試"
        elif "頻率限制" in error_msg:
            error_display += "\n\n### 💡 解決建議\n\n1. 等待 1-2 分鐘後再試\n2. 檢查 API 使用配額"
        elif "找不到" in error_msg:
            error_display += "\n\n### 💡 解決建議\n\n1. 檢查港口名稱是否正確\n2. 確認船舶長度輸入\n3. 檢查資料庫是否有該港口資料"
        
        return error_display
    
    analysis = result.get('analysis', '')
    usage = result.get('usage', {})
    model = result.get('model', PERPLEXITY_MODEL)
    elapsed_time = result.get('elapsed_time', 0)
    
    footer = "\n\n---\n\n"
    footer += f"**🤖 AI 模型**: {model}\n\n"
    
    if usage:
        prompt_tokens = usage.get('prompt_tokens', 'N/A')
        completion_tokens = usage.get('completion_tokens', 'N/A')
        total_tokens = usage.get('total_tokens', 'N/A')
        
        footer += f"**📊 Token 使用情況**:\n"
        footer += f"- 輸入: {prompt_tokens:,} tokens\n"
        footer += f"- 輸出: {completion_tokens:,} tokens\n"
        footer += f"- 總計: {total_tokens:,} tokens\n\n"
    
    if elapsed_time > 0:
        footer += f"**⏱️ 分析耗時**: {elapsed_time:.2f} 秒\n"
    
    footer += f"**⏰ 生成時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    footer += "\n---\n\n"
    footer += "*⚠️ 此分析結果僅供參考，實際靠泊調度應遵循港務局規定與專業引水人指示。*"
    
    return analysis + footer


# ==================== 測試程式 ====================

if __name__ == "__main__":
    print("=== 測試 AI 分析模組 v3.5（完全修正版） ===\n")
    
    from datetime import datetime, timedelta
    import pytz
    
    # 1️⃣ 測試資料庫連線
    print("1️⃣ 測試資料庫連線...")
    db = BerthDatabase()
    
    # 2️⃣ 測試查詢碼頭資訊
    print("\n2️⃣ 測試查詢碼頭資訊...")
    wharfs = db.get_wharf_info('基隆港')
    if wharfs:
        print(f"   ✅ 查詢成功，共 {len(wharfs)} 個碼頭")
        for w in wharfs[:3]:
            print(f"   - {w.get('泊位代碼')} {w.get('泊位名稱')} ({w.get('泊位長度')}m)")
    
    # 3️⃣ 測試查詢船舶
    print("\n3️⃣ 測試查詢船舶...")
    in_berth = db.get_in_berth_ships('基隆港')
    inbound = db.get_inbound_ships('基隆港')
    outbound = db.get_outbound_ships('基隆港')
    
    print(f"   在泊: {len(in_berth)} 艘")
    if in_berth:
        for s in in_berth[:3]:
            print(f"   - {s.get('船名')} @ {s.get('泊位')}")
    
    print(f"   進港: {len(inbound)} 艘")
    if inbound:
        for s in inbound[:3]:
            print(f"   - {s.get('船名')} ETA: {s.get('ETA')}")
    
    print(f"   出港: {len(outbound)} 艘")
    if outbound:
        for s in outbound[:3]:
            print(f"   - {s.get('船名')} ETD: {s.get('ETD')}")
    
    # 4️⃣ 測試查詢候選泊位
    print("\n4️⃣ 測試查詢候選泊位...")
    candidates = db.get_candidate_berths('基隆港', 330.0)
    print(f"   符合 330m 以上的泊位: {len(candidates)} 個")
    if candidates:
        for c in candidates[:5]:
            print(f"   - {c.get('泊位代碼')} {c.get('泊位名稱')} "
                  f"({c.get('泊位長度')}m) {c.get('適配度')}")
    
    # 5️⃣ 測試完整 AI 分析
    print("\n5️⃣ 測試完整 AI 分析...")
    
    tz = pytz.timezone('Asia/Taipei')
    test_eta = datetime.now(tz) + timedelta(hours=6)
    
    result = generate_berth_ai_analysis_from_db(
        port_name='基隆港',
        ship_type='貨櫃輪',
        ship_name='萬海船舶',
        eta=test_eta,
        ship_length=300.0,
        safety_buffer_each_side=15.0,
        competition_window_minutes=60,
        analysis_mode='quick'
    )
    
    if result.get('success'):
        print("\n✅ AI 分析成功！")
        print("\n" + "="*60)
        print(format_ai_analysis(result))
        print("="*60)
    else:
        print(f"\n❌ AI 分析失敗: {result.get('error')}")
    
    print("\n✅ 所有測試完成")
