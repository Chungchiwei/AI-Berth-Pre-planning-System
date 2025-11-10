"""
IFA 網站爬蟲模組 - 資料驗證與過濾優化版
版本: 2.6
新增: 
  - 修正第一欄位遺漏問題
  - 過濾不合理的 ETA 日期
  - 增強資料驗證
"""

import time
import re
import pandas as pd
import logging
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from modules.database import init_database, save_to_database, query_latest_data, is_cache_valid, get_cache_age,load_data_from_db

# ==================== 日誌設定 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# ==================== 配置 ====================

TARGET_SHIP_TYPE = "B11"
TARGET_SHIP_NAME = "貨櫃輪"

# 港口代碼映射表
PORT_CODE_MAPPING = {
    'KEL': '基隆港',
    'TPE': '臺北港',
    'TXG': '臺中港',
    'KHH': '高雄港'
}

# ==================== 🆕 新增：日期驗證函數 ====================

def is_valid_eta_date(date_str, min_year=2024, max_future_days=365):
    """
    驗證 ETA 日期是否合理
    
    Args:
        date_str: 日期字串
        min_year: 最小有效年份（預設 2024）
        max_future_days: 最大未來天數（預設 365 天）
    
    Returns:
        bool: 日期是否有效
    """
    if not date_str or date_str.strip() == "":
        return True  # 空值視為有效（由其他邏輯處理）
    
    try:
        # 移除時區資訊
        cleaned_str = re.sub(r'[+-]\d{2}:\d{2}$', '', date_str.strip())
        
        # 嘗試解析日期
        date_formats = [
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y/%m/%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y/%m/%d %H:%M',
            '%Y-%m-%d',
            '%Y/%m/%d'
        ]
        
        parsed_date = None
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(cleaned_str, fmt)
                break
            except ValueError:
                continue
        
        if not parsed_date:
            return True  # 無法解析，保留由其他邏輯處理
        
        # 檢查年份
        if parsed_date.year < min_year:
            print(f"    ⚠ 過期日期: {date_str} (年份 < {min_year})")
            return False
        
        # 檢查未來日期
        max_future_date = datetime.now() + timedelta(days=max_future_days)
        if parsed_date > max_future_date:
            print(f"    ⚠ 過於未來的日期: {date_str} (超過 {max_future_days} 天)")
            return False
        
        return True
        
    except Exception as e:
        print(f"    ⚠ 日期驗證失敗: {date_str} - {e}")
        return True  # 驗證失敗時保留資料


def validate_record_dates(record, date_fields=None):
    """
    驗證記錄中的所有日期欄位
    
    Args:
        record: 資料記錄字典
        date_fields: 要驗證的日期欄位列表（None = 驗證所有常見欄位）
    
    Returns:
        bool: 記錄是否有效
    """
    if date_fields is None:
        date_fields = [
            'eta_berth', 'ata_berth', 'eta_pilot', 'ata_pilot',
            'etd_berth', 'atd_berth', 'eta_report', 'etd_report'
        ]
    
    for field in date_fields:
        if field in record and record[field]:
            if not is_valid_eta_date(record[field]):
                return False
    
    return True


# ==================== 時間格式化函數 ====================

def format_datetime_string(datetime_str):
    """格式化日期時間字串"""
    if not datetime_str or datetime_str.strip() == "":
        return ""
    
    try:
        cleaned_str = re.sub(r'[+-]\d{2}:\d{2}$', '', datetime_str.strip())
        
        date_formats = [
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y/%m/%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y/%m/%d %H:%M',
        ]
        
        parsed_date = None
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(cleaned_str, fmt)
                break
            except ValueError:
                continue
        
        if parsed_date:
            return parsed_date.strftime('%Y/%m/%d %H:%M')
        else:
            return cleaned_str
    
    except Exception as e:
        return datetime_str


def format_datetime_columns_in_dict(record):
    """格式化字典中的日期時間欄位"""
    datetime_fields = [
        'eta_berth', 'ata_berth', 'eta_pilot', 'ata_pilot',
        'etd_berth', 'atd_berth', 'eta_report', 'etd_report',
        'vhf_report_time', 'anchor_time', 'inport_pass_time',
        'inport_5nm_time', 'outport_pass_time', 'captain_report_eta'
    ]
    
    for field in datetime_fields:
        if field in record and record[field]:
            record[field] = format_datetime_string(record[field])
    
    return record


# ==================== 工具函數 ====================

def extract_number(text):
    """從文字中提取數字"""
    if not text:
        return ""
    match = re.search(r'[\d,]+\.?\d*', text)
    if match:
        return match.group().replace(',', '')
    return text


def is_container_ship(ship_type):
    """判斷是否為貨櫃輪"""
    if not ship_type:
        return False
    
    ship_type_lower = str(ship_type).lower()
    keywords = ['貨櫃', 'container', 'b-11', 'b11']
    return any(keyword in ship_type_lower for keyword in keywords)


