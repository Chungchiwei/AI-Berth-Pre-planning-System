"""
泊位分析與判斷模組 (v5.0)
整合 TaiwanPort_wharf_information.db 和 berth_management_Data.db
修正:
  1. 避免重複資料計算
  2. 修正泊位長度計算（加入安全距離）
  3. 優化查詢效能
  4. 整合 database.py 的去重功能
"""
from datetime import datetime, timedelta
import pytz
import pandas as pd
import sqlite3
import os
from config import (
    TIMEZONE, DEFAULT_SAFETY_BUFFER, 
    DEFAULT_COMPETITION_WINDOW, DEFAULT_BERTH_DURATION,
    Port_DB_Path, DB_PATH
)


# ==================== 安全轉換函數 ====================

def safe_float(value, default=0.0):
    """安全轉換為浮點數"""
    if value is None or value == '' or value == '[無資料]':
        return default
    
    try:
        if isinstance(value, str):
            value = value.replace(',', '').strip()
        return float(value)
    except (ValueError, TypeError, AttributeError):
        return default


def safe_str(value, default=''):
    """安全轉換為字串"""
    if value is None or value == '' or value == '[無資料]':
        return default
    
    try:
        return str(value).strip()
    except (AttributeError, TypeError):
        return default


def safe_int(value, default=0):
    """安全轉換為整數"""
    if value is None or value == '' or value == '[無資料]':
        return default
    
    try:
        if isinstance(value, str):
            value = value.replace(',', '').strip()
        return int(float(value))
    except (ValueError, TypeError, AttributeError):
        return default


# ==================== 時間解析 ====================

def parse_iso_datetime(dt_str):
    """解析 ISO8601 時間字串"""
    if not dt_str or dt_str == "" or dt_str == "[無資料]":
        return None
    
    try:
        if 'T' in str(dt_str):
            dt = datetime.fromisoformat(str(dt_str).replace('Z', '+00:00'))
        else:
            formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y/%m/%d %H:%M']
            for fmt in formats:
                try:
                    dt = datetime.strptime(str(dt_str), fmt)
                    dt = pytz.timezone(TIMEZONE).localize(dt)
                    return dt
                except:
                    continue
            return None
        
        if dt.tzinfo is None:
            dt = pytz.timezone(TIMEZONE).localize(dt)
        
        return dt
    except Exception as e:
        return None


# ==================== 從 TaiwanPort_wharf_information.db 讀取泊位資訊 ====================

