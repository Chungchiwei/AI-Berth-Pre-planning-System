"""
資料處理與正規化模組 - 欄位修正版
版本: 2.4
修正: 根據爬蟲模組的實際欄位調整處理邏輯
"""
import pandas as pd
from datetime import datetime
import pytz
import re
from config import TIMEZONE, STANDARD_COLUMNS, PORTS

def parse_datetime(dt_str):
    """解析時間字串為 ISO8601 格式（Asia/Taipei）"""
    if not dt_str or dt_str.strip() == "":
        return None
    
    try:
        # 常見格式
        formats = [
            '%Y-%m-%d %H:%M',
            '%Y/%m/%d %H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%Y/%m/%d %H:%M:%S',
            '%m/%d %H:%M',
            '%m-%d %H:%M'
        ]
        
        tz = pytz.timezone(TIMEZONE)
        
        for fmt in formats:
            try:
                dt = datetime.strptime(dt_str.strip(), fmt)
                # 如果沒有年份，使用當前年份
                if '%Y' not in fmt:
                    dt = dt.replace(year=datetime.now().year)
                dt = tz.localize(dt)
                return dt.isoformat()
            except:
                continue
        
        return dt_str  # 無法解析則返回原值
    except:
        return dt_str


def normalize_numeric(value):
    """正規化數值（去除單位與逗號）"""
    if not value or value == "" or pd.isna(value):
        return None
    
    try:
        # ✅ 如果已經是數字，直接返回
        if isinstance(value, (int, float)):
            return value
        
        # 提取數字
        match = re.search(r'[\d,]+\.?\d*', str(value))
        if match:
            num_str = match.group().replace(',', '')
            return float(num_str) if '.' in num_str else int(num_str)
        return None
    except:
        return None


def normalize_port_tables(df, report_type, port_code):
    """
    正規化港口資料表（保留所有欄位）
    
    Args:
        df: DataFrame
        report_type: 報表類型 ('D005', 'D003', 'D004')
        port_code: 港口代碼
    
    Returns:
        DataFrame: 正規化後的資料
    """
    if df is None or df.empty:
        return pd.DataFrame()
    
    # ✅ 複製 DataFrame 避免修改原始資料
    df = df.copy()
    
    # ✅ 確保 port_code 和 port_name 存在
    if 'port_code' not in df.columns or df['port_code'].isna().all():
        df['port_code'] = str(port_code)
    
    if 'port_name' not in df.columns or df['port_name'].isna().all():
        df['port_name'] = PORTS.get(str(port_code), str(port_code))
    
    # ✅ 時間欄位正規化（根據實際欄位）
    time_columns = {
        'D005': [
            'eta_berth',           # 預定靠泊時間
            'ata_berth',           # 實際靠泊時間
            'etd_berth',           # 預定離泊時間
            'eta_pilot'            # 預定引水時間
        ],
        'D003': [
            'eta_report',          # 預報進港時間
            'eta_berth',           # 預定靠泊時間
            'ata_berth',           # 靠泊時間
            'etd_berth',           # 預定離泊時間
            'vhf_report_time',     # VHF報到時間
            'anchor_time',         # 下錨時間
            'inport_pass_time',    # 進港通過港口時間
            'captain_report_eta',  # 船長報到ETA
            'inport_5nm_time'      # 進港通過5浬時間
        ],
        'D004': [
            'etd_report',          # 預報出港時間
            'etd_berth',           # 預定離泊時間
            'atd_berth',           # 離泊時間
            'outport_pass_time'    # 出港通過港口時間
        ]
    }
    
    if report_type in time_columns:
        for col in time_columns[report_type]:
            if col in df.columns:
                df[col] = df[col].apply(parse_datetime)
    
    # ✅ 數值欄位正規化
    numeric_columns = ['loa_m', 'gt']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = df[col].apply(normalize_numeric)
    
    # ✅ 確保船種欄位存在
    if 'ship_type' not in df.columns:
        df['ship_type'] = '貨櫃輪'
    
    # ✅ 移除完全空白的列
    df = df.dropna(how='all')
    
    # ✅ 移除重複列（根據關鍵欄位）
    key_columns = {
        'D005': ['vessel_ename', 'wharf_code', 'ata_berth'],
        'D003': ['vessel_ename', 'eta_berth', 'berth'],
        'D004': ['vessel_ename', 'etd_berth', 'berth']
    }
    
    if report_type in key_columns:
        # 找出存在的關鍵欄位
        existing_keys = [col for col in key_columns[report_type] if col in df.columns]
        if existing_keys:
            df = df.drop_duplicates(subset=existing_keys, keep='first')
    
    # ✅ 重設索引
    df = df.reset_index(drop=True)
    
    print(f"  [正規化] {report_type}: {len(df)} 筆資料，{len(df.columns)} 個欄位")
    
    return df


