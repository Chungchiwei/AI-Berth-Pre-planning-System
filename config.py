"""
AI 船期泊位管理系統 - 配置文件（完整版 v2.5）
修正: 根據 TaiwanPort_wharf_information.db 實際欄位調整配置
"""
import os
from datetime import timedelta
from pathlib import Path
# ==================== 應用程式資訊 ====================
APP_TITLE = "AI 船期泊位管理系統"
APP_VERSION = "v2.5"

# ==================== IFA 系統設定 ====================
IFA_BASE_URL = "https://tpnet.twport.com.tw/IFAWeb"

# ✅ 修正：IFA 報表 URL（使用正確的路徑）
REPORT_URLS = {
    'D005': f"{IFA_BASE_URL}/Function?_RedirUrl=/IFAWeb/Board/ShipWharfAllStatus",  # 船席現況及指泊表
    'D003': f"{IFA_BASE_URL}/Function?_RedirUrl=/IFAWeb/Reports/InPortShipList",    # 進港船舶表
    'D004': f"{IFA_BASE_URL}/Function?_RedirUrl=/IFAWeb/Reports/OutPortShipList",   # 出港船舶表
}

# ==================== 港口設定 ====================
# ✅ 修正：使用正確的港口代碼（配合爬蟲模組和資料庫）
PORTS = {
    'KEL': '基隆港',
    'TPE': '台北港',
    'TXG': '台中港',
    'KHH': '高雄港'
}

# ✅ 港口代碼對應（新舊代碼轉換）
PORT_CODE_MAPPING = {
    'TP': 'TPE',   # 台北港
    'KL': 'KEL',   # 基隆港
    'TC': 'TXG',   # 台中港
    'KH': 'KHH',   # 高雄港
    'TWKEL': 'KEL',
    'TWTPE': 'TPE',
    'TWTXG': 'TXG',
    'TWKHH': 'KHH',
}

# 預設港口
DEFAULT_PORT = 'KEL'

# ==================== 船種設定 ====================
TARGET_SHIP_TYPE = "B11"  # ✅ IFA 系統中的船種代碼
TARGET_SHIP_NAME = "貨櫃輪"  # 目標船種（用於顯示）

# ✅ 船種對應表（配合 IFA 系統）
SHIP_TYPE_MAPPING = {
    '貨櫃輪': ['貨櫃輪', '貨櫃船', 'CONTAINER', 'CONTAINER SHIP', 'B11', 'B-11'],
    '散裝輪': ['散裝輪', '散裝船', 'BULK CARRIER', 'B01', 'B-01'],
    '油輪': ['油輪', '油船', 'TANKER', 'OIL TANKER', 'B02', 'B-02'],
    '雜貨輪': ['雜貨輪', '雜貨船', 'GENERAL CARGO', 'B03', 'B-03'],
}

# ✅ 船種代碼對應（IFA 系統）
SHIP_TYPE_CODES = {
    'B11': '貨櫃輪',
    'B01': '散裝輪',
    'B02': '油輪',
    'B03': '雜貨輪',
}

# ==================== Selenium 設定 ====================
SELENIUM_WAIT_TIMEOUT = 15  # 元素等待超時（秒）
SELENIUM_PAGE_LOAD_TIMEOUT = 30  # 頁面載入超時（秒）
SELENIUM_IMPLICIT_WAIT = 10  # 隱式等待（秒）

# ChromeDriver 設定
CHROMEDRIVER_AUTO_INSTALL = True  # 自動安裝 ChromeDriver
HEADLESS_MODE = True  # 預設使用無頭模式

# ✅ 爬蟲重試設定
MAX_RETRIES = 3  # 最大重試次數
RETRY_DELAY = 3  # 重試延遲（秒）