def check_wharf_container_capability(wharf_code, wharf_name):
    """判斷泊位是否能停靠貨櫃輪"""
    if not wharf_code or wharf_code == "UNKNOWN":
        return False
    
    wharf_code_upper = wharf_code.upper()
    
    # 基隆港貨櫃碼頭
    if wharf_code_upper.startswith('KEL'):
        match = re.search(r'KEL([EW])(\d+)', wharf_code_upper)
        if match:
            direction = match.group(1)
            number = int(match.group(2))
            
            if direction == 'E' and 1 <= number <= 12:
                return True
            if direction == 'W' and 16 <= number <= 24:
                return True
    
    # 臺中港貨櫃碼頭
    if wharf_code_upper.startswith('TXG'):
        match = re.search(r'TXG[A-Z]?(\d{2,3})', wharf_code_upper)
        if match:
            number = int(match.group(1))
            if 50 <= number <= 69:
                return True
    
    # 高雄港貨櫃碼頭
    if wharf_code_upper.startswith('KHH'):
        match = re.search(r'KHH[A-Z]?(\d{2,3})', wharf_code_upper)
        if match:
            number = int(match.group(1))
            if 70 <= number <= 79:
                return True
    
    # 臺北港貨櫃碼頭
    if wharf_code_upper.startswith('TPE'):
        match = re.search(r'TPE[A-Z]?(\d{2,3})', wharf_code_upper)
        if match:
            number = int(match.group(1))
            if 301 <= number <= 310:
                return True
    
    # 從泊位名稱判斷
    if wharf_name:
        wharf_name_lower = wharf_name.lower()
        container_keywords = ['貨櫃', 'container', 'ct', '櫃']
        if any(keyword in wharf_name_lower for keyword in container_keywords):
            return True
    
    return False


def clean_dataframe(df):
    """清理 DataFrame"""
    if df is None or df.empty:
        return pd.DataFrame()
    
    try:
        df = df.copy()
        
        for col in df.columns:
            if df[col].dtype == 'object':
                sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
                if sample is not None and not isinstance(sample, (str, int, float, bool, type(None))):
                    print(f"  ⚠ 移除非序列化欄位: {col} (type: {type(sample).__name__})")
                    df = df.drop(columns=[col])
        
        for col in df.columns:
            df[col] = df[col].astype(str)
        
        return df
    
    except Exception as e:
        print(f"  ✗ 清理 DataFrame 失敗: {e}")
        return pd.DataFrame()


def init_driver(headless=True, show_status=True):
    """
    設定 Chrome WebDriver（支援本地與雲端環境）
    
    Args:
        headless: 是否使用無頭模式
        show_status: 是否顯示初始化訊息
    
    Returns:
        webdriver.Chrome: WebDriver 實例
    """
    if show_status:
        logger.info("正在初始化 WebDriver...")
    
    options = Options()
    
    # ===== 基本設定 =====
    if headless:
        options.add_argument('--headless=new')
    
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-images')
    options.add_argument('--blink-settings=imagesEnabled=false')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument('--disable-infobars')
    
    # User Agent
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # 實驗性選項
    options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    # ===== 🔥 環境檢測 =====
    IS_CLOUD = os.getenv('STREAMLIT_SHARING_MODE') is not None
    
    if IS_CLOUD:
        # ===== Streamlit Cloud 環境 =====
        logger.info("🌐 偵測到 Streamlit Cloud 環境")
        
        options.binary_location = '/usr/bin/chromium-browser'
        options.add_argument('--single-process')
        options.add_argument('--disable-dev-shm-usage')  # 重要！避免記憶體問題
        
        try:
            driver = webdriver.Chrome(options=options)
            logger.info("✓ WebDriver 初始化成功（雲端模式）")
            return driver
        except Exception as e:
            logger.error(f"✗ 雲端 WebDriver 初始化失敗: {e}")
            raise
    
    else:
        # ===== 本地環境 =====
        logger.info("💻 偵測到本地環境")
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            logger.info("✓ WebDriver 初始化成功（本地模式）")
            return driver
        except Exception as e:
            logger.error(f"✗ 本地 WebDriver 初始化失敗: {e}")
            raise


# ==================== 港口選擇函數 ====================