def merge_ship_data(d005_df, d003_df, d004_df):
    """
    合併三個報表的船舶資料
    
    Args:
        d005_df: D005 DataFrame（在泊船舶）
        d003_df: D003 DataFrame（預定進港）
        d004_df: D004 DataFrame（預定離港）
    
    Returns:
        dict: {
            'in_berth': 在泊船舶列表,
            'inbound': 進港船舶列表,
            'outbound': 出港船舶列表
        }
    """
    result = {
        'in_berth': [],
        'inbound': [],
        'outbound': []
    }
    
    # ✅ 處理在泊船舶 (D005)
    if not d005_df.empty:
        for _, row in d005_df.iterrows():
            # ✅ 安全取得數值
            loa_m = row.get('loa_m')
            if pd.isna(loa_m):
                loa_m = 0
            elif isinstance(loa_m, str):
                loa_m = normalize_numeric(loa_m) or 0
            
            gt = row.get('gt')
            if pd.isna(gt):
                gt = 0
            elif isinstance(gt, str):
                gt = normalize_numeric(gt) or 0
            
            result['in_berth'].append({
                'port_code': str(row.get('port_code', '')),
                'port_name': str(row.get('port_name', '')),
                'vessel_name': str(row.get('vessel_cname', '') or row.get('vessel_ename', '')),
                'vessel_ename': str(row.get('vessel_ename', '')),
                'vessel_cname': str(row.get('vessel_cname', '')),
                'wharf_code': str(row.get('wharf_code', '')),
                'wharf_name': str(row.get('wharf_name', '')),
                'alongside_status': str(row.get('alongside_status', '')),  # 現靠/接靠
                'movement_status': str(row.get('movement_status', '')),    # 動態
                'loa_m': loa_m,
                'gt': gt,
                'eta_berth': str(row.get('eta_berth', '')),
                'ata_berth': str(row.get('ata_berth', '')),
                'etd_berth': str(row.get('etd_berth', '')),
                'eta_pilot': str(row.get('eta_pilot', '')),
                'ship_type': str(row.get('ship_type', '貨櫃輪')),
                'agent': str(row.get('agent', '')),
                'prev_port': str(row.get('prev_port', '')),
                'next_port': str(row.get('next_port', '')),
                'can_berth_container': bool(row.get('can_berth_container', False))
            })
    
    # ✅ 處理進港船舶 (D003)
    if not d003_df.empty:
        for _, row in d003_df.iterrows():
            loa_m = row.get('loa_m')
            if pd.isna(loa_m):
                loa_m = 0
            elif isinstance(loa_m, str):
                loa_m = normalize_numeric(loa_m) or 0
            
            gt = row.get('gt')
            if pd.isna(gt):
                gt = 0
            elif isinstance(gt, str):
                gt = normalize_numeric(gt) or 0
            
            result['inbound'].append({
                'port_code': str(row.get('port_code', '')),
                'port_name': str(row.get('port_name', '')),
                'vessel_name': str(row.get('vessel_cname', '') or row.get('vessel_ename', '')),
                'vessel_ename': str(row.get('vessel_ename', '')),
                'vessel_cname': str(row.get('vessel_cname', '')),
                'call_sign': str(row.get('call_sign', '')),
                'imo': str(row.get('imo', '')),
                'berth': str(row.get('berth', '')),
                'loa_m': loa_m,
                'gt': gt,
                'eta_report': str(row.get('eta_report', '')),          # 預報進港時間
                'eta_berth': str(row.get('eta_berth', '')),            # 預定靠泊時間
                'ata_berth': str(row.get('ata_berth', '')),            # 靠泊時間
                'etd_berth': str(row.get('etd_berth', '')),            # 預定離泊時間
                'vhf_report_time': str(row.get('vhf_report_time', '')),  # VHF報到時間
                'anchor_time': str(row.get('anchor_time', '')),        # 下錨時間
                'ship_type': str(row.get('ship_type', '貨櫃輪')),
                'agent': str(row.get('agent', '')),
                'prev_port': str(row.get('prev_port', '')),
                'next_port': str(row.get('next_port', '')),
                'can_berth_container': bool(row.get('can_berth_container', False))
            })
    
    # ✅ 處理出港船舶 (D004)
    if not d004_df.empty:
        for _, row in d004_df.iterrows():
            loa_m = row.get('loa_m')
            if pd.isna(loa_m):
                loa_m = 0
            elif isinstance(loa_m, str):
                loa_m = normalize_numeric(loa_m) or 0
            
            result['outbound'].append({
                'port_code': str(row.get('port_code', '')),
                'port_name': str(row.get('port_name', '')),
                'vessel_name': str(row.get('vessel_cname', '') or row.get('vessel_ename', '')),
                'vessel_ename': str(row.get('vessel_ename', '')),
                'vessel_cname': str(row.get('vessel_cname', '')),
                'call_sign': str(row.get('call_sign', '')),
                'imo': str(row.get('imo', '')),
                'berth': str(row.get('berth', '')),
                'loa_m': loa_m,
                'etd_report': str(row.get('etd_report', '')),          # 預報出港時間
                'etd_berth': str(row.get('etd_berth', '')),            # 預定離泊時間
                'atd_berth': str(row.get('atd_berth', '')),            # 離泊時間
                'ship_type': str(row.get('ship_type', '貨櫃輪')),
                'agent': str(row.get('agent', '')),
                'prev_port': str(row.get('prev_port', '')),
                'next_port': str(row.get('next_port', '')),
                'isps_level': str(row.get('isps_level', '')),
                'can_berth_container': bool(row.get('can_berth_container', False))
            })
    
    return result


