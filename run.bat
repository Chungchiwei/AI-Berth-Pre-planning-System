@echo off
chcp 65001
echo ========================================
echo   AI 船期泊位管理系統
echo   啟動中...
echo ========================================
echo.

REM 檢查 Python 是否安裝
python --version >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 Python，請先安裝 Python 3.8 或以上版本
    pause
    exit /b 1
)

REM 檢查虛擬環境
if not exist "venv" (
    echo [提示] 建立虛擬環境...
    python -m venv venv
)

REM 啟動虛擬環境
call venv\Scripts\activate.bat

REM 安裝依賴
echo [提示] 檢查依賴套件...
pip install -r requirements.txt --quiet

REM 啟動 Streamlit
echo.
echo [提示] 啟動 Streamlit 應用...
echo ========================================
streamlit run app.py

pause
