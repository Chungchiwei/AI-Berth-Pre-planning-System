"""
AI 船期泊位管理系統 - Streamlit 主程式（萬海航運風格版 + 欄位中文化）
Version: 2.3 - 修正版（配合 berth_analysis v3.1）
"""
import streamlit as st
from modules.driver_manager import init_driver, check_driver_status
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time
from pathlib import Path
import os

# ==================== 導入自定義模組 ====================

from config import (
    APP_TITLE, APP_VERSION, PORTS, TARGET_SHIP_NAME,
    DB_PATH, DISCLAIMER, TIMEZONE, CACHE_TTL_MINUTES,
    DEFAULT_SAFETY_BUFFER, DEFAULT_COMPETITION_WINDOW, DEFAULT_BERTH_DURATION
)

from modules.database import (
    init_database, save_to_database, query_latest_data, 
    is_cache_valid, get_cache_age,load_data_from_db
)

from modules.selenium_crawler import crawl_all_reports

from modules.data_processor import (
    normalize_port_tables, merge_ship_data, validate_data_quality
)

from modules.xml_exporter import export_all_reports

# ✅ 確認從 modules.berth_analyzer 匯入
from modules.berth_analyzer import (
    build_berth_timeline,
    check_current_availability,
    evaluate_berth_for_eta,
    analyze_competition,
    comprehensive_berth_analysis,
    parse_iso_datetime,
    get_berth_status,
    display_berth_status,
    search_vessel_in_port,
    get_specific_berth_info
)

from modules.visualization import (
    create_berth_gantt_chart,
    create_berth_capacity_chart,      
    create_competition_chart,
    create_ship_length_distribution,
    create_port_summary_dashboard     
)

from modules.ai_analyzer import (
    generate_berth_ai_analysis, format_ai_analysis
)

IS_CLOUD = os.getenv('STREAMLIT_SHARING_MODE') is not None
if IS_CLOUD:
    st.sidebar.info("🌐 運行於 Streamlit Cloud")
else:
    st.sidebar.info("💻 運行於本地環境")

# 初始化資料庫
from modules.database import init_database, migrate_database

try:
    init_database()
    migrate_database()
    st.sidebar.success("✓ 資料庫初始化完成")
except Exception as e:
    st.sidebar.error(f"✗ 資料庫初始化失敗: {e}")
# ==================== 🆕 欄位中文化配置 ====================

# D005 欄位映射（船席現況）
D005_COLUMN_MAPPING = {
    'port_name': '港口名稱',
    'wharf_code': '碼頭編號',
    'wharf_name': '碼頭名稱',
    'vessel_ename': '英文船名',
    'vessel_cname': '中文船名',
    'ship_type': '船舶類型',
    'alongside_status': '狀態(現靠/接靠)',
    'movement_status': '進出港動態',
    'eta_berth': '預計靠泊時間(ETB)',
    'ata_berth': '實際靠泊時間(ATB)',
    'etd_berth': '預定離泊時間(ETD)',
    'eta_pilot': '計畫引水時間',
    'prev_port': '上一港口',
    'next_port': '預計下一港',
    'loa_m': '船長(m)',
    'gt': '船舶總重(GT)',
    'agent': '碼頭代理行',
    'arrival_purpose': '靠泊到港目的',
    'mooring_type': '靠泊方式',
    'visa_no': '簽證編號',
    'isps_level': '保全等級',
    'can_berth_container': '可停靠貨櫃碼頭'
}

# D003 欄位映射（進港船舶）
D003_COLUMN_MAPPING = {
    'port_name': '港口名稱',
    'vessel_ename': '英文船名',
    'vessel_cname': '中文船名',
    'ship_type': '船舶類型',
    'call_sign': '船舶呼號',
    'imo': 'IMO Number',
    'eta_report': '預計到達時間(ETA)',
    'eta_berth': '預計靠泊時間(ETB)',
    'ata_berth': '實際靠泊時間(ATA)',
    'etd_berth': '預計離舶時間(ETD)',
    'berth': '靠泊碼頭',
    'prev_port': '上一港口',
    'next_port': '預計下一港',
    'loa_m': '船長(m)',
    'gt': '船舶總重(GT)',
    'agent': '碼頭代理行',
    'arrival_purpose': '到港目的',
    'visa_no': '簽證編號',
    'vhf_report_time': 'VHF報到時間',
    'anchor_time': '下錨時間',
    'captain_report_eta': '船長報到ETA時間'
}

# D004 欄位映射（出港船舶）
D004_COLUMN_MAPPING = {
    'port_name': '港口名稱',
    'vessel_ename': '英文船名',
    'vessel_cname': '中文船名',
    'ship_type': '船舶類型',
    'call_sign': '船舶呼號',
    'imo': 'IMO Number',
    'etd_report': '預計出港時間(ETD)',
    'etd_berth': '預計離泊時間(ETD)',
    'atd_berth': '實際離泊時間(ATD)',
    'berth': '靠泊碼頭',
    'prev_port': '上一港口',
    'next_port': '預計下一港',
    'loa_m': '船長(m)',
    'gt': '船舶總重(GT)',
    'agent': '碼頭代理行',
    'arrival_purpose': '到港目的',
    'visa_no': '簽證編號',
    'isps_level': '保全等級'
}

# 🆕 顯示欄位配置（按順序）
D005_DISPLAY_COLUMNS = [
    '港口名稱', '碼頭名稱', '碼頭編號','英文船名', '中文船名',
    '預計靠泊時間(ETB)', '實際靠泊時間(ATB)', '預定離泊時間(ETD)', '計畫引水時間',
    '上一港口', '預計下一港', '船長(m)', '船舶總重(GT)', '碼頭代理行'
]

D003_DISPLAY_COLUMNS = [
    '港口名稱', '靠泊碼頭','英文船名', '中文船名', 'IMO Number',
    '預計到達時間(ETA)', '預計靠泊時間(ETB)', '實際靠泊時間(ATA)', '預計離舶時間(ETD)',
    '上一港口', '預計下一港', '船長(m)', '碼頭代理行'
]

D004_DISPLAY_COLUMNS = [
    '港口名稱', '靠泊碼頭','英文船名', '中文船名', 'IMO Number',
    '預計出港時間(ETD)', '預計離泊時間(ETD)', '實際離泊時間(ATD)',
    '上一港口', '預計下一港', '船長(m)', '碼頭代理行'
]


#==================== Widget Keys 常數 ====================
class WidgetKeys:
    # 即時船席
    REALTIME_VESSEL_NAME = "realtime_input_vessel_name"
    REALTIME_SHIP_LENGTH = "realtime_input_ship_length"
    REALTIME_ETA_DATE = "realtime_input_eta_date"
    REALTIME_ETA_TIME = "realtime_input_eta_time"
    REALTIME_ANALYZE_BTN = "realtime_analyze_berth_button"
    
    # 泊位分析
    ANALYSIS_VESSEL_NAME = "analysis_input_vessel_name"
    ANALYSIS_SHIP_LENGTH = "analysis_input_ship_length"
    ANALYSIS_ETA_DATE = "analysis_input_eta_date"
    ANALYSIS_ETA_TIME = "analysis_input_eta_time"
    ANALYSIS_ANALYZE_BTN = "analysis_analyze_berth_button"

# 使用時
# ==================== 🆕 格式化函數 ====================