def select_port_by_tab(driver, port_code, port_name, container_id="portRadio", max_attempts=3):
    """統一的港口選擇函數"""
    try:
        wait = WebDriverWait(driver, 10)
        
        for attempt in range(max_attempts):
            try:
                if attempt > 0:
                    print(f"  🔄 重試選擇港口 ({attempt + 1}/{max_attempts})...")
                else:
                    print(f"  🔄 選擇港口: {port_name} ({port_code})")
                
                try:
                    port_button = wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, f'#{container_id} button.btn-tab[name="{port_code}"]')
                        )
                    )
                    
                    if 'active' in port_button.get_attribute('class'):
                        print(f"  ✓ 港口 {port_name} 已經是當前選擇")
                        return True
                    
                    driver.execute_script(f"""
                        var buttons = document.querySelectorAll('#{container_id} button.btn-tab');
                        buttons.forEach(function(btn) {{
                            btn.classList.remove('active');
                        }});
                    """)
                    
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", port_button)
                    time.sleep(1.5)
                    
                    active_button = driver.find_element(By.CSS_SELECTOR, f'#{container_id} button.btn-tab.active')
                    active_port = active_button.get_attribute('name')
                    
                    if active_port == port_code:
                        print(f"  ✓ 已選擇港口: {port_name} ({port_code})")
                        return True
                    else:
                        print(f"  ⚠ 港口選擇失敗，當前選中: {active_port}")
                        time.sleep(1)
                        continue
                        
                except Exception as e:
                    if attempt == max_attempts - 1:
                        print(f"  ⚠ 方法 1 失敗: {e}")
                    time.sleep(1)
                
                try:
                    port_button = driver.find_element(
                        By.XPATH,
                        f'//div[@id="{container_id}"]//button[@class="btn-tab" and @name="{port_code}"]'
                    )
                    driver.execute_script("arguments[0].click();", port_button)
                    time.sleep(1.5)
                    
                    active_button = driver.find_element(By.CSS_SELECTOR, f'#{container_id} button.btn-tab.active')
                    if active_button.get_attribute('name') == port_code:
                        print(f"  ✓ 已選擇港口: {port_name} (方法2)")
                        return True
                    
                except Exception as e:
                    if attempt == max_attempts - 1:
                        print(f"  ⚠ 方法 2 失敗: {e}")
                
                time.sleep(1)
                
            except Exception as e:
                if attempt == max_attempts - 1:
                    print(f"  ⚠ 嘗試 {attempt + 1} 失敗: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(2)
        
        print(f"  ✗ 無法選擇港口: {port_name}")
        return False
        
    except Exception as e:
        print(f"  ✗ 選擇港口失敗: {e}")
        return False


# ==================== IFA_D005 爬取（修正版）====================

def parse_d005_table(driver, port_code, port_name):
    """
    ✅ 解析 IFA_D005 表格（修正第一欄位遺漏問題）
    """
    try:
        port_code = str(port_code)
        port_name = str(port_name)
        
        wait = WebDriverWait(driver, 15)
        
        try:
            wait.until(EC.presence_of_element_located((By.ID, "result")))
            time.sleep(1)
        except:
            print("  ⚠ 找不到 result 容器")
            return pd.DataFrame()
        
        try:
            result_table = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#result table.pagetable tbody"))
            )
        except Exception as e:
            print(f"  ⚠ 找不到表格: {e}")
            
            try:
                no_data = driver.find_element(By.XPATH, "//*[contains(text(), '查無資料') or contains(text(), '無資料')]")
                if no_data:
                    print("  ℹ 網頁顯示：查無資料")
                    return pd.DataFrame()
            except:
                pass
            
            return pd.DataFrame()
        
        # ✅ 修正：使用更穩定的方式獲取所有行
        rows = result_table.find_elements(By.TAG_NAME, "tr")
        
        if len(rows) == 0:
            print("  ⚠ 表格無資料")
            return pd.DataFrame()
        
        print(f"  找到 {len(rows)} 行資料")
        
        data_list = []
        valid_count = 0
        invalid_date_count = 0
        i = 0
        
        while i < len(rows) - 1:
            try:
                row1 = rows[i]
                row2 = rows[i + 1]
                
                # ✅ 確保完整獲取所有 td 元素
                cells1 = row1.find_elements(By.TAG_NAME, "td")
                cells2 = row2.find_elements(By.TAG_NAME, "td")
                
                # ✅ 調試輸出
                if i == 0:
                    print(f"  第一行 cells1 數量: {len(cells1)}")
                    print(f"  第一行 cells2 數量: {len(cells2)}")
                
                if len(cells1) < 12:
                    print(f"  ⚠ 第 {i} 行欄位不足 (cells1: {len(cells1)})")
                    i += 2
                    continue
                
                # ✅ 先取得所有文字值
                ship_type = cells1[5].text.strip()
                
                if not is_container_ship(ship_type):
                    i += 2
                    continue
                
                # ✅ 確保第一欄位正確讀取
                wharf_code = cells1[0].text.strip()
                wharf_name = cells2[0].text.strip() if len(cells2) > 0 else ""
                
                # ✅ 調試第一筆資料
                if i == 0:
                    print(f"  第一筆泊位代碼: '{wharf_code}'")
                    print(f"  第一筆泊位名稱: '{wharf_name}'")
                
                vessel_ename = cells1[6].text.strip()
                vessel_cname = cells2[5].text.strip() if len(cells2) > 5 else ""
                
                # 建立記錄
                record = {
                    'port_code': port_code,
                    'port_name': port_name,
                    'wharf_code': str(wharf_code) if wharf_code else "",
                    'wharf_name': str(wharf_name) if wharf_name else "",
                    'alongside_status': str(cells1[1].text.strip()),
                    'mooring_type': str(cells1[2].text.strip()),
                    'prev_wharf': str(cells1[3].text.strip()),
                    'vessel_no': str(cells1[4].text.strip()),
                    'ship_type': str(ship_type),
                    'vessel_ename': str(vessel_ename),
                    'visa_no': str(cells1[7].text.strip()),
                    'eta_berth': str(cells1[8].text.strip()),
                    'etd_berth': str(cells1[9].text.strip()),
                    'prev_port': str(cells1[10].text.strip()),
                    'isps_level': str(cells1[11].text.strip()),
                    
                    'movement_status': str(cells2[1].text.strip() if len(cells2) > 1 else ""),
                    'via_port': str(cells2[2].text.strip() if len(cells2) > 2 else ""),
                    'gt': str(extract_number(cells2[3].text.strip() if len(cells2) > 3 else "")),
                    'arrival_purpose': str(cells2[4].text.strip() if len(cells2) > 4 else ""),
                    'vessel_cname': str(vessel_cname),
                    'agent': str(cells2[6].text.strip() if len(cells2) > 6 else ""),
                    'ata_berth': str(cells2[7].text.strip() if len(cells2) > 7 else ""),
                    'eta_pilot': str(cells2[8].text.strip() if len(cells2) > 8 else ""),
                    'next_port': str(cells2[9].text.strip() if len(cells2) > 9 else ""),
                    'loa_m': str(extract_number(cells2[10].text.strip() if len(cells2) > 10 else ""))
                }
                
                # ✅ 驗證日期
                if not validate_record_dates(record):
                    invalid_date_count += 1
                    print(f"  ⚠ 過濾無效日期: {vessel_ename}")
                    i += 2
                    continue
                
                # 格式化時間
                record = format_datetime_columns_in_dict(record)
                
                data_list.append(record)
                valid_count += 1
                print(f"  ✓ 成功解析: {vessel_ename} ({ship_type}) @ {wharf_code}")
                
            except Exception as e:
                print(f"    ✗ 解析第 {i} 行失敗: {e}")
                import traceback
                print(f"       詳細錯誤: {traceback.format_exc()}")
            
            i += 2
        
        if invalid_date_count > 0:
            print(f"  ℹ 已過濾 {invalid_date_count} 筆無效日期資料")
        
        if len(data_list) > 0:
            df = pd.DataFrame(data_list)
            df = clean_dataframe(df)
            
            print(f"  ✓ 成功解析 {len(df)} 筆 {port_name} 貨櫃輪資料")
            
            return df
        else:
            print(f"  ⚠ 無 {port_name} 貨櫃輪資料")
            return pd.DataFrame()
        
    except Exception as e:
        print(f"  ✗ 解析 D005 表格失敗: {e}")
        import traceback
        print(traceback.format_exc())
        return pd.DataFrame()