def validate_data_quality(df, report_type):
    """
    驗證資料品質
    
    Args:
        df: DataFrame
        report_type: 報表類型 ('D005', 'D003', 'D004')
    
    Returns:
        dict: 驗證結果
    """
    if df is None or df.empty:
        return {
            'is_valid': False,
            'missing_fields': ['DataFrame is empty'],
            'data_issues': ['無資料'],
            'total_records': 0
        }
    
    # ✅ 定義各報表的必要欄位（根據實際欄位）
    required_fields = {
        'D005': [
            'port_code',        # 港口代碼
            'port_name',        # 港口名稱      
            'vessel_ename',     # 船舶英文名
            'ship_type',        # 船種
            'wharf_code'        # 碼頭編號
        ],
        'D003': [
            'port_code',        # 港口代碼
            'port_name',        # 港口名稱
            'vessel_ename',     # 船舶英文名
            'ship_type',        # 船種
            'eta_berth'         # 預定靠泊時間
        ],
        'D004': [
            'port_code',        # 港口代碼
            'port_name',        # 港口名稱
            'vessel_ename',     # 船舶英文名
            'ship_type',        # 船種
            'etd_berth'         # 預定離泊時間
        ]
    }
    
    # 取得必要欄位
    fields = required_fields.get(report_type, [])
    
    # ✅ 檢查缺漏欄位
    missing_fields = []
    for field in fields:
        if field not in df.columns:
            missing_fields.append(field)
        else:
            # 檢查欄位是否全部為空
            is_all_empty = (
                df[field].isna().all() or 
                (df[field].astype(str).str.strip() == '').all()
            )
            if is_all_empty:
                missing_fields.append(f"{field} (全部為空)")
    
    # ✅ 檢查資料問題
    data_issues = []
    
    # 檢查 port_code
    if 'port_code' in df.columns:
        unique_ports = df['port_code'].dropna().unique()
        if len(unique_ports) == 0:
            data_issues.append('port_code 全部為空')
        elif len(unique_ports) > 1:
            data_issues.append(f'port_code 不一致: {list(unique_ports)}')
    
    # ✅ 檢查 wharf_code（D005 專用，允許部分為空）
    if report_type == 'D005' and 'wharf_code' in df.columns:
        empty_wharf = df['wharf_code'].isna() | (df['wharf_code'].astype(str).str.strip() == '')
        empty_count = empty_wharf.sum()
        if empty_count > 0:
            data_issues.append(f'wharf_code 有 {empty_count} 筆為空（共 {len(df)} 筆）')
    
    # ✅ 檢查 berth（D003/D004 專用）
    if report_type in ['D003', 'D004'] and 'berth' in df.columns:
        empty_berth = df['berth'].isna() | (df['berth'].astype(str).str.strip() == '')
        empty_count = empty_berth.sum()
        if empty_count > 0:
            data_issues.append(f'berth 有 {empty_count} 筆為空（共 {len(df)} 筆）')
    
    # ✅ 檢查船名（至少要有英文名或中文名）
    if 'vessel_ename' in df.columns:
        empty_ename = df['vessel_ename'].isna() | (df['vessel_ename'].astype(str).str.strip() == '')
        
        # 如果有中文名，檢查是否至少有一個不為空
        if 'vessel_cname' in df.columns:
            empty_cname = df['vessel_cname'].isna() | (df['vessel_cname'].astype(str).str.strip() == '')
            both_empty = empty_ename & empty_cname
            if both_empty.any():
                data_issues.append(f'有 {both_empty.sum()} 筆船名（中英文）都為空')
        else:
            if empty_ename.any():
                data_issues.append(f'有 {empty_ename.sum()} 筆英文船名為空')
    
    # ✅ 檢查時間欄位
    if report_type == 'D003' and 'eta_berth' in df.columns:
        empty_eta = df['eta_berth'].isna() | (df['eta_berth'].astype(str).str.strip() == '')
        if empty_eta.any():
            data_issues.append(f'有 {empty_eta.sum()} 筆 eta_berth 為空')
    
    if report_type == 'D004' and 'etd_berth' in df.columns:
        empty_etd = df['etd_berth'].isna() | (df['etd_berth'].astype(str).str.strip() == '')
        if empty_etd.any():
            data_issues.append(f'有 {empty_etd.sum()} 筆 etd_berth 為空')
    
    # ✅ 檢查船種是否為貨櫃輪
    if 'ship_type' in df.columns:
        non_container = ~df['ship_type'].astype(str).str.contains('貨櫃|container|b11|b-11', case=False, na=False)
        if non_container.any():
            data_issues.append(f'警告: 有 {non_container.sum()} 筆非貨櫃輪資料')
    
    # ✅ 檢查 can_berth_container 欄位
    if 'can_berth_container' in df.columns:
        can_berth_count = df['can_berth_container'].sum()
        cannot_berth_count = len(df) - can_berth_count
        data_issues.append(f'可停靠貨櫃碼頭: {can_berth_count} 筆, 其他碼頭: {cannot_berth_count} 筆')
    
    # ✅ 只有當「必要欄位完全缺失」時才判定為無效
    is_valid = len(missing_fields) == 0
    
    return {
        'is_valid': is_valid,
        'missing_fields': missing_fields,
        'data_issues': data_issues,
        'total_records': len(df)
    }


