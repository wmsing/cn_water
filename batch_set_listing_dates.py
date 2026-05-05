#!/usr/bin/env python3
"""
批量設置上市日期工具 (Batch set listing dates)

Usage:
    python batch_set_listing_dates.py
    
    Then enter data in format:
    00699, 2008-11-17
    01234, 2010-01-01
    (Press Ctrl+D on Mac/Linux or Ctrl+Z on Windows to finish)
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = "cn_water/hkex_southbound.db"

def ensure_stock_meta_table(conn):
    """Create stock_meta table if not exists."""
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
            sector TEXT,
            industry TEXT,
            turnover_rate_float REAL,
            volume_ratio_5d REAL,
            volume_ratio_20d REAL
        )
    ''')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)  # 10 second timeout for locks
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrency
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

def set_listing_date(stock_code: str, listing_date: str) -> bool:
    """Set listing date for a stock. Returns True if successful."""
    stock_code = str(stock_code).strip().zfill(5)
    listing_date = str(listing_date).strip()
    
    # Validate date format
    try:
        from datetime import datetime
        datetime.strptime(listing_date, '%Y-%m-%d')
    except ValueError:
        print(f"  ✗ {stock_code}: Invalid date format '{listing_date}' (use YYYY-MM-DD)")
        return False
    
    # Retry logic for database locks
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = get_db_connection()
            ensure_stock_meta_table(conn)
            
            conn.execute(
                "INSERT OR REPLACE INTO stock_meta (stock_code, listing_date) VALUES (?, ?)",
                (stock_code, listing_date)
            )
            conn.commit()
            conn.close()
            print(f"  ✓ {stock_code}: Set to {listing_date}")
            return True
            
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e) and attempt < max_retries - 1:
                import time
                wait_time = 0.5 * (2 ** attempt)  # Exponential backoff: 0.5s, 1s, 2s
                print(f"  ⏳ {stock_code}: Database locked, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                print(f"  ✗ {stock_code}: Database error - {e}")
                return False
        except Exception as e:
            print(f"  ✗ {stock_code}: Error - {e}")
            return False
        finally:
            try:
                conn.close()
            except:
                pass

def main():
    print("批量設置上市日期 (Batch Set Listing Dates)")
    print("=" * 50)
    print("格式 (Format): 股票代碼, YYYY-MM-DD")
    print("例如 (Example): 00699, 2008-11-17")
    print("輸入空行結束 (Press Ctrl+D/Ctrl+Z to finish)")
    print("=" * 50)
    print()
    
    success_count = 0
    error_count = 0
    
    try:
        while True:
            try:
                line = input(">>> ").strip()
                if not line:
                    continue
                
                # Parse line
                parts = [p.strip() for p in line.split(',')]
                if len(parts) != 2:
                    print(f"  ✗ Invalid format (expected 2 fields, got {len(parts)})")
                    continue
                
                stock_code, listing_date = parts
                if set_listing_date(stock_code, listing_date):
                    success_count += 1
                else:
                    error_count += 1
                    
            except KeyboardInterrupt:
                print("\n已中止 (Interrupted)")
                break
                
    except EOFError:
        pass
    
    print()
    print("=" * 50)
    print(f"完成 (Complete): ✓ {success_count} 成功, ✗ {error_count} 失敗")
    print("=" * 50)

if __name__ == '__main__':
    main()