def crawl_ifa_d005(driver, port_code, port_name, ship_type="B11"):
    """爬取 IFA_D005（船席現況）"""
    try:
        port_code = str(port_code)
        port_name = str(port_name)
        ship_type = str(ship_type) if ship_type else "B11"
        
        print(f"\n正在爬取 D005 - {port_name} ({TARGET_SHIP_NAME})...")
        
        url = "https://tpnet.twport.com.tw/IFAWeb/Function?_RedirUrl=/IFAWeb/Board/ShipWharfAllStatus"
        driver.get(url)
        
        wait = WebDriverWait(driver, 15)
        
        try:
            iframe = wait.until(EC.presence_of_element_located((By.ID, "ife")))
            driver.switch_to.frame("ife")
            time.sleep(2)
        except Exception as e:
            print(f"  ✗ 切換 iframe 失敗: {e}")
            return pd.DataFrame()
        
        if not select_port_by_tab(driver, port_code, port_name, container_id="portRadio"):
            print(f"  ✗ 無法選擇港口 {port_name}，終止爬取")
            driver.switch_to.default_content()
            return pd.DataFrame()
        
        try:
            ship_type_select = wait.until(EC.presence_of_element_located((By.ID, "shipType")))
            driver.execute_script(f"arguments[0].value = '{ship_type}';", ship_type_select)
            print(f"  ✓ 已設定船種: {TARGET_SHIP_NAME} ({ship_type})")
            time.sleep(0.5)
        except Exception as e:
            print(f"  ⚠ 設定船種失敗: {e}")
        
        try:
            checkboxes = driver.find_elements(By.CSS_SELECTOR, 'input[name="spSts"]')
            for checkbox in checkboxes:
                if not checkbox.is_selected():
                    driver.execute_script("arguments[0].click();", checkbox)
            print(f"  ✓ 已勾選所有靠泊狀態")
        except Exception as e:
            print(f"  ⚠ 勾選靠泊狀態失敗: {e}")
        
        try:
            search_btn = wait.until(EC.element_to_be_clickable((By.ID, "searchBtn")))
            driver.execute_script("arguments[0].click();", search_btn)
            print(f"  ✓ 已點擊查詢按鈕")
            time.sleep(3)
        except Exception as e:
            print(f"  ✗ 點擊查詢按鈕失敗: {e}")
            driver.switch_to.default_content()
            return pd.DataFrame()
        
        df = parse_d005_table(driver, port_code, port_name)
        
        try:
            driver.switch_to.default_content()
        except:
            pass
        
        if not df.empty:
            df['can_berth_container'] = df.apply(
                lambda row: check_wharf_container_capability(row['wharf_code'], row['wharf_name']),
                axis=1
            )
            
            total = len(df)
            can_berth = df['can_berth_container'].sum()
            
            print(f"\n✓ IFA_D005: {port_name}")
            print(f"  - 總計: {total} 筆貨櫃輪")
            print(f"  - 可停靠貨櫃碼頭: {can_berth} 筆")
            print(f"  - 其他碼頭: {total - can_berth} 筆")
        else:
            print(f"\n⚠ IFA_D005: {port_name} - 無貨櫃輪資料")
        
        return df
        
    except Exception as e:
        print(f"✗IFA_D005 爬取失敗: {e}")
        import traceback
        print(traceback.format_exc())
        try:
            driver.switch_to.default_content()
        except:
            pass
        return pd.DataFrame()


# ==================== IFA_D003/D004 爬取（套用相同修正）====================

