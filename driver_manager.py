"""
WebDriver 管理模組 - 支援本地 ChromeDriver 和自動下載
"""
import os
import sys
import platform
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
import streamlit as st

# 本地 ChromeDriver 路徑
LOCAL_CHROMEDRIVER_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'drivers', 'chromedriver.exe')

def get_chrome_options(headless=True):
    """獲取 Chrome 選項配置"""
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument('--headless=new')
    
    # 基本設定
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # 效能優化
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-logging')
    chrome_options.add_argument('--log-level=3')
    chrome_options.page_load_strategy = 'eager'
    
    # 設定 User-Agent
    chrome_options.add_argument(
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    )
    
    # 忽略證書錯誤
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--ignore-ssl-errors')
    
    # 實驗性選項
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    return chrome_options

def init_driver_local(headless=True):
    """使用本地 ChromeDriver 初始化"""
    try:
        if not os.path.exists(LOCAL_CHROMEDRIVER_PATH):
            return None, f"本地 ChromeDriver 不存在: {LOCAL_CHROMEDRIVER_PATH}"
        
        chrome_options = get_chrome_options(headless)
        service = Service(executable_path=LOCAL_CHROMEDRIVER_PATH)
        
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        return driver, "✓ 使用本地 ChromeDriver"
        
    except Exception as e:
        return None, f"本地 ChromeDriver 初始化失敗: {str(e)}"

def init_driver_webdriver_manager(headless=True):
    """使用 webdriver-manager 自動下載"""
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.core.os_manager import ChromeType
        
        chrome_options = get_chrome_options(headless)
        
        # 嘗試使用淘寶鏡像（中國大陸用戶）
        os.environ['WDM_CHROME_DRIVER_MIRROR'] = 'https://registry.npmmirror.com/-/binary/chromedriver/'
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        return driver, "✓ 使用 webdriver-manager 自動下載"
        
    except Exception as e:
        return None, f"webdriver-manager 失敗: {str(e)}"

def init_driver_system_path(headless=True):
    """使用系統 PATH 中的 ChromeDriver"""
    try:
        chrome_options = get_chrome_options(headless)
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        return driver, "✓ 使用系統 PATH 中的 ChromeDriver"
        
    except Exception as e:
        return None, f"系統 PATH ChromeDriver 失敗: {str(e)}"

def init_driver(headless=True, show_status=True):
    """
    初始化 WebDriver（多種方式嘗試）
    
    優先順序:
    1. 本地 drivers/chromedriver.exe
    2. webdriver-manager 自動下載
    3. 系統 PATH
    """
    methods = [
        ("本地 ChromeDriver", init_driver_local),
        ("webdriver-manager", init_driver_webdriver_manager),
        ("系統 PATH", init_driver_system_path),
    ]
    
    for method_name, method_func in methods:
        if show_status:
            with st.spinner(f"嘗試使用 {method_name}..."):
                driver, message = method_func(headless)
        else:
            driver, message = method_func(headless)
        
        if driver:
            if show_status:
                st.success(message)
            return driver
        else:
            if show_status:
                st.warning(message)
    
    # 所有方法都失敗
    error_msg = """
    ❌ **無法初始化 Chrome WebDriver**
    
    請嘗試以下解決方案：
    
    ### 方案 1: 使用本地 ChromeDriver（推薦）
    
    1. **檢查 Chrome 版本**
       - 開啟 Chrome 瀏覽器
       - 網址列輸入: `chrome://version/`
       - 記下版本號（例如：131.0.6778.86）
    
    2. **下載對應版本**
       - 訪問: https://googlechromelabs.github.io/chrome-for-testing/
       - 或使用鏡像: https://registry.npmmirror.com/-/binary/chromedriver/
    
    3. **放置 ChromeDriver**
       - 解壓縮下載的檔案
       - 將 `chromedriver.exe` 放到專案的 `drivers` 資料夾
       - 完整路徑應為: `{LOCAL_CHROMEDRIVER_PATH}`
    
    ### 方案 2: 升級 webdriver-manager
    
    ```bash
    pip install webdriver-manager --upgrade
    ```
    
    ### 方案 3: 手動加入系統 PATH
    
    1. 下載 ChromeDriver
    2. 將 `chromedriver.exe` 放到 `C:\\Windows\\System32\\`
    3. 或加入自訂路徑到系統環境變數
    
    ### 檢查清單
    
    - [ ] 已安裝 Chrome 瀏覽器
    - [ ] Chrome 版本與 ChromeDriver 版本相符
    - [ ] 防火牆未阻擋下載
    - [ ] 網路連線正常
    """
    
    if show_status:
        st.error(error_msg)
    
    raise WebDriverException(error_msg)

def check_driver_status():
    """檢查 WebDriver 狀態（用於診斷）"""
    status = {
        'local_exists': os.path.exists(LOCAL_CHROMEDRIVER_PATH),
        'local_path': LOCAL_CHROMEDRIVER_PATH,
        'system': platform.system(),
        'python_version': sys.version,
    }
    
    # 檢查 Chrome 是否安裝
    try:
        if platform.system() == 'Windows':
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ]
            status['chrome_installed'] = any(os.path.exists(p) for p in chrome_paths)
        else:
            status['chrome_installed'] = True  # Linux/Mac 假設已安裝
    except:
        status['chrome_installed'] = False
    
    # 檢查 webdriver-manager
    try:
        import webdriver_manager
        status['webdriver_manager_installed'] = True
        status['webdriver_manager_version'] = webdriver_manager.__version__
    except ImportError:
        status['webdriver_manager_installed'] = False
    
    return status

# 測試函數
if __name__ == "__main__":
    print("=== WebDriver 狀態檢查 ===")
    status = check_driver_status()
    
    for key, value in status.items():
        print(f"{key}: {value}")
    
    print("\n=== 嘗試初始化 WebDriver ===")
    try:
        driver = init_driver(headless=True, show_status=False)
        print("✓ WebDriver 初始化成功！")
        driver.quit()
    except Exception as e:
        print(f"✗ WebDriver 初始化失敗: {e}")
