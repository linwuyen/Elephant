# Elephant — 台灣經濟情報系統

[![Official data refresh](https://github.com/linwuyen/Elephant/actions/workflows/update-data.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/update-data.yml)
[![GitHub Pages](https://github.com/linwuyen/Elephant/actions/workflows/pages.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/pages.yml)

Elephant 是一個免伺服器、免本機常駐的台灣經濟情報系統。它每天自動抓官方資料、驗證、偵測歷史修正、計算景氣動能／轉折／背離／廣度與 Cycle Score，再把 30 秒摘要發布到 GitHub Pages。

網站：`https://linwuyen.github.io/Elephant/`

## 打開首頁會直接看到

- **Elephant Cycle Score**：-100～+100 的透明規則式景氣分數。
- **Momentum**：景氣正在加速、持平或減速。
- **Breadth**：多少產業 YoY 為正，以及相較前月是擴散或收斂。
- **Leading**：國發會官方領先指標近 3 個月方向。
- **Official signal**：國發會景氣燈號與綜合分數。
- **Confidence**：資料來源健康度與可用元件完整度。
- **Since your last visit**：只在瀏覽器本機記住上一份摘要快照，下次直接列實質變化。
- **Turning points**：YoY 負轉正、正轉負、收縮收斂、擴張降速、加速／減速。
- **Divergences**：科技 vs 整體製造、生產 vs 銷售、領先 vs 同時等背離。
- **What matters now**：依重大性過濾，只顯示值得注意的項目。
- **Next watch**：根據目前訊號產生下一步觀察清單。
- **Revision log**：官方回溯修正歷史值時，保留 old/new/delta 與偵測時間。

所有數字與分類均由 deterministic engine 從已驗證資料產生；生成式 AI 不決定任何事實或分數。

## Cycle Score：同一套月度公式

為了讓今天的分數可以和歷史真正比較，Cycle Score 只使用月度／高頻成分，不再把一年一次的 GDP 混入月度計分。GDP 仍保留為總體背景資訊。

| 元件 | 權重 |
| --- | ---: |
| 製造業生產 YoY | 30% |
| 產業正成長 Breadth | 20% |
| 國發會領先指標近 3M | 20% |
| 製造業銷售 YoY | 15% |
| PMI | 10% |
| 國發會景氣綜合分數 | 5% |

缺值時只對可用元件重新正規化權重。Elephant Cycle Score 是自訂透明分數，**不是**國發會官方景氣燈號。

## 情報歷史

網站「情報歷史」頁直接提供：

- Cycle Score / Momentum 歷史時間軸
- Regime changes
- 每次核心資料版本真的改變時留下的情報快照
- 官方歷史值 revision table
- Cycle Score CSV 下載

`data/intelligence_history.json` 同時保存兩種概念：

1. **Historical reconstruction**：用目前官方已修訂序列，以同一套月度公式回算歷史分數，適合比較景氣位置與轉折。
2. **Versioned snapshots**：資料 fingerprint 真正改變才新增一筆，保留當時 Elephant 看見的摘要與主要指標。

歷史重建不是 real-time vintage backtest；真正的版本差異由 snapshots + `data/revisions.json` + Git history 留存。

## 自動更新

- 每天 **18:17（Asia/Taipei）** 自動檢查。
- 修改資料管線也會立即觸發更新。
- Workflow 使用 concurrency cancellation，避免多個更新互搶 push。
- 資料 commit 前 fetch + rebase，避免 non-fast-forward。
- 任一關鍵來源異常時保留上一版，不把壞值覆蓋成健康資料。
- 驗證成功後 bot commit `data/**`，再明確 dispatch Pages。
- 關鍵來源失敗時自動建立／更新 GitHub Issue；恢復後自動關閉。
- 每日 heartbeat 降低 scheduled workflow 因 repository 長期無 activity 被停用的風險。

## 官方資料來源

| 來源 | 狀態 | 主要用途 |
| --- | --- | --- |
| 主計總處來源資料 | 自動、必要 | GDP、經濟成長率、CPI、產業 GDP |
| 經濟部統計處 | 自動、必要 | 工業生產、製造業銷售、主要產業 |
| 內政部戶政司 | 自動、必要 | 人口、出生死亡、年齡結構、縣市、高齡化 |
| 國家發展委員會 | 自動、必要 | 領先／同時／落後指標、景氣燈號、PMI/NMI、M1B、出口、失業率、利率、存貨等景氣構成項目 |
| 經濟部 legacy 下載 | Best effort | 舊銷售價值／投資等歷史補充；失效時保留 last-good |
| SEGIS | Blocked | 沒有穩定可驗證官方輸入前不偽造數值 |

## Intelligence pipeline

```text
DGBAS / MOEA / RIS / NDC
          ↓
官方資料抓取
          ↓
revision_tracker.capture()
          ↓
格式、值域、period、freshness 驗證
          ↓
data/*.json
          ↓
revision diff：old → new
          ↓
build_summary.py
          ↓
YoY / acceleration / MA3 / MA6 / 12M percentile
          ↓
Breadth / Turning points / Divergences
          ↓
build_history.py
          ↓
月度 Cycle Score / Momentum 歷史重建 + 版本快照
          ↓
validate_data.py
          ↓
GitHub Pages
```

## 資料完整性

發布前至少檢查：

- JSON 可解析、必要序列存在。
- period 不重複、排序正常。
- GDP／人口／產業指數合理值域。
- 最新縣市至少 20 個行政區。
- DGBAS / RIS 年資料至少到前一曆年。
- MOEA / NDC 核心月資料不得落後超過 4 個月。
- Cycle Score、Momentum、Confidence、Turning Point、Divergence 通過 schema/value validation。
- Historical Cycle Score 至少 24 個月，且 current score 與歷史重建最新期間對齊。
- Revision record schema 驗證。
- 單一來源失敗時保留 last-good data，不把 HTML、DNS 錯誤或欄位漂移當正式數據。

## 生成式 AI 的角色

目前**不使用生成式 AI 決定數字、趨勢或分數**。未來即使接 LLM，也只應放在已計算完成的 Facts / Signals / Scores 之上做自然語言解釋：

```text
官方資料 → 規則式 Facts / Signals / Scores → LLM 解釋
```

## 本機不是必要條件

日常使用、抓取、驗證、revision tracking、情報歷史、告警、commit 與 Pages 部署都在 GitHub 雲端完成。使用者只需要打開網頁。
