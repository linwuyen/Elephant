# Elephant — 台灣經濟情報與 Decision Engine

[![Official data refresh](https://github.com/linwuyen/Elephant/actions/workflows/update-data.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/update-data.yml)
[![Consultant research refresh](https://github.com/linwuyen/Elephant/actions/workflows/update-research.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/update-research.yml)
[![GitHub Pages](https://github.com/linwuyen/Elephant/actions/workflows/pages.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/pages.yml)

網站：`https://linwuyen.github.io/Elephant/`

Elephant 的目標不是做更多圖表，而是建立一條可驗證的決策閉環：

```text
Official Data
    ↓
Point-in-Time Vintage Store
    ↓
Deterministic State Estimation
    ↓
Forecast + Calibration
    ↓
Research Context / Alpha Engine
    ↓
Risk Budget / Position Sizing Envelope
    ↓
Decision Journal
    ↓
Outcome / Scorecard
    └──────────────→ learning loop
```

核心安全邊界不變：

```text
官方資料 → deterministic Scores
顧問研究 → context only，score_influence = false
Macro → portfolio risk envelope only
Alpha Buy Gate → 個股 action authority
Portfolio input → browser-local only
No automatic trading
Missing data → never fabricated
```

## Five-Layer Diagnosis

首頁持續提供五個 deterministic diagnosis：

1. **Cycle Score**：現在景氣強不強？
2. **Growth Persistence**：這波景氣還能持續嗎？
3. **Domestic Demand**：內需有沒有跟上？
4. **Financial Conditions**：資金環境是否支持景氣？
5. **AI Concentration**：成長有多集中在 AI／電子鏈？

前四者使用 `-100～+100`；AI Concentration 使用 `0～100`，高分代表更集中，不代表景氣更好。缺值不補 0，只重新正規化可用權重並降低 Data Confidence。

## Decision Engine v1

網站新增 **Decision Engine** 頁籤，production artifacts：

```text
data/vintages.db
data/vintage_manifest.json
data/forecast.json
data/research_claims.json
data/risk_budget.json
data/decision_journal.json
data/decision_engine.json
```

### 1. Point-in-Time / Vintage Database

`scripts/build_vintage.py` 在每次 official refresh 保存當次實際可觀測的決策關鍵官方序列。

SQLite tables：

```text
series
observations
snapshots
```

同一 `series_id + period` 只有在官方值真正改變時才新增 observation，並保存 `previous_value / revision_delta / observed_at`。

這解決 look-ahead bias 的核心問題：未來回測可以知道「某個時間點當時到底看得到什麼」，而不是偷用後來修訂過的數字。

**重要限制：** Vintage DB 建立之前的歷史仍是 revised-series reconstruction，不會被假裝成 real-time vintage。

### 2. Forecast + Calibration

`scripts/build_decision_engine.py` 對 Cycle / Growth / Domestic / Financial / AI Concentration 產生：

```text
1M
3M
6M
12M
```

每個 horizon 保存：

- probability
- expected score
- local sample size
- calibration bins
- Brier Score
- direction accuracy

目前方法是透明的 empirical score-bin calibration + Bayesian shrinkage，不使用黑箱模型。真正 prospective calibration 會隨 `vintages.db` 與 Decision Journal 累積而逐步取代舊 reconstructed history。

### 3. Three Confidence Layers

Decision Engine 不再把「資料齊不齊」與「模型準不準」混成同一個 Confidence：

```text
Data Confidence
Model Confidence
Decision Confidence
```

- **Data Confidence**：目前官方 score inputs 的完整度。
- **Model Confidence**：歷史 forecast calibration / sample support。
- **Decision Confidence**：資料 + 模型 + investment freshness 的綜合決策品質；不是報酬保證。

### 4. Risk Budget / Position Sizing

`data/risk_budget.json` 把 Macro 狀態轉成 portfolio risk envelope：

- target equity risk budget
- cash floor
- max single-stock exposure
- AI concentration penalty
- stress scenarios

它**不能**建立 BUY CANDIDATE，也不能修改 Alpha action。

網站 Portfolio calculator 的個人資產／持倉資料只寫入瀏覽器 `localStorage`，不寫進公開 repository。

### 5. Decision Journal + Outcome

`data/decision_journal.json` 保存 prospective machine decision snapshot：

- 當時 Scores
- Forecast probabilities
- Risk posture
- Alpha actions
- Invalidation thresholds
- Future outcomes

當 1M / 3M / 6M / 12M outcome 成熟後，自動計算：

- direction hit rate
- Brier Score

因此 Elephant 不再只是產生新分數，而會累積「以前判斷得準不準」。

### 6. Research Claim Engine

Consultant_System 仍是 McKinsey / BCG / Deloitte / PwC research ingestion layer。

`data/research_claims.json` 把公開 metadata 結構化為：

```text
claim candidate
company
geography
industry
direction
horizon
evidence strength
source URL
```

目前明確標記為 **metadata-derived claim candidates**，不是全文語意理解；沒有取得全文就不假裝讀過全文。所有 claim 都是 `score_influence=false`。

## Intelligence Layer

`data/intelligence_layer.json` 將 deterministic Scores 與 Consultant_System 組成：

```text
Official Evidence
Research Evidence
Contradictions
Risks
What Changed
Executive Brief
```

研究只提供全球策略 context，不作為台灣因果證據，也不進入 score。

## Investment Layer

Elephant 同步 `linwuyen/stock` Alpha Engine，但 Macro 與個股權限分離：

```text
Macro Context != Alpha Score
Screen != Buy Gate
Stock Buy Gate remains authoritative
No automatic trading
```

因此總經很強也不能把 WATCH / VERIFY 自動升成 BUY。

## Automatic Schedules

```text
09:17 Asia/Taipei  Consultant_System refresh
10:17 Asia/Taipei  Elephant consultant sync + Intelligence / Claims rebuild
18:17 Asia/Taipei  Official refresh + Vintage + Scores + Forecast + Journal + Risk Engine
```

兩條會寫 `main` 的 data workflow 共用 `elephant-data-writers` mutex；拿到鎖後先對齊 latest main，commit 後再次 fetch/rebase 再 push，避免 race / non-fast-forward。

## Official Data Sources

- 主計總處：GDP、CPI、薪資、就業
- 經濟部統計處：工業生產、製造業銷售、外銷訂單、零售、餐飲、存貨
- 財政部／關務：總出口、主要貨品出口、AI 核心出口
- 中央銀行：M1B、M2、銀行信用、短期利率、USD/TWD
- 金管會／聯卡中心：信用卡消費 proxy
- 內政部戶政司：人口與縣市結構
- 國發會：領先／同時／落後指標、景氣燈號、PMI/NMI
- SEGIS：未取得穩定可重現輸入前保持 blocked，不偽造數值

## Production Validation

正式發布前會驗：

- official data schema / period / range / freshness
- Cycle / Decision / AI Concentration contracts
- Consultant four-firm coverage + SQLite integrity
- Intelligence `score_influence=false`
- Investment guardrails
- Vintage SQLite `PRAGMA integrity_check = ok`
- Forecast probability / Brier / horizon contracts
- Research claim boundaries
- Risk budget guardrails
- Journal scorecard schema
- JavaScript / Python syntax
- GitHub Pages artifact

任何 critical source 失敗保留 last-good；HTML error、DNS error、欄位漂移、缺值都不會被當成 0。

## Historical Reconstruction vs Point-in-Time

`data/intelligence_history.json` 的舊 Cycle / Decision history 仍是以目前官方已修訂序列回算，適合比較 regime，但**不是**真正 real-time backtest。

從 Decision Engine v1 起，新的 `vintages.db + decision_journal.json` 才是 prospective point-in-time learning layer。未來模型績效應優先看這條資料，而不是把 revised history 當成當時可知資訊。

## Product State

目前 Elephant 已從：

```text
Dashboard → Economic Intelligence
```

進入：

```text
Economic Intelligence → Closed-Loop Decision Engine v1
```

下一階段若擴功能，Housing / Regional Vitality 可以作為新的 domain；但不能優先於 Vintage、Forecast、Calibration、Journal 這條閉環的長期樣本累積與驗證。
