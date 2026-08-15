# Elephant Investment / Alpha Layer

Elephant 的 Investment Layer 把兩種不同問題放在同一個決策畫面，但**不把兩套分數混在一起**。

## 兩個引擎，各自回答不同問題

```text
Elephant Macro Engine
Cycle / Growth Persistence / Domestic Demand / Financial Conditions
                  ↓
             Macro Context
                  │
                  │ 只提供 regime / risk background
                  │ 不加減 Alpha Score
                  ↓
Investment Decision Layer
                  ↑
                  │ Buy Gate 保持 authoritative
                  │
linwuyen/stock Alpha Engine
Full Market Screen → Deep Research → Alpha / Confidence → Valuation → Buy Gate
```

### Elephant 回答

- 現在台灣景氣強不強？
- 成長能不能持續？
- 內需有沒有跟上？
- 金融條件是在助攻還是壓制？

### Alpha Engine 回答

- 哪些股票值得研究？
- 哪些股票可能被錯價？
- 預期報酬是否勝過可替代資產？
- valuation / evidence / freshness / confidence 是否足以通過 Buy Gate？

## v2：Capital Allocation OS

Elephant v2 的目標不再只是「找股票」，而是回答：

> 目前這一塊新增資本，放在哪裡能提高長期稅後、成本後、風險調整後的幾何報酬，同時避免被迫賣出與永久資本損失？

因此新增八個決策層：

1. Deep Research Automation
2. Multi-Benchmark Opportunity Set
3. Portfolio Engine
4. BUY / ADD / HOLD / TRIM / EXIT lifecycle
5. Portfolio Risk Engine
6. Sector / archetype-specific valuation routing
7. Probabilistic Expected Return
8. Point-in-time Calibration

### 核心 contract

1. **Macro context 不改 Alpha Score。**
2. **Macro context 不可產生 BUY CANDIDATE。**
3. **Full-market Screen 不可產生 BUY CANDIDATE。**
4. **`linwuyen/stock` Buy Gate 仍是個股 BUY authority。**
5. **Portfolio Engine 只能在已通過 BUY Gate 的股票與顯式 benchmark/cash/debt alternatives 間配置。**
6. **Portfolio Engine 不得把 WATCH/VERIFY 自動升成 BUY。**
7. **SELL/TRIM 可以由 thesis invalidation、估值過熱、集中度或更佳 opportunity cost 觸發，但不得自行執行交易。**
8. **TSMC 3000 只是重新評估事件，不是自動賣出訊號。**
9. **所有 unavailable / stale / unverified inputs fail closed。**
10. **不執行交易。**

## 資料流

目前仍採 federated integration，避免兩套 scanner：

```text
linwuyen/stock/data/{alpha,screen,performance}.json
                    ↓
scripts/source_alpha.py
                    ↓
data/alpha_engine.json
                    ↓
Deep Research / Opportunity / Portfolio / Risk / Calibration
                    ↓
data/capital_allocation.json
                    ↓
Investment Decision Layer / Pages
```

## Opportunity Set

Benchmark 不再只看台積電。v2 支援：

- 2330 TSMC
- Taiwan broad-market proxy
- Global equity proxy
- Cash
- Debt repayment

未取得可靠、可重現的 expected-return input 時，該 alternative 標記為 `UNAVAILABLE`，不得用假設值填滿。

## Portfolio Policy

`data/portfolio_policy.json` 定義：

- 最大單股權重
- 最大產業 / factor exposure
- 最低現金
- 最大槓桿
- 目標集中度
- 新資本配置規則

`data/portfolio_state.json` 是使用者可填寫的現況輸入；未填時 Portfolio Engine 只輸出 research recommendation，不產生個人化 target weight。

## Deep Research Automation

Top 10 新進候選會建立 deterministic research queue。只有在第一手 evidence、freshness、valuation route 與 benchmark comparison 完整後，才可交還 upstream Alpha Buy Gate 判定；queue 本身永遠沒有 BUY 權限。

## Valuation Router

公司先分類到 business archetype，再選擇 valuation route，例如：

- secular_growth / AI infrastructure → forward EPS / FCF
- cyclical / memory → normalized mid-cycle EPS / EBITDA
- property → NAV / backlog
- utility → normalized cash flow / yield
- financial → P/B × sustainable ROE
- asset-heavy / holding → NAV

如果分類或必要欄位不足，valuation status = `INCOMPLETE`。

## Probabilistic ER

除了 point expected return，v2 會保留 scenario distribution：

- bear / base / bull probability
- downside probability
- probability of beating hurdle
- expected shortfall proxy

樣本或 scenario 不足時，不製造虛假的 confidence interval。

## Calibration

Primary cohort 仍以真實 `BUY_CANDIDATE` entry transition 為準。v2 增加 point-in-time snapshot 與 benchmark-set provenance，避免 look-ahead / survivorship bias。樣本數不足時只記錄，不自動調權重。

## Canonical migration

目前 Elephant 已是產品入口，但 Alpha scanner 仍由 `linwuyen/stock` upstream 提供。待 v2 穩定後再做最後 migration：

1. `stock/scripts/*` → `Elephant/scripts/alpha/`
2. `stock/data/*` durable history → `Elephant/data/alpha/`
3. 排程集中到 Elephant
4. `linwuyen/stock` archived / read-only redirect

先完成決策閉環，再移轉 code ownership，避免同時改模型與資料來源造成不可歸因風險。