def get_data_summary(df, report_type):
    """
    取得資料摘要統計
    
    Args:
        df: DataFrame
        report_type: 報表類型
    
    Returns:
        dict: 摘要統計
    """
    if df is None or df.empty:
        return {
            'total': 0,
            'ports': [],
            'ship_types': {},
            'avg_loa': 0,
            'avg_gt': 0,
            'container_berth_count': 0
        }
    
    summary = {
        'total': len(df),
        'ports': [],
        'ship_types': {},
        'avg_loa': 0,
        'avg_gt': 0,
        'container_berth_count': 0
    }
    
    # 港口統計
    if 'port_name' in df.columns:
        summary['ports'] = df['port_name'].value_counts().to_dict()
    
    # 船種統計
    if 'ship_type' in df.columns:
        summary['ship_types'] = df['ship_type'].value_counts().to_dict()
    
    # 平均船長
    if 'loa_m' in df.columns:
        loa_values = df['loa_m'].apply(normalize_numeric).dropna()
        if len(loa_values) > 0:
            summary['avg_loa'] = round(loa_values.mean(), 2)
    
    # 平均總噸
    if 'gt' in df.columns:
        gt_values = df['gt'].apply(normalize_numeric).dropna()
        if len(gt_values) > 0:
            summary['avg_gt'] = round(gt_values.mean(), 2)
    
    # 可停靠貨櫃碼頭統計
    if 'can_berth_container' in df.columns:
        summary['container_berth_count'] = int(df['can_berth_container'].sum())
        summary['container_berth_ratio'] = round(
            summary['container_berth_count'] / len(df) * 100, 2
        ) if len(df) > 0 else 0
    
    return summary