# ==================== 資料庫設定 ====================
IS_CLOUD = os.getenv('STREAMLIT_SHARING_MODE') is not None
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'berth_management_Data.db')
Port_DB_Path = os.path.join(os.path.dirname(__file__), 'data', 'TaiwanPort_wharf_information.db')
if IS_CLOUD:
    # 雲端環境：使用暫存目錄
    DB_PATH = '/tmp/berth_management_Data.db'
    Port_DB_Path = '/TaiwanPort_wharf_information.db'
else:
    # 本地環境：使用 data 資料夾
    DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'berth_management_Data.db')
    Port_DB_Path = os.path.join(os.path.dirname(__file__), 'data', 'TaiwanPort_wharf_information.db')
    # 確保資料夾存在
    Path('data').mkdir(exist_ok=True)
# 確保資料目錄存在
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# 快取設定
ENABLE_CACHE = True  # 啟用快取
CACHE_TTL_MINUTES = 30  # 快取有效期（分鐘）

# ==================== 時區設定 ====================
TIMEZONE = 'Asia/Taipei'
TIMEZ = TIMEZONE  # 別名，向後兼容

# ==================== 泊位設定 ====================
# ✅ 泊位資料庫欄位定義（配合 TaiwanPort_wharf_information.db）
WHARF_DB_COLUMNS = {
    'port_code': 'port_code',           # 港口代碼
    'port_name': 'port_name',           # 港口名稱
    'wharf_code': 'wharf_code',         # 碼頭編號
    'wharf_name': 'wharf_name',         # 碼頭名稱
    'wharf_name_en': 'wharf_name_en',   # 碼頭英文名稱
    'length_m': 'length_m',             # 碼頭長度（公尺）
    'depth_m': 'depth_m',               # 水深（公尺）
    'cargo_type': 'cargo_type',         # 貨物類型
}

# ✅ 貨櫃碼頭判斷關鍵字（配合資料庫 cargo_type 欄位）
CONTAINER_CARGO_KEYWORDS = [
    '貨櫃',
    '櫃',
    'container',
    'CONTAINER',
    'Container',
]

# ✅ 貨櫃碼頭泊位範圍（參考用，實際以資料庫為準）
CONTAINER_WHARVES = {
    'KEL': {  # 基隆港
        'east': range(1, 13),   # 東1-東12
        'west': range(16, 25),  # 西16-西24
    },
    'TXG': {  # 台中港
        'range': range(50, 70),  # 50-69
    },
    'KHH': {  # 高雄港
        'range': range(70, 80),  # 70-79
    },
}

# ✅ 泊位代碼前綴（參考用）
WHARF_CODE_PREFIXES = {
    'KEL': ['KELE', 'KELW', '東', '西'],  # 基隆港東、西碼頭
    'TXG': ['TXG', 'TXGC'],               # 台中港
    'KHH': ['KHH', 'KHHC'],               # 高雄港
}

# ==================== XML 輸出設定 ====================
# XML 輸出目錄
XML_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output', 'xml')
EXPORT_DIR = XML_OUTPUT_DIR  # 別名，向後兼容

# CSV 輸出目錄
CSV_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output', 'csv')

# Excel 輸出目錄
EXCEL_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output', 'excel')

# 確保所有輸出目錄存在
for output_dir in [XML_OUTPUT_DIR, EXPORT_DIR, CSV_OUTPUT_DIR, EXCEL_OUTPUT_DIR]:
    os.makedirs(output_dir, exist_ok=True)

# XML 編碼
XML_ENCODING = 'utf-8'

# XML 檔案前綴對應
XML_PREFIX_MAP = {
    'D005': 'berth_status',      # 船席現況及指泊表
    'D003': 'inbound_vessels',   # 進港船舶表
    'D004': 'outbound_vessels',  # 出港船舶表
}

# XML 根節點名稱
XML_ROOT_NAMES = {
    'D005': 'BerthStatusReport',
    'D003': 'InboundVesselsReport',
    'D004': 'OutboundVesselsReport',
}

