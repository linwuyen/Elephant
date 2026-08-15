# Capital Allocation OS v3

Elephant v3 answers the marginal-capital question under explicit uncertainty:

```text
What should the next dollar do, after opportunity cost, correlation, human capital,
liquidity, leverage and transaction friction, without fabricating unavailable facts?
```

## Public deterministic layer

Artifacts:

- `data/opportunity_market_facts.json` — first-party benchmark facts (0050 / VT / CBC proxy), last-good on transient failure.
- `data/opportunity_inputs.json` — modelled public expected-return alternatives. Issuer/CBC facts are not forecasts.
- `data/security_official_facts.json` — TWSE/MOPS OpenAPI monthly revenue / income statement / balance sheet for the research universe.
- `data/security_fact_store.json` — normalized security/evidence store with explicit research completeness.
- `data/portfolio_model.json` — transparent factor loadings, covariance assumptions, stress scenarios and human-capital profiles.
- `data/scenario_probability_calibration.json` — prospective probability calibration gate. Priors stay authoritative until enough real samples exist.
- `data/investment_calibration.json` — prospective realized opportunity-cost Alpha journal.
- `data/model_governance.json` — model version, code commit and artifact fingerprints.

## Opportunity set

Public alternatives are:

```text
2330 TSMC
TAIWAN_BROAD (0050 proxy)
GLOBAL_EQUITY (VT proxy)
CASH (CBC policy-rate proxy)
```

For 0050 / VT the public expected-return model is:

```text
ER = earnings yield + sustainable nominal growth assumption
```

This is an Elephant model estimate, **not issuer guidance**. Missing/stale facts make the alternative unavailable.

Debt repayment is never stored publicly. Its effective rate is entered only in the browser-private planner.

## Private capital layer

`personal_capital.js` stores all private values under browser `localStorage` only:

- holdings / cash
- debt and effective rate
- pledged collateral / maintenance threshold
- 12-month liquidity need
- human-capital equivalent and profile
- maximum acceptable drawdown
- commission / tax / slippage / FX cost assumptions

It computes a review-only portfolio using a constrained expected-log-growth approximation, transparent factor covariance, human-capital covariance penalty, risk-capacity-derived cash floor, drawdown/forced-sale proxies and deterministic reverse stress.

Only public alternatives plus upstream `BUY_CANDIDATE` securities may receive **new** Alpha allocation. Unknown existing holdings are not force-sold. `TRIM/EXIT` requires lifecycle authority. The planner never connects to a broker and never submits orders.

## Probability of ruin

The private planner reports model estimates for:

- probability of breaching user-selected 12M drawdown
- liquidity forced-sale proxy
- collateral maintenance breach proxy
- post-stress debt/assets under named reverse stresses

These are transparent model estimates, not guarantees or broker maintenance-rule calculations.

## Calibration

Primary investment KPI:

```text
realized opportunity-cost alpha
= security realized return - benchmark realized return
```

The decision record binds model version, code commit, evidence hash, expected return, hurdle and entry reference price. Future outcome fields may be appended; original decision inputs are immutable.

Scenario-probability recalibration requires prospective samples. Before the minimum sample threshold, Elephant preserves the upstream priors instead of manufacturing empirical probabilities.

## Governance

Hard boundaries:

```text
Screen / Research Queue != BUY authority
Macro != Alpha authority
Portfolio optimizer != BUY authority
Personal data != GitHub
Model estimate != official forecast
Missing data != zero
No automatic trading
```
