"""
測試船泊地爬蟲
"""
from modules.anchored_ships_crawler import AnchoredShipsCrawler
import pandas as pd

def test_crawler():
    """測試爬蟲功能"""
    
    print("="*60)
    print("🧪 船泊地爬蟲測試")
    print("="*60)
    
    # 初始化爬蟲
    crawler = AnchoredShipsCrawler(verbose=True)
    
    # 測試 1: 取得 CSRF Token
    print("\n【測試 1】取得 CSRF Token")
    print("-"*60)
    if crawler.get_csrf_token():
        print(f"✅ Token: {crawler.token[:30]}...")
        print(f"✅ Token 時間: {crawler.last_token_time}")
    else:
        print("❌ Token 取得失敗")
        return
    
    # 測試 2: 爬取單一港口（臺北港）
    print("\n【測試 2】爬取臺北港資料")
    print("-"*60)
    df_tpe = crawler.fetch_anchored_ships('TPE')
    
    if not df_tpe.empty:
        print(f"✅ 成功爬取 {len(df_tpe)} 筆資料")
        print(f"\n📊 資料欄位:")
        print(df_tpe.columns.tolist())
        print(f"\n📋 前 3 筆資料:")
        print(df_tpe.head(3))
        
        # 檢查關鍵欄位
        print(f"\n🔍 關鍵欄位檢查:")
        key_columns = ['船名_中文', '船名_英文', '錨泊時間', '船舶類型', '噸位']
        for col in key_columns:
            if col in df_tpe.columns:
                non_null = df_tpe[col].notna().sum()
                print(f"  ✅ {col}: {non_null}/{len(df_tpe)} 筆有值")
            else:
                print(f"  ❌ {col}: 欄位不存在")
        
        # 資料型態檢查
        print(f"\n📝 資料型態:")
        print(df_tpe.dtypes)
        
    else:
        print("⚠️ 臺北港目前無船泊地資料（或爬取失敗）")
    
    # 測試 3: 爬取高雄港
    print("\n【測試 3】爬取高雄港資料")
    print("-"*60)
    df_khh = crawler.fetch_anchored_ships('KHH')
    
    if not df_khh.empty:
        print(f"✅ 成功爬取 {len(df_khh)} 筆資料")
        print(f"📋 前 3 筆資料:")
        print(df_khh.head(3))
    else:
        print("⚠️ 高雄港目前無船泊地資料（或爬取失敗）")
    
    # 測試 4: 資料統計
    print("\n【測試 4】資料統計")
    print("-"*60)
    
    all_data = {}
    if not df_tpe.empty:
        all_data['臺北港'] = df_tpe
    if not df_khh.empty:
        all_data['高雄港'] = df_khh
    
    if all_data:
        stats = crawler.get_statistics(all_data)
        print(f"📊 統計結果:")
        print(f"  總筆數: {stats['總筆數']}")
        print(f"  港口數: {stats['港口數']}")
        print(f"  各港口統計:")
        for port, info in stats['各港口統計'].items():
            print(f"    • {port}: {info['船舶數']} 艘")
    
    # 測試 5: 儲存 CSV
    print("\n【測試 5】儲存 CSV")
    print("-"*60)
    
    if all_data:
        saved_df = crawler.save_to_csv(
            all_data, 
            filename='test_anchored_ships.csv',
            output_dir='test_output'
        )
        
        if saved_df is not None:
            print(f"✅ 成功儲存 {len(saved_df)} 筆資料")
        else:
            print("❌ 儲存失敗")
    
    # 測試 6: Token 過期檢查
    print("\n【測試 6】Token 過期檢查")
    print("-"*60)
    
    is_expired = crawler._is_token_expired()
    print(f"Token 是否過期: {'是' if is_expired else '否'}")
    
    if crawler.last_token_time:
        from datetime import datetime
        elapsed = (datetime.now() - crawler.last_token_time).total_seconds()
        print(f"Token 已存在: {elapsed:.0f} 秒")
    
    print("\n" + "="*60)
    print("🎉 測試完成")
    print("="*60)


def test_response_format():
    """測試 API 回應格式"""
    
    print("\n【額外測試】API 回應格式分析")
    print("-"*60)
    
    crawler = AnchoredShipsCrawler(verbose=True)
    
    if not crawler.get_csrf_token():
        print("❌ 無法取得 Token")
        return
    
    import requests
    
    url = f"{crawler.base_url}/IFAWeb/Board/PortStatus/LoadAnchoredShips"
    
    payload = {
        'portId': 'TPE',
        'wharfType': '',
        'wharfCode': '',
        'shipGroup': '',
        'vesselNo': '',
        'vesselCname': '',
        'vesselEname': '',
        'registerNoI': '',
        'callSign': '',
        'startDt': '',
        '__RequestVerificationToken': crawler.token
    }
    
    try:
        response = crawler.session.post(url, data=payload, timeout=30)
        
        print(f"狀態碼: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n📦 回應資料結構:")
            print(f"  類型: {type(data)}")
            
            if isinstance(data, dict):
                print(f"  Keys: {list(data.keys())}")
                
                # 檢查可能的資料位置
                for key in ['data', 'result', 'items', 'ships', 'list']:
                    if key in data:
                        print(f"\n  ✅ 找到資料 key: '{key}'")
                        print(f"     類型: {type(data[key])}")
                        
                        if isinstance(data[key], list) and len(data[key]) > 0:
                            print(f"     筆數: {len(data[key])}")
                            print(f"     第一筆資料 keys:")
                            print(f"     {list(data[key][0].keys())}")
            
            elif isinstance(data, list):
                print(f"  直接為 list，筆數: {len(data)}")
                if len(data) > 0:
                    print(f"  第一筆資料 keys:")
                    print(f"  {list(data[0].keys())}")
            
            # 顯示原始回應（前 500 字元）
            print(f"\n📄 原始回應（前 500 字元）:")
            print(response.text[:500])
        
        else:
            print(f"❌ 請求失敗: {response.status_code}")
            print(f"回應內容: {response.text[:200]}")
    
    except Exception as e:
        print(f"❌ 測試失敗: {str(e)}")


def test_all_ports():
    """測試所有港口"""
    
    print("\n【完整測試】所有港口爬取")
    print("="*60)
    
    crawler = AnchoredShipsCrawler(verbose=True)
    
    all_data = crawler.fetch_all_ports(delay=2.0)
    
    print("\n📊 最終統計:")
    print("-"*60)
    
    total_ships = 0
    for port_name, df in all_data.items():
        ship_count = len(df)
        total_ships += ship_count
        print(f"  {port_name}: {ship_count} 艘")
    
    print(f"\n  總計: {total_ships} 艘")
    
    # 儲存合併資料
    if all_data:
        crawler.save_to_csv(
            all_data,
            filename='all_ports_anchored_ships.csv',
            output_dir='test_output'
        )


if __name__ == '__main__':
    # 執行基本測試
    test_crawler()
    
    # 執行 API 格式測試
    test_response_format()
    
    # 執行完整測試（可選，會花較長時間）
    # test_all_ports()
