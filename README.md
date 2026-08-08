# Elephant — 台灣經濟資料庫

[![Official data refresh](https://github.com/linwuyen/Elephant/actions/workflows/update-data.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/update-data.yml)
[![GitHub Pages](https://github.com/linwuyen/Elephant/actions/workflows/pages.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/pages.yml)

Elephant 是一個免伺服器、免本機常駐的台灣經濟／人口資料儀表板。官方資料由 GitHub Actions 定時檢查，驗證通過後才更新網站資料並重新部署 GitHub Pages。

網站：`https://linwuyen.github.io/Elephant/`

## 自動更新

- 每天 **18:17（Asia/Taipei）** 自動檢查官方來源。
- 修改資料管線程式時也會立即觸發一次更新。
- 可從 Actions 手動執行 `Refresh official data`。
- 每日健康檢查會更新 `data/status.json` 並留下 heartbeat commit；官方資料有變化時會在同一次 commit 一併更新。
- heartbeat 讓首頁能顯示真實最後檢查時間，也降低 public repository 因長期無 activity 而被 GitHub 停用 scheduled workflow 的風險。
- 驗證失敗時不以無效資料覆蓋上一版有效內容。
- 關鍵來源異常時 workflow 會失敗，並建立／更新 GitHub Issue。
- 資料恢復正常後會自動關閉先前的 failure issue。

## 資料來源

| 來源 | 目前管線 | 內容 |
| --- | --- | --- |
| 主計總處來源資料 | 自動 | GDP、經濟成長率、CPI；由政府官方再發布資料取得 |
| 經濟部統計處 | 自動 | 工業生產、製造業銷售／投資與主要產業序列 |
| 內政部戶政司 | 自動 | 全國人口、出生死亡、年齡結構、縣市人口與老化 |
| SEGIS | 阻擋狀態 | 保留 schema/status；未取得穩定且可驗證的公開下載端點前不偽造觀測值 |

## 架構

```text
官方資料
   ↓
scripts/update_data.py
   ↓
驗證 scripts/validate_data.py
   ↓
data/*.json
   ↓
每日 heartbeat commit；有新官方資料時一併更新
   ↓
GitHub Pages validation + deploy
   ↓
Elephant
```

## 資料與 UI 分離

- `data/macro.json`：GDP / CPI / 相關總體序列
- `data/population.json`：全國與縣市人口結構
- `data/industry.json`：經濟部主要產業序列
- `data/coverage.json`：資料涵蓋範圍
- `data/status.json`：最後檢查時間、各來源健康狀態、最新期間
- `app.js`：僅負責前端呈現，不硬編經濟資料

## 防壞資料機制

發布前會檢查：JSON 可解析、必要序列、period 不重複且排序、GDP／人口／產業合理範圍、最新縣市至少 20 個行政區，以及 DGBAS／MOEA／RIS／SEGIS 狀態欄位。

某來源抓取失敗時，更新器會保留該來源上一版有效資料，並在 `data/status.json` 與網站的「資料健康」頁顯示 degraded/blocked 狀態。

## 本機不是必要條件

日常使用與更新都在 GitHub 雲端完成。完整 SQLite 歷史庫仍可保留作離線分析與原始資料稽核，但網站正常運作不依賴任何使用者電腦常駐。