def load_wharf_info(port_code='KEL'):
    """
    從 TaiwanPort_wharf_information.db 讀取泊位資訊
    
    Args:
        port_code: 港口代碼 (KEL=基隆港, KHH=高雄港, TXG=台中港, TPE=台北港)
    
    Returns:
        dict: {wharf_code: {wharf_name, length_m, depth_m, ...}}
    """
    wharf_db_path = os.path.join(
        os.path.dirname(DB_PATH),
        'TaiwanPort_wharf_information.db'
    )
    
    if not os.path.exists(wharf_db_path):
        print(f"⚠️ 找不到泊位資訊資料庫: {wharf_db_path}")
        # 從 D005 提取基本泊位資訊作為備案
        return load_wharf_info_from_d005(port_code)
    
    try:
        conn = sqlite3.connect(wharf_db_path)
        
        # 港口代碼對應
        port_code_map = {
            'KEL': 'KEL',  # 基隆港
            'KHH': 'KHH',  # 高雄港
            'TXG': 'TXG',  # 台中港
            'TPE': 'TPE'   # 台北港
        }
        
        query = """
        SELECT
            PortName_en as port_code,
            PortName_cn as port_name,
            wharf_code,
            wharf_name,
            basinName,
            wharf_length as length_m,
            wharf_depth as depth_m,
            wharf_type as cargo_type,
            wharf_area
        FROM wharf_information
        WHERE PortName_en = ?
        ORDER BY wharf_code
        """
        
        df = pd.read_sql_query(query, conn, params=(port_code_map.get(port_code, port_code),))
        conn.close()
        
        if df.empty:
            print(f"⚠️ 找不到 {port_code} 港的泊位資訊，使用 D005 資料")
            return load_wharf_info_from_d005(port_code)
        
        # 轉換為字典
        wharf_dict = {}
        for _, row in df.iterrows():
            wharf_code = safe_str(row['wharf_code'])
            wharf_dict[wharf_code] = {
                'port_code': safe_str(row['port_code']),
                'port_name': safe_str(row['port_name']),
                'wharf_name': safe_str(row['wharf_name']),
                'wharf_name_en': safe_str(row.get('basinName', '')),
                'length_m': safe_float(row.get('length_m', 300.0)),
                'depth_m': safe_float(row.get('depth_m', 12.0)),
                'cargo_type': safe_str(row.get('cargo_type', '貨櫃')),
                'wharf_area': safe_str(row.get('wharf_area', '')),
                'is_container': '貨櫃' in safe_str(row.get('cargo_type', ''))
            }
        
        print(f"✓ 載入 {port_code} ({df.iloc[0]['port_name']}) 港泊位資訊: {len(wharf_dict)} 個碼頭")
        
        return wharf_dict
    
    except sqlite3.Error as e:
        print(f"✗ 讀取泊位資訊失敗: {e}")
        return load_wharf_info_from_d005(port_code)
    except Exception as e:
        print(f"✗ 載入泊位資訊時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return load_wharf_info_from_d005(port_code)


def load_wharf_info_from_d005(port_code='KEL'):
    """
    從 ifa_d005 提取泊位資訊（備案方案）
    
    Args:
        port_code: 港口代碼
    
    Returns:
        dict: {wharf_code: {wharf_name, ...}}
    """
    if not os.path.exists(DB_PATH):
        print(f"⚠️ 找不到資料庫: {DB_PATH}")
        return {}
    
    try:
        conn = sqlite3.connect(DB_PATH)
        
        query = """
        SELECT DISTINCT
            port_code,
            port_name,
            wharf_code,
            wharf_name,
            can_berth_container
        FROM ifa_d005
        WHERE port_code = ? AND wharf_code IS NOT NULL
        ORDER BY wharf_code
        """
        
        df = pd.read_sql_query(query, conn, params=(port_code,))
        conn.close()
        
        if df.empty:
            print(f"⚠️ 找不到 {port_code} 港的泊位資訊")
            return {}
        
        wharf_dict = {}
        for _, row in df.iterrows():
            wharf_code = safe_str(row['wharf_code'])
            wharf_dict[wharf_code] = {
                'port_code': safe_str(row['port_code']),
                'port_name': safe_str(row['port_name']),
                'wharf_name': safe_str(row['wharf_name']),
                'wharf_name_en': '',
                'length_m': 300.0,  # 預設值
                'depth_m': 12.0,    # 預設值
                'cargo_type': '貨櫃',
                'wharf_area': '',
                'is_container': bool(row.get('can_berth_container', 0))
            }
        
        print(f"✓ 從 D005 提取 {port_code} 港泊位資訊: {len(wharf_dict)} 個碼頭")
        
        return wharf_dict
    
    except Exception as e:
        print(f"✗ 從 D005 提取泊位資訊失敗: {e}")
        return {}


# ==================== 從 berth_management_Data.db 讀取船舶資料（去重版）====================

def load_berth_status(port_code='KEL'):
    """
    從 berth_management_Data.db 讀取在泊船舶資料 (ifa_d005)
    🔥 修正: 自動去重，避免重複計算
    
    Args:
        port_code: 港口代碼
    
    Returns:
        pd.DataFrame: 在泊船舶資料（已去重）
    """
    if not os.path.exists(DB_PATH):
        print(f"⚠️ 找不到資料庫: {DB_PATH}")
        return pd.DataFrame()
    
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # 🔥 使用 DISTINCT 和 MAX(id) 去重
        query = """
        SELECT
            d.*
        FROM ifa_d005 d
        INNER JOIN (
            SELECT 
                port_code,
                wharf_code,
                vessel_ename,
                eta_berth,
                MAX(id) as max_id
            FROM ifa_d005
            WHERE port_code = ?
            GROUP BY port_code, wharf_code, vessel_ename, eta_berth
        ) latest
        ON d.id = latest.max_id
        ORDER BY d.wharf_code, d.ata_berth
        """
        
        df = pd.read_sql_query(query, conn, params=(port_code,))
        conn.close()
        
        # D005 沒有 call_sign，使用 vessel_no 代替
        df['call_sign'] = df['vessel_no']
        
        print(f"✓ 載入在泊船舶資料 (D005): {len(df)} 筆（已去重）")
        
        if len(df) == 0:
            print(f"⚠️ {port_code} 港目前沒有在泊船舶")
        
        return df
    
    except sqlite3.Error as e:
        print(f"✗ 載入在泊船舶時發生資料庫錯誤: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()
    except Exception as e:
        print(f"✗ 載入在泊船舶時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def load_eta_ships(port_code='KEL'):
    """
    從 berth_management_Data.db 讀取預計進港船舶資料 (ifa_d003)
    🔥 修正: 自動去重
    
    Args:
        port_code: 港口代碼
    
    Returns:
        pd.DataFrame: 預計進港船舶資料（已去重）
    """
    if not os.path.exists(DB_PATH):
        print(f"⚠️ 找不到資料庫: {DB_PATH}")
        return pd.DataFrame()
    
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # 🔥 使用 DISTINCT 和 MAX(id) 去重
        query = """
        SELECT
            d.*
        FROM ifa_d003 d
        INNER JOIN (
            SELECT 
                port_code,
                vessel_ename,
                eta_berth,
                MAX(id) as max_id
            FROM ifa_d003
            WHERE port_code = ?
            GROUP BY port_code, vessel_ename, eta_berth
        ) latest
        ON d.id = latest.max_id
        ORDER BY d.eta_report
        """
        
        df = pd.read_sql_query(query, conn, params=(port_code,))
        conn.close()
        
        print(f"✓ 載入預計進港船舶 (D003): {len(df)} 筆（已去重）")
        
        return df
    
    except Exception as e:
        print(f"✗ 載入預計進港船舶時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def load_etd_ships(port_code='KEL'):
    """
    從 berth_management_Data.db 讀取預計離港船舶資料 (ifa_d004)
    🔥 修正: 自動去重
    
    Args:
        port_code: 港口代碼
    
    Returns:
        pd.DataFrame: 預計離港船舶資料（已去重）
    """
    if not os.path.exists(DB_PATH):
        print(f"⚠️ 找不到資料庫: {DB_PATH}")
        return pd.DataFrame()
    
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # 🔥 使用 DISTINCT 和 MAX(id) 去重
        query = """
        SELECT
            d.*
        FROM ifa_d004 d
        INNER JOIN (
            SELECT 
                port_code,
                vessel_ename,
                etd_berth,
                MAX(id) as max_id
            FROM ifa_d004
            WHERE port_code = ?
            GROUP BY port_code, vessel_ename, etd_berth
        ) latest
        ON d.id = latest.max_id
        ORDER BY d.etd_report
        """
        
        df = pd.read_sql_query(query, conn, params=(port_code,))
        conn.close()
        
        print(f"✓ 載入預計離港船舶 (D004): {len(df)} 筆（已去重）")
        
        return df
    
    except Exception as e:
        print(f"✗ 載入預計離港船舶時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


# ==================== 整合泊位與船舶資訊（修正版）====================

def get_berth_status(port_code='KEL', check_time=None, safety_buffer=DEFAULT_SAFETY_BUFFER):
    """
    整合泊位資訊和在泊船舶,計算剩餘空間
    🔥 修正: 
      1. 自動去重
      2. 加入安全距離計算
      3. 剩餘長度不會為負
    
    Args:
        port_code: 港口代碼
        check_time: 檢查時間 (None = 現在)
        safety_buffer: 安全緩衝距離（米）
    
    Returns:
        dict: 泊位狀態資訊
    """
    if check_time is None:
        check_time = datetime.now(pytz.timezone(TIMEZONE))
    
    # 載入泊位資訊
    wharf_info = load_wharf_info(port_code)
    
    if not wharf_info:
        return {
            'error': f'無法載入 {port_code} 港泊位資訊',
            'port_code': port_code,
            'berths': []
        }
    
    # 載入在泊船舶（已去重）
    vessels_df = load_berth_status(port_code)
    
    # 建立結果結構
    result = {
        'port_code': port_code,
        'port_name': list(wharf_info.values())[0]['port_name'] if wharf_info else '',
        'check_time': check_time,
        'safety_buffer': safety_buffer,
        'berths': [],
        'summary': {
            'total_berths': len(wharf_info),
            'available_berths': 0,
            'occupied_berths': 0,
            'total_vessels': 0,
            'avg_occupancy_rate': 0.0
        }
    }
    
    total_occupancy = 0.0
    
    # 處理每個泊位
    for wharf_code, info in wharf_info.items():
        # 找出停泊在該泊位的船舶（已去重）
        berth_vessels = vessels_df[vessels_df['wharf_code'] == wharf_code]
        
        # 🔥 計算占用長度（加入安全距離）
        occupied_length = 0.0
        vessels_list = []
        
        for _, vessel in berth_vessels.iterrows():
            loa = safe_float(vessel['loa_m'], 0.0)
            
            # 解析時間
            ata = parse_iso_datetime(vessel['ata_berth'])
            eta = parse_iso_datetime(vessel['eta_berth'])
            etd = parse_iso_datetime(vessel['etd_berth'])
            
            # 判斷船舶是否在指定時間占用泊位
            start_time = ata if ata else (eta if eta else check_time)
            end_time = etd if etd else (start_time + timedelta(hours=DEFAULT_BERTH_DURATION))
            
            # 檢查時間範圍
            if start_time <= check_time <= end_time:
                # 🔥 船長 + 前後安全距離
                occupied_length += loa + (safety_buffer * 2)
                
                vessel_cname = safe_str(vessel['vessel_cname'])
                vessel_ename = safe_str(vessel['vessel_ename'])
                vessel_name = vessel_cname if vessel_cname else vessel_ename
                
                vessels_list.append({
                    'vessel_name': vessel_name,
                    'vessel_cname': vessel_cname,
                    'vessel_ename': vessel_ename,
                    'vessel_no': safe_str(vessel['vessel_no']),
                    'call_sign': safe_str(vessel['call_sign']),
                    'imo': safe_str(vessel['visa_no']),
                    'loa_m': loa,
                    'gt': safe_int(vessel['gt']),
                    'ship_type': safe_str(vessel['ship_type']),
                    'ata_berth': ata,
                    'eta_berth': eta,
                    'etd_berth': etd,
                    'alongside_status': safe_str(vessel['alongside_status']),
                    'movement_status': safe_str(vessel['movement_status']),
                    'agent': safe_str(vessel['agent']),
                    'prev_port': safe_str(vessel['prev_port']),
                    'next_port': safe_str(vessel['next_port']),
                    'crawl_time': safe_str(vessel['crawled_at'])
                })
        
        # 🔥 如果有船，減去最後一艘船的尾部安全距離
        if len(vessels_list) > 0:
            occupied_length -= safety_buffer
        
        # 🔥 計算剩餘空間（不會為負）
        total_length = info['length_m']
        remaining_length = max(0, total_length - occupied_length)
        occupancy_rate = (occupied_length / total_length * 100) if total_length > 0 else 0
        
        total_occupancy += occupancy_rate
        
        # 判斷泊位狀態
        if len(vessels_list) == 0:
            result['summary']['available_berths'] += 1
        else:
            result['summary']['occupied_berths'] += 1
        
        result['summary']['total_vessels'] += len(vessels_list)
        
        # 加入泊位資訊
        result['berths'].append({
            'wharf_code': wharf_code,
            'wharf_name': info['wharf_name'],
            'wharf_name_en': info['wharf_name_en'],
            'total_length_m': total_length,
            'depth_m': info['depth_m'],
            'cargo_type': info['cargo_type'],
            'is_container': info['is_container'],
            'occupied_length_m': round(occupied_length, 1),
            'remaining_length_m': round(remaining_length, 1),
            'occupancy_rate': round(occupancy_rate, 1),
            'vessel_count': len(vessels_list),
            'vessels': vessels_list
        })
    
    # 計算平均占用率
    if result['summary']['total_berths'] > 0:
        result['summary']['avg_occupancy_rate'] = round(
            total_occupancy / result['summary']['total_berths'], 1
        )
    
    # 按泊位代碼排序
    result['berths'].sort(key=lambda x: x['wharf_code'])
    
    return result


# ==================== 顯示泊位狀態 ====================

def display_berth_status(port_code='KEL', show_details=True, safety_buffer=DEFAULT_SAFETY_BUFFER):
    """
    顯示泊位狀態（文字版）
    
    Args:
        port_code: 港口代碼
        show_details: 是否顯示詳細船舶資訊
        safety_buffer: 安全緩衝距離
    """
    status = get_berth_status(port_code, safety_buffer=safety_buffer)
    
    if 'error' in status:
        print(f"❌ {status['error']}")
        return
    
    print("="*80)
    print(f"🏢 {status['port_name']} ({status['port_code']}) 泊位狀態")
    print(f"⏰ 查詢時間: {status['check_time'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🛡️ 安全距離: {status['safety_buffer']}m")
    print("="*80)
    
    # 顯示摘要
    summary = status['summary']
    print(f"\n📊 摘要統計:")
    print(f"  總泊位數: {summary['total_berths']} 個")
    print(f"  可用泊位: {summary['available_berths']} 個 (🟢)")
    print(f"  占用泊位: {summary['occupied_berths']} 個 (🔴)")
    print(f"  停泊船舶: {summary['total_vessels']} 艘")
    print(f"  平均占用率: {summary['avg_occupancy_rate']:.1f}%")
    
    # 顯示各泊位詳情
    print(f"\n{'='*80}")
    print(f"📋 泊位詳情:")
    print(f"{'='*80}\n")
    
    for berth in status['berths']:
        # 泊位狀態圖示
        if berth['vessel_count'] == 0:
            status_icon = "🟢"
            status_text = "空閒"
        elif berth['remaining_length_m'] > 50:
            status_icon = "🟡"
            status_text = "部分占用"
        else:
            status_icon = "🔴"
            status_text = "滿載"
        
        # 貨櫃碼頭標記
        container_mark = "🚢" if berth['is_container'] else "📦"
        
        print(f"{status_icon} {container_mark} {berth['wharf_code']}: {berth['wharf_name']}")
        print(f"   長度: {berth['total_length_m']:.0f}m | 水深: {berth['depth_m']:.1f}m | 貨物: {berth['cargo_type']}")
        print(f"   占用: {berth['occupied_length_m']:.1f}m ({berth['occupancy_rate']:.1f}%) | "
              f"剩餘: {berth['remaining_length_m']:.1f}m | 狀態: {status_text}")
        
        # 顯示停泊船舶
        if berth['vessel_count'] > 0:
            print(f"   停泊船舶 ({berth['vessel_count']} 艘):")
            
            for i, vessel in enumerate(berth['vessels'], 1):
                vessel_name = vessel['vessel_name']
                loa = vessel['loa_m']
                gt = vessel['gt']
                
                # 時間資訊
                ata_str = vessel['ata_berth'].strftime('%m/%d %H:%M') if vessel['ata_berth'] else 'N/A'
                etd_str = vessel['etd_berth'].strftime('%m/%d %H:%M') if vessel['etd_berth'] else 'N/A'
                
                print(f"      {i}. {vessel_name} ({loa:.0f}m, {gt:,}GT)")
                
                if show_details:
                    print(f"         • 船型: {vessel['ship_type']}")
                    print(f"         • 呼號: {vessel['call_sign']} | IMO: {vessel['imo']}")
                    print(f"         • 到港: {ata_str} | 預計離港: {etd_str}")
                    print(f"         • 代理: {vessel['agent']}")
                    print(f"         • 前港: {vessel['prev_port']} → 次港: {vessel['next_port']}")
                    print(f"         • 狀態: {vessel['alongside_status']} / {vessel['movement_status']}")
        
        print()
    
    print("="*80)


# ==================== 匯出為 DataFrame ====================

def export_berth_status_to_df(port_code='KEL', safety_buffer=DEFAULT_SAFETY_BUFFER):
    """
    匯出泊位狀態為 DataFrame
    
    Returns:
        tuple: (berth_df, vessel_df)
    """
    status = get_berth_status(port_code, safety_buffer=safety_buffer)
    
    if 'error' in status:
        return pd.DataFrame(), pd.DataFrame()
    
    # 泊位資料
    berth_data = []
    for berth in status['berths']:
        berth_data.append({
            '港口代碼': status['port_code'],
            '港口名稱': status['port_name'],
            '泊位代碼': berth['wharf_code'],
            '泊位名稱': berth['wharf_name'],
            '英文名稱': berth['wharf_name_en'],
            '總長度(m)': berth['total_length_m'],
            '水深(m)': berth['depth_m'],
            '貨物類型': berth['cargo_type'],
            '是否貨櫃': berth['is_container'],
            '占用長度(m)': berth['occupied_length_m'],
            '剩餘長度(m)': berth['remaining_length_m'],
            '占用率(%)': berth['occupancy_rate'],
            '船舶數': berth['vessel_count'],
            '安全距離(m)': safety_buffer,
            '查詢時間': status['check_time']
        })
    
    berth_df = pd.DataFrame(berth_data)
    
    # 船舶資料
    vessel_data = []
    for berth in status['berths']:
        for vessel in berth['vessels']:
            vessel_data.append({
                '港口代碼': status['port_code'],
                '港口名稱': status['port_name'],
                '泊位代碼': berth['wharf_code'],
                '泊位名稱': berth['wharf_name'],
                '中文船名': vessel['vessel_cname'],
                '英文船名': vessel['vessel_ename'],
                '船舶編號': vessel['vessel_no'],
                '呼號': vessel['call_sign'],
                'IMO': vessel['imo'],
                '船長(m)': vessel['loa_m'],
                '總噸位': vessel['gt'],
                '船型': vessel['ship_type'],
                '實際到港': vessel['ata_berth'],
                '預計到港': vessel['eta_berth'],
                '預計離港': vessel['etd_berth'],
                '靠泊狀態': vessel['alongside_status'],
                '移動狀態': vessel['movement_status'],
                '代理': vessel['agent'],
                '前港': vessel['prev_port'],
                '次港': vessel['next_port'],
                '爬取時間': vessel['crawl_time'],
                '查詢時間': status['check_time']
            })
    
    vessel_df = pd.DataFrame(vessel_data)
    
    return berth_df, vessel_df


# ==================== 查詢特定泊位 ====================

def get_specific_berth_info(port_code, wharf_code, safety_buffer=DEFAULT_SAFETY_BUFFER):
    """
    查詢特定泊位的詳細資訊
    
    Args:
        port_code: 港口代碼
        wharf_code: 泊位代碼
        safety_buffer: 安全緩衝距離
    
    Returns:
        dict: 泊位詳細資訊
    """
    status = get_berth_status(port_code, safety_buffer=safety_buffer)
    
    if 'error' in status:
        return {'error': status['error']}
    
    for berth in status['berths']:
        if berth['wharf_code'] == wharf_code:
            return {
                'port_code': status['port_code'],
                'port_name': status['port_name'],
                'check_time': status['check_time'],
                'safety_buffer': safety_buffer,
                'berth': berth
            }
    
    return {'error': f'找不到泊位 {wharf_code}'}


# ==================== 搜尋船舶 ====================

def search_vessel_in_port(port_code, vessel_name, safety_buffer=DEFAULT_SAFETY_BUFFER):
    """
    在港口中搜尋船舶
    
    Args:
        port_code: 港口代碼
        vessel_name: 船名（中文或英文，支援模糊搜尋）
        safety_buffer: 安全緩衝距離
    
    Returns:
        list: 找到的船舶資訊
    """
    status = get_berth_status(port_code, safety_buffer=safety_buffer)
    
    if 'error' in status:
        return []
    
    results = []
    vessel_name_lower = vessel_name.lower()
    
    for berth in status['berths']:
        for vessel in berth['vessels']:
            # 模糊搜尋
            if (vessel_name_lower in vessel['vessel_name'].lower() or
                vessel_name_lower in vessel['vessel_ename'].lower() or
                vessel_name_lower in vessel['vessel_cname'].lower()):
                
                results.append({
                    'port_code': status['port_code'],
                    'port_name': status['port_name'],
                    'wharf_code': berth['wharf_code'],
                    'wharf_name': berth['wharf_name'],
                    'vessel': vessel
                })
    
    return results


# ==================== 建立泊位時間線 ====================

def build_berth_timeline(port_code='KEL', safety_buffer=DEFAULT_SAFETY_BUFFER):
    """
    建立泊位時間線（整合 D003, D004, D005）
    🔥 修正: 自動去重
    
    Args:
        port_code: 港口代碼
        safety_buffer: 安全緩衝距離
    
    Returns:
        dict: 泊位時間線
    """
    # 載入泊位資訊
    wharf_info = load_wharf_info(port_code)
    
    # 載入船舶資料（已去重）
    d005_df = load_berth_status(port_code)  # 在泊
    d003_df = load_eta_ships(port_code)     # 預計進港
    d004_df = load_etd_ships(port_code)     # 預計離港
    
    timeline = {
        'port_code': port_code,
        'safety_buffer': safety_buffer,
        'wharves': {},
        'vessels': []
    }
    
    # 初始化每個泊位的時間線
    for wharf_code, info in wharf_info.items():
        timeline['wharves'][wharf_code] = {
            'wharf_name': info['wharf_name'],
            'total_length_m': info['length_m'],
            'depth_m': info['depth_m'],
            'is_container': info['is_container'],
            'events': []
        }
    
    # 處理 D005 在泊船舶
    if not d005_df.empty:
        for _, row in d005_df.iterrows():
            wharf_code = safe_str(row.get('wharf_code', ''))
            if not wharf_code or wharf_code not in timeline['wharves']:
                continue
            
            ata = parse_iso_datetime(row.get('ata_berth'))
            etd = parse_iso_datetime(row.get('etd_berth'))
            
            if not ata:
                continue
            
            if not etd:
                etd = ata + timedelta(hours=DEFAULT_BERTH_DURATION)
            
            loa = safe_float(row.get('loa_m', 0))
            
            vessel_info = {
                'vessel_name': safe_str(row.get('vessel_cname', row.get('vessel_ename', ''))),
                'vessel_ename': safe_str(row.get('vessel_ename', '')),
                'loa_m': loa,
                'occupied_length_m': loa + (safety_buffer * 2),  # 🔥 加入安全距離
                'gt': safe_int(row.get('gt', 0)),
                'ship_type': safe_str(row.get('ship_type', '')),
                'wharf_code': wharf_code,
                'start_time': ata,
                'end_time': etd,
                'source': 'D005',
                'agent': safe_str(row.get('agent', '')),
                'prev_port': safe_str(row.get('prev_port', '')),
                'next_port': safe_str(row.get('next_port', ''))
            }
            
            timeline['wharves'][wharf_code]['events'].append(vessel_info)
            timeline['vessels'].append(vessel_info)
    
    # 處理 D003 預計進港
    if not d003_df.empty:
        for _, row in d003_df.iterrows():
            eta = parse_iso_datetime(row.get('eta_report'))
            
            if not eta:
                continue
            
            etd = eta + timedelta(hours=DEFAULT_BERTH_DURATION)
            loa = safe_float(row.get('loa_m', 0))
            
            vessel_info = {
                'vessel_name': safe_str(row.get('vessel_cname', row.get('vessel_ename', ''))),
                'vessel_ename': safe_str(row.get('vessel_ename', '')),
                'loa_m': loa,
                'occupied_length_m': loa + (safety_buffer * 2),  # 🔥 加入安全距離
                'gt': safe_int(row.get('gt', 0)),
                'ship_type': safe_str(row.get('ship_type', '')),
                'wharf_code': None,  # D003 沒有泊位資訊
                'start_time': eta,
                'end_time': etd,
                'source': 'D003',
                'agent': safe_str(row.get('agent', '')),
                'prev_port': safe_str(row.get('prev_port', '')),
                'next_port': safe_str(row.get('next_port', ''))
            }
            
            timeline['vessels'].append(vessel_info)
    
    # 排序事件
    for wharf_code in timeline['wharves']:
        timeline['wharves'][wharf_code]['events'].sort(key=lambda x: x['start_time'])
    
    timeline['vessels'].sort(key=lambda x: x['start_time'])
    
    return timeline


# ==================== 檢查當前可用性 ====================

def check_current_availability(timeline, check_time=None):
    """
    檢查當前泊位可用性
    🔥 修正: 適配新的 timeline 結構
    
    Args:
        timeline: 泊位時間線（來自 build_berth_timeline）
        check_time: 檢查時間（None = 現在）
    
    Returns:
        dict: 可用泊位資訊
    """
    if check_time is None:
        check_time = datetime.now(pytz.timezone(TIMEZONE))
    elif isinstance(check_time, str):
        check_time = parse_iso_datetime(check_time)
    
    available_berths = []
    safety_buffer = timeline.get('safety_buffer', DEFAULT_SAFETY_BUFFER)
    
    # 🔥 適配新的 timeline 結構
    wharves = timeline.get('wharves', {})
    
    for wharf_code, wharf_info in wharves.items():
        total_length = wharf_info.get('total_length_m', 0)
        occupied_length = 0.0
        vessel_count = 0
        
        # 計算當前占用長度
        for event in wharf_info.get('events', []):
            if event['start_time'] <= check_time <= event['end_time']:
                # 🔥 使用 occupied_length_m（已包含安全距離）
                occupied_length += event.get('occupied_length_m', event.get('loa_m', 0))
                vessel_count += 1
        
        # 🔥 如果有船，減去最後一艘船的尾部安全距離
        if vessel_count > 0:
            occupied_length -= safety_buffer
        
        # 🔥 剩餘長度不會為負
        remaining_length = max(0, total_length - occupied_length)
        
        if remaining_length > 0:
            available_berths.append({
                'wharf_code': wharf_code,
                'wharf_name': wharf_info.get('wharf_name', wharf_code),
                'total_length_m': total_length,
                'occupied_length_m': round(occupied_length, 1),
                'remaining_length_m': round(remaining_length, 1),
                'occupancy_rate': round((occupied_length / total_length * 100) if total_length > 0 else 0, 1),
                'vessel_count': vessel_count,
                'is_container': wharf_info.get('is_container', False),
                'depth_m': wharf_info.get('depth_m', 0)
            })
    
    return {
        'check_time': check_time,
        'safety_buffer': safety_buffer,
        'available_berths': available_berths,
        'total_available': len(available_berths)
    }


# ==================== 評估 ETA 泊位 ====================

def evaluate_berth_for_eta(
    timeline,
    eta_str: str,
    ship_length: float,
    ship_name: str = "萬海船舶",
    safety_buffer_each_side: float = None,
    competition_window_minutes: int = 60):
    """
    評估指定 ETA 時間點的泊位可用性
    🔥 修正: 適配新的 timeline 結構
    
    Args:
        timeline: 泊位時間線（來自 build_berth_timeline）
        eta_str: ETA 時間字串
        ship_length: 船長（米）
        ship_name: 船名
        safety_buffer_each_side: 單側安全距離（若為 None 則使用 timeline 中的值）
        competition_window_minutes: 競爭時間窗口（分鐘）
    
    Returns:
        Dict: 包含分析結果的字典
    """
    try:
        # ✅ 參數驗證
        if not timeline:
            return {
                'can_berth': False,
                'recommendation': '時間軸資料為空',
                'available_berths': [],
                'candidate_berths': [],
                'reasons': ['時間軸資料為空'],
                'eta': None,
                'ship_length': ship_length,
                'ship_name': ship_name,
                'required_length': 0
            }
        
        if ship_length <= 0:
            return {
                'can_berth': False,
                'recommendation': '船長參數無效',
                'available_berths': [],
                'candidate_berths': [],
                'reasons': ['船長必須大於 0'],
                'eta': None,
                'ship_length': ship_length,
                'ship_name': ship_name,
                'required_length': 0
            }
        
        # ✅ 解析 ETA
        eta = parse_iso_datetime(eta_str)
        if not eta:
            return {
                'can_berth': False,
                'recommendation': 'ETA 格式錯誤',
                'available_berths': [],
                'candidate_berths': [],
                'reasons': [f'無法解析 ETA: {eta_str}'],
                'eta': None,
                'ship_length': ship_length,
                'ship_name': ship_name,
                'required_length': 0
            }
        
        # 🔥 取得安全距離
        if safety_buffer_each_side is None:
            safety_buffer_each_side = timeline.get('safety_buffer', DEFAULT_SAFETY_BUFFER)
        
        # 計算所需長度
        required_length = ship_length + (2 * safety_buffer_each_side)
        
        # 分析邏輯
        available_berths = []
        candidate_berths = []
        reasons = []
        
        # 🔥 適配新的 timeline 結構
        wharves = timeline.get('wharves', {})
        
        if not wharves:
            return {
                'can_berth': False,
                'recommendation': '無泊位資料',
                'available_berths': [],
                'candidate_berths': [],
                'reasons': ['時間軸中沒有泊位資料'],
                'eta': eta,
                'ship_length': ship_length,
                'ship_name': ship_name,
                'required_length': required_length
            }
        
        # 遍歷所有泊位
        for berth_code, berth_info in wharves.items():
            total_length = berth_info.get('total_length_m', 0)
            
            if total_length < required_length:
                reasons.append(f"{berth_code}: 泊位長度不足 ({total_length:.0f}m < {required_length:.0f}m)")
                continue
            
            # 檢查占用情況
            occupied_length = 0
            occupied_vessels = []
            
            for vessel in berth_info.get('events', []):
                vessel_start = vessel.get('start_time')
                vessel_end = vessel.get('end_time')
                
                if not vessel_start or not vessel_end:
                    continue
                
                # 檢查時間重疊
                if vessel_start <= eta <= vessel_end:
                    # 使用 occupied_length_m（已包含安全距離）
                    vessel_occupied = vessel.get('occupied_length_m', vessel.get('loa_m', 0))
                    occupied_length += vessel_occupied
                    occupied_vessels.append(vessel)
            
            # 🔥 如果有船，減去最後一艘船的尾部安全距離
            if len(occupied_vessels) > 0:
                occupied_length -= safety_buffer_each_side
            
            remaining_length = max(0, total_length - occupied_length)
            
            if remaining_length >= required_length:
                berth_data = {
                    'berth_code': berth_code,
                    'berth_name': berth_info.get('wharf_name', berth_code),
                    'total_length_m': total_length,
                    'occupied_length_m': round(occupied_length, 1),
                    'remaining_length_m': round(remaining_length, 1),
                    'occupancy_rate': round((occupied_length / total_length * 100) if total_length > 0 else 0, 1),
                    'occupied_vessels': occupied_vessels,
                    'depth_m': berth_info.get('depth_m', 0),
                    'cargo_type': berth_info.get('cargo_type', ''),
                    'is_container': berth_info.get('is_container', False),
                    'suitability_score': round((remaining_length / required_length * 100), 1),
                    'reason': f'剩餘 {remaining_length:.0f}m，足夠容納 {required_length:.0f}m'
                }
                
                available_berths.append(berth_data)
                candidate_berths.append(berth_data)
            else:
                reasons.append(
                    f"{berth_code} ({berth_info.get('wharf_name', '')}): "
                    f"剩餘空間不足 ({remaining_length:.0f}m < {required_length:.0f}m)"
                )
        
        # 排序候選泊位（按適合度分數）
        candidate_berths.sort(key=lambda x: x['suitability_score'], reverse=True)
        
        # 生成建議
        can_berth = len(available_berths) > 0
        
        if can_berth:
            best_berth = candidate_berths[0]
            recommendation = (
                f"✅ 建議靠泊 {best_berth['berth_name']} ({best_berth['berth_code']})\n"
                f"   • 剩餘空間: {best_berth['remaining_length_m']:.0f}m\n"
                f"   • 占用率: {best_berth['occupancy_rate']:.1f}%\n"
                f"   • 水深: {best_berth['depth_m']:.1f}m"
            )
        else:
            recommendation = "❌ 所有泊位空間不足或已被占用"
            if reasons:
                recommendation += "\n原因:\n" + "\n".join(f"  • {r}" for r in reasons[:3])
        
        # ✅ 確保回傳完整的字典
        return {
            'can_berth': can_berth,
            'recommendation': recommendation,
            'available_berths': available_berths,
            'candidate_berths': candidate_berths,
            'recommended_berth': candidate_berths[0] if candidate_berths else None,
            'reasons': reasons,
            'eta': eta,
            'ship_length': ship_length,
            'ship_name': ship_name,
            'required_length': required_length,
            'safety_buffer': safety_buffer_each_side
        }
    
    except Exception as e:
        # ✅ 錯誤處理 - 回傳有效的字典而非 None
        import traceback
        error_msg = f"分析過程發生錯誤: {str(e)}"
        print(f"❌ {error_msg}")
        traceback.print_exc()
        
        return {
            'can_berth': False,
            'recommendation': error_msg,
            'available_berths': [],
            'candidate_berths': [],
            'recommended_berth': None,
            'reasons': [error_msg],
            'eta': None,
            'ship_length': ship_length,
            'ship_name': ship_name,
            'required_length': 0,
            'error': str(e)
        }


# ==================== 競爭分析 ====================

def analyze_competition(timeline, eta_str, ship_length, ship_name='Unknown',
                       competition_window_minutes=DEFAULT_COMPETITION_WINDOW):
    """
    分析進港競爭情況
    
    Args:
        timeline: 泊位時間線
        eta_str: ETA 時間字串
        ship_length: 船長
        ship_name: 船名
        competition_window_minutes: 競爭時間窗口
    
    Returns:
        dict: 競爭分析結果
    """
    eta = parse_iso_datetime(eta_str)
    
    if not eta:
        return {
            'competition_level': 'unknown',
            'competition_count': 0,
            'competing_vessels': [],
            'reason': '無效的 ETA 時間'
        }
    
    # 計算時間窗口
    window_start = eta - timedelta(minutes=competition_window_minutes)
    window_end = eta + timedelta(minutes=competition_window_minutes)
    
    # 找出競爭船舶
    competing_vessels = []
    
    for vessel in timeline['vessels']:
        vessel_eta = vessel['start_time']
        
        # 檢查是否在時間窗口內
        if window_start <= vessel_eta <= window_end:
            time_diff = (vessel_eta - eta).total_seconds() / 60
            
            competing_vessels.append({
                'vessel_name': vessel['vessel_name'],
                'vessel_ename': vessel['vessel_ename'],
                'eta': vessel_eta,
                'time_diff_minutes': time_diff,
                'loa_m': vessel['loa_m'],
                'gt': vessel['gt'],
                'berth': vessel['wharf_code'],
                'agent': vessel['agent'],
                'prev_port': vessel['prev_port'],
                'next_port': vessel['next_port']
            })
    
    # 排序（按時間差）
    competing_vessels.sort(key=lambda x: abs(x['time_diff_minutes']))
    
    # 判斷競爭程度
    competition_count = len(competing_vessels)
    
    if competition_count == 0:
        level = 'low'
        reason = '無競爭船舶，可按原定時間到港'
    elif competition_count <= 2:
        level = 'medium'
        reason = f'有 {competition_count} 艘船在相近時間進港，建議提前規劃'
    else:
        level = 'high'
        reason = f'有 {competition_count} 艘船在相近時間進港，建議加速或延後'
    
    # 建議是否加速
    should_accelerate = False
    recommended_eta = eta
    
    if competition_count > 0:
        earliest_competitor = min(competing_vessels, key=lambda x: x['eta'])
        
        if earliest_competitor['eta'] < eta:
            # 有船比我們早到，建議加速
            should_accelerate = True
            time_diff = (earliest_competitor['eta'] - eta).total_seconds() / 60
            recommended_eta = earliest_competitor['eta'] - timedelta(minutes=30)
    
    return {
        'competition_level': level,
        'competition_count': competition_count,
        'competing_vessels': competing_vessels,
        'reason': reason,
        'should_accelerate': should_accelerate,
        'recommended_eta': recommended_eta,
        'time_adjustment': recommended_eta - eta
    }


# ==================== 綜合分析 ====================

def comprehensive_berth_analysis(
    timeline,
    eta_str,
    ship_length,
    ship_name='Unknown',
    ship_type='貨櫃輪',
    competition_window_minutes=DEFAULT_COMPETITION_WINDOW,
    safety_buffer_each_side=None,
    use_ai=True):
    """
    綜合泊位分析（整合 AI 分析）
    
    Args:
        timeline: 泊位時間線
        eta_str: ETA 時間字串
        ship_length: 船長
        ship_name: 船名（✅ 確保傳遞）
        ship_type: 船舶類型
        competition_window_minutes: 競爭時間窗口
        safety_buffer_each_side: 單側安全距離
        use_ai: 是否使用 AI 分析
    
    Returns:
        dict: 完整分析結果
    """
    # ✅ 確保船名不為空
    if not ship_name or ship_name.strip() == '':
        ship_name = '未命名船舶'
    
    # 基本分析
    berth_eval = evaluate_berth_for_eta(
        timeline, 
        eta_str, 
        ship_length, 
        ship_name,  # ✅ 傳遞船名
        safety_buffer_each_side=safety_buffer_each_side or timeline.get('safety_buffer', DEFAULT_SAFETY_BUFFER),
        competition_window_minutes=competition_window_minutes
    )
    
    # 競爭分析
    competition = analyze_competition(
        timeline, 
        eta_str, 
        ship_length, 
        ship_name,  # ✅ 傳遞船名
        competition_window_minutes
    )
    
    result = {
        'ship_name': ship_name,  # ✅ 確保包含船名
        'ship_type': ship_type,
        'ship_length': ship_length,
        'eta': berth_eval.get('eta'),
        'can_berth': berth_eval.get('can_berth', False),
        'berth_evaluation': berth_eval,
        'competition_analysis': competition,
        'final_recommendation': _generate_final_recommendation(berth_eval, competition)
    }
    
    # ✅ AI 分析（如果啟用）
    if use_ai:
        try:
            from ai_analyzer import generate_berth_ai_analysis_from_db
            
            # 取得港口代碼
            port_code = timeline.get('port_code', 'KEL')
            
            # ✅ 呼叫 AI 分析（確保傳遞所有參數）
            ai_result = generate_berth_ai_analysis_from_db(
                port_name=_get_port_name(port_code),
                ship_type=ship_type,
                vessel_name=ship_name,  # ✅ 傳遞船名
                eta=berth_eval.get('eta'),
                ship_length=ship_length,
                safety_buffer_each_side=safety_buffer_each_side or timeline.get('safety_buffer', DEFAULT_SAFETY_BUFFER),
                competition_window_minutes=competition_window_minutes,
                analysis_mode='normal'
            )
            
            result['ai_analysis'] = ai_result
            
        except Exception as e:
            print(f"⚠️ AI 分析失敗: {e}")
            result['ai_analysis'] = {
                'success': False,
                'error': str(e)
            }
    
    return result

def _get_port_name(port_code):
    """取得港口中文名稱"""
    port_names = {
        'KEL': '基隆港',
        'KHH': '高雄港',
        'TXG': '台中港',
        'TPE': '台北港'
    }
    return port_names.get(port_code, port_code)

def _generate_final_recommendation(berth_eval, competition):
    """生成最終建議"""
    if not berth_eval.get('can_berth', False):
        return {
            'action': 'delay',
            'message': berth_eval.get('recommendation', '無法靠泊'),
            'priority': 'high'
        }
    
    if competition['competition_level'] == 'high':
        if competition['should_accelerate']:
            return {
                'action': 'accelerate',
                'message': f"建議加速，提前到 {competition['recommended_eta'].strftime('%Y-%m-%d %H:%M')}",
                'priority': 'high'
            }
        else:
            return {
                'action': 'monitor',
                'message': '競爭激烈，建議密切監控泊位狀況',
                'priority': 'medium'
            }
    
    # 🔥 修正: 使用 recommended_berth 而非 recommended_berth
    recommended_berth = berth_eval.get('recommended_berth')
    
    if recommended_berth:
        berth_name = recommended_berth.get('berth_name', '未指定')
        return {
            'action': 'proceed',
            'message': f"可按原定時間到港，建議靠泊 {berth_name}",
            'priority': 'low'
        }
    else:
        return {
            'action': 'proceed',
            'message': '可按原定時間到港',
            'priority': 'low'
        }


# ==================== 測試程式 ====================

if __name__ == "__main__":
    print("=== 測試泊位分析模組 v5.0 (修正版) ===\n")
    
    # 測試基隆港
    print("\n" + "="*80)
    print("測試 1: 顯示基隆港泊位狀態（含安全距離）")
    print("="*80)
    display_berth_status('KEL', show_details=True, safety_buffer=10)
    
    # 測試匯出
    print("\n" + "="*80)
    print("測試 2: 匯出為 DataFrame")
    print("="*80)
    berth_df, vessel_df = export_berth_status_to_df('KEL', safety_buffer=10)
    print(f"\n泊位資料: {len(berth_df)} 筆")
    if not berth_df.empty:
        print(berth_df[['泊位代碼', '泊位名稱', '總長度(m)', '占用長度(m)', '剩餘長度(m)', '占用率(%)']].head())
    
    print(f"\n船舶資料: {len(vessel_df)} 筆")
    if not vessel_df.empty:
        print(vessel_df[['泊位代碼', '中文船名', '船長(m)', '總噸位']].head())
    
    # 測試搜尋
    print("\n" + "="*80)
    print("測試 3: 搜尋船舶")
    print("="*80)
    results = search_vessel_in_port('KEL', '萬海')
    print(f"找到 {len(results)} 艘船")
    for r in results:
        print(f"  • {r['vessel']['vessel_name']} 停泊在 {r['wharf_name']}")
    
    # 測試時間線
    print("\n" + "="*80)
    print("測試 4: 建立泊位時間線")
    print("="*80)
    timeline = build_berth_timeline('KEL', safety_buffer=10)
    print(f"✓ 已建立時間線，共 {len(timeline['vessels'])} 艘船")
    print(f"✓ 安全距離: {timeline['safety_buffer']}m")
    
    # 測試可用性檢查
    print("\n" + "="*80)
    print("測試 5: 檢查當前可用性")
    print("="*80)
    availability = check_current_availability(timeline)
    print(f"✓ 當前可用泊位: {availability['total_available']} 個")
    for berth in availability['available_berths'][:3]:
        print(f"  • {berth['wharf_name']}: 剩餘 {berth['remaining_length_m']:.1f}m ({berth['occupancy_rate']:.1f}% 占用)")
    
    print("\n✓ 測試完成")