def parse_d003_table(driver, port_code, port_name):
    """解析 IFA_D003 表格（含日期驗證）"""
    try:
        port_code = str(port_code)
        port_name = str(port_name)
        
        wait = WebDriverWait(driver, 15)
        
        try:
            result_div = wait.until(
                EC.presence_of_element_located((By.ID, "queryResult"))
            )
            print(f"  ✓ 找到 queryResult")
        except:
            print(f"  ✗ 找不到 queryResult")
            return pd.DataFrame()
        
        table = None
        table_selectors = [
            (By.ID, "tbResult"),
            (By.CSS_SELECTOR, "#queryResult table"),
            (By.CSS_SELECTOR, "table.table"),
            (By.TAG_NAME, "table")
        ]
        
        for selector_type, selector_value in table_selectors:
            try:
                if selector_type == By.TAG_NAME:
                    tables = result_div.find_elements(selector_type, selector_value)
                    if tables:
                        table = tables[0]
                        print(f"  ✓ 找到表格 (使用 {selector_value})")
                        break
                else:
                    table = result_div.find_element(selector_type, selector_value)
                    print(f"  ✓ 找到表格 (使用 {selector_value})")
                    break
            except:
                continue
        
        if not table:
            print(f"  ✗ 找不到表格")
            return pd.DataFrame()
        
        try:
            rows = table.find_elements(By.TAG_NAME, "tr")
            print(f"  總行數: {len(rows)}")
            
            if len(rows) < 4:
                print(f"  ⚠ 表格資料不足")
                return pd.DataFrame()
            
            data_list = []
            container_count = 0
            other_count = 0
            invalid_date_count = 0
            
            for i in range(3, len(rows), 2):
                if i + 1 >= len(rows):
                    break
                
                try:
                    row1 = rows[i]
                    cells1 = row1.find_elements(By.TAG_NAME, "td")
                    values1 = [cell.text.strip() for cell in cells1]
                    
                    row2 = rows[i + 1]
                    cells2 = row2.find_elements(By.TAG_NAME, "td")
                    values2 = [cell.text.strip() for cell in cells2]
                    
                    if len(values1) < 11 or len(values2) < 11:
                        continue
                    
                    ship_type = values1[1]
                    
                    if not is_container_ship(ship_type):
                        other_count += 1
                        continue
                    
                    container_count += 1
                    
                    record = {
                        'port_code': port_code,
                        'port_name': port_name,
                        'call_sign': str(values1[0]),
                        'ship_type': str(ship_type),
                        'vessel_ename': str(values1[2]),
                        'visa_no': str(values1[3]),
                        'eta_report': str(values1[4]),
                        'eta_berth': str(values1[5]),
                        'berth': str(values1[6]),
                        'prev_port': str(values1[7]),
                        'vhf_report_time': str(values1[8]),
                        'loa_m': str(extract_number(values1[9])),
                        'anchor_time': str(values1[10]),
                        
                        'imo': str(values2[0]),
                        'agent': str(values2[1]),
                        'vessel_cname': str(values2[2]),
                        'arrival_purpose': str(values2[3]),
                        'inport_pass_time': str(values2[4]),
                        'etd_berth': str(values2[5]),
                        'ata_berth': str(values2[6]),
                        'next_port': str(values2[7]),
                        'captain_report_eta': str(values2[8]),
                        'gt': str(extract_number(values2[9])),
                        'inport_5nm_time': str(values2[10])
                    }
                    
                    # ✅ 驗證日期
                    if not validate_record_dates(record):
                        invalid_date_count += 1
                        continue
                    
                    record = format_datetime_columns_in_dict(record)
                    data_list.append(record)
                    
                except Exception as e:
                    print(f"    ⚠ 解析行 {i} 失敗: {e}")
                    continue
            
            if invalid_date_count > 0:
                print(f"  ℹ 已過濾 {invalid_date_count} 筆無效日期資料")
            
            print(f"  ℹ 船種統計: 貨櫃輪 {container_count} 筆, 其他船種 {other_count} 筆")
            print(f"  ✓ 解析 {len(data_list)} 筆 {port_name} 貨櫃輪數據")
            
            if len(data_list) > 0:
                df = pd.DataFrame(data_list)
                df = clean_dataframe(df)
                return df
            else:
                return pd.DataFrame()
            
        except Exception as e:
            print(f"  ✗ 解析資料失敗: {e}")
            import traceback
            print(traceback.format_exc())
            return pd.DataFrame()
        
    except Exception as e:
        print(f"  ✗ 解析表格失敗: {e}")
        import traceback
        print(traceback.format_exc())
        return pd.DataFrame()