def format_dataframe_for_display(df, column_mapping, display_columns):
    """
    格式化 DataFrame 用於顯示
    
    Args:
        df: 原始 DataFrame
        column_mapping: 欄位映射字典
        display_columns: 要顯示的欄位列表（中文）
    
    Returns:
        格式化後的 DataFrame
    """
    if df.empty:
        return pd.DataFrame()
    
    # 複製資料
    display_df = df.copy()
    
    # 重新命名欄位為中文
    display_df = display_df.rename(columns=column_mapping)
    
    # 只保留要顯示的欄位（如果存在）
    available_columns = [col for col in display_columns if col in display_df.columns]
    display_df = display_df[available_columns]
    
    # 處理空值
    display_df = display_df.fillna('--')
    
    # 格式化數值欄位
    if '船長(m)' in display_df.columns:
        display_df['船長(m)'] = display_df['船長(m)'].apply(
            lambda x: f"{float(x):.1f}" if str(x) not in ['--', '', 'nan'] else '--'
        )
    
    if '船舶總重(GT)' in display_df.columns:
        display_df['船舶總重(GT)'] = display_df['船舶總重(GT)'].apply(
            lambda x: f"{int(float(x)):,}" if str(x) not in ['--', '', 'nan'] else '--'
        )
    
    return display_df