# XML 記錄節點名稱
XML_RECORD_NAMES = {
    'D005': 'BerthRecord',
    'D003': 'InboundVessel',
    'D004': 'OutboundVessel',
}

# ✅ XML 欄位名稱對應（配合爬蟲模組的實際欄位）
XML_FIELD_NAMES = {
    # 共通欄位
    'report_type': 'ReportType',
    'port_code': 'PortCode',
    'port_name': 'PortName',
    'crawled_at': 'DataCrawlTime',
    'crawl_time': 'DataCrawlTime',  # 別名
    
    # 船舶基本資訊
    'vessel_cname': 'VesselChineseName',
    'vessel_ename': 'VesselEnglishName',
    'vessel_no': 'VesselNumber',
    'call_sign': 'CallSign',
    'imo': 'IMONumber',
    'ship_type': 'ShipType',
    'visa_no': 'VisaNumber',
    
    # 船舶規格
    'loa_m': 'LengthOverAll',
    'gt': 'GrossTonnage',
    
    # 泊位資訊
    'wharf_code': 'WharfCode',
    'wharf_name': 'WharfName',
    'berth': 'Berth',
    'alongside_status': 'AlongsideStatus',      # 現靠/接靠
    'mooring_type': 'MooringType',              # 靠泊方式
    'prev_wharf': 'PreviousWharf',              # 移泊前碼頭
    'movement_status': 'MovementStatus',        # 動態
    
    # 時間資訊 (D005)
    'eta_berth': 'EstimatedTimeToBerth',        # 預定靠泊時間
    'ata_berth': 'ActualTimeToBerth',           # 實際靠泊時間
    'etd_berth': 'EstimatedTimeToDepart',       # 預定離泊時間
    'eta_pilot': 'EstimatedPilotTime',          # 預定引水時間
    
    # 時間資訊 (D003)
    'eta_report': 'EstimatedTimeOfArrivalReport',    # 預報進港時間
    'vhf_report_time': 'VHFReportTime',              # VHF報到時間
    'anchor_time': 'AnchorTime',                     # 下錨時間
    'inport_pass_time': 'InportPassTime',            # 進港通過港口時間
    'captain_report_eta': 'CaptainReportETA',        # 船長報到ETA
    'inport_5nm_time': 'Inport5NMTime',              # 進港通過5浬時間
    
    # 時間資訊 (D004)
    'etd_report': 'EstimatedTimeOfDepartureReport',  # 預報出港時間
    'atd_berth': 'ActualTimeToDepart',               # 離泊時間
    'outport_pass_time': 'OutportPassTime',          # 出港通過港口時間
    
    # 港口資訊
    'prev_port': 'PreviousPort',
    'next_port': 'NextPort',
    'via_port': 'ViaPort',
    
    # 其他資訊
    'agent': 'ShippingAgent',
    'arrival_purpose': 'ArrivalPurpose',
    'isps_level': 'ISPSLevel',
    'can_berth_container': 'CanBerthContainer',  # 是否可停靠貨櫃碼頭
}

# XML 命名空間（可選）
XML_NAMESPACE = None  # 例如: 'http://www.twport.com.tw/schema/ifa'
XML_NAMESPACE_PREFIX = 'ifa'  # 命名空間前綴

# XML 格式化設定
XML_PRETTY_PRINT = True  # 是否格式化輸出
XML_INDENT = '  '  # 縮排字元（2 個空格）
XML_DECLARATION = True  # 是否包含 XML 宣告

# XML 檔案命名格式
XML_FILENAME_FORMAT = '{prefix}_{port_code}_{timestamp}.xml'
XML_TIMESTAMP_FORMAT = '%Y%m%d_%H%M%S'

# 是否在 XML 中包含空值欄位
XML_INCLUDE_NULL_FIELDS = False

# 是否在 XML 中包含爬取時間
XML_INCLUDE_CRAWL_TIME = True

# 是否在 XML 中包含統計資訊
XML_INCLUDE_STATISTICS = True

