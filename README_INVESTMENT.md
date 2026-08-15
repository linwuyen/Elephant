# Elephant Investment / Alpha Layer

Elephant 的 Investment Layer 把總經、個股 Alpha、風險與資本配置放在同一個決策畫面，但**不把不同層的分數混成一個黑箱分數**。

## 第一性原理目標

Elephant v2 的最終問題不是「哪支股票好」，而是：

> 目前這一塊新增資本，放在哪裡能提高長期稅後、成本後、風險調整後的幾何報酬，同時降低被迫賣出與永久資本損失？

因此系統分成：

```text
Official Macro / Market / Company Evidence
                  ↓
Macro Regime + Full Market Discovery
                  ↓
Deep Research + Valuation Router
                  ↓
Alpha / Confidence / Probabilistic ER
                  ↓
Multi-Benchmark Opportunity Set
                  ↓
Portfolio / Risk / Lifecycle Engine
                  ↓
BUY / ADD / HOLD / TRIM / EXIT REVIEW
                  ↓
Point-in-time Performance Calibration
```

## 核心 contract

1. **Macro context 不改 Alpha Score。**
2. **Macro context 不可產生 BUY CANDIDATE。**
3. **Full-market Screen / Deep Research Queue 都不可產生 BUY CANDIDATE。**
4. **`linwuyen/stock` Buy Gate 仍是個股 BUY authority。**
5. **Portfolio Engine 只能在已通過 BUY Gate 的股票與顯式 benchmark / cash / debt alternatives 間配置。**
6. **Portfolio Engine 不得把 WATCH / VERIFY 自動升成 BUY。**
7. **SELL / TRIM 可由 thesis invalidation、估值過熱、集中度或更佳 opportunity cost 觸發，但只輸出 review，不執行交易。**
8. **TSMC 3000 只是重新評估事件，不是自動賣出訊號。**
9. **Unavailable / stale / unverified inputs fail closed。**
10. **不執行交易。**

## v2 八個決策層

### 1. Deep Research Automation

`data/deep_research_queue.json` 由 Full Market Deep Research Top 10 deterministic 生成，為每檔指定：

- business archetype
- required first-party evidence
- research / refresh 狀態
- next action

Queue 本身 `promotion_authority = NONE`。

### 2. Multi-Benchmark Opportunity Set

`data/opportunity_set.json` 不再只允許 TSMC：

- 2330 TSMC
- Taiwan broad-market proxy
- Global equity proxy
- Cash
- Debt repayment

沒有可靠 expected-return input 的 alternative 一律 `UNAVAILABLE`，不得造數字。Hurdle 只由 AVAILABLE alternatives 形成。

### 3. Portfolio Engine

`data/portfolio_policy.json` 定義：

- 最大單股
- 最大產業 / factor exposure
- 現金底線
- 最大槓桿
- 新部位上限
- lifecycle hysteresis

`data/portfolio_state.json` 是使用者可填寫的現況輸入。未配置前，系統只提供 research / non-personalized decision，不輸出個人 target weights。

### 4. Position Lifecycle

Portfolio layer 輸出：

- `BUY_REVIEW`
- `ADD_REVIEW`
- `HOLD_REVIEW`
- `TRIM_REVIEW`
- `EXIT_REVIEW`
- `RESEARCH`

只有 upstream `BUY CANDIDATE` 才可能進 BUY / ADD review。

### 5. Risk Engine

若 portfolio state 完整，會檢查：

- single-stock concentration
- common-factor concentration
- leverage
- -20% / -35% / -50% market shock

未配置時 `UNCONFIGURED`，不假裝知道個人風險。

### 6. Sector / Archetype Valuation Router

`data/valuation_archetypes.json` 定義：

- SECULAR_GROWTH
- CYCLICAL_MEMORY
- PROPERTY
- UTILITY
- FINANCIAL
- ASSET_NAV
- GENERAL_INDUSTRIAL

不同商業模式用不同 valuation route；必要欄位缺失就 `INCOMPLETE`。

### 7. Probabilistic Expected Return

從 upstream bear / base / bull scenario 直接生成：

- scenario return distribution
- probability of beating current hurdle
- probability of loss >20%
- downside expected shortfall proxy

不額外製造假的 confidence interval。

### 8. Point-in-time Calibration

`data/calibration/` 保存不可回寫的 decision snapshots：

- 當時 macro context
- opportunity set
- buy entries
- researched actions
- benchmark state
- portfolio-state status

只有 fingerprint 改變才新增 snapshot，未來績效必須用當時可見資料計算，降低 look-ahead / revision bias。

## 資料流

目前採 federated integration：

```text
linwuyen/stock/data/{alpha,screen,performance}.json
                    ↓
scripts/source_alpha.py
                    ↓
data/alpha_engine.json
                    ↓
scripts/capital_allocation.py
                    ↓
research queue / opportunity set / probabilistic ER / lifecycle / risk / sizing
                    ↓
data/capital_allocation.json
                    ↓
scripts/update_calibration.py
                    ↓
data/calibration/*
```

## Canonical migration

Elephant 已是產品入口，但 Alpha scanner 目前仍由 `linwuyen/stock` upstream 提供。待 v2 穩定後，最後再做 code ownership migration：

1. `stock/scripts/*` → `Elephant/scripts/alpha/`
2. `stock/data/*` durable history → `Elephant/data/alpha/`
3. 排程集中到 Elephant
4. `linwuyen/stock` archived / read-only redirect

先完成決策閉環，再移轉 scanner ownership，避免同時改模型與資料來源造成不可歸因風險。