# ==================== 頁面配置 ====================
st.set_page_config(
    page_title=f"{APP_TITLE} - 萬海航運",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
:root {
  --wh-primary: #004B91;
  --wh-primary-dark: #003870;
  --wh-secondary: #E60012;
  --wh-accent: #0074C2;
  --wh-bg-main: linear-gradient(180deg, #002E5C 0%, #004B91 100%);
  --wh-bg-card: #0A2C57;
  --wh-border: #0E3A6A;
  --wh-text-light: #FFFFFF;
  --wh-text-muted: #B3C4DA;
  --wh-radius: 10px;
  --wh-shadow: 0 4px 10px rgba(0,0,0,0.4);
}

/* 背景與全域文字 */
html, body, [data-testid="stAppViewContainer"], .stApp {
  background: var(--wh-bg-main) !important;
  color: var(--wh-text-light) !important;
  font-family: "Noto Sans TC", "Source Han Sans", sans-serif;
}

/* 側邊欄 */
[data-testid="stSidebar"] {
  background: var(--wh-primary-dark) !important;
  border-right: 1px solid rgba(255,255,255,0.1);
}
[data-testid="stSidebar"] * {
  color: var(--wh-text-light) !important;
}

/* 主標題 */
h1, h2, h3 {
  color: #FFFFFF !important;
  text-shadow: 0 2px 4px rgba(0,0,0,0.4);
}

/* 卡片 */
.wh-card {
  background: var(--wh-bg-card);
  border: 1px solid var(--wh-border);
  border-radius: var(--wh-radius);
  padding: 1.5rem;
  box-shadow: var(--wh-shadow);
  margin: 1rem 0;
  transition: all 0.3s ease;
}
.wh-card:hover {
  border-color: var(--wh-secondary);
  box-shadow: 0 4px 15px rgba(230,0,18,0.4);
}

/* 按鈕 */
.stButton>button {
  background: var(--wh-primary-dark);
  color: white;
  border-radius: var(--wh-radius);
  border: 1px solid var(--wh-secondary);
  padding: 0.6rem 1.2rem;
  font-weight: 600;
  transition: all 0.3s ease;
}
.stButton>button:hover {
  background: var(--wh-secondary);
  transform: translateY(-2px);
}

/* 表格 */
.dataframe {
  background: #0B305F;
  border-radius: var(--wh-radius);
  color: var(--wh-text-light);
  border: 1px solid var(--wh-border);
}
.dataframe thead tr th {
  background: #003870;
  color: #FFFFFF;
  border-bottom: 2px solid var(--wh-secondary);
}
.dataframe tbody tr:hover td {
  background: #0F417A !important;
}

/* 輸入框 */
input, select, textarea {
  background: #0E3A6A !important;
  color: white !important;
  border-radius: 6px !important;
  border: 1px solid #1C5EA5 !important;
}
input:focus, select:focus {
  border-color: var(--wh-secondary) !important;
  box-shadow: 0 0 0 2px rgba(230,0,18,0.4);
}

/* 頁尾 */
.wh-footer {
  background: #003870;
  text-align: center;
  padding: 2rem;
  margin-top: 2rem;
  border-top: 2px solid var(--wh-secondary);
  color: var(--wh-text-light);
}
</style>
""", unsafe_allow_html=True)
# ==================== 初始化 ====================
@st.cache_resource
def initialize_system():
    """初始化系統（只執行一次）"""
    init_database()
    return True

initialize_system()

# ==================== 🆕 Session State 初始化 ====================
if 'selected_port' not in st.session_state:
    st.session_state.selected_port = 'KEL'

if 'crawl_data' not in st.session_state:
    st.session_state.crawl_data = {
        'D005': pd.DataFrame(),
        'D003': pd.DataFrame(),
        'D004': pd.DataFrame(),
        'port_code': None,
        'timestamp': None,
        'from_cache': False
    }

if 'timeline' not in st.session_state:
    st.session_state.timeline = None

if 'evaluation_result' not in st.session_state:
    st.session_state.evaluation_result = None

if 'ai_analysis' not in st.session_state:
    st.session_state.ai_analysis = None
if 'default_eta_time' not in st.session_state:
    st.session_state.default_eta_time = datetime.now(pytz.timezone(TIMEZONE)).time()
    
# ==================== 輔助函數 ====================
def safe_format_datetime(dt_value, default="[未提供]"):
    """安全格式化日期時間"""
    if dt_value is None:
        return default
    
    try:
        if isinstance(dt_value, datetime):
            return dt_value.strftime('%Y-%m-%d %H:%M')
        elif isinstance(dt_value, str):
            parsed = parse_iso_datetime(dt_value)
            if parsed:
                return parsed.strftime('%Y-%m-%d %H:%M')
            return dt_value
        else:
            return str(dt_value)
    except Exception:
        return default

# ==================== 側邊欄（統一港口選擇）====================
with st.sidebar:
    st.markdown("### ⚙️ 系統設定")
    
    # ✅ 唯一的港口選擇器
    st.session_state.selected_port = st.selectbox(
        "🏢 選擇港口",
        options=list(PORTS.keys()),
        format_func=lambda x: f"{PORTS[x]} ({x})",
        index=list(PORTS.keys()).index(st.session_state.selected_port),
        key="global_port_selector"
    )
    
    selected_port = st.session_state.selected_port
    
    st.markdown("---")
    
    # 顯示當前選擇
    st.info(f"📍 當前港口: **{PORTS[selected_port]}**")
    
    st.markdown("---")
    
    with st.expander("🕷️ 爬蟲設定", expanded=True):
        use_cache = st.checkbox(
            "使用快取資料",
            value=True,
            help=f"若快取未過期（30 分鐘內），直接讀取資料庫",
            key="use_cache_checkbox"
        )
        
        headless_mode = st.checkbox(
            "無頭模式（Headless）",
            value=True,
            help="背景執行瀏覽器，不顯示視窗",
            key="headless_checkbox"
        )
        
        # 🆕 顯示快取狀態
        if use_cache:
            st.markdown("#### 📊 快取狀態")
            
            # D005 快取狀態
            d005_valid = is_cache_valid('ifa_d005', selected_port, cache_hours=0.5)
            d005_age = get_cache_age('ifa_d005', selected_port)
            
            if d005_age is not None:
                if d005_valid:
                    st.success(f"✓ D005: {d005_age:.0f} 分鐘前")
                else:
                    st.warning(f"⚠ D005: {d005_age:.0f} 分鐘前 (已過期)")
            else:
                st.error("✗ D005: 無快取")
            
            # D003 快取狀態
            d003_valid = is_cache_valid('ifa_d003', selected_port, cache_hours=0.5)
            d003_age = get_cache_age('ifa_d003', selected_port)
            
            if d003_age is not None:
                if d003_valid:
                    st.success(f"✓ D003: {d003_age:.0f} 分鐘前")
                else:
                    st.warning(f"⚠ D003: {d003_age:.0f} 分鐘前 (已過期)")
            else:
                st.error("✗ D003: 無快取")
            
            # D004 快取狀態
            d004_valid = is_cache_valid('ifa_d004', selected_port, cache_hours=0.5)
            d004_age = get_cache_age('ifa_d004', selected_port)
            
            if d004_age is not None:
                if d004_valid:
                    st.success(f"✓ D004: {d004_age:.0f} 分鐘前")
                else:
                    st.warning(f"⚠ D004: {d004_age:.0f} 分鐘前 (已過期)")
            else:
                st.error("✗ D004: 無快取")
    
    with st.expander("📊 分析參數", expanded=True):
        safety_buffer = st.number_input(
            "船舶前後安全距離（m）",
            min_value=15,
            max_value=50,
            value=DEFAULT_SAFETY_BUFFER,
            step=5,
            key="safety_buffer_input"
        )
        
        competition_window = st.number_input(
            "競合判斷時窗（Min.）",
            min_value=15,
            max_value=180,
            value=DEFAULT_COMPETITION_WINDOW,
            step=15,
            key="competition_window_input"
        )
        
        berth_duration = st.number_input(
            "預計靠泊時間(Port Stay)（Hrs.）",
            min_value=1,
            max_value=48,
            value=DEFAULT_BERTH_DURATION,
            step=1,
            key="berth_duration_input"
        )
    
    with st.expander("🤖 AI 分析設定"):
        perplexity_api_key = st.text_input(
            "Perplexity API Key",
            type="password",
            help="請輸入您的 Perplexity API Key",
            key="api_key_input"
        )
        
        if perplexity_api_key:
            st.success("✓ API Key 已設定")
        else:
            st.warning("⚠ 未設定 API Key")
    
    st.markdown("---")
    
    with st.expander("🔧 系統診斷"):
        if st.button("🔍 診斷 WebDriver", use_container_width=True, key="diagnose_button"):
            status = check_driver_status()
            st.json(status)
    
    with st.expander("💾 資料庫資訊"):
        st.code(DB_PATH, language=None)
    
    with st.expander("📢 免責聲明"):
        st.markdown(DISCLAIMER)

# ==================== 主要內容區 ====================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📥 舶位資料爬取",
    "📊 舶位資料檢視",
    "🎯 泊位分析系統",
    "📈 舶位訊息視覺化",
    "🤖 AI分析"
])

# ==================== Tab 1: 資料爬取 ====================
with tab1:
    st.markdown("<h2 class='sub-header'>🔍 資料爬取</h2>", unsafe_allow_html=True)
    
    st.info(f"📍 當前選擇: **{PORTS[selected_port]}** ({selected_port})")
    
    st.markdown("---")
    
    # ✅ 先顯示快取狀態
    if use_cache:
        st.markdown("### 📊 查詢舶位狀態")
        
        d005_valid = is_cache_valid('ifa_d005', selected_port, cache_hours=0.5)
        d003_valid = is_cache_valid('ifa_d003', selected_port, cache_hours=0.5)
        d004_valid = is_cache_valid('ifa_d004', selected_port, cache_hours=0.5)
        
        all_cache_valid = d005_valid and d003_valid and d004_valid
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if d005_valid:
                age = get_cache_age('ifa_d005', selected_port)
                # ✅ 檢查 age 是否為 None
                if age is not None:
                    st.success(f"✅ D005:上次爬取時間: {age:.0f} 分鐘前")
                else:
                    st.success("✅ D005: Database資料30分鐘內")
            else:
                st.error("❌ D005: 資料爬取超過30分鐘，請重新爬取")
        
        with col2:
            if d003_valid:
                age = get_cache_age('ifa_d003', selected_port)
                # ✅ 檢查 age 是否為 None
                if age is not None:
                    st.success(f"✅ D003:上次爬取時間: {age:.0f} 分鐘前")
                else:
                    st.success("✅ D003: Database資料30分鐘內")
            else:
                st.error("❌ D003: 資料爬取超過30分鐘，請重新爬取")
        
        with col3:
            if d004_valid:
                age = get_cache_age('ifa_d004', selected_port)
                # ✅ 檢查 age 是否為 None
                if age is not None:
                    st.success(f"✅ D004:上次爬取時間: {age:.0f} 分鐘前")
                else:
                    st.success("✅ D004: Database資料30分鐘內")
            else:
                st.error("❌ D004: 資料爬取超過30分鐘，請重新爬取")
        
        st.markdown("---")
        
        # ✅ 根據快取狀態決定按鈕文字和行為
        if all_cache_valid:
            button_text = "📥 載入Database資料"
            button_type = "secondary"
            st.info("✅ Database資料30分鐘內，點擊按鈕將直接載入資料庫資料")
        else:
            button_text = "🚀 開始爬取"
            button_type = "primary"
            st.warning("⚠️ Database資料已過期或不存在，點擊按鈕將執行爬取作業")
    else:
        button_text = "🚀 開始爬取"
        button_type = "primary"
        st.info("ℹ️ 快取功能已停用，點擊按鈕將執行爬取作業")
        all_cache_valid = False
    
    # ✅ 修正後的按鈕邏輯
    if st.button(button_text, type=button_type, use_container_width=True, key="crawl_button"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # 清除舊資料（如果切換港口）
            if st.session_state.crawl_data['port_code'] != selected_port:
                old_port = st.session_state.crawl_data.get('port_code')
                if old_port:
                    status_text.info(f"🗑️ 已清除 {PORTS.get(old_port, old_port)} 的舊資料")
                    time.sleep(1)
                
                st.session_state.crawl_data = {
                    'D005': pd.DataFrame(),
                    'D003': pd.DataFrame(),
                    'D004': pd.DataFrame(),
                    'port_code': None,
                    'timestamp': None,
                    'from_cache': False
                }
                st.session_state.timeline = None
                st.session_state.evaluation_result = None
                st.session_state.ai_analysis = None
            
            # ✅ 關鍵修正：根據快取狀態決定行為
            if use_cache and all_cache_valid:
                # 直接從資料庫載入，不爬取
                status_text.markdown(
                    f"<div class='info-box'>📥 正在從資料庫載入 {PORTS[selected_port]} 快取資料...</div>", 
                    unsafe_allow_html=True
                )
                progress_bar.progress(30)
                
                # 從資料庫讀取
                from modules.database import load_data_from_db
                
                d005_df = load_data_from_db('ifa_d005', selected_port)
                progress_bar.progress(50)
                
                d003_df = load_data_from_db('ifa_d003', selected_port)
                progress_bar.progress(70)
                
                d004_df = load_data_from_db('ifa_d004', selected_port)
                progress_bar.progress(90)
                
                from_cache = True
                
            else:
                # 執行爬取
                status_text.markdown(
                    f"<div class='info-box'>🕷️ 正在爬取 {PORTS[selected_port]} 資料...</div>", 
                    unsafe_allow_html=True
                )
                progress_bar.progress(10)
                
                # 呼叫爬取函數（強制爬取，不使用快取）
                d005_df, d003_df, d004_df, from_cache = crawl_all_reports(
                    port_code=selected_port,
                    port_name=PORTS[selected_port],
                    ship_type="B11",
                    headless=headless_mode,
                    save_to_db=True,
                    use_cache=False,  # 👈 強制爬取
                    cache_hours=0.5
                )
                
                progress_bar.progress(90)
            
            # 儲存到 session_state
            st.session_state.crawl_data = {
                'D005': d005_df,
                'D003': d003_df,
                'D004': d004_df,
                'port_code': selected_port,
                'port_name': PORTS[selected_port],
                'timestamp': datetime.now(pytz.timezone(TIMEZONE)),
                'from_cache': from_cache
            }
            
            progress_bar.progress(100)
            status_text.empty()
            
            total_records = len(d005_df) + len(d003_df) + len(d004_df)
            
            # 根據資料來源顯示不同訊息
            if from_cache:
                st.markdown(
                    f"<div class='success-box'>"
                    f"<h3>✅ Database資料載入完成！</h3>"
                    f"<p>共 <b>{total_records}</b> 筆貨櫃輪資料（來自資料庫快取）</p>"
                    f"</div>", 
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"<div class='success-box'>"
                    f"<h3>✅ 爬取完成！</h3>"
                    f"<p>共取得 <b>{total_records}</b> 筆貨櫃輪資料（已儲存到資料庫）</p>"
                    f"</div>", 
                    unsafe_allow_html=True
                )
            
            # 強制重新載入
            time.sleep(1)
            st.rerun()
            
        except Exception as e:
            st.markdown(
                f"<div class='error-box'><h3>❌ 處理失敗</h3><p>{str(e)}</p></div>", 
                unsafe_allow_html=True
            )
            import traceback
            st.error(traceback.format_exc())
# ==================== Tab 2: 資料檢視 ====================
with tab2:
    st.markdown('<div class="section-title">📊 資料檢視</div>', unsafe_allow_html=True)
    
    if not st.session_state.crawl_data['port_code']:
        st.markdown("<div class='warning-box'><h3>⚠️ 請先爬取資料</h3><p>請前往「資料爬取」頁面執行資料爬取作業</p></div>", unsafe_allow_html=True)
    else:
        data = st.session_state.crawl_data
        
        report_type = st.selectbox(
            "📋 選擇報表類型",
            options=['進港船舶表 (IFA_D003)', '出港船舶表 (IFA_D004)','船席現況及指泊表 (IFA_D005)'],
            key="report_type_selector"
        )
        
        # 根據報表類型選擇對應的映射和顯示欄位
        if 'IFA_D005' in report_type:
            df = data['D005']
            icon = "🚢"
            title = "在泊船舶列表"
            column_mapping = D005_COLUMN_MAPPING
            display_columns = D005_DISPLAY_COLUMNS
        elif 'IFA_D003' in report_type:
            df = data['D003']
            icon = "⬇️"
            title = "進港船舶列表"
            column_mapping = D003_COLUMN_MAPPING
            display_columns = D003_DISPLAY_COLUMNS
        else:
            df = data['D004']
            icon = "⬆️"
            title = "出港船舶列表"
            column_mapping = D004_COLUMN_MAPPING
            display_columns = D004_DISPLAY_COLUMNS
        
        st.markdown(f'<div class="sub-section-title">{icon} {title}</div>', unsafe_allow_html=True)
        
        if df.empty:
            st.markdown("<div class='info-box'>ℹ️ 目前無資料</div>", unsafe_allow_html=True)
        else:
            # 格式化顯示
            display_df = format_dataframe_for_display(df, column_mapping, display_columns)
            
            # 搜尋功能
            search_term = st.text_input("🔍 搜尋船名（中文或英文）", key="search_vessel_input")
            
            if search_term:
                mask = (
                    display_df['中文船名'].str.contains(search_term, case=False, na=False) |
                    display_df['英文船名'].str.contains(search_term, case=False, na=False)
                )
                filtered_df = display_df[mask]
                st.markdown(f"<div class='info-box'>找到 <b>{len(filtered_df)}</b> 筆符合的資料</div>", unsafe_allow_html=True)
            else:
                filtered_df = display_df
            
            # 顯示統計
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("總筆數", len(filtered_df))
            with col2:
                if '港口' in filtered_df.columns or '港口名稱' in filtered_df.columns:
                    port_col = '港口' if '港口' in filtered_df.columns else '港口名稱'
                    st.metric("港口數", filtered_df[port_col].nunique())
            with col3:
                if '船長(m)' in filtered_df.columns:
                    valid_lengths = filtered_df['船長(m)'].replace('--', '0').astype(float)
                    avg_length = valid_lengths[valid_lengths > 0].mean()
                    if not pd.isna(avg_length):
                        st.metric("平均船長", f"{avg_length:.1f}m")
            
            # 顯示表格
            st.dataframe(
                filtered_df,
                use_container_width=True,
                height=500,
                hide_index=True
            )
            
            # 下載按鈕
            csv = filtered_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 下載 CSV 檔案",
                data=csv,
                file_name=f"{report_type.split(' ')[0]}_{selected_port}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_csv_button"
            )

# ==================== Tab 3: 泊位分析（v4.0 整合版）====================
with tab3:
    st.markdown('<div class="section-title">🎯 泊位分析與船舶狀態</div>', unsafe_allow_html=True)
    
    if not st.session_state.crawl_data['port_code']:
        st.markdown("<div class='warning-box'><h3>⚠️ 請先爬取資料</h3><p>請前往「資料爬取」頁面執行資料爬取作業</p></div>", unsafe_allow_html=True)
    else:
        data = st.session_state.crawl_data
        selected_port = data['port_code']  # 👈 定義 selected_port 變數
        
        # ==================== 子頁籤 ====================
        sub_tab1, sub_tab2, sub_tab3 = st.tabs([
            "🏢 泊位狀態總覽",
            "🚢 船舶靠泊分析",
            "⚔️ 競爭分析"
        ])
        
        # ==================== 子頁籤 1: 泊位狀態總覽 ====================
        with sub_tab1:
            st.markdown('<div class="sub-section-title">🏢 即時泊位狀態</div>', unsafe_allow_html=True)
            
            try:
                # 取得泊位狀態
                berth_status = get_berth_status(selected_port)
                
                if 'error' in berth_status:
                    st.error(f"❌ {berth_status['error']}")
                else:
                    # 顯示摘要統計
                    summary = berth_status['summary']
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.markdown(f"""
                        <div class="metric-card" style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);">
                          <div style="font-size: 2rem;">🏢</div>
                          <div class="metric-value">{summary['total_berths']}</div>
                          <div class="metric-label">總泊位數</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown(f"""
                        <div class="metric-card" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%);">
                          <div style="font-size: 2rem;">✅</div>
                          <div class="metric-value">{summary['available_berths']}</div>
                          <div class="metric-label">可用泊位</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col3:
                        st.markdown(f"""
                        <div class="metric-card" style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);">
                          <div style="font-size: 2rem;">🚫</div>
                          <div class="metric-value">{summary['occupied_berths']}</div>
                          <div class="metric-label">占用泊位</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col4:
                        st.markdown(f"""
                        <div class="metric-card" style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);">
                          <div style="font-size: 2rem;">🚢</div>
                          <div class="metric-value">{summary['total_vessels']}</div>
                          <div class="metric-label">停泊船舶</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.markdown("---")
                    
                    # 搜尋船舶功能
                    st.markdown('<div class="sub-section-title">🔍 搜尋船舶</div>', unsafe_allow_html=True)
                    
                    search_vessel = st.text_input(
                        "輸入船名（中文或英文，支援模糊搜尋）",
                        key="search_vessel_berth"
                    )
                    
                    if search_vessel:
                        results = search_vessel_in_port(selected_port, search_vessel)
                        
                        if results:
                            st.success(f"✅ 找到 {len(results)} 艘船")
                            
                            for r in results:
                                vessel = r['vessel']
                                
                                st.markdown(f"""
                                <div class="wh-card">
                                  <h4>🚢 {vessel['vessel_name']}</h4>
                                  <table style="width: 100%;">
                                    <tr>
                                      <td style="padding: 0.5rem; font-weight: 600; width: 150px;">停泊泊位</td>
                                      <td style="padding: 0.5rem;">{r['wharf_name']} ({r['wharf_code']})</td>
                                    </tr>
                                    <tr>
                                      <td style="padding: 0.5rem; font-weight: 600;">英文船名</td>
                                      <td style="padding: 0.5rem;">{vessel['vessel_ename']}</td>
                                    </tr>
                                    <tr>
                                      <td style="padding: 0.5rem; font-weight: 600;">船長</td>
                                      <td style="padding: 0.5rem;">{vessel['loa_m']:.0f} m</td>
                                    </tr>
                                    <tr>
                                      <td style="padding: 0.5rem; font-weight: 600;">總噸位</td>
                                      <td style="padding: 0.5rem;">{vessel['gt']:,} GT</td>
                                    </tr>
                                    <tr>
                                      <td style="padding: 0.5rem; font-weight: 600;">到港時間</td>
                                      <td style="padding: 0.5rem;">{vessel['ata_berth'].strftime('%Y-%m-%d %H:%M') if vessel['ata_berth'] else 'N/A'}</td>
                                    </tr>
                                    <tr>
                                      <td style="padding: 0.5rem; font-weight: 600;">預計離港</td>
                                      <td style="padding: 0.5rem;">{vessel['etd_berth'].strftime('%Y-%m-%d %H:%M') if vessel['etd_berth'] else 'N/A'}</td>
                                    </tr>
                                    <tr>
                                      <td style="padding: 0.5rem; font-weight: 600;">代理</td>
                                      <td style="padding: 0.5rem;">{vessel['agent']}</td>
                                    </tr>
                                    <tr>
                                      <td style="padding: 0.5rem; font-weight: 600;">航線</td>
                                      <td style="padding: 0.5rem;">{vessel['prev_port']} → {vessel['next_port']}</td>
                                    </tr>
                                  </table>
                                </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.warning(f"⚠️ 找不到包含 '{search_vessel}' 的船舶")
                    
                    st.markdown("---")
                    
                    # 顯示所有泊位詳情
                    st.markdown('<div class="sub-section-title">📋 泊位詳細資訊</div>', unsafe_allow_html=True)
                    
                    # 篩選選項
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        show_only_occupied = st.checkbox(
                            "只顯示有船泊位",
                            value=False,
                            key="show_occupied_only"
                        )
                    
                    with col2:
                        show_container_only = st.checkbox(
                            "只顯示貨櫃碼頭",
                            value=False,
                            key="show_container_only"
                        )
                    
                    # 篩選泊位
                    filtered_berths = berth_status['berths']
                    
                    if show_only_occupied:
                        filtered_berths = [b for b in filtered_berths if b['vessel_count'] > 0]
                    
                    if show_container_only:
                        filtered_berths = [b for b in filtered_berths if b['is_container']]
                    
                    if not filtered_berths:
                        st.warning("⚠️ 沒有符合條件的泊位")
                    else:
                        # 顯示每個泊位
                        for berth in filtered_berths:
                            # 狀態圖示
                            if berth['vessel_count'] == 0:
                                status_icon = "🟢"
                                status_text = "空閒"
                                status_color = "green"
                            elif berth['remaining_length_m'] > 50:
                                status_icon = "🟡"
                                status_text = "部分占用"
                                status_color = "orange"
                            else:
                                status_icon = "🔴"
                                status_text = "滿載"
                                status_color = "red"
                            
                            # 貨櫃碼頭標記
                            container_mark = "🚢" if berth['is_container'] else "📦"
                            
                            with st.container():
                                # 泊位標題
                                col1, col2 = st.columns([3, 1])
                                
                                with col1:
                                    st.markdown(f"### {status_icon} {container_mark} {berth['wharf_code']}: {berth['wharf_name']}")
                                
                                with col2:
                                    st.markdown(f"**狀態:** :{status_color}[{status_text}]")
                                
                                # 泊位資訊
                                col1, col2, col3, col4 = st.columns(4)
                                
                                col1.metric("總長度", f"{berth['total_length_m']:.0f} m")
                                col2.metric("占用長度", f"{berth['occupied_length_m']:.0f} m")
                                col3.metric("剩餘長度", f"{berth['remaining_length_m']:.0f} m")
                                col4.metric("占用率", f"{berth['occupancy_rate']:.1f}%")
                                
                                st.caption(f"水深: {berth['depth_m']:.1f}m | 貨物類型: {berth['cargo_type']}")
                                
                                # 顯示停泊船舶
                                if berth['vessel_count'] > 0:
                                    st.markdown(f"**停泊船舶 ({berth['vessel_count']} 艘):**")
                                    
                                    # 建立表格
                                    vessel_data = []
                                    for vessel in berth['vessels']:
                                        vessel_data.append({
                                            '船名': vessel['vessel_name'],
                                            '船長(m)': f"{vessel['loa_m']:.0f}",
                                            '總噸位': f"{vessel['gt']:,}",
                                            '船型': vessel['ship_type'],
                                            '到港時間': vessel['ata_berth'].strftime('%m/%d %H:%M') if vessel['ata_berth'] else 'N/A',
                                            '預計離港': vessel['etd_berth'].strftime('%m/%d %H:%M') if vessel['etd_berth'] else 'N/A',
                                            '代理': vessel['agent']
                                        })
                                    
                                    vessel_df = pd.DataFrame(vessel_data)
                                    st.dataframe(vessel_df, use_container_width=True, hide_index=True)
                                    
                                    # 詳細資訊
                                    with st.expander("查看詳細資訊"):
                                        for i, vessel in enumerate(berth['vessels'], 1):
                                            st.markdown(f"""
                                            **{i}. {vessel['vessel_name']}**
                                            - 英文船名: {vessel['vessel_ename']}
                                            - 呼號: {vessel['call_sign']} | IMO: {vessel['imo']}
                                            - 船舶編號: {vessel['vessel_no']}
                                            - 靠泊狀態: {vessel['alongside_status']}
                                            - 移動狀態: {vessel['movement_status']}
                                            - 前港: {vessel['prev_port']} → 次港: {vessel['next_port']}
                                            - 爬取時間: {vessel['crawl_time']}
                                            """)
                                            st.divider()
                                else:
                                    st.info("目前無船舶停泊")
                                
                                st.markdown("---")
            
            except Exception as e:
                st.error(f"❌ 無法載入泊位狀態: {str(e)}")
                with st.expander("🔍 詳細錯誤訊息"):
                    import traceback
                    st.code(traceback.format_exc())
        
        # ==================== 子頁籤 2: 船舶靠泊分析 ====================
        with sub_tab2:
            st.markdown('<div class="sub-section-title">🚢 船舶靠泊分析</div>', unsafe_allow_html=True)
            
            # ✅ 方案 1：檢查是否有爬取資料
            if not st.session_state.crawl_data['port_code']:
                st.markdown(
                    "<div class='warning-box'>"
                    "<h3>⚠️ 請先爬取資料</h3>"
                    "<p>請前往「資料爬取」頁面執行資料爬取作業</p>"
                    "</div>", 
                    unsafe_allow_html=True
                )
                st.stop()
            
            # ✅ 從 crawl_data 取得港口代碼
            selected_port = st.session_state.crawl_data['port_code']
            
            # 或者使用側邊欄選擇的港口（方案 2）
            # selected_port = st.session_state.selected_port
            
            # 建立或載入時間軸
            if 'timeline' not in st.session_state or st.session_state.timeline is None:
                with st.spinner("🔄 正在建立泊位時間軸..."):
                    timeline = build_berth_timeline(selected_port, safety_buffer=safety_buffer)
                    st.session_state.timeline = timeline
            else:
                timeline = st.session_state.timeline
            
            # ✅ 檢查時間軸是否有效
            if timeline is None or not timeline:
                st.error("❌ 無法建立泊位時間軸，請確認資料完整性")
                st.stop()
            
            # 顯示當前港口資訊
            st.info(f"📍 當前分析港口: **{PORTS.get(selected_port, selected_port)}** ({selected_port})")
            
            col1, col2 = st.columns(2)
            
            with col1:
                vessel_name = st.text_input(
                    "Ship's Name",
                    value="WanHai XXX",
                    key=WidgetKeys.REALTIME_VESSEL_NAME
                )
                
                ship_length = st.number_input(
                    "LOA(m)",
                    min_value=50.0,
                    max_value=500.0,
                    value=300.0,
                    step=10.0,
                    key=WidgetKeys.REALTIME_SHIP_LENGTH
                )
            
            with col2:
                eta_date = st.date_input(
                    "ETA(Day)",
                    value=datetime.now(pytz.timezone(TIMEZONE)).date(),
                    key=WidgetKeys.REALTIME_ETA_DATE
                )
                
                eta_time = st.time_input(
                    "ETA(Time)",
                    value=st.session_state.default_eta_time,
                    key=WidgetKeys.REALTIME_ETA_TIME
                )
            
            eta_datetime = datetime.combine(eta_date, eta_time)
            eta_datetime = pytz.timezone(TIMEZONE).localize(eta_datetime)
            
            st.markdown(f"""
            <div class="info-box">
              <h4>📅 預計到港時間</h4>
              <p style="font-size: 1.2rem; font-weight: 600;">
                {eta_datetime.strftime('%Y年%m月%d日 %H:%M')} ({TIMEZONE[5::]})
              </p>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("🎯 開始分析泊位可用性", type="primary", use_container_width=True, key=WidgetKeys.REALTIME_ANALYZE_BTN):
                with st.spinner("正在分析泊位可用性..."):
                    try:
                        # ✅ 呼叫分析函數
                        result = evaluate_berth_for_eta(
                            timeline=timeline,
                            eta_str=eta_datetime.isoformat(),
                            ship_length=ship_length,
                            ship_name=vessel_name,
                            safety_buffer_each_side=safety_buffer,
                            competition_window_minutes=competition_window
                        )
                        
                        # ✅ 檢查結果是否有效
                        if result is None:
                            st.error("❌ 分析函數回傳 None，請檢查 berth_analyzer.py")
                            st.stop()
                        
                        if not isinstance(result, dict):
                            st.error(f"❌ 分析結果格式錯誤: {type(result)}")
                            st.stop()
                        
                        # ✅ 儲存結果
                        st.session_state.evaluation_result = result
                        
                        # ✅ 顯示結果
                        if result.get('can_berth', False):
                            st.markdown(f"""
                            <div class="success-box">
                              <h3>✅ 可以靠泊！</h3>
                              <p>{result.get('recommendation', '建議靠泊')}</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # 顯示可用泊位
                            available_berths = result.get('available_berths', [])
                            if available_berths:
                                st.markdown("### 📋 可用泊位列表")
                                
                                for berth in available_berths:
                                    with st.container():
                                        col1, col2, col3 = st.columns(3)
                                        
                                        with col1:
                                            st.markdown(f"""
                                            <div class="wh-card">
                                              <h4>🏢 {berth.get('berth_name', 'N/A')}</h4>
                                              <p><strong>碼頭編號:</strong> {berth.get('berth_code', 'N/A')}</p>
                                            </div>
                                            """, unsafe_allow_html=True)
                                        
                                        with col2:
                                            st.metric("總長度", f"{berth.get('total_length_m', 0):.0f}m")
                                            st.metric("水深", f"{berth.get('depth_m', 0):.1f}m")
                                        
                                        with col3:
                                            st.metric("剩餘空間", f"{berth.get('remaining_length_m', 0):.0f}m")
                                            st.metric("占用船舶", f"{len(berth.get('occupied_vessels', []))} 艘")
                                        
                                        st.markdown("---")
                            
                            # 顯示候選泊位
                            candidate_berths = result.get('candidate_berths', [])
                            if candidate_berths:
                                st.markdown("### 🎯 推薦泊位")
                                
                                for i, berth in enumerate(candidate_berths, 1):
                                    st.markdown(f"""
                                    <div class="wh-card">
                                      <h4>{i}. {berth.get('berth_name', 'N/A')} ({berth.get('berth_code', 'N/A')})</h4>
                                      <ul>
                                        <li><strong>適合度:</strong> {berth.get('suitability_score', 0):.1f}%</li>
                                        <li><strong>剩餘長度:</strong> {berth.get('remaining_length_m', 0):.0f}m</li>
                                        <li><strong>占用率:</strong> {berth.get('occupancy_rate', 0):.1f}%</li>
                                        <li><strong>理由:</strong> {berth.get('reason', '適合靠泊')}</li>
                                      </ul>
                                    </div>
                                    """, unsafe_allow_html=True)
                        
                        else:
                            st.markdown(f"""
                            <div class="error-box">
                              <h3>❌ 無法靠泊</h3>
                              <p>{result.get('recommendation', '無法找到合適泊位')}</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # 顯示原因
                            reasons = result.get('reasons', [])
                            if reasons:
                                st.markdown("### 📋 無法靠泊的原因")
                                for reason in reasons:
                                    st.warning(f"⚠️ {reason}")
                        
                        # 顯示詳細資訊
                        with st.expander("🔍 查看詳細分析資料"):
                            st.json(result)
                        
                    except Exception as e:
                        st.error(f"❌ 分析失敗: {str(e)}")
                        with st.expander("🔍 詳細錯誤訊息"):
                            import traceback
                            st.code(traceback.format_exc())
        
        # ==================== 子頁籤 3: 競爭分析 ====================
        with sub_tab3:
            st.markdown('<div class="sub-section-title">⚔️ 進港競爭分析</div>', unsafe_allow_html=True)
            
            if st.session_state.evaluation_result:
                try:
                    result = st.session_state.evaluation_result
                    
                    # 確保有時間軸
                    if 'timeline' not in st.session_state:
                        timeline = build_berth_timeline(selected_port)
                        st.session_state.timeline = timeline
                    else:
                        timeline = st.session_state.timeline
                    
                    # 執行競爭分析
                    competition_result = analyze_competition(
                        timeline=timeline,
                        eta_str=result['eta'].isoformat(),
                        ship_length=result['ship_length'],
                        ship_name=result['ship_name'],
                        competition_window_minutes=competition_window
                    )
                    
                    # 顯示競爭程度
                    level_config = {
                        'low': ('🟢', '低', 'green', '#10b981'),
                        'medium': ('🟡', '中', 'orange', '#f59e0b'),
                        'high': ('🔴', '高', 'red', '#ef4444')
                    }
                    
                    icon, level_text, color, bg_color = level_config.get(
                        competition_result['competition_level'],
                        ('❓', '未知', 'gray', '#6b7280')
                    )
                    
                    st.markdown(f"""
                    <div class="wh-card" style="border-left: 6px solid {bg_color};">
                      <h3>{icon} 競爭程度: {level_text}</h3>
                      <p style="font-size: 1.1rem; margin-top: 1rem;">
                        {competition_result['reason']}
                      </p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 顯示競爭船舶
                    if competition_result['competition_count'] > 0:
                        st.markdown("### 🚢 競爭船舶列表")
                        
                        for i, vessel in enumerate(competition_result['competing_vessels'], 1):
                            time_diff = vessel['time_diff_minutes']
                            diff_str = f"早 {abs(time_diff):.0f} 分鐘" if time_diff < 0 else f"晚 {abs(time_diff):.0f} 分鐘"
                            
                            st.markdown(f"""
                            <div class="wh-card">
                              <h4>{i}. {vessel['vessel_name']}</h4>
                              <table style="width: 100%;">
                                <tr>
                                  <td style="padding: 0.5rem; font-weight: 600; width: 150px;">英文船名</td>
                                  <td style="padding: 0.5rem;">{vessel['vessel_ename']}</td>
                                </tr>
                                <tr>
                                  <td style="padding: 0.5rem; font-weight: 600;">ETA</td>
                                  <td style="padding: 0.5rem;">{vessel['eta'].strftime('%Y-%m-%d %H:%M')} ({diff_str})</td>
                                </tr>
                                <tr>
                                  <td style="padding: 0.5rem; font-weight: 600;">船長</td>
                                  <td style="padding: 0.5rem;">{vessel['loa_m']:.0f} m</td>
                                </tr>
                                <tr>
                                  <td style="padding: 0.5rem; font-weight: 600;">總噸位</td>
                                  <td style="padding: 0.5rem;">{vessel['gt']:,} GT</td>
                                </tr>
                                <tr>
                                  <td style="padding: 0.5rem; font-weight: 600;">預定泊位</td>
                                  <td style="padding: 0.5rem;">{vessel['berth']}</td>
                                </tr>
                                <tr>
                                  <td style="padding: 0.5rem; font-weight: 600;">代理</td>
                                  <td style="padding: 0.5rem;">{vessel['agent']}</td>
                                </tr>
                                <tr>
                                  <td style="padding: 0.5rem; font-weight: 600;">航線</td>
                                  <td style="padding: 0.5rem;">{vessel['prev_port']} → {vessel['next_port']}</td>
                                </tr>
                              </table>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # 顯示建議
                    if competition_result['should_accelerate']:
                        st.markdown(f"""
                        <div class="warning-box">
                          <h3>⚡ 建議加速！</h3>
                          <p>建議 ETA: <strong>{competition_result['recommended_eta'].strftime('%Y-%m-%d %H:%M')}</strong></p>
                          <p>提早時間: <strong>{abs(competition_result['time_adjustment'].total_seconds()/60):.0f} 分鐘</strong></p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div class="success-box">
                          <h3>✅ 可按原定時間到港</h3>
                          <p>競爭壓力低，無需調整 ETA</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"❌ 競爭分析失敗: {str(e)}")
                    with st.expander("🔍 詳細錯誤訊息"):
                        import traceback
                        st.code(traceback.format_exc())
            else:
                st.warning("⚠️ 請先在「船舶靠泊分析」頁面執行分析")

# ==================== Tab 4: 視覺化（完整修正版）====================
with tab4:
    st.markdown('<div class="section-title">📈 資料視覺化</div>', unsafe_allow_html=True)
    
    if not st.session_state.crawl_data['port_code']:
        st.markdown("<div class='warning-box'><h3>⚠️ 請先爬取資料</h3><p>請前往「資料爬取」頁面執行資料爬取作業</p></div>", unsafe_allow_html=True)
    else:
        data = st.session_state.crawl_data
        selected_port = data['port_code']
        
        # ==================== 1. 泊位占用甘特圖 ====================
        st.markdown('<div class="sub-section-title">📊 泊位占用甘特圖</div>', unsafe_allow_html=True)
        
        try:
            berth_status = get_berth_status(selected_port)
            
            if 'error' not in berth_status:
                # 取得 ETA 和船長（如果有分析結果）
                eta_str = None
                ship_length = None
                
                if st.session_state.evaluation_result:
                    eta_dt = st.session_state.evaluation_result.get('eta')
                    if eta_dt:
                        eta_str = eta_dt.isoformat()
                    ship_length = st.session_state.evaluation_result.get('ship_length')
                
                fig = create_berth_gantt_chart(berth_status, eta_str, ship_length)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error(f"❌ {berth_status['error']}")
                
        except Exception as e:
            st.markdown(f"<div class='error-box'><h3>❌ 圖表生成失敗</h3><p>{str(e)}</p></div>", unsafe_allow_html=True)
            with st.expander("🔍 詳細錯誤訊息"):
                import traceback
                st.code(traceback.format_exc())
        
        # ==================== 2. 進港競合程度分析 ====================
        if st.session_state.evaluation_result:
            st.markdown('<div class="sub-section-title">📈 進港競合程度分析</div>', unsafe_allow_html=True)
            
            try:
                # 建立時間軸（如果不存在）
                if 'timeline' not in st.session_state:
                    timeline = build_berth_timeline(selected_port)
                    st.session_state.timeline = timeline
                else:
                    timeline = st.session_state.timeline
                
                eta_dt = st.session_state.evaluation_result.get('eta')
                if eta_dt:
                    eta_str = eta_dt.isoformat()
                    fig = create_competition_chart(timeline, eta_str, competition_window)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("⚠️ 缺少 ETA 資訊")
                    
            except Exception as e:
                st.markdown(f"<div class='error-box'><h3>❌ 圖表生成失敗</h3><p>{str(e)}</p></div>", unsafe_allow_html=True)
                with st.expander("🔍 詳細錯誤訊息"):
                    import traceback
                    st.code(traceback.format_exc())
        
        # ==================== 3. 泊位容量分析 ====================
        st.markdown('<div class="sub-section-title">📊 泊位容量分析</div>', unsafe_allow_html=True)
        
        try:
            berth_status = get_berth_status(selected_port)
            
            if 'error' not in berth_status:
                fig = create_berth_capacity_chart(berth_status)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error(f"❌ {berth_status['error']}")
                
        except Exception as e:
            st.markdown(f"<div class='error-box'><h3>❌ 圖表生成失敗</h3><p>{str(e)}</p></div>", unsafe_allow_html=True)
            with st.expander("🔍 詳細錯誤訊息"):
                import traceback
                st.code(traceback.format_exc())
        
        # ==================== 4. 港口摘要儀表板 ====================
        st.markdown('<div class="sub-section-title">📊 港口摘要儀表板</div>', unsafe_allow_html=True)
        
        try:
            berth_status = get_berth_status(selected_port)
            
            if 'error' not in berth_status:
                fig = create_port_summary_dashboard(berth_status)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error(f"❌ {berth_status['error']}")
                
        except Exception as e:
            st.markdown(f"<div class='error-box'><h3>❌ 圖表生成失敗</h3><p>{str(e)}</p></div>", unsafe_allow_html=True)
            with st.expander("🔍 詳細錯誤訊息"):
                import traceback
                st.code(traceback.format_exc())
        
        # ==================== 5. 船舶長度分布 ====================
        st.markdown('<div class="sub-section-title">📏 船舶長度分布</div>', unsafe_allow_html=True)
        
        try:
            if data.get('D005') is not None and data.get('D003') is not None and data.get('D004') is not None:
                fig = create_ship_length_distribution(
                    data['D005'],
                    data['D003'],
                    data['D004']
                )
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.markdown("<div class='info-box'>ℹ️ 無足夠資料生成圖表</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='warning-box'>⚠️ 缺少必要資料</div>", unsafe_allow_html=True)
                
        except Exception as e:
            st.markdown(f"<div class='error-box'><h3>❌ 圖表生成失敗</h3><p>{str(e)}</p></div>", unsafe_allow_html=True)
            with st.expander("🔍 詳細錯誤訊息"):
                import traceback
                st.code(traceback.format_exc())
        
        # ==================== 6. 統計摘要 ====================
        st.markdown("---")
        st.markdown('<div class="sub-section-title">📋 統計摘要</div>', unsafe_allow_html=True)
        
        try:
            berth_status = get_berth_status(selected_port)
            
            if 'error' not in berth_status:
                summary = berth_status['summary']
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown(f"""
                    <div class="metric-card" style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);">
                      <div style="font-size: 2rem;">🏢</div>
                      <div class="metric-value">{summary['total_berths']}</div>
                      <div class="metric-label">總泊位數</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"""
                    <div class="metric-card" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%);">
                      <div style="font-size: 2rem;">✅</div>
                      <div class="metric-value">{summary['available_berths']}</div>
                      <div class="metric-label">可用泊位</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col3:
                    st.markdown(f"""
                    <div class="metric-card" style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);">
                      <div style="font-size: 2rem;">🚢</div>
                      <div class="metric-value">{summary['total_vessels']}</div>
                      <div class="metric-label">停泊船舶</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col4:
                    st.markdown(f"""
                    <div class="metric-card" style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);">
                      <div style="font-size: 2rem;">📊</div>
                      <div class="metric-value">{summary['avg_occupancy_rate']:.1f}%</div>
                      <div class="metric-label">平均占用率</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.error(f"❌ {berth_status['error']}")
                
        except Exception as e:
            st.error(f"❌ 無法計算統計資訊: {str(e)}")

# ==================== Tab 5: AI 分析 ====================
with tab5:
    st.markdown('<div class="section-title">🤖 AI 智慧分析</div>', unsafe_allow_html=True)
    
    if not perplexity_api_key:
        st.markdown("<div class='error-box'><h3>❌ 請設定 API Key</h3><p>請在側邊欄的「AI 分析設定」中輸入您的 Perplexity API Key</p></div>", unsafe_allow_html=True)
    elif not st.session_state.crawl_data['port_code']:
        st.markdown("<div class='warning-box'><h3>⚠️ 請先爬取資料</h3><p>請前往「資料爬取」頁面執行資料爬取作業</p></div>", unsafe_allow_html=True)
    elif not st.session_state.evaluation_result:
        st.markdown("<div class='warning-box'><h3>⚠️ 請先進行泊位分析</h3><p>請前往「泊位分析」頁面執行分析作業</p></div>", unsafe_allow_html=True)
    else:
        data = st.session_state.crawl_data
        result = st.session_state.evaluation_result
        selected_port = data['port_code']  # 👈 定義 selected_port 變數
        
        st.markdown("""
        <div class="wh-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
          <h3 style="color: white !important;">🤖 AI 分析功能</h3>
          <p style="color: white !important;">使用 Perplexity AI 進行靠泊動態綜合評估,提供更深入的分析與建議。</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 合併船舶資料
        try:
            merged_data = merge_ship_data(
                data['D005'],
                data['D003'],
                data['D004']
            )
        except Exception as e:
            st.error(f"❌ 資料合併失敗: {str(e)}")
            st.stop()
        
        st.markdown('<div class="sub-section-title">📋 分析輸入摘要</div>', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        metrics = [
            ("在泊船舶", len(merged_data.get('in_berth', [])), "🚢", "#10b981"),
            ("進港船舶", len(merged_data.get('inbound', [])), "⬇️", "#3b82f6"),
            ("出港船舶", len(merged_data.get('outbound', [])), "⬆️", "#f59e0b")
        ]
        
        for col, (label, value, icon, color) in zip([col1, col2, col3], metrics):
            with col:
                st.markdown(f"""
                <div class="wh-card" style="text-align: center; border-top: 4px solid {color};">
                  <div style="font-size: 2rem;">{icon}</div>
                  <div class="metric-value" style="color: {color};">{value}</div>
                  <div class="metric-label">{label}</div>
                </div>
                """, unsafe_allow_html=True)
        
        # AI 分析按鈕
        if st.button("🚀 開始 AI 分析", type="primary", use_container_width=True, key="start_ai_analysis"):
            with st.spinner("🤖 AI 正在分析中,請稍候(約 30-60 秒)..."):
                try:
                    # 取得船舶資訊
                    vessel_name = st.session_state.get('input_vessel_name', '測試貨櫃輪')
                    ship_length = st.session_state.get('input_ship_length', 300.0)
                    
                    # 檢查必要資料
                    if not result.get('eta'):
                        st.error("❌ 缺少 ETA 資訊")
                        st.stop()
                    
                    if not result.get('required_length'):
                        st.error("❌ 缺少所需長度資訊")
                        st.stop()
                    
                    # 執行 AI 分析
                    ai_result = generate_berth_ai_analysis(
                        port_name=PORTS.get(selected_port, selected_port),
                        ship_type=TARGET_SHIP_NAME,
                        vessel_name=vessel_name,
                        eta=result['eta'],
                        ship_length=ship_length,
                        safety_buffer_each_side=safety_buffer,
                        required_length=result['required_length'],
                        in_berth_list=merged_data.get('in_berth', []),
                        inbound_list=merged_data.get('inbound', []),
                        outbound_list=merged_data.get('outbound', []),
                        candidate_berths=result.get('candidate_berths', []),
                        competition_window_minutes=competition_window,
                        perplexity_api_key=perplexity_api_key
                    )
                    
                    st.session_state.ai_analysis = ai_result
                    st.success("✅ AI 分析完成!")
                    st.rerun()
                
                except Exception as e:
                    st.markdown(f"<div class='error-box'><h3>❌ AI 分析失敗</h3><p>{str(e)}</p></div>", unsafe_allow_html=True)
                    with st.expander("🔍 詳細錯誤訊息"):
                        import traceback
                        st.code(traceback.format_exc())
        
        # 顯示 AI 分析結果
        if st.session_state.ai_analysis:
            st.markdown('<div class="sub-section-title">🎯 AI 分析結果</div>', unsafe_allow_html=True)
            
            ai_result = st.session_state.ai_analysis
            
            if ai_result.get('success'):
                # 顯示分析內容
                st.markdown(f"""
                <div class="wh-card">
                  {ai_result.get('analysis', '無分析內容')}
                </div>
                """, unsafe_allow_html=True)
                
                # 顯示 API 使用統計
                if 'usage' in ai_result:
                    with st.expander("📊 API 使用統計"):
                        usage = ai_result['usage']
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("Prompt Tokens", f"{usage.get('prompt_tokens', 0):,}")
                        
                        with col2:
                            st.metric("Completion Tokens", f"{usage.get('completion_tokens', 0):,}")
                        
                        with col3:
                            st.metric("Total Tokens", f"{usage.get('total_tokens', 0):,}")
                
                # 匯出功能
                st.markdown("---")
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("📄 匯出為 Markdown", use_container_width=True):
                        md_content = f"""# AI 靠泊分析報告

                                            ## 基本資訊
                                            - **港口**: {PORTS.get(selected_port, selected_port)}
                                            - **船名**: {vessel_name}
                                            - **ETA**: {result['eta'].strftime('%Y-%m-%d %H:%M')}
                                            - **船長**: {ship_length}m
                                            
                                            ## AI 分析結果
                                            
                                            {ai_result.get('analysis', '無分析內容')}
                                            
                                            ---
                                            *報告產生時間: {datetime.now(pytz.timezone(TIMEZONE)).strftime('%Y-%m-%d %H:%M:%S')}*
"""
                        st.download_button(
                            label="⬇️ 下載 Markdown",
                            data=md_content,
                            file_name=f"AI分析報告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                            mime="text/markdown"
                        )
                
                with col2:
                    if st.button("🔄 重新分析", use_container_width=True):
                        st.session_state.ai_analysis = None
                        st.rerun()
            
            else:
                st.markdown(f"""
                <div class='error-box'>
                  <h3>❌ 分析失敗</h3>
                  <p>{ai_result.get('error', '未知錯誤')}</p>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("🔄 重試", type="primary", use_container_width=True):
                    st.session_state.ai_analysis = None
                    st.rerun()

# ==================== 頁尾 ====================
st.markdown("---")
st.markdown(f"""
<div class="wh-footer">
  <div class="wh-footer-content">
    <h3 style="color: white; margin-bottom: 0.5rem;">🚢 {APP_TITLE}</h3>
    <p style="opacity: 0.8; margin-bottom: 1rem;">{APP_VERSION}</p>
    <p style="opacity: 0.7; font-size: 0.9rem;">資料來源: 臺灣港務公司 IFA 系統</p>
    <div class="wh-footer-links" style="margin-top: 1rem;">
      <a href="#" onclick="alert('功能開發中')">使用說明</a>
      <a href="#" onclick="alert('功能開發中')">聯絡我們</a>
      <a href="#" onclick="alert('功能開發中')">隱私權政策</a>
    </div>
    <p style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid rgba(255, 255, 255, 0.1); opacity: 0.6; font-size: 0.85rem;">
      ⚠️ 系統開發人員 Wan Hai FRM_Harry 
    </p>
  </div>
</div>
""", unsafe_allow_html=True)
