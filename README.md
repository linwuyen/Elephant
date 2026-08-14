# Elephant — 台灣經濟情報系統

[![Official data refresh](https://github.com/linwuyen/Elephant/actions/workflows/update-data.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/update-data.yml)
[![Consultant research refresh](https://github.com/linwuyen/Elephant/actions/workflows/update-research.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/update-research.yml)
[![GitHub Pages](https://github.com/linwuyen/Elephant/actions/workflows/pages.yml/badge.svg)](https://github.com/linwuyen/Elephant/actions/workflows/pages.yml)

Elephant 是一個免伺服器、免本機常駐的台灣經濟情報系統：官方資料負責 **Facts / Signals / Scores**，`Consultant_System` 提供 McKinsey / BCG / Deloitte / PwC 的外部研究 context，兩者在 Intelligence Layer 合流，但顧問研究永遠不直接改分數。

網站：`https://linwuyen.github.io/Elephant/`

## 首頁：五層診斷

1. **Elephant Cycle Score**：現在景氣強不強？
2. **Growth Persistence Score**：這波景氣還能持續嗎？
3. **Domestic Demand Score**：內需與一般家庭有沒有跟上？
4. **Financial Conditions Score**：資金環境是否支持景氣？
5. **AI Concentration Score**：台灣成長有多集中在 AI／電子鏈？

前四類景氣方向 score 使用 `-100～+100`；AI Concentration 使用 `0～100` 的**集中度**刻度，數字越高代表成長越集中，**不代表景氣更好**。

所有 score 均由 deterministic engine 依已驗證官方資料與固定 transform 計算。缺值不補 0，只對可用元件重新正規化並降低 Confidence。

## AI Concentration

回答：**台灣現在的成長是不是過度依賴 AI／電子鏈？**

```text
電子相關外銷訂單         30%
AI 核心出口             30%
資訊電子生產領先幅度     25%
非電子產業 breadth       15%
```

其中 AI 核心出口使用財政部主要貨品出口資料中的：

```text
電子零組件 + 資通與視聽產品
-----------------------------
          總出口
```

如果官方輸入當期沒有乾淨、可驗證的電子分類外銷訂單序列，就**不推估、不補假值**；該 component 缺值並反映在 Confidence。

## Intelligence Layer v1

Elephant 不再只是 dashboard。`data/intelligence_layer.json` 會把 deterministic scores 與顧問研究組成可追溯的 decision context：

```text
                    Taiwan official data
                           ↓
                deterministic Scores
                           ↓
       Official Evidence / What Changed
                           ↓
              Intelligence Layer v1
              ↙          ↓          ↘
     Research Evidence  Risks  Contradictions
              ↑
McKinsey / BCG / Deloitte / PwC
              ↑
       Consultant_System
```

每個維度都產生：

- Official Evidence
- Research Evidence
- Contradictions
- Risks
- What Changed
- Dimension Brief
- Cross-dimension Executive Brief

研究 mapping 使用可重現的 topic / keyword / recency metadata rules。它是**全球策略 context**，不是台灣因果證據。

最重要的 contract：

```json
{
  "contract": "official-deterministic-scores-plus-consultant-context",
  "score_influence": false
}
```

## Consultant_System integration

上游：`linwuyen/Consultant_System`

它每天先建立並驗證：

```text
reports.json
reports.csv
consultant.db
```

Elephant 再同步進：

```text
data/consultant/reports.json
data/consultant/reports.csv
data/consultant/consultant.db
data/consultant/status.json
```

同步不是盲目 copy。Elephant 會再次 gate：

- McKinsey ≥ 3
- BCG ≥ 3
- Deloitte ≥ 3
- PwC ≥ 3
- undated = 0
- duplicate URL = 0
- SQLite magic / integrity / schema contract 正常

任何一項失敗都不會把不完整研究 snapshot 當 production data。

網站「**顧問研究**」頁籤提供關鍵字、公司、Topic、年份篩選、官方原文連結、CSV / SQLite 下載及 browser-side SQLite SQL Console。

## Automatic schedules

```text
09:17 Asia/Taipei  Consultant_System refresh
10:17 Asia/Taipei  Elephant consultant sync + Intelligence rebuild
18:17 Asia/Taipei  Elephant official-data refresh + all deterministic rebuilds
```

每次資料 commit 後都會明確觸發 GitHub Pages。Workflow 使用 concurrency、validation、fetch/rebase/push 與 last-good 策略，避免 race condition 或來源暫時失效污染正式資料。

## Official data sources

| 來源 | 主要用途 |
| --- | --- |
| 主計總處 | GDP、CPI、薪資、就業 |
| 經濟部統計處 | 工業生產、製造業銷售、外銷訂單、零售、餐飲、存貨 |
| 財政部 / 關務資料 | 總出口、主要貨品出口、AI 核心出口占比 |
| 中央銀行 | M1B、M2、銀行信用、短期利率、USD/TWD |
| 金管會 / 聯合信用卡處理中心 | 信用卡消費 proxy |
| 內政部戶政司 | 人口、出生死亡、年齡結構、縣市、高齡化 |
| 國家發展委員會 | 領先／同時／落後指標、景氣燈號、PMI/NMI |
| SEGIS | 未取得穩定可驗證輸入前保持 blocked，不偽造數值 |

## Core score chains

### Cycle Score

```text
製造業生產 YoY 30%
產業正成長 Breadth 20%
國發會領先指標近 3M 20%
製造業銷售 YoY 15%
PMI 10%
國發會景氣綜合分數 5%
```

Cycle Score 是 Elephant 自訂透明分數，**不是**國發會官方景氣燈號。

### Growth Persistence

```text
外銷訂單 → 出口 → 生產 → 銷售 → 庫存
```

固定原始權重：30% / 20% / 20% / 15% / 15%。

### Domestic Demand

```text
實質薪資 → 就業 → 零售 → 餐飲 → 信用卡消費
```

固定原始權重：25% / 20% / 20% / 15% / 20%。信用卡 component 是 proxy，不代表全部支付行為。

### Financial Conditions

```text
M1B → M2 → 銀行信用 → 利率 → 匯率
```

固定原始權重：25% / 20% / 25% / 15% / 15%。匯率 component 採透明的出口型金融條件假設，不視為一般經濟定律。

## Intelligence pipeline

```text
DGBAS / MOEA / MOF / CBC / NCCC / RIS / NDC
                      ↓
                official ingestion
                      ↓
       validation + revision_tracker
                      ↓
                 data/*.json
                      ↓
 summary / history / decision scores
                      ↓
 Cycle + Growth + Domestic + Financial + AI Concentration
                      ↓
             deterministic validation
                      ↓
                Intelligence Layer
                      ↑
      Consultant_System validated snapshot
                      ↓
                  GitHub Pages
```

## Data integrity contract

正式發布前至少檢查：

- JSON/schema 可解析且必要序列存在
- period 不重複、排序正常、值域合理
- freshness contract
- Cycle / Decision / AI Concentration score range、component、weight、history/current alignment
- Intelligence Layer `score_influence=false`
- consultant four-firm coverage + SQLite integrity
- revision record contract
- JavaScript/Python syntax
- Pages artifact validation

單一來源失敗時保留 last-good；不把 HTML、DNS error、欄位漂移或缺值當作 0。

## 情報歷史

「情報歷史」保留 Cycle Score / Momentum、regime changes、版本快照與官方 revision。`data/intelligence_history.json` 同時區分：

- **Historical reconstruction**：以目前官方已修訂序列回算歷史。
- **Versioned snapshots**：核心資料 fingerprint 真正改變時留下當時視角。

因此 historical reconstruction 不是 real-time vintage backtest；vintage 差異由 snapshots + `data/revisions.json` + Git history 留存。

## 生成式 AI 的角色

目前**不使用生成式 AI 決定數字、分類或 score**。安全邊界是：

```text
官方資料 → deterministic Facts / Signals / Scores
                            ↓
             deterministic Research Mapping
                            ↓
          optional LLM natural-language explanation
```

即使未來加入 LLM，它也只能解釋已計算結果，不能改寫數字或資料 provenance。

## 本機不是必要條件

抓取、驗證、revision tracking、score rebuild、研究同步、Intelligence rebuild、commit、告警與 Pages deployment 都在 GitHub 雲端完成；日常使用只需打開網站。

## 下一層產品路線

五層核心診斷與 Intelligence Layer v1 已落地。下一個主要決策層是：

**Housing / Regional Vitality**：哪些城市真的在變強？預計使用 `人口 × 信用卡 × 新設公司 × 房市成交 × 房價 × 用電`，並延續同一套「官方 score 與外部 research context 分離」原則。
