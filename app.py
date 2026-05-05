from flask import Flask, render_template, request, jsonify
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import calendar
import os
import time
import re
from io import StringIO
from urllib.request import Request, urlopen
import yfinance as yf
import json

try:
    import cloudscraper
except Exception:
    cloudscraper = None

app = Flask(__name__)
# 支持 Replit 和本地運行（獨立仓库）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv('DB_PATH', os.path.join(BASE_DIR, 'hkex_southbound.db'))

# 英文行業自動轉中文；無對應時保留英文
SECTOR_ZH_MAP = {
    'Technology': '科技',
    'Financial Services': '金融服務',
    'Healthcare': '醫療保健',
    'Consumer Cyclical': '非必需消費',
    'Consumer Defensive': '必需消費',
    'Communication Services': '通訊服務',
    'Industrials': '工業',
    'Energy': '能源',
    'Basic Materials': '基礎材料',
    'Real Estate': '房地產',
    'Utilities': '公用事業',
    'Materials': '原材料',
}

INDUSTRY_ZH_MAP = {
    'Internet Content & Information': '互聯網內容與資訊',
    'Semiconductors': '半導體',
    'Semiconductor Equipment & Materials': '半導體設備及材料',
    'Software - Infrastructure': '基建軟件',
    'Software - Application': '應用軟件',
    'Consumer Electronics': '消費電子',
    'Electronic Components': '電子元件',
    'Solar': '太陽能',
    'Solar Equipment & Services': '太陽能設備及服務',
    'Electrical Equipment & Parts': '電力設備及零件',
    'Specialty Industrial Machinery': '專用工業機械',
    'Industrial Machinery': '工業機械',
    'Auto Parts': '汽車零件',
    'Auto Manufacturers': '汽車製造',
    'Farm & Heavy Construction Machinery': '農業及重型建築機械',
    'Banks - Regional': '地區銀行',
    'Banks - Diversified': '綜合銀行',
    'Insurance - Diversified': '綜合保險',
    'Insurance Brokers': '保險經紀',
    'Insurance - Life': '人壽保險',
    'Insurance - Property & Casualty': '財產及意外保險',
    'Asset Management': '資產管理',
    'Capital Markets': '資本市場',
    'Financial Conglomerates': '綜合金融',
    'Credit Services': '信貸服務',
    'Biotechnology': '生物科技',
    'Drug Manufacturers - General': '藥品製造（綜合）',
    'Drug Manufacturers - Specialty & Generic': '藥品製造（專科及仿製藥）',
    'Medical Devices': '醫療器械',
    'Medical Care Facilities': '醫療服務機構',
    'Oil & Gas Integrated': '綜合油氣',
    'Oil & Gas E&P': '油氣勘探與生產',
    'Oil & Gas Midstream': '油氣中游',
    'Oil & Gas Refining & Marketing': '油氣煉化及銷售',
    'Telecom Services': '電訊服務',
    'Telecom Services - Domestic': '本地電訊服務',
    'Telecom Services - Foreign': '國際電訊服務',
    'Utilities - Regulated Electric': '公用事業（電力）',
    'Utilities - Renewable': '公用事業（新能源）',
    'REIT - Retail': '房託（零售）',
    'REIT - Diversified': '房託（綜合）',
    'Gold': '黃金',
    'Other Precious Metals & Mining': '其他貴金屬及採礦',
    'Copper': '銅業',
    'Steel': '鋼鐵',
    'Coking Coal': '焦煤',
    'Thermal Coal': '動力煤',
    'Aluminum': '鋁業',
    'Marine Shipping': '航運',
    'Shipping & Ports': '航運及港口',
    'Airlines': '航空公司',
    'Airports & Air Services': '機場及航空服務',
    'Real Estate - Development': '房地產開發',
    'Apparel Manufacturing': '服裝製造',
    'Real Estate Services': '房地產服務',
    'Medical Distribution': '醫藥流通',
    'Infrastructure Operations': '基礎設施運營',
    'Specialty Retail': '專營零售',
    'Health Information Services': '健康資訊服務',
    'Information Technology Services': '資訊科技服務',
    'Advertising Agencies': '廣告代理',
    'Aerospace & Defense': '航空航天與國防',
    'Real Estate - Diversified': '綜合房地產',
    'Education & Training Services': '教育培訓及服務',
    'Industrial Distribution': '工業物資分銷',
    'Waste Management': '廢品處理',
    'Railroads': '鐵路運輸',
    'Trucking': '貨車運輸',
    'Integrated Freight & Logistics': '綜合貨運及物流',
    'Logistics': '物流',
    'Engineering & Construction': '工程及建築',
    'Building Materials': '建材',
    'Conglomerates': '綜合企業',
    'Packaging & Containers': '包裝及容器',
    'Restaurants': '餐飲',
    'Travel Services': '旅遊服務',
    'Lodging': '酒店住宿',
    'Entertainment': '娛樂',
    'Gambling': '博彩',
    'Apparel Retail': '服裝零售',
    'Luxury Goods': '奢侈品',
    'Footwear & Accessories': '鞋履及配飾',
    'Discount Stores': '折扣零售',
    'Household & Personal Products': '家居及個人用品',
    'Beverages - Non-Alcoholic': '非酒精飲料',
    'Packaged Foods': '包裝食品',
    'Communication Equipment': '通訊設備',
    'Specialty Chemicals': '特種化學品',
    'Farm Products': '農產品',
    'Computer Hardware': '電腦硬件',
    'Other Industrial Metals & Mining': '其他工業金屬及採礦',
    'Building Products & Equipment': '建築產品及設備',
    'Chemicals': '化工基礎實體',
    'Electronic Gaming & Multimedia': '電子遊戲與多媒體',
    'Broadcasting': '廣播',
}


def map_to_zh(text, mapping):
    if not text:
        return text
    s = str(text).strip()
    if not s:
        return text
    return mapping.get(s, s)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def fetch_market_cap_from_yf(stock_code):
    """Use yfinance to fetch current market cap and price for HK stock."""
    raw = str(int(stock_code)) if stock_code.isdigit() else stock_code.lstrip('0')
    candidates = []
    if raw:
        candidates.append(f"{raw.zfill(4)}.HK")
        candidates.append(f"{raw}.HK")

    for yf_symbol in candidates:
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info or {}
        market_cap = info.get('marketCap')
        price = info.get('currentPrice') or info.get('regularMarketPrice')
        volume = info.get('volume')
        float_shares = info.get('floatShares')
        fifty_two_week_high = info.get('fiftyTwoWeekHigh')
        fifty_two_week_low = info.get('fiftyTwoWeekLow')
        sector = info.get('sector')
        industry = info.get('industry')

        listing_date = None
        try:
            # Try to get listing date (earliest history date)
            hist_max = ticker.history(period='max')
            if not hist_max.empty:
                listing_date = hist_max.index[0].strftime('%Y-%m-%d')
        except Exception:
            pass

        volume_ratio_5d = None
        volume_ratio_20d = None
        turnover_rate_float = None

        try:
            hist = ticker.history(period='3mo', interval='1d', auto_adjust=False)
            if not hist.empty and 'Volume' in hist.columns:
                volumes = hist['Volume'].dropna()
                if not volumes.empty:
                    current_volume = volume if volume is not None else float(volumes.iloc[-1])
                    prev_volumes = volumes.iloc[:-1] if len(volumes) > 1 else volumes.iloc[0:0]
                    if current_volume is not None and len(prev_volumes) >= 1:
                        avg_5d = prev_volumes.tail(5).mean() if len(prev_volumes.tail(5)) > 0 else None
                        avg_20d = prev_volumes.tail(20).mean() if len(prev_volumes.tail(20)) > 0 else None
                        if avg_5d and avg_5d > 0:
                            volume_ratio_5d = float(current_volume) / float(avg_5d)
                        if avg_20d and avg_20d > 0:
                            volume_ratio_20d = float(current_volume) / float(avg_20d)
        except Exception:
            pass

        if volume is not None and float_shares:
            try:
                if float_shares > 0:
                    turnover_rate_float = float(volume) / float(float_shares)
            except Exception:
                turnover_rate_float = None

        if any(v is not None for v in [market_cap, price, fifty_two_week_high, fifty_two_week_low, sector, industry, turnover_rate_float, volume_ratio_5d, volume_ratio_20d, listing_date]):
            return {
                'market_cap': market_cap,
                'price': price,
                'turnover_rate_float': turnover_rate_float,
                'volume_ratio_5d': volume_ratio_5d,
                'volume_ratio_20d': volume_ratio_20d,
                'fifty_two_week_high': fifty_two_week_high,
                'fifty_two_week_low': fifty_two_week_low,
                'sector': sector,
                'industry': industry,
                'listing_date': listing_date,
                'yf_symbol': yf_symbol,
            }

    return {
        'market_cap': None,
        'price': None,
        'turnover_rate_float': None,
        'volume_ratio_5d': None,
        'volume_ratio_20d': None,
        'fifty_two_week_high': None,
        'fifty_two_week_low': None,
        'sector': None,
        'industry': None,
        'listing_date': None,
        'yf_symbol': candidates[0] if candidates else None,
    }