# XML 統計資訊欄位
XML_STATISTICS_FIELDS = [
    'total_records',
    'container_ships',
    'can_berth_container',  # ✅ 可停靠貨櫃碼頭數量
    'export_time',
    'data_source',
]

# 是否壓縮 XML 檔案
XML_COMPRESS = False
XML_COMPRESSION_LEVEL = 9

# 是否保留歷史檔案
XML_KEEP_HISTORY = True
XML_MAX_HISTORY_DAYS = 30

# CSV 設定
CSV_ENCODING = 'utf-8-sig'
CSV_SEPARATOR = ','
CSV_INCLUDE_INDEX = False

# Excel 設定
EXCEL_ENGINE = 'openpyxl'
EXCEL_SHEET_NAME_MAP = {
    'D005': '船席現況',
    'D003': '進港船舶',
    'D004': '出港船舶',
}

# ==================== 泊位分析設定 ====================
# 安全距離（公尺）
DEFAULT_SAFETY_BUFFER = 15
MIN_SAFETY_BUFFER = 5
MAX_SAFETY_BUFFER = 50

# 競合時窗（分鐘）
DEFAULT_COMPETITION_WINDOW = 60
MIN_COMPETITION_WINDOW = 15
MAX_COMPETITION_WINDOW = 180

# 預估停靠時長（小時）
DEFAULT_BERTH_DURATION = 12
MIN_BERTH_DURATION = 1
MAX_BERTH_DURATION = 48

# 泊位長度容差（公尺）
BERTH_LENGTH_TOLERANCE = 5

# 泊位剩餘空間閾值（公尺）
BERTH_AVAILABLE_THRESHOLD = 50  # 剩餘空間 > 50m 視為可用

# ==================== Perplexity AI 設定 ====================
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "deep_research"
perplexity_api_key = "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"

# AI 分析參數
AI_MAX_TOKENS = 4000
AI_TEMPERATURE = 0.2
AI_TIMEOUT = 120

# ==================== 資料欄位對應 ====================
# ✅ 修正：配合爬蟲模組的實際欄位（12+11, 11+11, 9+8）

D005_COLUMN_MAPPING = {
    # 港口資訊
    'port_code': 'port_code',
    'port_name': 'port_name',
    
    # 泊位資訊
    'wharf_code': 'wharf_code',
    'wharf_name': 'wharf_name',
    'alongside_status': 'alongside_status',      # 現靠/接靠
    'mooring_type': 'mooring_type',              # 靠泊方式
    'prev_wharf': 'prev_wharf',                  # 移泊前碼頭
    
    # 船舶基本資訊 (Row1)
    'vessel_no': 'vessel_no',                    # 船舶號數
    'ship_type': 'ship_type',                    # 船種
    'vessel_ename': 'vessel_ename',              # 英文船名
    'visa_no': 'visa_no',                        # 簽證編號
    
    # 船舶基本資訊 (Row2)
    'vessel_cname': 'vessel_cname',              # 中文船名
    'agent': 'agent',                            # 港口代理
    
    # 船舶規格
    'gt': 'gt',                                  # 總噸
    'loa_m': 'loa_m',                            # 船舶總長
    
    # 時間資訊 (Row1)
    'eta_berth': 'eta_berth',                    # 預定靠泊時間
    'etd_berth': 'etd_berth',                    # 預定離泊時間
    
    # 時間資訊 (Row2)
    'ata_berth': 'ata_berth',                    # 實際靠泊時間
    'eta_pilot': 'eta_pilot',                    # 預定引水時間
    
    # 港口資訊
    'prev_port': 'prev_port',                    # 前一港
    'next_port': 'next_port',                    # 次一港
    'via_port': 'via_port',                      # 通過港口
    
    # 其他資訊
    'arrival_purpose': 'arrival_purpose',        # 到港目的
    'movement_status': 'movement_status',        # 動態
    'isps_level': 'isps_level',                  # 保全等級
    'can_berth_container': 'can_berth_container', # 可停靠貨櫃碼頭
}

