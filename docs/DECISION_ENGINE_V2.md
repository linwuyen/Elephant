# Elephant Decision Engine v2 — Prospective Validation Challenger

Decision Engine v2 exists to answer one question:

> Does Elephant improve future decisions out of sample, or does it merely explain revised history well?

It is deliberately **non-authoritative**. v1 deterministic Scores, v1 Risk Budget, Capital OS and the Alpha Buy Gate remain the production authorities.

## 1. Strict walk-forward OOS

For every historical prediction at month `t`, a training example is eligible only when its outcome was already observable:

```text
training.outcome_period <= prediction_period(t)
```

This removes calibration leakage from using the same full history to fit and score a forecast. The implementation uses an expanding window and keeps the existing transparent score-bin + Bayesian shrinkage family so the challenger is explainable.

Pre-vintage score history is still reconstructed from currently revised official series. Therefore strict temporal OOS removes model-fit look-ahead, but it cannot retroactively remove official revision bias. Prospective `vintages.db` and Decision Journal outcomes remain the highest-quality evidence.

## 2. Sample-aware Model Confidence

A good Brier score from a tiny sample is not strong evidence. v2 Model Confidence combines:

- Brier skill versus a climatology baseline
- direction accuracy
- global OOS sample adequacy
- local current-bin sample adequacy
- prospective resolved-outcome support
- current regime similarity

The reconstructed-history evidence factor starts below 1 and can rise only as prospective outcomes mature.

## 3. External real-world outcomes

v2 does not validate Scores only against future Scores. Existing official NDC / DGBAS series are used as external outcome targets:

- industrial production YoY
- customs exports YoY
- employment YoY
- NDC stock-index forward return
- NDC stock-index forward drawdown

These are evidence targets, not trading signals or return guarantees.

## 4. Risk Budget diagnostic backtest

The v1 Risk Budget formula is reconstructed historically without changing its production parameters. v2 tests whether higher historical risk scores were associated with:

- stronger future stock-index returns
- shallower future drawdowns
- improved scaled-equity path versus a static 60% equity exposure

The path comparison assumes 0% cash return and excludes transaction costs. It is explicitly a **diagnostic**, not a tradable performance claim.

## 5. Regime similarity

The current five-dimensional state:

```text
Cycle
Growth Persistence
Domestic Demand
Financial Conditions
AI Concentration
```

is compared with historical states. Low similarity applies a confidence penalty. This prevents a structurally unusual regime from receiving the same confidence as a well-supported historical regime.

## 6. Multi-dimension prospective scorecard

v2 evaluates Decision Journal forecasts separately for all five dimensions instead of judging the entire system only by future Cycle Score. It does not rewrite historical journal entries.

## 7. Promotion gate

v2 can never self-promote. At minimum the challenger requires:

- positive strict-OOS Brier skill on enough core 3M/6M metrics
- at least four adequately sampled core OOS metrics
- at least 36 Risk Budget backtest observations
- at least 24 resolved prospective outcomes
- external outcome evidence present

Even when every gate passes, status becomes only:

```text
PROMOTION_ELIGIBLE_FOR_REVIEW
```

An explicit reviewed model-version change is still required before v2 may replace any v1 authority.

## Artifacts

```text
data/decision_engine_v2.json
scripts/build_decision_engine_v2.py
scripts/validate_decision_engine_v2.py
scripts/test_decision_engine_v2.py
```

The artifact is rebuilt by the official refresh pipeline and by Pages CI.