def ensure_stock_meta_table(conn):
    """Create stock_meta table if it doesn't exist."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS stock_meta (
            stock_code TEXT PRIMARY KEY,
            listing_date TEXT,
            concentration_top5 REAL,
            concentration_top10 REAL,
            concentration_stake REAL,
            concentration_date TEXT,
            fifty_two_week_high REAL,
            fifty_two_week_low REAL,
            turnover_rate_float REAL,
            volume_ratio_5d REAL,
            volume_ratio_20d REAL,
            sector TEXT,
            industry TEXT
        )
    ''')

    # Backward compatible migration for older schema.
    existing_cols = {
        row[1] for row in conn.execute("PRAGMA table_info(stock_meta)").fetchall()
    }
    if 'concentration_top5' not in existing_cols:
        conn.execute("ALTER TABLE stock_meta ADD COLUMN concentration_top5 REAL")
    if 'concentration_top10' not in existing_cols:
        conn.execute("ALTER TABLE stock_meta ADD COLUMN concentration_top10 REAL")
    if 'concentration_stake' not in existing_cols:
        conn.execute("ALTER TABLE stock_meta ADD COLUMN concentration_stake REAL")
    if 'concentration_date' not in existing_cols:
        conn.execute("ALTER TABLE stock_meta ADD COLUMN concentration_date TEXT")
    if 'fifty_two_week_high' not in existing_cols:
        conn.execute("ALTER TABLE stock_meta ADD COLUMN fifty_two_week_high REAL")
    if 'fifty_two_week_low' not in existing_cols:
        conn.execute("ALTER TABLE stock_meta ADD COLUMN fifty_two_week_low REAL")
    if 'turnover_rate_float' not in existing_cols:
        conn.execute("ALTER TABLE stock_meta ADD COLUMN turnover_rate_float REAL")
    if 'volume_ratio_5d' not in existing_cols:
        conn.execute("ALTER TABLE stock_meta ADD COLUMN volume_ratio_5d REAL")
    if 'volume_ratio_20d' not in existing_cols:
        conn.execute("ALTER TABLE stock_meta ADD COLUMN volume_ratio_20d REAL")
    if 'sector' not in existing_cols:
        conn.execute("ALTER TABLE stock_meta ADD COLUMN sector TEXT")
    if 'industry' not in existing_cols:
        conn.execute("ALTER TABLE stock_meta ADD COLUMN industry TEXT")
    if 'price' not in existing_cols:
        conn.execute("ALTER TABLE stock_meta ADD COLUMN price REAL")
    if 'market_cap' not in existing_cols:
        conn.execute("ALTER TABLE stock_meta ADD COLUMN market_cap REAL")


def fetch_listing_date_from_yf(stock_code):
    """Get listing date from yfinance by finding earliest history date."""
    raw = str(int(stock_code)) if stock_code.isdigit() else stock_code.lstrip('0')
    candidates = []
    if raw:
        candidates.append(f"{raw.zfill(4)}.HK")
        candidates.append(f"{raw}.HK")
    for yf_symbol in candidates:
        try:
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period='max')
            if not hist.empty:
                return hist.index[0].strftime('%Y-%m-%d'), yf_symbol
        except Exception:
            continue
    return None, candidates[0] if candidates else None


def fetch_ccass_concentration_from_webb(stock_code):
    """Fetch latest concentration snapshot from Webb CCASS concentration history page."""
    raw = str(int(stock_code)) if stock_code.isdigit() else stock_code.lstrip('0')
    if not raw:
        return None

    url = f"https://webbsite.0xmd.com/ccass/cconchist.asp?sc={raw}"
    html = None

    def to_float(v):
        if pd.isna(v):
            return None
        s = str(v).replace('%', '').replace(',', '').strip()
        if not s:
            return None
        try:
            return float(s)
        except Exception:
            return None

    def parse_html_table(raw_html):
        tables = pd.read_html(StringIO(raw_html))
        if not tables:
            return None

        df = None
        for t in tables:
            cols = [str(c).strip() for c in t.columns]
            if any('Top 5' in c for c in cols) and any('Top 10' in c for c in cols):
                df = t
                break

        if df is None or df.empty:
            return None

        col_map = {}
        for c in df.columns:
            # Handle MultiIndex or complex column names
            if isinstance(c, tuple):
                c_str = " ".join([str(sub).strip() for sub in c if pd.notna(sub)])
            else:
                c_str = str(c)

            s = c_str.replace('\n', ' ').strip().lower()
            if 'date' in s:
                col_map['date'] = c
            elif 'top 5' in s:
                col_map['top5'] = c
            elif 'top 10' in s and 'ncip' not in s:
                col_map['top10'] = c
            elif ('stake in' in s and 'ccass' in s) or ('% in' in s and 'ccass' in s):
                col_map['stake'] = c

        if not {'date', 'top5', 'top10', 'stake'}.issubset(col_map.keys()):
            # One more attempt for Stake if column name is very simple
            if 'stake' not in col_map:
                for c in df.columns:
                    c_str = " ".join([str(sub).strip() for sub in c if pd.notna(sub)]) if isinstance(c, tuple) else str(c)
                    if '% in' in c_str.lower():
                        col_map['stake'] = c
                        break
        
        if not {'date', 'top5', 'top10', 'stake'}.issubset(col_map.keys()):
            return None

        row = df.iloc[0]
        d = str(row[col_map['date']]).strip()
        if len(d) >= 10:
            d = d[:10]

        return {
            'date': d,
            'top5': to_float(row[col_map['top5']]),
            'top10': to_float(row[col_map['top10']]),
            'stake': to_float(row[col_map['stake']]),
            'url': url,
        }

    def parse_jina_markdown(md_text):
        # Handles both normal markdown tables and Jina-reader plain-text-ish tables
        # Standard: | 1 | 2026-04-30 | 81.43 | ...
        # Jina-ish: 1 \t 2026-04-30 \t 81.43 ... (or spaces)
        lines = md_text.splitlines()
        for i, line in enumerate(lines):
            ln = line.strip()
            
            # Match "| 1 |" or line starting with "1" followed by whitespace and date
            # Regex for "1 [whitespace] YYYY-MM-DD" or "| 1 | [Date]"
            if re.search(r'^\|?\s*1\s*\|?\s*(\d{4}-\d{2}-\d{2}|\[\d{4}-\d{2}-\d{2}\])', ln) or \
               re.search(r'^1\s+(\d{4}-\d{2}-\d{2})', ln):
                
                # If it's a pipe-separated table
                if '|' in ln:
                    cells = [c.strip() for c in ln.strip('|').split('|')]
                else:
                    # Split by multiple spaces or tabs
                    cells = re.split(r'\s{2,}|\t', ln)
                
                if len(cells) < 4: continue # Row, Date, Top5, Top10...
                
                # Find date in cells[1]
                m_date = re.search(r'(\d{4}-\d{2}-\d{2})', cells[1])
                if not m_date: continue
                
                # Jina sometimes has 6 columns: Row, Date, Top5, Top10, Top10+NCIP, Stake
                # 1  2026-04-30  81.43  90.85  90.85  47.22
                # cells[2] = 81.43 (Top5)
                # cells[3] = 90.85 (Top10)
                # cells[5] = 47.22 (Stake)
                
                top5 = to_float(cells[2])
                top10 = to_float(cells[3])
                stake = to_float(cells[5]) if len(cells) > 5 else 0.0
                
                return {
                    'date': m_date.group(1),
                    'top5': top5,
                    'top10': top10,
                    'stake': stake,
                    'url': url,
                }
        return None

    # Try cloudscraper first to handle Cloudflare challenge pages.
    try:
        if cloudscraper is not None:
            scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'darwin', 'mobile': False})
            r = scraper.get(url, timeout=20, headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept-Language': 'zh-HK,zh;q=0.9,en;q=0.8'
            })
            if r.ok and r.text and 'Top 5' in r.text and 'Top 10' in r.text:
                html = r.text
    except Exception:
        html = None

    if html:
        parsed = parse_html_table(html)
        if parsed:
            return parsed

    # Fallback to direct request.
    try:
        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept-Language': 'zh-HK,zh;q=0.9,en;q=0.8'
        })
        with urlopen(req, timeout=20) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        parsed = parse_html_table(html)
        if parsed:
            return parsed
    except Exception:
        pass

    # Final fallback: r.jina.ai proxy can access Cloudflare-protected pages and returns markdown.
    proxy_url = f"https://r.jina.ai/http://webbsite.0xmd.com/ccass/cconchist.asp?sc={raw}"
    req = Request(proxy_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urlopen(req, timeout=25) as resp:
        md_text = resp.read().decode('utf-8', errors='ignore')
    return parse_jina_markdown(md_text)


@app.route('/api/toggle_bookmark', methods=['POST'])
def api_toggle_bookmark():
    data = request.json
    stock_code = data.get('stock_code')
    if not stock_code:
        return jsonify({'ok': False, 'msg': 'Missing stock_code'}), 400
    
    conn = get_db_connection()
    try:
        # 檢查是否已存在
        exists = conn.execute("SELECT 1 FROM bookmarks WHERE stock_code = ?", (stock_code,)).fetchone()
        if exists:
            conn.execute("DELETE FROM bookmarks WHERE stock_code = ?", (stock_code,))
            status = 'unmarked'
        else:
            conn.execute("INSERT INTO bookmarks (stock_code) VALUES (?)", (stock_code,))
            status = 'marked'
        conn.commit()
        return jsonify({'ok': True, 'status': status})
    except Exception as e:
        return jsonify({'ok': False, 'msg': str(e)}), 500
    finally:
        conn.close()


@app.route('/')
def index():
    sort_by = request.args.get('sort', 'curr_pct')
    order = request.args.get('order', 'DESC').upper()
    search = request.args.get('search', '').strip() # 新增搜尋參數
    requested_sector = request.args.get('sector', '').strip() # 新增板塊過濾
    requested_industry = request.args.get('industry', '').strip() # 新增細分板塊過濾
    requested_base_date = request.args.get('base_date', '').strip()
    show_bookmarks_only = request.args.get('bookmarks_only') == '1'
    min_market_cap_text = request.args.get('min_market_cap', '').strip()
    recent_listing_months_text = request.args.get('recent_listing_months', '').strip()
    min_market_cap = 90.0
    recent_listing_months = None
    if min_market_cap_text:
        try:
            parsed_min_cap = float(min_market_cap_text)
            if parsed_min_cap >= 0:
                min_market_cap = parsed_min_cap
        except ValueError:
            min_market_cap = 90.0

    if recent_listing_months_text:
        try:
            parsed_months = int(recent_listing_months_text)
            if parsed_months > 0:
                recent_listing_months = parsed_months
        except ValueError:
            recent_listing_months = None

    if order not in ('ASC', 'DESC'):
        order = 'DESC'

    allowed_sql_sorts = {
        'curr_pct', 'stock_code', 'stock_name', 'price', 'market_cap', 'listing_date',
        'diff_today', 'diff_1_7d', 'diff_8_14d', 'diff_15_21d', 'diff_22_28d',
        'diff_M1', 'diff_M2', 'diff_M3', 'diff_M4', 'diff_M5',
        'diff_1m', 'diff_3m', 'diff_6m', 'diff_12m',
        'turnover_rate_float', 'volume_ratio_5d', 'volume_ratio_20d'
    }
    if sort_by != 'trend_score' and sort_by not in allowed_sql_sorts:
        sort_by = 'curr_pct'
    
    conn = get_db_connection()
    
    # 獲取最新日期 (有任何數據的最晚日期)
    latest_all_row = conn.execute("SELECT MAX(date) FROM shareholding").fetchone()
    if not latest_all_row or not latest_all_row[0]:
        return "數據庫中暫無數據，請先運行 index.py 抓取數據。"
    latest_full_date = latest_all_row[0]
    
    # 獲取最新有有效持股比例(percent)數據的日期
    # 解決今日數據尚未更新(盤中或剛收盤)時顯示空值的問題
    latest_data_row = conn.execute("SELECT MAX(date) FROM shareholding WHERE percent IS NOT NULL AND percent > 0").fetchone()
    latest_date = latest_data_row[0] if latest_data_row and latest_data_row[0] else latest_full_date

    # 可選回放基準日；若非交易日則回退至該日前最近有數據的一天
    if requested_base_date:
        try:
            datetime.strptime(requested_base_date, '%Y-%m-%d')
        except ValueError:
            requested_base_date = ''

    if requested_base_date:
        base_date_row = conn.execute(
            "SELECT MAX(date) FROM shareholding WHERE date <= ?",
            (requested_base_date,)
        ).fetchone()
        base_date = base_date_row[0] if base_date_row and base_date_row[0] else latest_date
    else:
        base_date = latest_date

    earliest_date_row = conn.execute("SELECT MIN(date) FROM shareholding").fetchone()
    earliest_date = earliest_date_row[0] if earliest_date_row and earliest_date_row[0] else base_date

    ld_dt = datetime.strptime(base_date, '%Y-%m-%d')

    def subtract_months(dt, months):
        month_index = dt.month - 1 - months
        year = dt.year + month_index // 12
        month = month_index % 12 + 1
        day = min(dt.day, calendar.monthrange(year, month)[1])
        return dt.replace(year=year, month=month, day=day)

    recent_listing_cutoff = None
    if recent_listing_months is not None:
        recent_listing_cutoff = subtract_months(ld_dt, recent_listing_months).strftime('%Y-%m-%d')
    
    # 定義時段邏輯
    # 1. 最近週單位變動 (1-7, 8-14, 15-21, 22-28)
    # 2. 歷史月單位變動 (M1, M2, M3, M4, M5) -> 指過往完整月份的對比
    # 3. 滾動長周期變動 (3m, 6m, 12m)
    
    period_configs = [
        ('today', 1, 1),
        ('1-7d', 1, 7), ('8-14d', 8, 14), ('15-21d', 15, 21), ('22-28d', 22, 28),
        ('M1', 1, 30), ('M2', 31, 60), ('M3', 61, 90), ('M4', 91, 120), ('M5', 121, 150),
        ('1m', 1, 30), ('3m', 1, 90), ('6m', 1, 180), ('12m', 1, 365)
    ]

    # 計算每個時段的 Start 和 End 日期
    # 注意：這裡的邏輯是對齊 all_stocks_summary.md 的格式
    date_points = {}
    
    def get_nearest_date(target_dt):
        t_str = target_dt.strftime('%Y-%m-%d')
        r = conn.execute("SELECT MAX(date) FROM shareholding WHERE date <= ?", (t_str,)).fetchone()
        return r[0] if r else None

    results_meta = []
    for label, start_offset, end_offset in period_configs:
        # End 對應的是靠近現在的時間點，Start 對應的是較遠的時間點
        # 例如 1-7d: 從 7天前 到 1天前
        dt_end = ld_dt - timedelta(days=start_offset-1)
        dt_start = ld_dt - timedelta(days=end_offset)
        
        d_end = get_nearest_date(dt_end)
        d_start = get_nearest_date(dt_start)
        results_meta.append({'label': label, 'start': d_start, 'end': d_end})

    # 構造 SQL
    ensure_stock_meta_table(conn)
    sql = """
        SELECT
            curr.stock_code,
            curr.stock_name,
            curr.percent as curr_pct,
            COALESCE(sm.price, curr.price, lp.latest_price) as price,
            COALESCE(sm.market_cap, curr.market_cap, lm.latest_market_cap) as market_cap,
            CASE
                WHEN sm.price IS NOT NULL THEN 'latest'
                WHEN curr.price IS NOT NULL THEN curr.date
                ELSE lp.latest_price_date
            END as price_asof,
            CASE
                WHEN sm.market_cap IS NOT NULL THEN 'latest'
                WHEN curr.market_cap IS NOT NULL THEN curr.date
                ELSE lm.latest_market_cap_date
            END as market_cap_asof,
            sm.listing_date,
            sm.concentration_top5,
            sm.concentration_top10,
            sm.concentration_stake,
            sm.concentration_date,
            sm.fifty_two_week_high,
            sm.fifty_two_week_low,
            sm.turnover_rate_float,
            sm.volume_ratio_5d,
            sm.volume_ratio_20d,
            sm.sector,
            sm.industry,
            COALESCE((SELECT 1 FROM bookmarks WHERE stock_code = curr.stock_code), 0) as is_bookmarked
    """
    joins = """
        LEFT JOIN stock_meta sm ON curr.stock_code = sm.stock_code
        LEFT JOIN (
            SELECT p1.stock_code, p1.price as latest_price, p1.date as latest_price_date
            FROM shareholding p1
            JOIN (
                SELECT stock_code, MAX(date) as max_date
                FROM shareholding
                WHERE price IS NOT NULL
                GROUP BY stock_code
            ) p2
            ON p1.stock_code = p2.stock_code AND p1.date = p2.max_date
        ) lp ON curr.stock_code = lp.stock_code
        LEFT JOIN (
            SELECT m1.stock_code, m1.market_cap as latest_market_cap, m1.date as latest_market_cap_date
            FROM shareholding m1
            JOIN (
                SELECT stock_code, MAX(date) as max_date
                FROM shareholding
                WHERE market_cap IS NOT NULL
                GROUP BY stock_code
            ) m2
            ON m1.stock_code = m2.stock_code AND m1.date = m2.max_date
        ) lm ON curr.stock_code = lm.stock_code
    """
    params = [base_date]

    for i, meta in enumerate(results_meta):
        label = meta['label'].replace('-', '_')
        s_date = meta['start']
        e_date = meta['end']
        
        if s_date and e_date:
            # 計算 (結束點持倉 - 開始點持倉)
            sql += f", (p_e_{i}.percent - p_s_{i}.percent) as diff_{label}, p_s_{i}.date as s_{label}, p_e_{i}.date as e_{label} "
            joins += f" LEFT JOIN shareholding p_s_{i} ON curr.stock_code = p_s_{i}.stock_code AND p_s_{i}.date = '{s_date}' "
            joins += f" LEFT JOIN shareholding p_e_{i} ON curr.stock_code = p_e_{i}.stock_code AND p_e_{i}.date = '{e_date}' "
        else:
            sql += f", NULL as diff_{label}, NULL as s_{label}, NULL as e_{label} "

    sql += f" FROM shareholding curr {joins} WHERE curr.date = ?"

    # 增加搜尋過濾
    if search:
        sql += " AND (curr.stock_code LIKE ? OR curr.stock_name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    # 市值下限篩選 (輸入單位: 億)
    if min_market_cap is not None:
        sql += " AND COALESCE(sm.market_cap, curr.market_cap, lm.latest_market_cap) >= ?"
        params.append(min_market_cap * 100000000.0)

    # 板塊過濾
    if requested_sector:
        # yfinance 的 sector 是英文，我們需要匹配英文
        # 建立一個反向映射來找到對齊的英文名
        rev_sector_map = {v: k for k, v in SECTOR_ZH_MAP.items()}
        english_sector = rev_sector_map.get(requested_sector, requested_sector)
        # 同時檢查英文名與中文名（以防萬一）
        sql += " AND (sm.sector = ? OR sm.sector = ?)"
        params.extend([english_sector, requested_sector])

    # 細分板塊過濾
    if requested_industry:
        # yfinance 的 industry 也是英文
        rev_industry_map = {v: k for k, v in INDUSTRY_ZH_MAP.items()}
        english_industry = rev_industry_map.get(requested_industry, requested_industry)
        sql += " AND (sm.industry = ? OR sm.industry = ?)"
        params.extend([english_industry, requested_industry])

    # 只看書籤
    if show_bookmarks_only:
        sql += " AND is_bookmarked = 1"

    # 次新股篩選：直接在 SQL 層過濾，排序只針對次新股名單
    if recent_listing_cutoff is not None:
        sql += " AND sm.listing_date IS NOT NULL AND sm.listing_date >= ? AND sm.listing_date <= ?"
        params.extend([recent_listing_cutoff, base_date])

    sql_sort_by = sort_by if sort_by in allowed_sql_sorts else 'curr_pct'
    sql += f" ORDER BY {sql_sort_by} {order} LIMIT 300"
    
    df = pd.read_sql_query(sql, conn, params=params)

    # 計算基準日期下仍缺市值的數量
    # 改為檢查 stock_meta 表中的數據，或檢查 shareholding 但優先看 sm
    # 注意：如果 sm.market_cap 有值，就不算缺失
    missing_market_cap_count = conn.execute(
        """SELECT COUNT(*) FROM shareholding s
           LEFT JOIN stock_meta m ON s.stock_code = m.stock_code
           WHERE s.date = ? 
           AND (m.market_cap IS NULL AND s.market_cap IS NULL)""",
        (base_date,)
    ).fetchone()[0]

    # 計算缺上市日的數量
    missing_listing_date_count = conn.execute(
        """SELECT COUNT(*) FROM shareholding s
           LEFT JOIN stock_meta m ON s.stock_code = m.stock_code
           WHERE s.date = ? 
           AND (m.listing_date IS NULL)""",
        (base_date,)
    ).fetchone()[0]

    # 計算缺換手率的數量
    missing_turnover_count = conn.execute(
        """SELECT COUNT(*) FROM shareholding s
           LEFT JOIN stock_meta m ON s.stock_code = m.stock_code
           WHERE s.date = ? AND m.turnover_rate_float IS NULL""",
        (base_date,)
    ).fetchone()[0]

    # 計算缺量比(5日)的數量
    missing_vr5d_count = conn.execute(
        """SELECT COUNT(*) FROM shareholding s
           LEFT JOIN stock_meta m ON s.stock_code = m.stock_code
           WHERE s.date = ? AND m.volume_ratio_5d IS NULL""",
        (base_date,)
    ).fetchone()[0]

    # 計算缺量比(20日)的數量
    missing_vr20d_count = conn.execute(
        """SELECT COUNT(*) FROM shareholding s
           LEFT JOIN stock_meta m ON s.stock_code = m.stock_code
           WHERE s.date = ? AND m.volume_ratio_20d IS NULL""",
        (base_date,)
    ).fetchone()[0]

    conn.close()

    # 計算趨勢信號
    def get_signal(row):
        sigs = []
        # 短期變動 (使用 round 處理浮點數殘差)
        dt = round(row.get('diff_today') or 0, 4)
        d1 = round(row.get('diff_1_7d') or 0, 4)
        d2 = round(row.get('diff_8_14d') or 0, 4)
        d3 = round(row.get('diff_15_21d') or 0, 4)
        d4 = round(row.get('diff_22_28d') or 0, 4)
        m1 = round(row.get('diff_M1') or 0, 4)
        m2 = round(row.get('diff_M2') or 0, 4)
        m3 = round(row.get('diff_M3') or 0, 4)
        m4 = round(row.get('diff_M4') or 0, 4)
        m5 = round(row.get('diff_M5') or 0, 4)

        # A. 短期偏強 (加速掃貨)
        if d1 > 0 and d2 >= 0 and d3 >= 0:
            if d1 > d2: sigs.append(('短期加速', 'danger'))
            else: sigs.append(('短期偏強', 'warning'))
        
        # B. 中長線強勢 (長線建倉)
        if m2 > 0.1 or m3 > 0.1: # 門檻大幅調低，只要有明顯建倉即顯示
            sigs.append(('長線莊家', 'info'))
        
        # C. 短期轉弱 (高位派貨)
        if d1 < 0 and (m1 > 0.1 or m2 > 0.1):
            sigs.append(('短期獲利', 'success'))

        # D. 中長期弱勢 (持續撤離)
        if m1 < 0 and m2 < 0:
            sigs.append(('長線撤離', 'secondary'))

        # E. 啟動日 (今日轉正，但過去 1-4 週仍偏弱)
        weak_recent_count = sum(1 for x in [d1, d2, d3, d4] if x <= 0)
        if dt > 0 and d1 <= 0 and weak_recent_count >= 3:
            sigs.append(('啟動日', 'danger'))
            
        # F. 抄碼信號 (近期轉向)
        if d1 > 0 and d2 <= 0:
            sigs.append(('負轉正', 'primary'))

        # G. 回流買點 (類似: 今日微升 + 近一週強升 + 更早週期偏弱 + 月度有回踩後再轉強)
        weekly_rebound = (
            dt > 0 and
            d1 > 0.1 and
            d1 > d2 and
            d2 > -0.02 and
            d3 <= 0.03 and
            d4 <= 0.03
        )
        monthly_rebound = (
            m1 > 0 and
            m3 > 0 and
            m4 >= 0 and
            m2 <= 0 and
            m5 <= 0
        )
        if weekly_rebound and monthly_rebound:
            sigs.append(('回流買點', 'success'))

        return sigs

    def calc_trend_score(row):
        """0-100 升趨勢力度分：方向 + 動量 + 加速 + 持久 - 風險"""
        def v(key):
            val = row.get(key)
            return float(val) if val is not None else None

        # 1) 方向分 (0-25)
        direction_keys = ['diff_1_7d', 'diff_8_14d', 'diff_15_21d', 'diff_22_28d', 'diff_M1', 'diff_M2', 'diff_M3']
        direction_vals = [v(k) for k in direction_keys if v(k) is not None]
        if direction_vals:
            pos_count = sum(1 for x in direction_vals if x > 0)
            direction = 25.0 * pos_count / len(direction_vals)
        else:
            direction = 0.0

        # 2) 動量分 (-10 到 30)，最近權重大
        weights = {
            'diff_today': 0.40,
            'diff_1_7d': 0.25,
            'diff_8_14d': 0.15,
            'diff_15_21d': 0.10,
            'diff_22_28d': 0.05,
            'diff_M1': 0.03,
            'diff_M2': 0.02,
        }
        weighted_sum = 0.0
        for k, w in weights.items():
            val = v(k)
            if val is not None:
                weighted_sum += val * w
        # 調整分母以維護得分比例 (假設原本總和基準為 2.0，現在稍微調整以反映權重分配)
        momentum = max(-10.0, min(30.0, 30.0 * (weighted_sum / 1.5)))

        # 3) 加速分 (-10 到 20)
        d1 = v('diff_1_7d') or 0.0
        d2 = v('diff_8_14d') or 0.0
        d3 = v('diff_15_21d') or 0.0
        a1 = d1 - d2
        a2 = d2 - d3
        accel = max(-10.0, min(20.0, 8.0 * a1 + 4.0 * a2))

        # 4) 持久分 (0-15)
        endurance = 0.0
        if (v('diff_3m') or 0.0) > 0:
            endurance += 5.0
        if (v('diff_6m') or 0.0) > 0:
            endurance += 5.0
        if (v('diff_12m') or 0.0) > 0:
            endurance += 5.0

        # 5) 風險扣分 (0-20)
        risk = 0.0
        m1 = v('diff_M1') or 0.0
        m2 = v('diff_M2') or 0.0
        if d1 < 0 and m1 > 0:
            risk += 6.0
        if m1 < 0 and m2 < 0:
            risk += 8.0
        if d1 < -0.3:
            risk += 3.0
        if d2 < -0.3:
            risk += 3.0

        score = direction + momentum + accel + endurance - risk
        score = max(0.0, min(100.0, score))

        if score >= 80:
            label, color = '極強', 'danger'
        elif score >= 65:
            label, color = '強勢', 'warning'
        elif score >= 50:
            label, color = '偏強', 'info'
        elif score >= 35:
            label, color = '中性', 'secondary'
        else:
            label, color = '偏弱', 'dark'

        return round(score, 1), label, color

    stocks_list = df.to_dict(orient='records')
    diff_keys = [k for k in (stocks_list[0] if stocks_list else {}) if k.startswith('diff_')]
    concentration_keys = ['concentration_top5', 'concentration_top10', 'concentration_stake', 'fifty_two_week_high', 'fifty_two_week_low', 'turnover_rate_float', 'volume_ratio_5d', 'volume_ratio_20d']
    str_keys = ['listing_date', 'concentration_date', 'price_asof', 'market_cap_asof', 'sector', 'industry']
    for s in stocks_list:
        # Convert NaN diff values to None so Jinja can use "is not none" check
        for k in diff_keys + concentration_keys:
            v = s.get(k)
            if v is not None and (isinstance(v, float) and v != v):  # NaN check
                s[k] = None
        # Convert NaN string fields to None
        for k in str_keys:
            v = s.get(k)
            if v is not None and isinstance(v, float):
                s[k] = None

        # sector/industry 自動轉中文，無對應則保留英文
        s['sector'] = map_to_zh(s.get('sector'), SECTOR_ZH_MAP)
        s['industry'] = map_to_zh(s.get('industry'), INDUSTRY_ZH_MAP)

        s['signals'] = get_signal(s)
        score, label, color = calc_trend_score(s)
        s['trend_score'] = score
        s['trend_score_label'] = label
        s['trend_score_color'] = color

    if sort_by == 'trend_score':
        stocks_list.sort(key=lambda x: x.get('trend_score', 0), reverse=(order == 'DESC'))

    # 時段標籤與描述的映射
    period_desc = {
        'today': '今日變動',
        '1_7d': '1-7 日', '8_14d': '8-14 日', '15_21d': '15-21 日', '22_28d': '22-28 日',
        'M1': '上 1 個月', 'M2': '上 2 個月', 'M3': '上 3 個月', 'M4': '上 4 個月', 'M5': '上 5 個月',
        '1m': '最近 1 個月', '3m': '最近 3 個月', '6m': '最近 6 個月', '12m': '最近 12 個月'
    }
    display_periods = list(period_desc.keys())

    return render_template('index.html', 
                           stocks=stocks_list, 
                           latest_date=latest_date,
                           base_date=base_date,
                           earliest_date=earliest_date,
                           sort_by=sort_by,
                           order=order,
                           search=search,
                           current_sector=requested_sector,
                           current_industry=requested_industry,
                           show_bookmarks_only=show_bookmarks_only,
                           sector_map=SECTOR_ZH_MAP,
                           industry_map=INDUSTRY_ZH_MAP,
                           min_market_cap=min_market_cap,
                           recent_listing_months=recent_listing_months,
                           display_periods=display_periods,
                           period_desc=period_desc,
                           missing_market_cap_count=missing_market_cap_count,
                           missing_listing_date_count=missing_listing_date_count,
                           missing_turnover_count=missing_turnover_count,
                           missing_vr5d_count=missing_vr5d_count,
                           missing_vr20d_count=missing_vr20d_count)


@app.route('/api/refresh_market_cap', methods=['POST'])
def refresh_market_cap():
    payload = request.get_json(silent=True) or {}
    stock_code = str(payload.get('stock_code', '')).strip()

    if not stock_code.isdigit():
        return jsonify({'ok': False, 'error': 'invalid stock_code'}), 400

    stock_code = stock_code.zfill(5)

    conn = get_db_connection()
    ensure_stock_meta_table(conn)
    conn.commit()
    latest_date_row = conn.execute("SELECT MAX(date) as d FROM shareholding").fetchone()
    latest_date = latest_date_row['d'] if latest_date_row else None

    if not latest_date:
        conn.close()
        return jsonify({'ok': False, 'error': 'no data in db'}), 400

    exists = conn.execute(
        "SELECT stock_code FROM shareholding WHERE date = ? AND stock_code = ?",
        (latest_date, stock_code)
    ).fetchone()
    if not exists:
        conn.close()
        return jsonify({'ok': False, 'error': 'stock not found on latest date'}), 404

    try:
        yf_data = fetch_market_cap_from_yf(stock_code)
    except Exception as e:
        conn.close()
        return jsonify({'ok': False, 'error': f'yfinance failed: {e}'}), 500

    market_cap = yf_data.get('market_cap')
    price = yf_data.get('price')
    yf_symbol = yf_data.get('yf_symbol')
    turnover_rate_float = yf_data.get('turnover_rate_float')
    volume_ratio_5d = yf_data.get('volume_ratio_5d')
    volume_ratio_20d = yf_data.get('volume_ratio_20d')
    fifty_two_week_high = yf_data.get('fifty_two_week_high')
    fifty_two_week_low = yf_data.get('fifty_two_week_low')
    sector = yf_data.get('sector')
    industry = yf_data.get('industry')

    if all(v is None for v in [market_cap, price, fifty_two_week_high, fifty_two_week_low, turnover_rate_float, volume_ratio_5d, volume_ratio_20d, sector, industry]):
        conn.close()
        return jsonify({'ok': False, 'error': 'no market data from yfinance'}), 404

    try:
        conn.execute(
            """
            UPDATE shareholding
            SET market_cap = COALESCE(?, market_cap),
                price = COALESCE(?, price)
            WHERE date = ? AND stock_code = ?
            """,
            (market_cap, price, latest_date, stock_code)
        )
        conn.execute(
            """
            INSERT INTO stock_meta
            (stock_code, fifty_two_week_high, fifty_two_week_low, turnover_rate_float, volume_ratio_5d, volume_ratio_20d, sector, industry)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stock_code) DO UPDATE SET
                fifty_two_week_high = COALESCE(excluded.fifty_two_week_high, stock_meta.fifty_two_week_high),
                fifty_two_week_low = COALESCE(excluded.fifty_two_week_low, stock_meta.fifty_two_week_low),
                turnover_rate_float = COALESCE(excluded.turnover_rate_float, stock_meta.turnover_rate_float),
                volume_ratio_5d = COALESCE(excluded.volume_ratio_5d, stock_meta.volume_ratio_5d),
                volume_ratio_20d = COALESCE(excluded.volume_ratio_20d, stock_meta.volume_ratio_20d),
                sector = COALESCE(excluded.sector, stock_meta.sector),
                industry = COALESCE(excluded.industry, stock_meta.industry)
            """,
            (stock_code, fifty_two_week_high, fifty_two_week_low, turnover_rate_float, volume_ratio_5d, volume_ratio_20d, sector, industry)
        )
        conn.commit()
    except sqlite3.OperationalError as e:
        conn.close()
        return jsonify({'ok': False, 'error': f'database busy: {e}'}), 503

    row = conn.execute(
        "SELECT market_cap, price FROM shareholding WHERE date = ? AND stock_code = ?",
        (latest_date, stock_code)
    ).fetchone()
    meta_row = conn.execute(
        """SELECT fifty_two_week_high, fifty_two_week_low, turnover_rate_float, volume_ratio_5d, volume_ratio_20d, sector, industry
           FROM stock_meta WHERE stock_code = ?""",
        (stock_code,)
    ).fetchone()
    conn.close()

    sector = map_to_zh(meta_row['sector'], SECTOR_ZH_MAP) if meta_row else None
    industry = map_to_zh(meta_row['industry'], INDUSTRY_ZH_MAP) if meta_row else None

    return jsonify({
        'ok': True,
        'stock_code': stock_code,
        'date': latest_date,
        'yf_symbol': yf_symbol,
        'market_cap': row['market_cap'] if row else None,
        'price': row['price'] if row else None,
        'fifty_two_week_high': meta_row['fifty_two_week_high'] if meta_row else None,
        'fifty_two_week_low': meta_row['fifty_two_week_low'] if meta_row else None,
        'turnover_rate_float': meta_row['turnover_rate_float'] if meta_row else None,
        'volume_ratio_5d': meta_row['volume_ratio_5d'] if meta_row else None,
        'volume_ratio_20d': meta_row['volume_ratio_20d'] if meta_row else None,
        'sector': sector,
        'industry': industry,
    })


@app.route('/api/refresh_market_cap_bulk', methods=['POST'])
def refresh_market_cap_bulk():
    """批量獲取雅虎財經中的市值和價格等數據"""
    payload = request.get_json(silent=True) or {}
    only_missing = bool(payload.get('only_missing', True))
    try:
        limit = int(payload.get('limit', 20))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'invalid limit'}), 400

    if limit <= 0:
        return jsonify({'ok': False, 'error': 'limit must be > 0'}), 400

    recent_listing_months = payload.get('recent_listing_months')
    base_date_param = str(payload.get('base_date', '')).strip()
    try:
        recent_listing_months = int(recent_listing_months) if recent_listing_months is not None else None
        if recent_listing_months is not None and recent_listing_months <= 0:
            recent_listing_months = None
    except (TypeError, ValueError):
        recent_listing_months = None

    conn = get_db_connection()
    ensure_stock_meta_table(conn)
    conn.commit()

    latest_date_row = conn.execute("SELECT MAX(date) as d FROM shareholding").fetchone()
    latest_date = latest_date_row['d'] if latest_date_row else None

    if not latest_date:
        conn.close()
        return jsonify({'ok': False, 'error': 'no data in db'}), 400

    if base_date_param:
        try:
            datetime.strptime(base_date_param, '%Y-%m-%d')
            base_date = base_date_param
        except ValueError:
            base_date = latest_date
    else:
        base_date = latest_date

    recent_listing_cutoff = None
    if recent_listing_months is not None:
        base_dt = datetime.strptime(base_date, '%Y-%m-%d')
        month_index = base_dt.month - 1 - recent_listing_months
        year = base_dt.year + month_index // 12
        month = month_index % 12 + 1
        day = min(base_dt.day, calendar.monthrange(year, month)[1])
        base_dt = base_dt.replace(year=year, month=month, day=day)
        recent_listing_cutoff = base_dt.strftime('%Y-%m-%d')

    incomplete_expr = """
        m.market_cap IS NULL OR m.price IS NULL OR
        m.fifty_two_week_high IS NULL OR m.fifty_two_week_low IS NULL OR
        m.turnover_rate_float IS NULL OR m.volume_ratio_5d IS NULL OR m.volume_ratio_20d IS NULL OR
        m.sector IS NULL OR m.industry IS NULL OR m.listing_date IS NULL
    """

    params = [base_date]
    recent_order = ""
    if recent_listing_cutoff is not None:
        recent_order = "CASE WHEN m.listing_date IS NOT NULL AND m.listing_date >= ? AND m.listing_date <= ? THEN 0 ELSE 1 END, "
        params.extend([recent_listing_cutoff, base_date])

    base_sql = """
        SELECT s.stock_code
        FROM shareholding s
        LEFT JOIN stock_meta m ON s.stock_code = m.stock_code
        WHERE s.date = ?
    """
    
    if only_missing:
        base_sql += f" AND ({incomplete_expr})"
        base_sql += f" ORDER BY {recent_order}s.stock_code LIMIT ?"
    else:
        base_sql += f" ORDER BY CASE WHEN ({incomplete_expr}) THEN 0 ELSE 1 END, {recent_order}s.stock_code LIMIT ?"
    params.append(limit)

    codes = [r['stock_code'] for r in conn.execute(base_sql, params).fetchall()]

    success = 0
    failed = 0
    skipped = 0
    errors = []

    for idx, stock_code in enumerate(codes):
        try:
            yf_data = fetch_market_cap_from_yf(stock_code)
            market_cap = yf_data.get('market_cap')
            price = yf_data.get('price')
            turnover_rate_float = yf_data.get('turnover_rate_float')
            volume_ratio_5d = yf_data.get('volume_ratio_5d')
            volume_ratio_20d = yf_data.get('volume_ratio_20d')
            fifty_two_week_high = yf_data.get('fifty_two_week_high')
            fifty_two_week_low = yf_data.get('fifty_two_week_low')
            sector = yf_data.get('sector')
            industry = yf_data.get('industry')
            listing_date = yf_data.get('listing_date')

            if all(v is None for v in [market_cap, price, fifty_two_week_high, fifty_two_week_low, turnover_rate_float, volume_ratio_5d, volume_ratio_20d, sector, industry, listing_date]):
                failed += 1
                if len(errors) < 20:
                    errors.append({'stock_code': stock_code, 'error': 'no market data from yfinance'})
            else:
                conn.execute(
                    """
                    INSERT INTO stock_meta
                    (stock_code, price, market_cap, fifty_two_week_high, fifty_two_week_low, turnover_rate_float, volume_ratio_5d, volume_ratio_20d, sector, industry, listing_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(stock_code) DO UPDATE SET
                        price = COALESCE(excluded.price, stock_meta.price),
                        market_cap = COALESCE(excluded.market_cap, stock_meta.market_cap),
                        fifty_two_week_high = COALESCE(excluded.fifty_two_week_high, stock_meta.fifty_two_week_high),
                        fifty_two_week_low = COALESCE(excluded.fifty_two_week_low, stock_meta.fifty_two_week_low),
                        turnover_rate_float = COALESCE(excluded.turnover_rate_float, stock_meta.turnover_rate_float),
                        volume_ratio_5d = COALESCE(excluded.volume_ratio_5d, stock_meta.volume_ratio_5d),
                        volume_ratio_20d = COALESCE(excluded.volume_ratio_20d, stock_meta.volume_ratio_20d),
                        sector = COALESCE(excluded.sector, stock_meta.sector),
                        industry = COALESCE(excluded.industry, stock_meta.industry),
                        listing_date = COALESCE(excluded.listing_date, stock_meta.listing_date)
                    """,
                    (stock_code, price, market_cap, fifty_two_week_high, fifty_two_week_low, turnover_rate_float, volume_ratio_5d, volume_ratio_20d, sector, industry, listing_date)
                )
                success += 1
        except Exception as e:
            failed += 1
            if len(errors) < 20:
                errors.append({'stock_code': stock_code, 'error': str(e)})

        # 每次請求後暫停 1 秒，降低被封鎖機率
        if idx < len(codes) - 1:
            time.sleep(1)

    conn.commit()
    conn.close()

    return jsonify({
        'ok': True,
        'date': base_date,
        'limit': limit,
        'total': len(codes),
        'success': success,
        'failed': failed,
        'skipped': skipped,
        'errors_sample': errors,
        'recent_listing_months': recent_listing_months,
    })

@app.route('/api/sync_hkex', methods=['POST'])
def sync_hkex():
    """運行 cn_water/index.py 中的數據同步邏輯"""
    try:
        import sys
        import yfinance as yf
        # 修正：將當前目錄加入 sys.path 以確保能正確導入同目錄下的 index.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)
            
        from index import fetch_and_save, init_db
        init_db()
        
        # 透過 yfinance 獲取真實的最新交易日
        sync_dates = []
        try:
            hsi = yf.Ticker("^HSI")
            # 下載最近 7 天數據以確包含足夠的交易日
            hist = hsi.history(period="7d")
            if not hist.empty:
                # 獲取最近 3 個真實交易日（排除周末和假期的空數據）
                # 注意：yf 返回的 index 是 Timestamp 對象
                valid_days = hist.index.tolist()
                valid_days.reverse() # 從最近的開始
                for d in valid_days[:3]:
                    sync_dates.append(d)
        except Exception as e:
            print(f"yfinance 獲取交易日失敗: {e}")
            
        # 如果 yfinance 失敗，回退到普通日期邏輯（最近 5 天）
        if not sync_dates:
            for i in range(0, 5):
                sync_dates.append(datetime.now() - timedelta(days=i))
        
        # 新增/修正：自動清理邏輯
        # 清理週六 (5), 週日 (6) 數據，以及公眾假期
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT date FROM shareholding WHERE date >= ?", 
                          [(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')])
            db_dates = [row[0] for row in cursor.fetchall()]
            
            # 從外部 JSON 讀取假期配置，方便用戶自行修改
            holidays = []
            holiday_file = os.path.join(os.path.dirname(__file__), 'holidays.json')
            if os.path.exists(holiday_file):
                try:
                    with open(holiday_file, 'r') as f:
                        holidays = json.load(f)
                except Exception as e:
                    print(f"讀取 holidays.json 失敗: {e}")
            
            # 手動定義的預設備選
            if not holidays:
                holidays = ['2026-05-01', '2026-05-04', '2026-05-05'] 
            
            for d_str in db_dates:
                dt = datetime.strptime(d_str, '%Y-%m-%d')
                # 如果是週六(5)、週日(6) 或 名單中的假期
                if dt.weekday() >= 5 or d_str in holidays:
                    print(f"🧹 檢測到非交易日數據: {d_str}，正在清理...")
                    cursor.execute("DELETE FROM shareholding WHERE date = ?", (d_str,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"清理錯誤日期失敗: {e}")

        sync_results = []
        for target in sync_dates:
            success = fetch_and_save(target)
            sync_results.append({'date': target.strftime('%Y-%m-%d'), 'success': success})
            
        return jsonify({'ok': True, 'results': sync_results})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    payload = request.get_json(silent=True) or {}
    only_missing = bool(payload.get('only_missing', True))
    try:
        limit = int(payload.get('limit', 20))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'invalid limit'}), 400

    if limit <= 0:
        return jsonify({'ok': False, 'error': 'limit must be > 0'}), 400

    recent_listing_months = payload.get('recent_listing_months')
    base_date_param = str(payload.get('base_date', '')).strip()
    try:
        recent_listing_months = int(recent_listing_months) if recent_listing_months is not None else None
        if recent_listing_months is not None and recent_listing_months <= 0:
            recent_listing_months = None
    except (TypeError, ValueError):
        recent_listing_months = None

    conn = get_db_connection()
    ensure_stock_meta_table(conn)
    conn.commit()

    latest_date_row = conn.execute("SELECT MAX(date) as d FROM shareholding").fetchone()
    latest_date = latest_date_row['d'] if latest_date_row else None

    if not latest_date:
        conn.close()
        return jsonify({'ok': False, 'error': 'no data in db'}), 400

    if base_date_param:
        try:
            datetime.strptime(base_date_param, '%Y-%m-%d')
            base_date = base_date_param
        except ValueError:
            base_date = latest_date
    else:
        base_date = latest_date

    recent_listing_cutoff = None
    if recent_listing_months is not None:
        base_dt = datetime.strptime(base_date, '%Y-%m-%d')
        month_index = base_dt.month - 1 - recent_listing_months
        year = base_dt.year + month_index // 12
        month = month_index % 12 + 1
        day = min(base_dt.day, calendar.monthrange(year, month)[1])
        recent_listing_cutoff = base_dt.replace(year=year, month=month, day=day).strftime('%Y-%m-%d')

    incomplete_expr = """
        m.market_cap IS NULL OR m.price IS NULL OR
        m.fifty_two_week_high IS NULL OR m.fifty_two_week_low IS NULL OR
        m.turnover_rate_float IS NULL OR m.volume_ratio_5d IS NULL OR m.volume_ratio_20d IS NULL OR
        m.sector IS NULL OR m.industry IS NULL OR m.listing_date IS NULL
    """

    params = [latest_date]
    recent_order = ""
    if recent_listing_cutoff is not None:
        recent_order = "CASE WHEN m.listing_date IS NOT NULL AND m.listing_date >= ? AND m.listing_date <= ? THEN 0 ELSE 1 END, "
        params.extend([recent_listing_cutoff, base_date])

    base_sql = """
        SELECT s.stock_code
        FROM shareholding s
        LEFT JOIN stock_meta m ON s.stock_code = m.stock_code
        WHERE s.date = ?
    """
    if only_missing:
        base_sql += f" AND ({incomplete_expr})"
        base_sql += f" ORDER BY {recent_order}s.stock_code LIMIT ?"
    else:
        base_sql += f" ORDER BY CASE WHEN ({incomplete_expr}) THEN 0 ELSE 1 END, {recent_order}s.stock_code LIMIT ?"
    params.append(limit)

    codes = [r['stock_code'] for r in conn.execute(base_sql, params).fetchall()]

    success = 0
    failed = 0
    skipped = 0
    errors = []

    for idx, stock_code in enumerate(codes):
        try:
            yf_data = fetch_market_cap_from_yf(stock_code)
            market_cap = yf_data.get('market_cap')
            price = yf_data.get('price')
            turnover_rate_float = yf_data.get('turnover_rate_float')
            volume_ratio_5d = yf_data.get('volume_ratio_5d')
            volume_ratio_20d = yf_data.get('volume_ratio_20d')
            fifty_two_week_high = yf_data.get('fifty_two_week_high')
            fifty_two_week_low = yf_data.get('fifty_two_week_low')
            sector = yf_data.get('sector')
            industry = yf_data.get('industry')

            if all(v is None for v in [market_cap, price, fifty_two_week_high, fifty_two_week_low, turnover_rate_float, volume_ratio_5d, volume_ratio_20d, sector, industry]):
                failed += 1
                if len(errors) < 20:
                    errors.append({'stock_code': stock_code, 'error': 'no market data from yfinance'})
            else:
                conn.execute(
                    """
                    UPDATE shareholding
                    SET market_cap = COALESCE(?, market_cap),
                        price = COALESCE(?, price)
                    WHERE date = ? AND stock_code = ?
                    """,
                    (market_cap, price, latest_date, stock_code)
                )
                conn.execute(
                    """
                    INSERT INTO stock_meta
                    (stock_code, fifty_two_week_high, fifty_two_week_low, turnover_rate_float, volume_ratio_5d, volume_ratio_20d, sector, industry)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(stock_code) DO UPDATE SET
                        fifty_two_week_high = COALESCE(excluded.fifty_two_week_high, stock_meta.fifty_two_week_high),
                        fifty_two_week_low = COALESCE(excluded.fifty_two_week_low, stock_meta.fifty_two_week_low),
                        turnover_rate_float = COALESCE(excluded.turnover_rate_float, stock_meta.turnover_rate_float),
                        volume_ratio_5d = COALESCE(excluded.volume_ratio_5d, stock_meta.volume_ratio_5d),
                        volume_ratio_20d = COALESCE(excluded.volume_ratio_20d, stock_meta.volume_ratio_20d),
                        sector = COALESCE(excluded.sector, stock_meta.sector),
                        industry = COALESCE(excluded.industry, stock_meta.industry)
                    """,
                    (stock_code, fifty_two_week_high, fifty_two_week_low, turnover_rate_float, volume_ratio_5d, volume_ratio_20d, sector, industry)
                )
                success += 1
        except Exception as e:
            failed += 1
            if len(errors) < 20:
                errors.append({'stock_code': stock_code, 'error': str(e)})

        # 每次請求後暫停 1 秒，降低被封鎖機率
        if idx < len(codes) - 1:
            time.sleep(1)

    conn.commit()
    conn.close()

    return jsonify({
        'ok': True,
        'date': latest_date,
        'limit': limit,
        'total': len(codes),
        'success': success,
        'failed': failed,
        'skipped': skipped,
        'errors_sample': errors,
        'recent_listing_months': recent_listing_months,
    })


@app.route('/api/refresh_listing_date', methods=['POST'])
def refresh_listing_date():
    payload = request.get_json(silent=True) or {}
    stock_code = str(payload.get('stock_code', '')).strip()

    if not stock_code.isdigit():
        return jsonify({'ok': False, 'error': 'invalid stock_code'}), 400

    stock_code = stock_code.zfill(5)

    conn = get_db_connection()
    ensure_stock_meta_table(conn)
    conn.commit()

    latest_date_row = conn.execute("SELECT MAX(date) as d FROM shareholding").fetchone()
    latest_date = latest_date_row['d'] if latest_date_row else None
    if not latest_date:
        conn.close()
        return jsonify({'ok': False, 'error': 'no data in db'}), 400

    exists = conn.execute(
        "SELECT stock_code FROM shareholding WHERE date = ? AND stock_code = ?",
        (latest_date, stock_code)
    ).fetchone()
    if not exists:
        conn.close()
        return jsonify({'ok': False, 'error': 'stock not found on latest date'}), 404

    try:
        listing_date, yf_symbol = fetch_listing_date_from_yf(stock_code)
    except Exception as e:
        conn.close()
        return jsonify({'ok': False, 'error': f'yfinance failed: {e}'}), 500

    if not listing_date:
        conn.close()
        return jsonify({'ok': False, 'error': 'no listing date found'}), 404

    try:
        conn.execute(
            "INSERT OR REPLACE INTO stock_meta (stock_code, listing_date) VALUES (?, ?)",
            (stock_code, listing_date)
        )
        conn.commit()
    except sqlite3.OperationalError as e:
        conn.close()
        return jsonify({'ok': False, 'error': f'database busy: {e}'}), 503
    conn.close()

    return jsonify({
        'ok': True,
        'stock_code': stock_code,
        'yf_symbol': yf_symbol,
        'listing_date': listing_date,
    })


@app.route('/api/refresh_concentration', methods=['POST'])
def refresh_concentration():
    payload = request.get_json(silent=True) or {}
    stock_code = str(payload.get('stock_code', '')).strip()

    if not stock_code.isdigit():
        return jsonify({'ok': False, 'error': 'invalid stock_code'}), 400

    stock_code = stock_code.zfill(5)

    conn = get_db_connection()
    ensure_stock_meta_table(conn)
    conn.commit()

    latest_date_row = conn.execute("SELECT MAX(date) as d FROM shareholding").fetchone()
    latest_date = latest_date_row['d'] if latest_date_row else None
    if not latest_date:
        conn.close()
        return jsonify({'ok': False, 'error': 'no data in db'}), 400

    exists = conn.execute(
        "SELECT stock_code FROM shareholding WHERE date = ? AND stock_code = ?",
        (latest_date, stock_code)
    ).fetchone()
    if not exists:
        conn.close()
        return jsonify({'ok': False, 'error': 'stock not found on latest date'}), 404

    try:
        info = fetch_ccass_concentration_from_webb(stock_code)
    except Exception as e:
        conn.close()
        return jsonify({'ok': False, 'error': f'webb fetch failed: {e}'}), 500

    if not info:
        conn.close()
        return jsonify({'ok': False, 'error': 'no concentration data found'}), 404

    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO stock_meta
            (stock_code, listing_date, concentration_top5, concentration_top10, concentration_stake, concentration_date)
            VALUES (
                ?,
                (SELECT listing_date FROM stock_meta WHERE stock_code = ?),
                ?, ?, ?, ?
            )
            """,
            (stock_code, stock_code, info['top5'], info['top10'], info['stake'], info['date'])
        )
        conn.commit()
    except sqlite3.OperationalError as e:
        conn.close()
        return jsonify({'ok': False, 'error': f'database busy: {e}'}), 503

    row = conn.execute(
        """SELECT concentration_top5, concentration_top10, concentration_stake, concentration_date
           FROM stock_meta WHERE stock_code = ?""",
        (stock_code,)
    ).fetchone()
    conn.close()

    return jsonify({
        'ok': True,
        'stock_code': stock_code,
        'concentration_top5': row['concentration_top5'] if row else None,
        'concentration_top10': row['concentration_top10'] if row else None,
        'concentration_stake': row['concentration_stake'] if row else None,
        'concentration_date': row['concentration_date'] if row else None,
        'source_url': info.get('url')
    })


