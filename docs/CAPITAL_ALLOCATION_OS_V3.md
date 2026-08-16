# Capital Allocation OS v3.2

Elephant v3.2 answers one marginal-capital question:

```text
What should the next dollar do after opportunity cost, horizon normalization,
transaction friction, correlation, liquidity and leverage — without allowing any
downstream model to invent a BUY?
```

## Authority boundary

```text
linwuyen/stock
  Market Screen → Security Research → Valuation → Alpha Buy Gate
                                │
                                ▼
Elephant
  Macro → Comparable Opportunity Set → Constitution → Portfolio/Risk
        → Decision Journal → Shadow Book → Calibration
```

Hard rules:

- Elephant never upgrades `WATCH` / `VERIFY` into `BUY_CANDIDATE`.
- Investment Constitution cannot create upstream BUY authority.
- Macro and expectation analysis are context/analytics only.
- Public repo never stores personal holdings, debt, collateral or brokerage maintenance rules.
- No automatic trading.

## 1. Comparable-return contract

Raw expected returns with different native horizons are retained for audit but never compared directly.

The canonical public comparison basis is:

```text
ANNUALIZED_NOMINAL_PRE_TAX_AFTER_PUBLIC_FRICTION
```

For a native total return `R` over `H` months, public round-trip friction is first applied to terminal value; the result is then annualized.

Every comparable alternative exposes:

- `native_expected_return_pct`
- `native_horizon_months`
- `annualized_expected_return_pct`
- `comparison_basis`

The opportunity hurdle is selected only from AVAILABLE annualized alternatives.

## 2. Market-implied expectation analysis

For scenario-PE securities, Elephant derives:

```text
market_implied_eps = reference_price / base_case_multiple
```

and reports the gap between market-implied EPS and the upstream base / normalized EPS.

This layer answers “what must the market already believe?” It is `ANALYTIC_ONLY` and has no BUY authority.

## 3. Scenario probability provenance

Bear / Base / Bull probabilities remain upstream model assumptions until prospective samples satisfy the calibration contract.

Each distribution publishes probability source, calibration status, resolved sample count, minimum sample count and whether an empirical override is authoritative. No silent probability rewrite is allowed.

## 4. Investment Constitution research seed

`data/constitution_research.json` contains explicit 24–36 month research records for the initial seed set:

- 2301 光寶科
- 2376 技嘉
- 2451 創見

Forward EPS/multiple values are explicitly marked `MODEL ASSUMPTION`, never company guidance. Missing dedicated survival evidence remains `INCOMPLETE`, which fail-closes the Constitution rather than manufacturing PASS.

## 5. Research queue as a Value-of-Information queue

The deep-research queue now asks the smallest question most capable of changing capital eligibility. Each item contains archetype, `voi_priority`, decision question, explicit unknowns, pass signal, fail signal and first-party source priority. Extreme growth/base-effect flags raise research priority, not BUY authority.

## 6. Survival before sizing

Server-side risk remains unconfigured while the public portfolio sentinel is empty. When a private portfolio is configured, risk evaluation uses factor stress scenarios from `portfolio_model.json`, reverse market shocks, debt/assets, concentration constraints and brokerage-maintenance state when supplied privately.

Unknown leveraged maintenance rules fail closed. `target_sizing` cannot become COMPLETE unless the survival gate passes. The browser-private planner remains the authoritative location for personal collateral, maintenance ratio, liquidity need, debt rate, transaction cost and human-capital inputs.

## 7. Shadow Book

`data/shadow_book.json` records all upstream researched securities prospectively, not only BUY entries.

Primary calibration has exactly one forecast pointer per:

```text
decision_period + ticker
```

If the model reruns in the same period, the old forecast remains immutable but becomes a revision rather than an independent sample. Discovery-only candidates are recorded without fabricated expected returns.

Primary KPI:

```text
realized security price return - realized TSMC price return
```

Current decision-regret scope is explicitly `TSMC_ONLY` until point-in-time prices for every alternative are available.

## 8. Capital Decision Journal

`data/capital_decision_journal.json` separates immutable decision snapshots, same-period model/input revisions and one primary snapshot pointer per ISO decision week. Only primary pointers enter the primary decision cohort. Repeated debug/rerun snapshots cannot inflate sample size.

## 9. Calibration order

Elephant now accumulates three distinct learning loops:

1. Macro calibration — state/forecast probability quality.
2. Security calibration — expected Alpha versus realized opportunity-cost Alpha.
3. Portfolio calibration — decision regret and capital-allocation quality.

Scenario probabilities remain priors until the prospective sample floor is met.

## Governance invariant

```text
Prediction → Decision → Outcome → Calibration
```

is the product loop. New dashboards, indicators, sentiment or model complexity should not outrank accumulation of clean point-in-time samples.
