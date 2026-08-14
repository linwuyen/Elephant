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
- 預期報酬是否勝過 TSMC benchmark？
- valuation / evidence / freshness / confidence 是否足以通過 Buy Gate？

## 核心 contract

1. **Macro context 不改 Alpha Score。**
2. **Macro context 不可產生 BUY CANDIDATE。**
3. **Full-market Screen 不可產生 BUY CANDIDATE。**
4. **`linwuyen/stock` Buy Gate 是個股 action 的唯一 authority。**
5. **TSMC 3000 只是重新評估事件，不是自動賣出訊號。**
6. **不執行交易。**

`validate_investment.py` 與 `test_investment_integration.py` 會在 CI 中鎖住以上邊界。

## 資料流

目前採 federated integration，避免把同一套 scanner 複製到兩個 repo：

```text
linwuyen/stock/data/alpha.json
linwuyen/stock/data/screen.json
linwuyen/stock/data/performance.json
                ↓
scripts/source_alpha.py
                ↓
data/alpha_engine.json   # upstream snapshot + provenance
                ↓
scripts/build_investment.py
        ↑               ↑
data/summary.json   data/decision_scores.json
                ↓
data/investment.json
                ↓
investment.js / Elephant Pages
```

Elephant 每日官方資料更新時同步 Alpha upstream；Pages 發布前也會在工作區重新抓取一次最新 Alpha snapshot，因此 public dashboard 不依賴前一次 bot commit 才能取得最新投資層資料。

## Freshness

Investment Layer 分開顯示：

- Alpha research `as_of`：深度研究／估值模型時間。
- Full-market Screen `as_of`：市場掃描時間。
- Elephant Macro period：官方總經資料所對應期間。

目前規則：

- Alpha research 超過 10 天 → Investment status `DEGRADED`。
- Screen 超過 3 天 → Investment status `DEGRADED`。
- Screen 不是 `COMPLETE` → Investment status `DEGRADED`。

`DEGRADED` 不會刪除 last-good research，但提醒使用者不能把 stale snapshot 當成即時買入依據。

## Macro Context

Macro Context 是 deterministic label，不是第五個 Alpha 分數：

- `BROADLY_SUPPORTIVE`
- `EXPORT_LED_SUPPORTIVE`
- `CONSTRUCTIVE`
- `MIXED`
- `DEFENSIVE`
- `UNKNOWN`

它只描述現有四層 Elephant scores 的組合狀態。

## 下一階段：單一 repo migration

當 federated integration 穩定後，再做真正的 canonical migration：

1. 將 `stock/scripts/scan_market.py`、source resilience、Alpha validator、performance loop 搬進 Elephant 的 `scripts/alpha/`。
2. 將 `stock/data/*` 的 durable history 遷移到 `Elephant/data/alpha/`。
3. 將排程集中到 Elephant Actions。
4. Elephant 成為唯一 canonical repository。
5. `linwuyen/stock` 改為 archived / read-only redirect，避免雙重 source of truth。

這樣做的順序是刻意的：**先整合 decision contract，再搬 code ownership**，比直接複製整個 repo 更容易驗證、回滾，也不會在過渡期維護兩套 scanner。
