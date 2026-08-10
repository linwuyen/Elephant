# Elephant — 台灣經濟情報系統

[![Official data refresh](https://github.com/linwuyen/Elephant/actions/workflows/update-data.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/update-data.yml)
[![GitHub Pages](https://github.com/linwuyen/Elephant/actions/workflows/pages.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/pages.yml)

Elephant 是一個免伺服器、免本機常駐的台灣經濟情報系統。它每天自動抓官方資料、驗證、偵測歷史修正、計算景氣動能／轉折／背離／廣度與多層診斷 Score，再把 30 秒摘要發布到 GitHub Pages。

網站：`https://linwuyen.github.io/Elephant/`

## 打開首頁會直接看到

首頁核心是四層診斷：

- **Elephant Cycle Score**：現在景氣強不強？
- **Growth Persistence Score**：這波景氣還能持續嗎？
- **Domestic Demand Score**：內需與一般家庭有沒有跟上？
- **Financial Conditions Score**：資金環境是否支持景氣？

同時保留：Momentum、Breadth、Leading、Official signal、Confidence、Turning points、Divergences、What matters now、Next watch、Revision log 與 Since your last visit。

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
| 主計總處 | 自動、必要 | GDP、CPI、薪資、就業 |
| 經濟部統計處 | 自動、必要 | 工業生產、製造業銷售、外銷訂單、零售、餐飲、存貨 |
| 財政部關務署 | 自動、必要 | 海關出口 |
| 中央銀行 | 自動、必要 | M1B、M2、銀行信用、短期利率、USD/TWD |
| 金管會／聯合信用卡處理中心 | 自動、Decision Score | 信用卡消費 proxy |
| 內政部戶政司 | 自動、必要 | 人口、出生死亡、年齡結構、縣市、高齡化 |
| 國家發展委員會 | 自動、必要 | 領先／同時／落後指標、景氣燈號、PMI/NMI 等景氣構成項目 |
| 經濟部 legacy 下載 | Best effort | 舊銷售價值／投資等歷史補充；失效時保留 last-good |
| SEGIS | Blocked | 沒有穩定可驗證官方輸入前不偽造數值 |

## Intelligence pipeline

```text
DGBAS / MOEA / Customs / CBC / NCCC / RIS / NDC
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
build_summary.py + build_decision_scores.py
          ↓
Cycle / Growth Persistence / Domestic Demand / Financial Conditions
          ↓
build_history.py
          ↓
月度歷史重建 + 版本快照
          ↓
validate_data.py + validate_decision_scores.py
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
- Decision Score 的 component set、權重、值域、current/history alignment 通過固定 contract validation。
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

---

## 三個 Decision Scores

三個 Score 都固定為 **-100～+100**，每個 component 保存 raw value、period、weight、transform note 與 source。缺值不補 0，只重新正規化可用權重並降低 Confidence。

### 1. Growth Persistence Score

回答：**這波景氣還能持續嗎？**

```text
外銷訂單 → 出口 → 生產 → 銷售 → 庫存
```

固定權重：外銷訂單 30%、出口 20%、製造業生產 20%、製造業銷售 15%、存貨壓力 15%。

### 2. Domestic Demand Score

回答：**台灣一般人的經濟真的有變好嗎？**

```text
實質薪資 → 就業 → 零售 → 餐飲 → 信用卡消費
```

固定權重：實質薪資 25%、就業 20%、零售 20%、餐飲 15%、信用卡消費 20%。信用卡 component 使用聯合信用卡處理中心的處理金額作 proxy；它不是所有支付行為。可取得 CPI 時，以 YoY 減 CPI YoY 做實質化。

### 3. Financial Conditions Score

回答：**資金環境是在支持還是壓制景氣？**

```text
M1B → M2 → 銀行信用 → 利率 → 匯率
```

固定權重：M1B 25%、M2 20%、金融機構放款與投資 25%、短期利率 15%、USD/TWD 15%。

匯率 component 的透明模型假設：在台灣出口導向的金融條件框架中，USD/TWD 適度上升（新台幣貶值）暫視為較寬鬆；這不是普遍經濟定律，極端匯率波動仍需另視為風險。

完整公式、資料邊界與 contract：[`README_DECISION_SCORES.md`](README_DECISION_SCORES.md)

## 下一層產品路線

Elephant 最終要回答五個問題：

1. **Growth Persistence**：這波景氣還能持續嗎？
2. **AI Concentration**：台灣現在到底多依賴 AI？使用 `電子訂單 × 電子出口 × 電子生產 × 非電子 breadth`。
3. **Domestic Demand**：台灣一般人的經濟真的有變好嗎？
4. **Financial Conditions**：資金環境是在支持還是壓制景氣？
5. **Housing / Regional Vitality**：哪些城市真的在變強？預計使用 `人口 × 信用卡 × 新設公司 × 房市成交 × 房價 × 用電`。

目標不是再堆更多總體圖表，而是把 Elephant 做成**台灣經濟的多層次診斷系統**。
