import requests
import pandas as pd
from datetime import datetime, timedelta
import os
import sqlite3
from bs4 import BeautifulSoup
import time
import yfinance as yf

# 數據庫路徑
DB_PATH = "cn_water/hkex_southbound.db"
# 港股通 (南向資金) 持股紀錄 URL
HKEX_URL = "https://www3.hkexnews.hk/sdw/search/mutualmarket_c.aspx?t=hk"

def get_stock_price(stock_code, date_str):
    """從本地 CSV 或 yfinance 獲取股價"""
    # 1. 嘗試本地 CSV (針對歷史數據)
    short_code = stock_code.lstrip('0')
    paths = [
        f"prices/{stock_code}/{stock_code}_prices.csv",
        f"prices/{short_code}/{short_code}_prices.csv"
    ]
    for path in paths:
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                row = df[df['atDate'] == date_str]
                if not row.empty:
                    return float(row.iloc[0]['closing'])
            except: continue
    
    # 2. 如果是最近幾天的數據且本地無 CSV，嘗試 yfinance
    today_str = datetime.now().strftime('%Y-%m-%d')
    # 如果日期是今天或昨天，嘗試 yfinance
    if date_str >= (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d'):
        try:
            yf_code = f"{short_code}.HK"
            ticker = yf.Ticker(yf_code)
            # 獲取最新價格 (注意：這獲取的是實時/收盤現價)
            price = ticker.info.get('currentPrice') or ticker.info.get('regularMarketPrice')
            if price:
                print(f"  [yfinance] 獲取 {yf_code} 現價: {price}")
                return float(price)
        except: pass
        
    return None

def init_db():
    """初始化數據庫"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 創建持股紀錄表: date + stock_code 為聯合主鍵避免重複
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shareholding (
            date TEXT,
            stock_code TEXT,
            stock_name TEXT,
            shareholding INTEGER,
            percent REAL,
            price REAL,
            market_cap REAL,
            PRIMARY KEY (date, stock_code)
        )
    ''')
    conn.commit()
    conn.close()

def fetch_and_save(date_obj):
    """抓取指定日期的數據並存入數據庫"""
    date_str = date_obj.strftime('%Y/%m/%d')
    date_db = date_obj.strftime('%Y-%m-%d')
    
    print(f"正在從 HKEX 獲取 {date_str} 的港股通持股數據...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    session = requests.Session()
    try:
        # 1. 獲取頁面拿到必要的 ASP.NET 隱藏參數
        r = session.get(HKEX_URL, headers=headers)
        soup = BeautifulSoup(r.text, 'lxml')
        
        def find_input(name):
            node = soup.find('input', {'name': name})
            return node['value'] if node else ""

        viewstate = find_input('__VIEWSTATE')
        viewstate_gen = find_input('__VIEWSTATEGENERATOR')
        eventvalidation = find_input('__EVENTVALIDATION')
        
        if not viewstate:
            print(f"❌ 無法獲取 __VIEWSTATE，港交所頁面結構可能已變更。")
            return False
        
        # 2. 構造 POST 請求模擬點擊「搜尋」
        post_data = {
            '__VIEWSTATE': viewstate,
            '__VIEWSTATEGENERATOR': viewstate_gen,
            '__EVENTVALIDATION': eventvalidation,
            'today': datetime.now().strftime('%Y%m%d'),
            'sortBy': '',
            'sortDirection': '',
            'alertMsg': '',
            'txtShareholdingDate': date_str,
            'btnSearch': '搜尋'
        }
        
        response = session.post(HKEX_URL, data=post_data, headers=headers)
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 修正：自動過濾非交易日的錯誤數據
        # 檢查頁面上實際顯示的日期。如果港交所返回的是「最近交易日」而不是我們請求的日期，則跳過。
        actual_date_node = soup.find('input', {'name': 'txtShareholdingDate'})
        if actual_date_node:
            actual_date_str = actual_date_node.get('value', '') # 格式通常為 2026/05/04
            if actual_date_str != date_str:
                print(f"⏩ 跳過 {date_str}: 港交所返回實際日期為 {actual_date_str} (可能是週末或假期)")
                return False

        # 3. 解析結果表格
        # 港股通(南向) 頁面的表格 ID 通常是 'mutualmarket-result'
        table = soup.find('table', {'id': 'mutualmarket-result'})
        if not table:
            # A股(北向) 頁面的表格 ID 可能是 'tableShareholdingSearch'
            table = soup.find('table', {'id': 'tableShareholdingSearch'})
            
        if not table:
            print(f"⚠️ {date_str} 沒有找到表格數據 (可能是週末、假期或數據尚未上傳)")
            return False
            
        rows = table.find('tbody').find_all('tr')
        records = []
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 4:
                # 解析邏輯適配：
                # 第一欄可能帶有 mobile-list-body 的 div
                def get_clean_text(td):
                    div = td.find('div', {'class': 'mobile-list-body'})
                    return div.get_text(strip=True) if div else td.get_text(strip=True)

                code = get_clean_text(cols[0])
                name = get_clean_text(cols[1])
                holding_str = get_clean_text(cols[2]).replace(',', '')
                percent_str = get_clean_text(cols[3]).replace('%', '')
                
                try:
                    holding = int(holding_str)
                    percent = float(percent_str)
                    # 格式化代號 (確保代號為 5 位，例如 700 -> 00700)
                    if code.isdigit():
                        code = code.zfill(5)
                    
                    # 嘗試獲取股價並計算市值
                    price = get_stock_price(code, date_db)
                    mkt_cap = (holding / (percent / 100)) * price if price and percent > 0 else None
                    
                    records.append((date_db, code, name, holding, percent, price, mkt_cap))
                except (ValueError, ZeroDivisionError):
                    continue
        
        # 4. 寫入數據庫
        if records:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT OR REPLACE INTO shareholding (date, stock_code, stock_name, shareholding, percent, price, market_cap)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', records)
            conn.commit()
            conn.close()
            print(f"✅ 成功保存 {len(records)} 條 {date_db} 的紀錄。")
            return True
            
    except Exception as e:
        print(f"❌ 處理 {date_str} 時出錯: {e}")
        return False

def get_change_report(stock_code, days_list=[5, 10, 20, 60]):
    """獲取特定股票在不同時間跨度的持股變化"""
    conn = sqlite3.connect(DB_PATH)
    
    # 獲取最新的一條紀錄作為基準
    latest_query = "SELECT date, shareholding, percent, stock_name FROM shareholding WHERE stock_code = ? ORDER BY date DESC LIMIT 1"
    latest_df = pd.read_sql_query(latest_query, conn, params=(stock_code,))
    
    if latest_df.empty:
        conn.close()
        return f"數據庫中找不到股票 {stock_code} 的紀錄。"
    
    latest_val = latest_df.iloc[0]
    results = {
        "stock": f"{latest_val['stock_name']} ({stock_code})",
        "latest_date": latest_val['date'],
        "current_holding": latest_val['shareholding'],
        "changes": {}
    }
    
    for d in days_list:
        # 尋找約 d 天前的最接近紀錄
        past_date = (datetime.strptime(latest_val['date'], '%Y-%m-%d') - timedelta(days=d)).strftime('%Y-%m-%d')
        past_query = "SELECT date, shareholding, percent FROM shareholding WHERE stock_code = ? AND date <= ? ORDER BY date DESC LIMIT 1"
        past_df = pd.read_sql_query(past_query, conn, params=(stock_code, past_date))
        
        if not past_df.empty:
            past_val = past_df.iloc[0]
            diff_shares = latest_val['shareholding'] - past_val['shareholding']
            diff_pct = latest_val['percent'] - past_val['percent']
            results["changes"][f"{d}d"] = {
                "from_date": past_val['date'],
                "share_diff": diff_shares,
                "pct_diff": round(diff_pct, 3)
            }
    
    conn.close()
    return results

if __name__ == "__main__":
    init_db()
    
    # 1. 抓取近期數據 (往回抓 400 天，確保持倉對比有足夠數據)
    print("--- 開始同步歷史數據 (預計耗時幾分鐘) ---")
    for i in range(1, 401): 
        target = datetime.now() - timedelta(days=i)
        success = fetch_and_save(target)
        if success:
            time.sleep(0.5) # 有數據時稍微停頓，避免被封 IP
        else:
            time.sleep(0.1) # 無數據時快一點
        
    # 2. 測試分析功能 (以騰訊 0700 為例)
    print("\n--- 變化分析範例 (00700) ---")
    analysis = get_change_report("00700")
    if isinstance(analysis, dict):
        print(f"股票: {analysis['stock']}")
        for period, data in analysis['changes'].items():
            print(f"近 {period} (自 {data['from_date']}): 持股變動 {data['share_diff']:,} 股, 佔比變動 {data['pct_diff']}%")
    else:
        print(analysis)