D003_COLUMN_MAPPING = {
    # 港口資訊
    'port_code': 'port_code',
    'port_name': 'port_name',
    
    # 船舶基本資訊 (Row1)
    'call_sign': 'call_sign',                    # 船舶呼號
    'ship_type': 'ship_type',                    # 船種
    'vessel_ename': 'vessel_ename',              # 英文船名
    'visa_no': 'visa_no',                        # 簽證編號
    
    # 船舶基本資訊 (Row2)
    'imo': 'imo',                                # IMO
    'agent': 'agent',                            # 港口代理
    'vessel_cname': 'vessel_cname',              # 中文船名
    
    # 船舶規格
    'loa_m': 'loa_m',                            # 船長(M)
    'gt': 'gt',                                  # 總噸
    
    # 時間資訊 (Row1)
    'eta_report': 'eta_report',                  # 預報進港時間
    'eta_berth': 'eta_berth',                    # 預定靠泊時間
    'vhf_report_time': 'vhf_report_time',        # VHF報到時間
    'anchor_time': 'anchor_time',                # 下錨時間
    
    # 時間資訊 (Row2)
    'inport_pass_time': 'inport_pass_time',      # 進港通過港口時間
    'etd_berth': 'etd_berth',                    # 預定離泊時間
    'ata_berth': 'ata_berth',                    # 靠泊時間
    'captain_report_eta': 'captain_report_eta',  # 船長報到ETA
    'inport_5nm_time': 'inport_5nm_time',        # 進港通過5浬時間
    
    # 港口資訊
    'berth': 'berth',                            # 靠泊碼頭
    'prev_port': 'prev_port',                    # 前一港
    'next_port': 'next_port',                    # 次一港
    
    # 其他資訊
    'arrival_purpose': 'arrival_purpose',        # 到港目的
    'can_berth_container': 'can_berth_container', # 可停靠貨櫃碼頭
}

D004_COLUMN_MAPPING = {
    # 港口資訊
    'port_code': 'port_code',
    'port_name': 'port_name',
    
    # 船舶基本資訊 (Row1)
    'call_sign': 'call_sign',                    # 船舶呼號
    'ship_type': 'ship_type',                    # 船種
    'vessel_ename': 'vessel_ename',              # 英文船名
    'visa_no': 'visa_no',                        # 簽證編號
    
    # 船舶基本資訊 (Row2)
    'imo': 'imo',                                # IMO
    'agent': 'agent',                            # 港口代理
    'vessel_cname': 'vessel_cname',              # 中文船名
    
    # 船舶規格
    'loa_m': 'loa_m',                            # 船長(M)
    
    # 時間資訊 (Row1)
    'etd_report': 'etd_report',                  # 預報出港時間
    'etd_berth': 'etd_berth',                    # 預定離泊時間
    
    # 時間資訊 (Row2)
    'outport_pass_time': 'outport_pass_time',    # 出港通過港口時間
    'atd_berth': 'atd_berth',                    # 離泊時間
    
    # 港口資訊
    'berth': 'berth',                            # 靠泊碼頭
    'prev_port': 'prev_port',                    # 前一港
    'next_port': 'next_port',                    # 次一港
    
    # 其他資訊
    'arrival_purpose': 'arrival_purpose',        # 到港目的
    'isps_level': 'isps_level',                  # 保全等級
    'can_berth_container': 'can_berth_container', # 可停靠貨櫃碼頭
}

# ==================== 標準化欄位定義 ====================
# ✅ 修正：配合爬蟲模組的實際欄位