def parse_d004_table(driver, port_code, port_name):
    """解析 IFA_D004 表格（含日期驗證）"""
    try:
        port_code = str(port_code)
        port_name = str(port_name)
        
        wait = WebDriverWait(driver, 15)
        
        try:
            result_div = wait.until(
                EC.presence_of_element_located((By.ID, "queryResult"))
            )
            print(f"  ✓ 找到 queryResult")
        except:
            print(f"  ✗ 找不到 queryResult")
            return pd.DataFrame()
        
        table = None
        table_selectors = [
            (By.ID, "tbResult"),
            (By.CSS_SELECTOR, "#queryResult table"),
            (By.CSS_SELECTOR, "table.table"),
            (By.TAG_NAME, "table")
        ]
        
        for selector_type, selector_value in table_selectors:
            try:
                if selector_type == By.TAG_NAME:
                    tables = result_div.find_elements(selector_type, selector_value)
                    if tables:
                        table = tables[0]
                        print(f"  ✓ 找到表格 (使用 {selector_value})")
                        break
                else:
                    table = result_div.find_element(selector_type, selector_value)
                    print(f"  ✓ 找到表格 (使用 {selector_value})")
                    break
            except:
                continue
        
        if not table:
            print(f"  ✗ 找不到表格")
            return pd.DataFrame()
        
        try:
            rows = table.find_elements(By.TAG_NAME, "tr")
            print(f"  總行數: {len(rows)}")
            
            if len(rows) < 4:
                print(f"  ⚠ 表格資料不足")
                return pd.DataFrame()
            
            data_list = []
            container_count = 0
            other_count = 0
            invalid_date_count = 0
            
            for i in range(3, len(rows), 2):
                if i + 1 >= len(rows):
                    break
                
                try:
                    row1 = rows[i]
                    cells1 = row1.find_elements(By.TAG_NAME, "td")
                    values1 = [cell.text.strip() for cell in cells1]
                    
                    row2 = rows[i + 1]
                    cells2 = row2.find_elements(By.TAG_NAME, "td")
                    values2 = [cell.text.strip() for cell in cells2]
                    
                    if len(values1) < 9 or len(values2) < 8:
                        continue
                    
                    ship_type = values1[1]
                    
                    if not is_container_ship(ship_type):
                        other_count += 1
                        continue
                    
                    container_count += 1
                    
                    record = {
                        'port_code': port_code,
                        'port_name': port_name,
                        'call_sign': str(values1[0]),
                        'ship_type': str(ship_type),
                        'vessel_ename': str(values1[2]),
                        'visa_no': str(values1[3]),
                        'etd_report': str(values1[4]),
                        'etd_berth': str(values1[5]),
                        'berth': str(values1[6]),
                        'prev_port': str(values1[7]),
                        'isps_level': str(values1[8]),
                        
                        'imo': str(values2[0]),
                        'agent': str(values2[1]),
                        'vessel_cname': str(values2[2]),
                        'arrival_purpose': str(values2[3]),
                        'outport_pass_time': str(values2[4]),
                        'atd_berth': str(values2[5]),
                        'next_port': str(values2[6]),
                        'loa_m': str(extract_number(values2[7]))
                    }
                    
                    # ✅ 驗證日期
                    if not validate_record_dates(record, date_fields=['etd_berth', 'etd_report', 'atd_berth']):
                        invalid_date_count += 1
                        continue
                    
                    record = format_datetime_columns_in_dict(record)
                    data_list.append(record)
                    
                except Exception as e:
                    print(f"    ⚠ 解析行 {i} 失敗: {e}")
                    continue
            
            if invalid_date_count > 0:
                print(f"  ℹ 已過濾 {invalid_date_count} 筆無效日期資料")
            
            print(f"  ℹ 船種統計: 貨櫃輪 {container_count} 筆, 其他船種 {other_count} 筆")
            print(f"  ✓ 解析 {len(data_list)} 筆 {port_name} 貨櫃輪數據")
            
            if len(data_list) > 0:
                df = pd.DataFrame(data_list)
                df = clean_dataframe(df)
                return df
            else:
                return pd.DataFrame()
            
        except Exception as e:
            print(f"  ✗ 解析資料失敗: {e}")
            import traceback
            print(traceback.format_exc())
            return pd.DataFrame()
        
    except Exception as e:
        print(f"  ✗ 解析表格失敗: {e}")
        import traceback
        print(traceback.format_exc())
        return pd.DataFrame()


def crawl_ifa_d003(driver, port_code, port_name, ship_type="B11", max_retries=3):
    """爬取 IFA_D003（進港船舶）"""
    port_code = str(port_code)
    port_name = str(port_name)
    
    for attempt in range(max_retries):
        try:
            print(f"\n正在爬取 D003 - {port_name} ({TARGET_SHIP_NAME}) (嘗試 {attempt + 1}/{max_retries})...")
            
            url = "https://tpnet.twport.com.tw/IFAWeb/Function?_RedirUrl=/IFAWeb/Reports/InPortShipList"
            
            try:
                driver.get(url)
            except TimeoutException:
                print(f"  ⚠ 頁面載入超時")
                driver.execute_script("window.stop();")
                time.sleep(2)
            
            wait = WebDriverWait(driver, 15)
            
            try:
                iframe = wait.until(EC.presence_of_element_located((By.ID, "ife")))
                driver.switch_to.frame("ife")
            except TimeoutException:
                print(f"  ⚠ 找不到 iframe")
                driver.switch_to.default_content()
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                return pd.DataFrame()
            
            time.sleep(2)
            
            if not select_port_by_tab(driver, port_code, port_name, container_id="port"):
                print(f"  ⚠ 無法選擇港口，繼續使用預設港口")
            
            try:
                ship_type_select = wait.until(EC.presence_of_element_located((By.ID, "shipType")))
                driver.execute_script(f"arguments[0].value = '{TARGET_SHIP_TYPE}';", ship_type_select)
                print(f"  ✓ 已設定船種: {TARGET_SHIP_NAME} ({TARGET_SHIP_TYPE})")
            except:
                pass
            
            try:
                submit_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]')))
                driver.execute_script("arguments[0].click();", submit_btn)
                print(f"  ✓ 已點擊查詢按鈕")
            except Exception as e:
                print(f"  ⚠ 無法點擊查詢: {e}")
            
            time.sleep(3)
            
            df = parse_d003_table(driver, port_code, port_name)
            
            driver.switch_to.default_content()
            
            if not df.empty:
                print(f"\n✓ D003: {port_name} - {len(df)} 筆貨櫃輪")
            else:
                print(f"\n⚠ D003: {port_name} - 無貨櫃輪數據")
            
            return df
            
        except Exception as e:
            print(f"✗ 爬取失敗 (嘗試 {attempt + 1}/{max_retries}): {e}")
            try:
                driver.switch_to.default_content()
            except:
                pass
            
            if attempt < max_retries - 1:
                time.sleep(3)
    
    return pd.DataFrame()


