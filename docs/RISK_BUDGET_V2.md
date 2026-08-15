# Elephant Risk Budget v2 — Market-Aware Allocation Challenger

Risk Budget v2 answers a narrower and more useful question than the v1 macro-risk score:

> Given the macro state **and where the market already is**, how much aggregate equity risk is justified over the next six months?

It is deliberately **non-authoritative**. `risk_budget.json`, Decision Engine v1, Capital OS, Alpha and the Investment Constitution remain production authorities.

## Why v2 exists

Risk Budget v1 assumes stronger Cycle / Growth / Financial Conditions should generally increase equity exposure. Decision Engine v2 historical diagnostics showed that this assumption is not empirically safe: high reconstructed v1 Risk Scores were associated with weaker 12-month returns and deeper forward drawdowns.

Risk Budget v2 therefore separates:

1. **economic state** — Cycle, Growth Persistence, Domestic Demand, Financial Conditions, AI Concentration;
2. **market state** — trailing 6-month index momentum and trailing 6-month drawdown;
3. **allocation evidence** — realized next-6-month index return and next-6-month drawdown.

Economic strength is not assumed to be expected return.

## Strict walk-forward model

For prediction month `t`, a historical state is eligible for training only when its six-month outcome had already occurred:

```text
training.outcome_period <= prediction_period(t)
```

The model uses the 12 nearest historical states in a fixed normalized feature space. Neighbor outcomes are inverse-distance weighted.

The predicted return and drawdown are converted into historical percentiles:

```text
allocation_score = 50% × return_percentile
                 + 50% × drawdown_quality_percentile
```

A high score therefore requires both attractive forward return evidence and relatively survivable forward drawdown evidence.

## Evidence shrinkage

The raw policy range is 35–85% equity. It is **not** used directly.

```text
raw_target = 35% + 0.50 × allocation_score

target = 60% + evidence_confidence × (raw_target - 60%)
```

Evidence Confidence combines historical sample adequacy and analog similarity. Current regime similarity adds an additional confidence penalty.

Weak evidence therefore converges toward a static **60% neutral equity anchor**, rather than creating an extreme position from a fragile analogy.

## Turnover guardrail

Historical and prospective review budgets are limited to:

```text
±10 equity percentage points per month
```

This is a hard policy guardrail. It reduces instability and lets the backtest expose turnover costs instead of pretending reallocations are free.

## Backtest comparators

The strict-OOS window compares three policies on the same official NDC stock-index return path:

- Risk Budget v2 challenger;
- reconstructed Risk Budget v1 champion;
- static 60% equity.

Reported metrics include:

- total return;
- max drawdown;
- return / absolute max drawdown;
- average equity exposure;
- annualized one-way turnover;
- 0 / 10 / 25 bps cost sensitivity per 100% turnover.

Cash return is assumed to be 0% in this diagnostic. This is deliberately conservative/simple and is **not a tradable performance claim**.

## Allocation authority boundary

Risk Budget v2 only proposes an **aggregate equity-risk envelope**:

```text
equity risk budget review %
cash / low-risk reserve review %
```

It does not decide:

- which stock to buy;
- Taiwan vs global equity;
- whether a security passes the Investment Constitution;
- whether an Alpha candidate is valid;
- whether to execute a trade.

Within-equity selection remains the job of Capital OS / Alpha / the Investment Constitution.

## Promotion gate

Risk Budget v2 can never self-promote. Historical review requires:

- at least 48 strict-OOS months;
- verified no-lookahead training boundary;
- return/drawdown efficiency at least 5% above v1;
- return/drawdown efficiency at least 5% above static 60;
- max drawdown no worse than v1;
- advantage versus static 60 survives 25 bps turnover-cost sensitivity;
- at least 24 resolved **prospective** outcomes.

Even if every gate passes, status becomes only:

```text
PROMOTION_ELIGIBLE_FOR_REVIEW
```

A reviewed model-version change is still required before v2 may replace v1.

## Evidence limitation

Pre-vintage Elephant Score histories are reconstructed from currently revised official series. Strict walk-forward prevents model-fit lookahead, but it cannot retroactively remove official-data revision bias. Prospective Decision Journal / Vintage outcomes remain mandatory for promotion.

## Artifacts

```text
data/risk_budget_v2.json
scripts/build_risk_budget_v2.py
scripts/validate_risk_budget_v2.py
scripts/test_risk_budget_v2.py
```