STANDARD_COLUMNS = {
    'D005': [
        # 基本資訊
        'report_type', 'port_code', 'port_name',
        # 泊位資訊
        'wharf_code', 'wharf_name', 'alongside_status', 'mooring_type', 'prev_wharf',
        # 船舶基本資訊
        'vessel_no', 'ship_type', 'vessel_ename', 'vessel_cname', 'visa_no',
        # 船舶規格
        'gt', 'loa_m',
        # 時間資訊
        'eta_berth', 'ata_berth', 'etd_berth', 'eta_pilot',
        # 港口資訊
        'prev_port', 'next_port', 'via_port',
        # 其他資訊
        'agent', 'arrival_purpose', 'movement_status', 'isps_level',
        'can_berth_container', 'crawled_at',
    ],
    'D003': [
        # 基本資訊
        'report_type', 'port_code', 'port_name',
        # 船舶基本資訊
        'call_sign', 'ship_type', 'vessel_ename', 'vessel_cname', 'visa_no', 'imo',
        # 船舶規格
        'gt', 'loa_m',
        # 時間資訊
        'eta_report', 'eta_berth', 'ata_berth', 'etd_berth',
        'vhf_report_time', 'anchor_time', 'inport_pass_time',
        'captain_report_eta', 'inport_5nm_time',
        # 港口資訊
        'berth', 'prev_port', 'next_port',
        # 其他資訊
        'agent', 'arrival_purpose',
        'can_berth_container', 'crawled_at',
    ],
    'D004': [
        # 基本資訊
        'report_type', 'port_code', 'port_name',
        # 船舶基本資訊
        'call_sign', 'ship_type', 'vessel_ename', 'vessel_cname', 'visa_no', 'imo',
        # 船舶規格
        'loa_m',
        # 時間資訊
        'etd_report', 'etd_berth', 'atd_berth', 'outport_pass_time',
        # 港口資訊
        'berth', 'prev_port', 'next_port',
        # 其他資訊
        'agent', 'arrival_purpose', 'isps_level',
        'can_berth_container', 'crawled_at',
    ],
}

# ✅ 必要欄位（用於驗證）
COMMON_REQUIRED_FIELDS = ['port_code', 'port_name', 'vessel_ename', 'ship_type']

TIME_COLUMNS = {
    'D005': [
        'eta_berth', 'ata_berth', 'etd_berth', 'eta_pilot', 'crawled_at'
    ],
    'D003': [
        'eta_report', 'eta_berth', 'ata_berth', 'etd_berth',
        'vhf_report_time', 'anchor_time', 'inport_pass_time',
        'captain_report_eta', 'inport_5nm_time', 'crawled_at'
    ],
    'D004': [
        'etd_report', 'etd_berth', 'atd_berth', 'outport_pass_time', 'crawled_at'
    ],
}

NUMERIC_COLUMNS = ['loa_m', 'gt']

TEXT_COLUMNS = [
    'report_type', 'port_code', 'port_name',
    'wharf_code', 'wharf_name', 'berth',
    'vessel_cname', 'vessel_ename', 'vessel_no',
    'ship_type', 'agent', 'visa_no', 'imo', 'call_sign',
    'prev_port', 'next_port', 'via_port',
    'arrival_purpose', 'movement_status', 'isps_level',
    'alongside_status', 'mooring_type', 'prev_wharf',
]

# ==================== 資料驗證規則 ====================
# ✅ 修正：配合爬蟲模組
REQUIRED_FIELDS = {
    'D005': ['port_code', 'port_name', 'vessel_ename', 'ship_type', 'wharf_code'],
    'D003': ['port_code', 'port_name', 'vessel_ename', 'ship_type', 'eta_berth'],
    'D004': ['port_code', 'port_name', 'vessel_ename', 'ship_type', 'etd_berth'],
}

LOA_MIN = 10
LOA_MAX = 500

DATETIME_FORMATS = [
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d %H:%M',
    '%Y/%m/%d %H:%M:%S',
    '%Y/%m/%d %H:%M',
    '%m/%d %H:%M',
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%dT%H:%M:%S.%f',
    '%Y-%m-%dT%H:%M:%S%z',
]