def crawl_ifa_d004(driver, port_code, port_name, ship_type="B11", max_retries=3):
    """爬取 IFA_D004（出港船舶）"""
    port_code = str(port_code)
    port_name = str(port_name)
    
    for attempt in range(max_retries):
        try:
            print(f"\n正在爬取 D004 - {port_name} ({TARGET_SHIP_NAME}) (嘗試 {attempt + 1}/{max_retries})...")
            
            url = "https://tpnet.twport.com.tw/IFAWeb/Function?_RedirUrl=/IFAWeb/Reports/OutPortShipList"
            
            try:
                driver.get(url)
            except TimeoutException:
                print(f"  ⚠ 頁面載入超時")
                driver.execute_script("window.stop();")
                time.sleep(2)
            
            wait = WebDriverWait(driver, 15)
            
            try:
                iframe = wait.until(EC.presence_of_element_located((By.ID, "ife")))
                driver.switch_to.frame("ife")
            except TimeoutException:
                print(f"  ⚠ 找不到 iframe")
                driver.switch_to.default_content()
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                return pd.DataFrame()
            
            time.sleep(2)
            
            if not select_port_by_tab(driver, port_code, port_name, container_id="port"):
                print(f"  ⚠ 無法選擇港口，繼續使用預設港口")
            
            try:
                ship_type_select = wait.until(EC.presence_of_element_located((By.ID, "shipType")))
                driver.execute_script(f"arguments[0].value = '{TARGET_SHIP_TYPE}';", ship_type_select)
                print(f"  ✓ 已設定船種: {TARGET_SHIP_NAME} ({TARGET_SHIP_TYPE})")
            except:
                pass
            
            try:
                submit_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]')))
                driver.execute_script("arguments[0].click();", submit_btn)
                print(f"  ✓ 已點擊查詢按鈕")
            except Exception as e:
                print(f"  ⚠ 無法點擊查詢: {e}")
            
            time.sleep(3)
            
            df = parse_d004_table(driver, port_code, port_name)
            
            driver.switch_to.default_content()
            
            if not df.empty:
                print(f"\n✓ D004: {port_name} - {len(df)} 筆貨櫃輪")
            else:
                print(f"\n⚠ D004: {port_name} - 無貨櫃輪數據")
            
            return df
            
        except Exception as e:
            print(f"✗ 爬取失敗 (嘗試 {attempt + 1}/{max_retries}): {e}")
            try:
                driver.switch_to.default_content()
            except:
                pass
            
            if attempt < max_retries - 1:
                time.sleep(3)
    
    return pd.DataFrame()



# ==================== 整合爬取函數====================

