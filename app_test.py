#!/usr/bin/env python3
"""
簡化版 app - 用於 Replit 診斷
"""
from flask import Flask, render_template, request, jsonify
import sqlite3
import os
import sys

app = Flask(__name__)

# 數據庫路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv('DB_PATH', os.path.join(BASE_DIR, 'hkex_southbound.db'))

print(f"DEBUG: BASE_DIR = {BASE_DIR}", file=sys.stderr)
print(f"DEBUG: DB_PATH = {DB_PATH}", file=sys.stderr)
print(f"DEBUG: DB exists = {os.path.exists(DB_PATH)}", file=sys.stderr)

@app.route('/', methods=['GET'])
def index():
    """主頁 - 測試數據庫連接"""
    try:
        # 測試數據庫連接
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 查詢股票數量
        cursor.execute("SELECT COUNT(*) as cnt FROM (SELECT DISTINCT stock_code FROM shareholding LIMIT 100)")
        result = cursor.fetchone()
        stock_count = result['cnt'] if result else 0
        
        # 查詢最新日期
        cursor.execute("SELECT MAX(date) as max_date FROM shareholding")
        date_result = cursor.fetchone()
        max_date = date_result['max_date'] if date_result else 'N/A'
        
        conn.close()
        
        return jsonify({
            'status': '✅ 應用運行正常',
            'database': f'✅ 連接成功',
            'db_path': DB_PATH,
            'db_exists': os.path.exists(DB_PATH),
            'stock_count': stock_count,
            'latest_date': max_date
        }), 200
    
    except Exception as e:
        return jsonify({
            'status': '❌ 應用啟動失敗',
            'error': str(e),
            'db_path': DB_PATH,
            'db_exists': os.path.exists(DB_PATH)
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """健康檢查"""
    return {'status': 'ok'}, 200

if __name__ == '__main__':
    # 確保 templates 目錄存在
    os.makedirs("templates", exist_ok=True)
    
    port = int(os.getenv('PORT', 5001))
    host = os.getenv('HOST', '0.0.0.0')
    
    print(f"🚀 啟動應用...", file=sys.stderr)
    print(f"   Host: {host}", file=sys.stderr)
    print(f"   Port: {port}", file=sys.stderr)
    print(f"   DB Path: {DB_PATH}", file=sys.stderr)
    
    app.run(debug=False, host=host, port=port, use_reloader=False)
