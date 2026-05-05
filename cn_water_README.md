# 港股通持股變動分析系統 (CN Water)

本系統用於追蹤港股通（南向資金）的持股變動，並結合市值、集中度及上市時間進行量化分析。

## 數據更新流程

### 第一步：同步北水持股歷史 (最重要)
運行以下腳本從港交所獲取最新的持股百分比數據（數據來源：[港交所持股紀錄查詢](https://www3.hkexnews.hk/sdw/search/mutualmarket_c.aspx?t=hk)），並存入數據庫：
```bash
python cn_water/index.py
```
*註：港交所通常在交易日 17:00 - 18:00 更新當日數據。*

### 第二步：啟動分析儀表面板
啟動 Flask 服務器：
```bash
python cn_water/app.py
```
訪問地址：[http://127.0.0.1:5001/](http://127.0.0.1:5001/)

### 第三步：在介面中完善其餘數據 (UI 操作)
在儀表面板頂部，點擊以下按鈕：
1. **更新上市日**：獲取新股的上市日期。
2. **批量更新市值**：從 yfinance 同步最新股價、市值及換手率。
3. **批量更新集中度**：更新 CCASS 前五/前十券商的持倉集中度。

## Replit 部署與更新

### 初始部署 (首次設置)
1. 在 Replit 上克隆此倉庫或導入 GitHub 項目
2. 系統會自動使用 `.replit` 配置文件運行應用
3. 點擊「Run」按鈕，應用會在 **http://localhost:5000** 啟動

### 運行工作流程
- **按鈕**：選擇「Project」運行按鈕 (在 `.replit` 中配置)
- **App 啟動**：自動執行 `env PORT=5000 python3 app.py`
- **預覽**：Replit 在 port 5000 上等待應用響應

### 從 GitHub 同步最新代碼

#### 方式 1：完全重置到最新版本（推薦用於有本地修改時）
```bash
cd ~/workspace
git reset --hard origin/main
```
這會丟棄所有本地修改，同步到 GitHub 最新版本。

#### 方式 2：合併更新（保留本地修改時）
```bash
cd ~/workspace
git pull origin main
```
如果有衝突，可使用：
```bash
git pull --no-rebase origin main  # 合併方式
git pull --rebase origin main      # 變基方式
```

### 環境配置
- **PORT**：在 `.replit` 中設置為 `5000`（Replit 預覽等待該端口）
- **DATABASE**：數據庫自動保存到 `cn_water/hkex_southbound.db`
- **PYTHONUNBUFFERED**：已在本地 `.replit` 中設置，保證日誌實時顯示

### 故障排查

#### 問題：應用啟動卡住，preview 一直轉圈
**原因**：`.replit` 配置的 `waitForPort` 與應用實際監聽的端口不匹配

**解決**：
1. 確保 `.replit` 中有 `env PORT=5000` 設置
2. 確保 `waitForPort = 5000` 與上面的 PORT 一致
3. 重新啟動：點擊「Stop」再點擊「Run」

#### 問題：git pull 出現分支衝突警告
**解決**：使用強制重置
```bash
git reset --hard origin/main
```

#### 問題：修改代碼後應用沒有更新
**解決**：手動重啟應用
1. 點擊 Replit 的「Stop」按鈕
2. 再點擊「Run」重新啟動

### 開發工作流程
**推薦流程**：
1. **本地開發**：在本地修改代碼、測試
2. **推送到 GitHub**：`git add . && git commit -m "..." && git push origin main`
3. **Replit 更新**：`git reset --hard origin/main`（或 `git pull origin main`）
4. **重啟應用**：點擊「Run」或重啟

## 核心邏輯說明
- **升勢分 (Trend Score)**：綜和方向、動量、加速、持久及風險扣分。今日變動佔動量分權重 40%。
- **高亮行 (Row Highlight)**：當 `(今日+1-7日) > max(15-21d, 22-28d)` 且 `M1 處於高位` 時觸發粗黃框提醒。
- **信號標籤**：包括「負轉正」、「短期加速」、「啟動日」等。
