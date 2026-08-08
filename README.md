# Elephant — 台灣經濟資料庫

[![Official data refresh](https://github.com/linwuyen/Elephant/actions/workflows/update-data.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/update-data.yml)
[![GitHub Pages](https://github.com/linwuyen/Elephant/actions/workflows/pages.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/pages.yml)

Elephant 是一個免伺服器、免本機常駐的台灣經濟／人口資料儀表板。官方資料由 GitHub Actions 定時檢查，驗證與新鮮度檢查通過後更新網站資料並重新部署 GitHub Pages。

網站：`https://linwuyen.github.io/Elephant/`

## 自動更新

- 每天 **18:17（Asia/Taipei）** 自動檢查官方來源。
- 修改資料管線程式時也會立即觸發一次更新。
- 可從 Actions 手動執行 `Refresh official data`。
- 每日健康檢查更新 `data/status.json` 並留下 heartbeat commit；官方資料有變化時在同一次 commit 一併更新。
- 更新 workflow 會明確 dispatch Pages；不依賴 `GITHUB_TOKEN` 產生的 commit 再觸發另一個 push workflow。
- heartbeat 讓首頁顯示真實最後檢查時間，也降低 public repository 因長期無 activity 而被 GitHub 停用 scheduled workflow 的風險。
- 驗證失敗或資料過舊時，不把來源標成健康；上一版有效資料仍保留可查。
- 關鍵來源異常時 workflow 失敗並建立／更新 GitHub Issue；恢復後自動關閉。

## 資料來源

| 來源 | 目前管線 | 內容 |
| --- | --- | --- |
| 主計總處來源資料 | 自動、必要 | GDP、經濟成長率、CPI；由政府官方再發布資料取得 |
| 經濟部統計處 | 自動、必要 | 工業生產與現行 110年=100 製造業銷售指數 |
| 經濟部 legacy 下載 | Best effort | 舊銷售價值／投資等歷史補充；端點失效時保留 last-good，不拖垮核心健康狀態 |
| 內政部戶政司 | 自動、必要 | 全國人口、出生死亡、年齡結構、縣市人口與老化 |
| SEGIS | 阻擋狀態 | 保留 schema/status；未取得穩定且可驗證的公開下載端點前不偽造觀測值 |

### 基期處理

舊「製造業銷售量指數」與現行「製造業銷售指數」基期不同，不直接拼接成同一條時間序列。現行序列依經濟部目前頁面標示使用 **110年=100**；歷史舊基期資料另列，避免製造不存在的連續性。

## 架構

```text
官方資料
   ↓
scripts/update_data.py
   ↓
格式／值域驗證 scripts/validate_data.py
   ↓
data/*.json
   ↓
每日 heartbeat commit；有新官方資料時一併更新
   ↓
明確 workflow_dispatch GitHub Pages
   ↓
資料新鮮度／來源健康 scripts/check_health.py
   ↓
正常：關閉舊 failure issue
異常：建立／更新 failure issue
```

## 資料與 UI 分離

- `data/macro.json`：GDP / CPI / 相關總體序列
- `data/population.json`：全國與縣市人口結構
- `data/industry.json`：經濟部主要產業序列
- `data/coverage.json`：資料涵蓋範圍
- `data/status.json`：最後檢查時間、各來源健康狀態、最新期間
- `app.js`：僅負責前端呈現，不硬編經濟資料

## 防壞資料與 stale-data 機制

發布與健康檢查包含：

- JSON 可解析、必要序列存在
- period 不重複且排序正常
- GDP／人口／產業指數值域合理
- 最新縣市至少 20 個行政區
- DGBAS／MOEA／RIS／SEGIS 都有明確來源狀態
- DGBAS／RIS 年資料至少到前一曆年
- MOEA 核心月資料不得落後超過 4 個月
- 現行製造業銷售指數另有獨立 freshness gate

單一來源抓取失敗時，更新器保留該來源上一版有效資料並在網站標示 degraded/blocked；不會因遠端 HTML、DNS、欄位改名等問題把壞資料覆蓋進網站。

## 本機不是必要條件

日常使用、抓取、驗證、commit、告警與 Pages 部署都在 GitHub 雲端完成。完整 SQLite 歷史庫仍可保留作離線分析與原始資料稽核，但網站正常運作不依賴任何使用者電腦常駐。