@app.route('/api/refresh_concentrations', methods=['POST'])
def refresh_concentrations():
    payload = request.get_json(silent=True) or {}
    only_missing = bool(payload.get('only_missing', True))
    try:
        limit = int(payload.get('limit', 20))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'invalid limit'}), 400

    if limit <= 0:
        return jsonify({'ok': False, 'error': 'limit must be > 0'}), 400

    recent_listing_months = payload.get('recent_listing_months')
    base_date = str(payload.get('base_date', '')).strip()
    try:
        recent_listing_months = int(recent_listing_months) if recent_listing_months is not None else None
        if recent_listing_months is not None and recent_listing_months <= 0:
            recent_listing_months = None
    except (TypeError, ValueError):
        recent_listing_months = None

    conn = get_db_connection()
    ensure_stock_meta_table(conn)
    conn.commit()

    latest_date_row = conn.execute("SELECT MAX(date) as d FROM shareholding").fetchone()
    latest_date = latest_date_row['d'] if latest_date_row else None
    if not latest_date:
        conn.close()
        return jsonify({'ok': False, 'error': 'no data in db'}), 400

    if base_date:
        try:
            datetime.strptime(base_date, '%Y-%m-%d')
        except ValueError:
            base_date = latest_date
    else:
        base_date = latest_date

    recent_listing_cutoff = None
    if recent_listing_months is not None:
        base_dt = datetime.strptime(base_date, '%Y-%m-%d')
        month_index = base_dt.month - 1 - recent_listing_months
        year = base_dt.year + month_index // 12
        month = month_index % 12 + 1
        day = min(base_dt.day, calendar.monthrange(year, month)[1])
        recent_listing_cutoff = base_dt.replace(year=year, month=month, day=day).strftime('%Y-%m-%d')

    missing_concentration_expr = """
        m.concentration_top5 IS NULL OR
        m.concentration_top10 IS NULL OR
        m.concentration_stake IS NULL OR
        m.concentration_date IS NULL
    """
    params = [latest_date]
    recent_order = ""
    if recent_listing_cutoff is not None:
        recent_order = "CASE WHEN m.listing_date IS NOT NULL AND m.listing_date >= ? AND m.listing_date <= ? THEN 0 ELSE 1 END, "
        params.extend([recent_listing_cutoff, base_date])

    sql = f"""
        SELECT s.stock_code
        FROM shareholding s
        LEFT JOIN stock_meta m ON s.stock_code = m.stock_code
        WHERE s.date = ?
    """
    if only_missing:
        sql += f" AND ({missing_concentration_expr}) ORDER BY {recent_order}s.stock_code LIMIT ?"
    else:
        sql += f" ORDER BY CASE WHEN ({missing_concentration_expr}) THEN 0 ELSE 1 END, {recent_order}s.stock_code LIMIT ?"
    params.append(limit)
    codes = [r['stock_code'] for r in conn.execute(sql, params).fetchall()]

    success = 0
    failed = 0
    errors = []

    for stock_code in codes:
        try:
            info = fetch_ccass_concentration_from_webb(stock_code)
        except Exception as e:
            failed += 1
            if len(errors) < 20:
                errors.append({'stock_code': stock_code, 'error': f'webb fetch failed: {e}'})
            continue

        if not info:
            failed += 1
            if len(errors) < 20:
                errors.append({'stock_code': stock_code, 'error': 'no concentration data found'})
            continue

        try:
            conn.execute(
                """
                INSERT INTO stock_meta
                (stock_code, concentration_top5, concentration_top10, concentration_stake, concentration_date)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(stock_code) DO UPDATE SET
                    concentration_top5 = excluded.concentration_top5,
                    concentration_top10 = excluded.concentration_top10,
                    concentration_stake = excluded.concentration_stake,
                    concentration_date = excluded.concentration_date
                """,
                (stock_code, info['top5'], info['top10'], info['stake'], info['date'])
            )
            conn.commit()
            success += 1
        except sqlite3.OperationalError as e:
            failed += 1
            if len(errors) < 20:
                errors.append({'stock_code': stock_code, 'error': f'database busy: {e}'})

    conn.close()

    return jsonify({
        'ok': True,
        'success': success,
        'failed': failed,
        'total': len(codes),
        'limit': limit,
        'only_missing': only_missing,
        'recent_listing_months': recent_listing_months,
        'errors': errors,
    })

