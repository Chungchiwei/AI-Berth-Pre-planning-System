"""
XML 輸出模組
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import pandas as pd
from pathlib import Path
import pytz
from config import EXPORT_DIR, XML_PREFIX_MAP, PORTS, TARGET_SHIP_NAME, TIMEZONE

def prettify_xml(elem):
    """美化 XML 輸出"""
    rough_string = ET.tostring(elem, encoding='utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')

def create_xml_element(parent, tag, text=""):
    """建立 XML 元素"""
    elem = ET.SubElement(parent, tag)
    if text:
        elem.text = str(text) if text else "[無資料]"
    else:
        elem.text = "[無資料]"
    return elem

def export_to_xml(df, report_type, port_code, out_dir=None, prefix=None):
    """
    將 DataFrame 導出為 XML 檔案
    
    Args:
        df: DataFrame 資料
        report_type: 報表類型 (D005/D003/D004)
        port_code: 港口代碼
        out_dir: 輸出目錄（預設使用 config 設定）
        prefix: 檔名前綴（預設使用 config 設定）
    
    Returns:
        str: XML 檔案路徑
    """
    if df.empty:
        raise ValueError(f"資料為空，無法導出 XML")
    
    # 設定輸出目錄與前綴
    if out_dir is None:
        out_dir = EXPORT_DIR
    else:
        out_dir = Path(out_dir)
        out_dir.mkdir(exist_ok=True)
    
    if prefix is None:
        prefix = XML_PREFIX_MAP.get(port_code, f"{port_code.lower()}_port_container")
    
    # 建立根節點
    port_name = PORTS.get(port_code, port_code)
    created_at = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
    
    root = ET.Element("Report")
    root.set("type", f"IFA_{report_type}")
    root.set("port", port_name)
    root.set("port_code", port_code)
    root.set("ship_type", TARGET_SHIP_NAME)
    root.set("created_at", created_at)
    root.set("total_ships", str(len(df)))
    
    # 添加船舶資料
    for idx, row in df.iterrows():
        ship_elem = ET.SubElement(root, "Ship")
        ship_elem.set("index", str(idx + 1))
        
        # 遍歷所有欄位
        for col in df.columns:
            value = row[col]
            
            # 處理空值
            if pd.isna(value) or value == "" or value is None:
                value = "[無資料]"
            else:
                value = str(value)
            
            # 建立子元素（欄位名稱轉換為合法的 XML tag）
            tag_name = col.replace("_", "-")
            create_xml_element(ship_elem, tag_name, value)
    
    # 美化並儲存
    xml_string = prettify_xml(root)
    
    # 生成檔名（含時間戳）
    timestamp = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%dT%H-%M-%S")
    filename = f"ifa_{report_type.lower()}_{prefix}_{timestamp}.xml"
    filepath = out_dir / filename
    
    # 寫入檔案
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(xml_string)
    
    print(f"✓ XML 已導出: {filepath}")
    return str(filepath)

def export_all_reports(d005_df, d003_df, d004_df, port_code, out_dir=None, prefix=None):
    """
    導出所有三個報表為 XML
    
    Returns:
        dict: {
            'D005': 檔案路徑,
            'D003': 檔案路徑,
            'D004': 檔案路徑,
            'success': bool,
            'errors': list
        }
    """
    results = {
        'D005': None,
        'D003': None,
        'D004': None,
        'success': True,
        'errors': []
    }
    
    # 導出 D005
    if not d005_df.empty:
        try:
            results['D005'] = export_to_xml(d005_df, 'D005', port_code, out_dir, prefix)
        except Exception as e:
            results['errors'].append(f"D005 導出失敗: {e}")
            results['success'] = False
    else:
        results['errors'].append("D005 資料為空")
    
    # 導出 D003
    if not d003_df.empty:
        try:
            results['D003'] = export_to_xml(d003_df, 'D003', port_code, out_dir, prefix)
        except Exception as e:
            results['errors'].append(f"D003 導出失敗: {e}")
            results['success'] = False
    else:
        results['errors'].append("D003 資料為空")
    
    # 導出 D004
    if not d004_df.empty:
        try:
            results['D004'] = export_to_xml(d004_df, 'D004', port_code, out_dir, prefix)
        except Exception as e:
            results['errors'].append(f"D004 導出失敗: {e}")
            results['success'] = False
    else:
        results['errors'].append("D004 資料為空")
    
    return results

def read_xml_report(filepath):
    """
    讀取 XML 報表並轉換為 DataFrame
    
    Args:
        filepath: XML 檔案路徑
    
    Returns:
        pd.DataFrame
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        data_list = []
        for ship in root.findall('Ship'):
            record = {}
            for child in ship:
                tag = child.tag.replace("-", "_")
                value = child.text
                if value == "[無資料]":
                    value = None
                record[tag] = value
            data_list.append(record)
        
        return pd.DataFrame(data_list)
    except Exception as e:
        print(f"✗ 讀取 XML 失敗: {e}")
        return pd.DataFrame()