def export_to_json(data, filename):
    """
    匯出資料為 JSON 格式
    
    Args:
        data: 要匯出的資料（dict 或 DataFrame）
        filename: 檔案名稱
    
    Returns:
        bool: 是否匯出成功
    """
    try:
        import json
        
        if isinstance(data, pd.DataFrame):
            data = data.to_dict(orient='records')
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 已匯出至 {filename}")
        return True
        
    except Exception as e:
        print(f"✗ 匯出失敗: {e}")
        return False


def export_to_excel(data, filename):
    """
    匯出資料為 Excel 格式
    
    Args:
        data: 要匯出的資料（dict 或 DataFrame）
        filename: 檔案名稱
    
    Returns:
        bool: 是否匯出成功
    """
    try:
        if isinstance(data, dict):
            # 如果是 dict，假設是 merge_ship_data 的結果
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                for sheet_name, records in data.items():
                    if records:
                        df = pd.DataFrame(records)
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
        elif isinstance(data, pd.DataFrame):
            data.to_excel(filename, index=False)
        else:
            print(f"✗ 不支援的資料格式: {type(data)}")
            return False
        
        print(f"✓ 已匯出至 {filename}")
        return True
        
    except Exception as e:
        print(f"✗ 匯出失敗: {e}")
        return False


# ==================== 測試程式 ====================

if __name__ == "__main__":
    print("=== 測試資料處理模組（欄位修正版 v2.4）===\n")
    
    # 測試時間解析
    print("1. 測試時間解析:")
    test_times = [
        "2025-11-05 14:30",
        "11/05 14:30",
        "2025/11/05 14:30:00",
        ""
    ]
    for t in test_times:
        result = parse_datetime(t)
        print(f"  {t:20s} -> {result}")
    
    # 測試數值正規化
    print("\n2. 測試數值正規化:")
    test_values = [
        "300.5",
        "1,234",
        "150 M",
        150,
        ""
    ]
    for v in test_values:
        result = normalize_numeric(v)
        print(f"  {str(v):20s} -> {result}")
    
    print("\n✓ 測試完成")