@app.route('/api/set_listing_date', methods=['POST'])
def set_listing_date():
    """Manually set listing date for a stock (Option 1: manual insertion)."""
    payload = request.get_json(silent=True) or {}
    stock_code = str(payload.get('stock_code', '')).strip()
    listing_date = str(payload.get('listing_date', '')).strip()

    if not stock_code.isdigit():
        return jsonify({'ok': False, 'error': 'invalid stock_code'}), 400

    if not listing_date:
        return jsonify({'ok': False, 'error': 'missing listing_date'}), 400

    # Validate date format YYYY-MM-DD
    try:
        from datetime import datetime
        datetime.strptime(listing_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'ok': False, 'error': 'invalid date format, use YYYY-MM-DD'}), 400

    stock_code = stock_code.zfill(5)

    conn = get_db_connection()
    ensure_stock_meta_table(conn)

    try:
        conn.execute(
            "INSERT OR REPLACE INTO stock_meta (stock_code, listing_date) VALUES (?, ?)",
            (stock_code, listing_date)
        )
        conn.commit()
    except sqlite3.OperationalError as e:
        conn.close()
        return jsonify({'ok': False, 'error': f'database busy: {e}'}), 503

    conn.close()

    return jsonify({
        'ok': True,
        'stock_code': stock_code,
        'listing_date': listing_date,
        'message': f'Listing date set for {stock_code}'
    })


