# Risk Budget v2.1 — Availability-Corrected Timing

Risk Budget v2.1 fixes two timing defects discovered only after the first v2 production backtest was run.

## 1. Historical Score availability

A macro observation labelled month `t` is not assumed to be investable information during month `t`.

For reconstructed pre-vintage history, Elephant applies a conservative two-month publication lag:

```text
score_period = t
decision_period = t + 2 months
```

The allocation model therefore measures market momentum/drawdown at the later decision period and evaluates returns only after that point.

This is deliberately conservative and transparent. It is **not** a claim that every component historically had exactly a two-month publication lag. Exact historical release timestamps are not reconstructed for all legacy series; prospective Vintage/Decision Journal evidence remains the higher-quality authority.

## 2. Current market freshness

NDC `stock_index` remains the single historical calibration / outcome source. It is appropriate for the long history but can lag the current market state.

Risk Budget v2.1 therefore uses a second official source for a **non-overlapping role**:

- **NDC `stock_index`** — historical model fitting, analog outcomes, OOS backtest;
- **TWSE TAIEX completed-month close** — current market momentum and drawdown only.

The TWSE current window is derived deterministically from the official `MI_5MINS_HIST` daily index report by taking each completed calendar month's final trading-day close.

A current allocation review is blocked if the TWSE window is more than one month behind the expected latest completed month.

## Why this is not a second calibration source

TWSE data does not enter the historical nearest-neighbor training set. NDC remains the historical market source. TWSE only supplies the current query point so the allocation review is not based on a stale market state.

## Authority remains unchanged

Risk Budget v2.1 is still a challenger:

- v1 `risk_budget.json` remains authoritative;
- no deterministic Score is changed;
- no Capital OS, Alpha, Investment Constitution, or security-selection action is changed;
- no trade can be executed;
- no automatic promotion is allowed.

## Promotion evidence

The existing v2 promotion gates remain intact and additionally operate on the availability-corrected backtest. At least 24 genuinely resolved prospective outcomes are still mandatory before the challenger can become only `PROMOTION_ELIGIBLE_FOR_REVIEW`.