# ==================== 視覺化設定 ====================
PLOT_COLORS = {
    'in_berth': '#2ecc71',
    'inbound': '#3498db',
    'outbound': '#e67e22',
    'eta_line': '#e74c3c',
    'target_window': '#f39c12',
}

PLOT_FONT_FAMILY = 'Microsoft JhengHei, Arial, sans-serif'
PLOT_FONT_SIZE = 12
PLOT_TITLE_SIZE = 18

GANTT_CHART_HEIGHT = 600
COMPETITION_CHART_HEIGHT = 400
UTILIZATION_CHART_HEIGHT = 500
DISTRIBUTION_CHART_HEIGHT = 400

# ==================== 日誌設定 ====================
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# ==================== 免責聲明 ====================
DISCLAIMER = """
**⚠️ 免責聲明**

1. **資料來源**: 本系統資料來自臺灣港務公司 IFA 系統，僅供參考。
2. **使用目的**: 本系統僅供港務作業研究與教育用途，不構成航行指令或法律建議。
3. **動態風險**: 靠泊作業涉及動態風險（天候、潮汐、交通流、臨時管制等），實際作業請以港務中心與船長指示為準。
4. **AI 分析**: AI 提供之分析僅供參考，不保證準確性與完整性。
5. **資料時效**: 船期資料可能隨時變動,請以最新官方資訊為準。
6. **責任限制**: 使用本系統所產生之任何損失，開發者與資料提供者不負任何責任。

**使用本系統即表示您已閱讀並同意以上聲明。**
"""

# ==================== 系統資訊 ====================
SYSTEM_INFO = {
    'name': APP_TITLE,
    'version': APP_VERSION,
    'author': 'Claude 4.5 Sonnet (Anthropic)',
    'license': 'MIT',
}

# ==================== 開發模式 ====================
DEBUG_MODE = os.getenv('DEBUG', 'False').lower() == 'true'

if DEBUG_MODE:
    SELENIUM_WAIT_TIMEOUT = 30
    SELENIUM_PAGE_LOAD_TIMEOUT = 60
    CACHE_TTL_MINUTES = 5
    LOG_LEVEL = 'DEBUG'

# ==================== 環境變數載入 ====================
def load_env():
    """載入環境變數"""
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            load_dotenv(env_path)
            return True
        return False
    except ImportError:
        return False

load_env()
perplexity_api_key = os.getenv('PERPLEXITY_API_KEY', perplexity_api_key)

# ==================== 輔助函數 ====================
def get_port_name(port_code):
    """取得港口名稱"""
    # ✅ 先轉換新舊代碼
    port_code = normalize_port_code(port_code)
    return PORTS.get(port_code, port_code)


def get_port_code(port_name_or_code):
    """取得標準港口代碼"""
    # 如果是代碼，轉換為標準代碼
    if port_name_or_code in PORT_CODE_MAPPING:
        return PORT_CODE_MAPPING[port_name_or_code]
    
    # 如果是名稱，查找對應代碼
    for code, name in PORTS.items():
        if name == port_name_or_code:
            return code
    
    return port_name_or_code


def normalize_port_code(port_code):
    """正規化港口代碼為標準格式"""
    if not port_code:
        return None
    
    port_code_upper = str(port_code).upper().strip()
    
    # 使用對應表轉換
    return PORT_CODE_MAPPING.get(port_code_upper, port_code_upper)


def get_report_url(report_type):
    """取得報表 URL"""
    return REPORT_URLS.get(report_type, '')


def is_target_ship_type(ship_type):
    """判斷是否為目標船種"""
    if not ship_type:
        return False
    
    ship_type_str = str(ship_type).lower()
    
    # 檢查所有目標船種的關鍵字
    target_types = SHIP_TYPE_MAPPING.get(TARGET_SHIP_NAME, [])
    for target in target_types:
        if target.lower() in ship_type_str:
            return True
    
    return False


