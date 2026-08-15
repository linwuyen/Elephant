# Elephant Model Validation & Structural Layers

這一層的目的不是再增加漂亮分數，而是回答兩個第一性問題：

1. **既有分數對未來是否真的有 information value？**
2. **新 domain 的證據不足時，系統能不能拒絕產生假精確度？**

## Model Validation Extension

Production artifact：`data/model_validation.json`

### Cross-dimension validation

核心檢驗：

```text
Growth Persistence(t)   ─┐
Domestic Demand(t)       ├→ Cycle(t+3 / t+6)
Financial Conditions(t) ─┘
```

AI Concentration 因為是集中度而非景氣方向分數，只驗自己的 3M / 6M persistence。

每個 horizon 保存：

- sample count
- Pearson correlation
- score bucket 下的 future Cycle mean
- future expansion / neutral / contraction rate
- historical reliability diagnostic

### Evidence boundary

這些歷史驗證仍使用 **目前已修訂官方序列重新建構的 history**，因此可能含 official-revision bias。

```text
Historical reconstruction != point-in-time forecast performance
```

真正 prospective reliability 只能由既有：

```text
data/vintages.db
+
data/decision_journal.json
```

隨時間累積。Validation Extension 不取代 Decision Engine forecast authority。

## Confidence decomposition

舊 score 的 `confidence` 主要表示可用 component weight。Validation Extension 將不確定性拆開：

```text
Coverage
Freshness
Signal Agreement
Historical Reliability
```

另外提供 `provisional_overall` 方便診斷，但它的 `authority=false`，不能取代 Decision Engine 的：

```text
Data Confidence
Model Confidence
Decision Confidence
```

## Historical analog regime probability

使用目前：

```text
Cycle + Growth Persistence + Financial Conditions
```

尋找歷史相似狀態，產生 3M / 6M：

```text
Expansion / Neutral / Contraction
```

的 distance-weighted empirical probability。

這只是 revised-history cross-check，`authority=false`；正式 forecast 仍由 Decision Engine 負責。

## Weight robustness

固定 production weights 不自動最佳化。

Validation Extension 只做 one-component weight ±20% sensitivity，觀察目前 score 最大變動量。目的是檢查模型是否對單一人為權重極度敏感，不是 data-mining 最佳權重。

## Reverse stress

對 Growth / Domestic / Financial 計算：

- 所有現有 component 同幅下降多少，score 才會跨過 0。
- 單一 component 需要下降多少才可能獨自造成翻盤。

這是 sensitivity threshold，不是 forecast probability。

## Structural Layers

Production artifact：`data/structural_layers.json`

所有 structural layer 只能有：

```text
READY
BLOCKED_UPSTREAM
BLOCKED_EVIDENCE
```

證據不足時 `score=null`。

### Business Investment

問題：**企業是在擴產，還是只是在消化既有需求？**

目前可用官方鏈：

```text
製造業固定資產增購 YoY   50%
機械設備製造業生產 YoY   25%
銀行信用 YoY              25%
```

缺值重新正規化；available weight < 50% 時不發布 score。季度 capex 與月度 machinery / credit 各自保留真正來源期，不假裝同月。

### External Demand

問題：**台灣景氣的全球上游需求正在加速還是轉弱？**

台灣外銷訂單與出口只是 transmission signals，不等於 global upstream demand。因此在全球半導體/電子週期、主要終端需求或 capex、中國需求、全球製造業與 trade/freight breadth 沒有形成穩定一手資料鏈前：

```text
status = BLOCKED_UPSTREAM
score = null
```

### Regional Vitality

問題：**哪些城市真的在變強？**

正式 contract：

```text
人口 × 信用卡 × 新設公司 × 房市成交 × 房價 × 用電
```

至少 4/6 個 city-level official components 通過 period alignment 與資料驗證後才允許發布排名。現在證據不足：

```text
status = BLOCKED_EVIDENCE
score = null
```

## Source resilience supplements

`scripts/source_supplements.py` 只補既有 Decision Score 的已知 coverage holes：

- MOEA 製造業存貨量指數
- MOEA 電子產品外銷訂單
- MOEA 資訊通訊產品外銷訂單
- DGBAS 薪資 / 就業 verified-TLS retry

TLS fallback 使用系統 CA 的 `curl`，**不使用 `-k`，不關閉 certificate verification**。

跨不同 MOEA resource 的電子訂單 level 不假設可直接比較；若不是同表 level，AI Concentration 只使用 YoY relative-growth signal，不偽造 share。

## Authority boundary

```text
Official data → deterministic scores
Decision Engine → forecast / risk budget / journal authority
Validation Extension → challenge / diagnostics only
Structural Layer → score only when evidence gate passes
Consultant research → context only
Alpha Buy Gate → stock action authority
No automatic trading
```