@app.route('/api/refresh_listing_dates', methods=['POST'])
def refresh_listing_dates():
    payload = request.get_json(silent=True) or {}
    only_missing = bool(payload.get('only_missing', True))
    try:
        limit = int(payload.get('limit', 20))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'invalid limit'}), 400

    if limit <= 0:
        return jsonify({'ok': False, 'error': 'limit must be > 0'}), 400

    recent_listing_months = payload.get('recent_listing_months')
    base_date_param = str(payload.get('base_date', '')).strip()
    try:
        recent_listing_months = int(recent_listing_months) if recent_listing_months is not None else None
        if recent_listing_months is not None and recent_listing_months <= 0:
            recent_listing_months = None
    except (TypeError, ValueError):
        recent_listing_months = None

    conn = get_db_connection()
    ensure_stock_meta_table(conn)
    conn.commit()

    latest_date_row = conn.execute("SELECT MAX(date) as d FROM shareholding").fetchone()
    latest_date = latest_date_row['d'] if latest_date_row else None
    if not latest_date:
        conn.close()
        return jsonify({'ok': False, 'error': 'no data in db'}), 400

    if base_date_param:
        try:
            datetime.strptime(base_date_param, '%Y-%m-%d')
            base_date = base_date_param
        except ValueError:
            base_date = latest_date
    else:
        base_date = latest_date

    recent_listing_cutoff = None
    if recent_listing_months is not None:
        base_dt = datetime.strptime(base_date, '%Y-%m-%d')
        month_index = base_dt.month - 1 - recent_listing_months
        year = base_dt.year + month_index // 12
        month = month_index % 12 + 1
        day = min(base_dt.day, calendar.monthrange(year, month)[1])
        recent_listing_cutoff = base_dt.replace(year=year, month=month, day=day).strftime('%Y-%m-%d')

    params = [latest_date]
    recent_order = ""
    if recent_listing_cutoff is not None:
        recent_order = "CASE WHEN m.listing_date IS NOT NULL AND m.listing_date >= ? AND m.listing_date <= ? THEN 0 ELSE 1 END, "
        params.extend([recent_listing_cutoff, base_date])

    sql = """SELECT s.stock_code FROM shareholding s
             LEFT JOIN stock_meta m ON s.stock_code = m.stock_code
             WHERE s.date = ?"""
    if only_missing:
        sql += " AND m.listing_date IS NULL"
    sql += f" ORDER BY {recent_order}s.stock_code LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()

    codes = [r['stock_code'] for r in rows]
    success = 0
    failed = 0
    errors = []

    for idx, stock_code in enumerate(codes):
        try:
            listing_date, yf_symbol = fetch_listing_date_from_yf(stock_code)
            if listing_date:
                conn.execute(
                    "INSERT OR REPLACE INTO stock_meta (stock_code, listing_date) VALUES (?, ?)",
                    (stock_code, listing_date)
                )
                success += 1
            else:
                failed += 1
                if len(errors) < 20:
                    errors.append({'stock_code': stock_code, 'error': 'no listing date found'})
        except Exception as e:
            failed += 1
            if len(errors) < 20:
                errors.append({'stock_code': stock_code, 'error': str(e)})

        if idx < len(codes) - 1:
            time.sleep(1)

    conn.commit()
    conn.close()

    return jsonify({
        'ok': True,
        'total': len(codes),
        'success': success,
        'failed': failed,
        'errors_sample': errors,
        'recent_listing_months': recent_listing_months,
    })


if __name__ == '__main__':
    # 確保 templates 目錄存在
    os.makedirs("cn_water/templates", exist_ok=True)
    # 禁用調試模式與自動重載以節省記憶體
    port = int(os.getenv('PORT', 5001))
    host = os.getenv('HOST', '0.0.0.0')  # Replit 需要監聽 0.0.0.0
    app.run(debug=False, host=host, port=port, use_reloader=False)