def is_container_ship(ship_type):
    """判斷是否為貨櫃輪（別名）"""
    return is_target_ship_type(ship_type)


def is_container_cargo(cargo_type):
    """
    判斷貨物類型是否為貨櫃
    
    Args:
        cargo_type: 貨物類型字串
    
    Returns:
        bool: 是否為貨櫃貨物
    """
    if not cargo_type:
        return False
    
    cargo_type_str = str(cargo_type).lower()
    
    for keyword in CONTAINER_CARGO_KEYWORDS:
        if keyword.lower() in cargo_type_str:
            return True
    
    return False


def get_ship_type_name(ship_type_code):
    """根據船種代碼取得船種名稱"""
    return SHIP_TYPE_CODES.get(ship_type_code, ship_type_code)


def get_column_mapping(report_type):
    """取得欄位對應表"""
    mappings = {
        'D005': D005_COLUMN_MAPPING,
        'D003': D003_COLUMN_MAPPING,
        'D004': D004_COLUMN_MAPPING,
    }
    return mappings.get(report_type, {})


def get_standard_columns(report_type):
    """取得標準欄位列表"""
    return STANDARD_COLUMNS.get(report_type, [])


def get_time_columns(report_type):
    """取得時間欄位列表"""
    return TIME_COLUMNS.get(report_type, [])


# ✅ 新增：驗證配置
def validate_config():
    """驗證配置是否正確"""
    issues = []
    
    # 檢查必要目錄
    required_dirs = [XML_OUTPUT_DIR, CSV_OUTPUT_DIR, EXCEL_OUTPUT_DIR]
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            issues.append(f"目錄不存在: {dir_path}")
    
    # 檢查資料庫
    if not os.path.exists(Port_DB_Path):
        issues.append(f"泊位資料庫不存在: {Port_DB_Path}")
    
    # 檢查 API Key
    if not perplexity_api_key:
        issues.append("未設定 PERPLEXITY_API_KEY")
    
    # 檢查港口代碼
    for old_code, new_code in PORT_CODE_MAPPING.items():
        if new_code not in PORTS:
            issues.append(f"港口代碼對應錯誤: {old_code} -> {new_code}")
    
    # 檢查欄位對應
    for report_type in ['D005', 'D003', 'D004']:
        mapping = get_column_mapping(report_type)
        standard = get_standard_columns(report_type)
        
        # 檢查標準欄位是否都有對應
        for col in standard:
            if col not in ['report_type', 'crawled_at'] and col not in mapping.values():
                issues.append(f"{report_type}: 標準欄位 '{col}' 缺少對應")
    
    return issues


# 執行配置驗證
if __name__ == '__main__':
    print(f"=== {APP_TITLE} {APP_VERSION} ===\n")
    print("配置驗證:")
    
    issues = validate_config()
    if issues:
        print("⚠️ 發現問題:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✓ 配置正確")
    
    print(f"\n港口列表:")
    for code, name in PORTS.items():
        print(f"  {code}: {name}")
    
    print(f"\n報表 URL:")
    for report_type, url in REPORT_URLS.items():
        print(f"  {report_type}: {url}")
    
    print(f"\n標準欄位數量:")
    for report_type in ['D005', 'D003', 'D004']:
        cols = get_standard_columns(report_type)
        time_cols = get_time_columns(report_type)
        print(f"  {report_type}: {len(cols)} 欄位 (含 {len(time_cols)} 個時間欄位)")
    
    print(f"\n泊位資料庫:")
    print(f"  路徑: {Port_DB_Path}")
    print(f"  存在: {'✓' if os.path.exists(Port_DB_Path) else '✗'}")
    
    print(f"\n貨櫃碼頭判斷關鍵字:")
    for keyword in CONTAINER_CARGO_KEYWORDS:
        print(f"  - {keyword}")
    
    print("\n✓ 配置載入完成")
