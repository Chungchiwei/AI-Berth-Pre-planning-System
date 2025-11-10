#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
檢查 save_to_database 函數定義
"""

import re

def check_save_function():
    """檢查 save_to_database 函數的參數定義"""
    
    crawler_path = 'modules/selenium_crawler.py'
    
    try:
        with open(crawler_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 搜尋函數定義
        pattern = r'def\s+save_to_database\s*\(([^)]+)\)'
        matches = re.finditer(pattern, content)
        
        found = False
        for match in matches:
            found = True
            params = match.group(1)
            
            # 找到函數定義的行號
            lines = content[:match.start()].split('\n')
            line_num = len(lines)
            
            print(f"🔍 找到 save_to_database 函數定義")
            print(f"📍 位置: 第 {line_num} 行")
            print(f"📋 參數: {params}")
            print()
            
            # 分析參數
            param_list = [p.strip() for p in params.split(',')]
            print(f"📊 參數數量: {len(param_list)}")
            print("📝 參數列表:")
            for i, param in enumerate(param_list, 1):
                print(f"   {i}. {param}")
            
            print("\n" + "="*60 + "\n")
        
        if not found:
            print("❌ 未找到 save_to_database 函數定義")
            print("\n建議:")
            print("1. 檢查函數名稱是否拼寫正確")
            print("2. 檢查是否在其他檔案中定義")
            return
        
        # 搜尋函數呼叫
        call_pattern = r'save_to_database\s*\(([^)]+)\)'
        calls = re.finditer(call_pattern, content)
        
        print("🔍 找到的函數呼叫:")
        print()
        
        for i, call in enumerate(calls, 1):
            args = call.group(1)
            
            # 找到呼叫的行號
            lines = content[:call.start()].split('\n')
            line_num = len(lines)
            
            # 計算參數數量
            arg_list = [a.strip() for a in args.split(',') if a.strip()]
            
            print(f"呼叫 #{i}:")
            print(f"   位置: 第 {line_num} 行")
            print(f"   參數數量: {len(arg_list)}")
            print(f"   參數: {args[:100]}{'...' if len(args) > 100 else ''}")
            print()
        
    except FileNotFoundError:
        print(f"❌ 找不到檔案: {crawler_path}")
    except Exception as e:
        print(f"❌ 發生錯誤: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_save_function()