def crawl_all_reports(
    port_code: str,
    port_name: str,
    ship_type: str = "B11",
    headless: bool = True,
    save_to_db: bool = True,
    use_cache: bool = True,
    cache_hours: float = 0.5):
    """
    爬取所有報表
    
    Returns:
        (d005_df, d003_df, d004_df, from_cache)
    """
    
    # ✅ 先檢查快取
    if use_cache:
        d005_valid = is_cache_valid('ifa_d005', port_code, cache_hours)
        d003_valid = is_cache_valid('ifa_d003', port_code, cache_hours)
        d004_valid = is_cache_valid('ifa_d004', port_code, cache_hours)
        
        if d005_valid and d003_valid and d004_valid:
            print(f"[INFO] 快取有效，從資料庫載入資料")
            
            # 從資料庫讀取
            d005_df = load_data_from_db('ifa_d005', port_code)
            d003_df = load_data_from_db('ifa_d003', port_code)
            d004_df = load_data_from_db('ifa_d004', port_code)
            
            return d005_df, d003_df, d004_df, True  # 👈 from_cache = True
    
    # ✅ 快取無效或停用，執行爬取
    print(f"[INFO] 開始爬取 {port_name} ({port_code}) 資料")
    # ==================== ✅ 優化快取檢查邏輯 ====================
    if use_cache:
        print(f"\n🔍 檢查資料庫快取（有效期限: {cache_hours * 60:.0f} 分鐘）...")
        try:
            # 檢查各報表快取狀態
            d005_valid = is_cache_valid('ifa_d005', port_code, cache_hours=cache_hours)
            d003_valid = is_cache_valid('ifa_d003', port_code, cache_hours=cache_hours)
            d004_valid = is_cache_valid('ifa_d004', port_code, cache_hours=cache_hours)
            
            # 獲取快取年齡
            d005_age = get_cache_age('ifa_d005', port_code)
            d003_age = get_cache_age('ifa_d003', port_code)
            d004_age = get_cache_age('ifa_d004', port_code)
            
            # 顯示快取狀態
            print(f"  📊 D005 快取: {'✓ 有效' if d005_valid else '✗ 過期'} "
                  f"({d005_age:.1f} 分鐘前)" if d005_age else "  📊 D005 快取: 無資料")
            print(f"  📊 D003 快取: {'✓ 有效' if d003_valid else '✗ 過期'} "
                  f"({d003_age:.1f} 分鐘前)" if d003_age else "  📊 D003 快取: 無資料")
            print(f"  📊 D004 快取: {'✓ 有效' if d004_valid else '✗ 過期'} "
                  f"({d004_age:.1f} 分鐘前)" if d004_age else "  📊 D004 快取: 無資料")
            
            # ✅ 只有當所有報表快取都有效時才使用快取
            if d005_valid and d003_valid and d004_valid:
                print(f"\n✅ 快取有效，直接讀取資料庫（節省爬取時間）")
                
                d005_df = query_latest_data('ifa_d005', port_code, ship_type)
                d003_df = query_latest_data('ifa_d003', port_code, ship_type)
                d004_df = query_latest_data('ifa_d004', port_code, ship_type)
                
                # 驗證資料完整性
                if not d005_df.empty and not d003_df.empty and not d004_df.empty:
                    print(f"  📦 D005: {len(d005_df)} 筆貨櫃輪資料")
                    print(f"  📦 D003: {len(d003_df)} 筆貨櫃輪資料")
                    print(f"  📦 D004: {len(d004_df)} 筆貨櫃輪資料")
                    print(f"  ⏱️  資料年齡: {min(d005_age, d003_age, d004_age):.1f} 分鐘")
                    return d005_df, d003_df, d004_df, True
                else:
                    print("  ⚠️  快取資料不完整，將重新爬取")
            else:
                # 顯示哪些報表需要更新
                expired_reports = []
                if not d005_valid:
                    expired_reports.append('D005')
                if not d003_valid:
                    expired_reports.append('D003')
                if not d004_valid:
                    expired_reports.append('D004')
                
                print(f"\n⏰ 快取已過期，需要更新: {', '.join(expired_reports)}")
                print(f"  將重新爬取最新資料...")
                
        except Exception as e:
            print(f"  ⚠️  快取檢查失敗: {e}")
            print(f"  將繼續進行爬取...")
    else:
        print("\n🔄 已停用快取，將直接爬取最新資料...")
    
    # ==================== 執行爬取 ====================
    print(f"\n🕷️  開始爬取 {port_name} ({port_code}) 最新資料...")
    print(f"  ⏱️  預計需要 30-60 秒...")
    
    driver = None
    try:
        # 初始化 WebDriver
        driver = init_driver(headless=headless, show_status=False)
        print("  ✓ WebDriver 初始化完成")
        
        # 爬取三個報表
        print(f"\n  📥 正在爬取 D005（船席現況）...")
        d005_df = crawl_ifa_d005(driver, port_code, port_name, ship_type)
        
        print(f"\n  📥 正在爬取 D003（進港船舶）...")
        d003_df = crawl_ifa_d003(driver, port_code, port_name, ship_type)
        
        print(f"\n  📥 正在爬取 D004（出港船舶）...")
        d004_df = crawl_ifa_d004(driver, port_code, port_name, ship_type)
        
        # 儲存到資料庫
        if save_to_db:
            print(f"\n💾 儲存到資料庫...")
            try:
                save_to_database(d005_df, 'ifa_d005', port_code)
                save_to_database(d003_df, 'ifa_d003', port_code)
                save_to_database(d004_df, 'ifa_d004', port_code)
                print("  ✓ 資料已儲存到資料庫")
                print(f"  ✓ 快取將在 {cache_hours * 60:.0f} 分鐘後過期")
            except Exception as e:
                print(f"  ⚠️  儲存失敗: {e}")
        
        # 顯示爬取結果摘要
        print(f"\n✅ 爬取完成！")
        print(f"  📦 D005: {len(d005_df)} 筆貨櫃輪資料")
        print(f"  📦 D003: {len(d003_df)} 筆貨櫃輪資料")
        print(f"  📦 D004: {len(d004_df)} 筆貨櫃輪資料")
        
        return d005_df, d003_df, d004_df, False
        
    except Exception as e:
        print(f"\n❌ 爬取失敗: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), False
        
    finally:
        if driver:
            try:
                driver.quit()
                print("  ✓ WebDriver 已關閉")
            except:
                pass



# ==================== 測試程式 ====================

if __name__ == "__main__":
    print("=== 測試爬蟲模組（修正版 v2.6）===\n")
    
    test_ports = [
        ("KEL", "基隆港"),
    ]
    
    for port_code, port_name in test_ports:
        d005_df, d003_df, d004_df, from_cache = crawl_all_reports(
            port_code, port_name, headless=False, use_cache=False
        )
        
        print(f"\n=== {port_name} 測試結果 ===")
        print(f"D005: {len(d005_df)} 筆貨櫃輪")
        print(f"D003: {len(d003_df)} 筆貨櫃輪")
        print(f"D004: {len(d004_df)} 筆貨櫃輪")
        
        if not d005_df.empty:
            print(f"\n{port_name} D005 前 5 筆:")
            print(d005_df[['wharf_code', 'vessel_ename', 'ship_type', 'eta_berth']].head(5))
        
        if not d003_df.empty:
            print(f"\n{port_name} D003 前 3 筆:")
            print(d003_df[['vessel_ename', 'ship_type', 'berth', 'eta_berth']].head(3))
        
        if not d004_df.empty:
            print(f"\n{port_name} D004 前 3 筆:")
            print(d004_df[['vessel_ename', 'ship_type', 'berth', 'etd_berth']].head(3))
        
        print("\n" + "="*60 + "\n")
        time.sleep(5)
