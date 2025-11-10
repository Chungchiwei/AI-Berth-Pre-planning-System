# modules/__init__.py
import sys
import os

# 添加專案根目錄到路徑
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)