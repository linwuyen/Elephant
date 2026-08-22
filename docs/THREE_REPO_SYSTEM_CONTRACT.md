# Consultant_System × stock × Elephant — system contract

## First-principles objective

The system exists to reduce expected decision error under incomplete information, not to maximize dashboard features.

```text
Information → Belief → Decision → Outcome → Learning
```

The three repositories remain authority-separated:

```text
Consultant_System: What external research context exists, and is its provenance healthy?
stock:             Does this security deserve BUY CANDIDATE status on its own evidence?
Elephant:          Given macro, evidence quality, portfolio risk and opportunity cost, what capital action is reviewable?
```

No repository is allowed to answer the next repository's question by shortcut.

## Canonical data flow

```text
McKinsey / BCG / Deloitte / PwC
        ↓
Consultant_System
  metadata / provenance / ingestion health
        ↓  research-context-only, score_influence=false
        └──────────────────────────────┐
                                       ↓
TWSE / TPEx → stock → Alpha schema v6 ─→ Elephant
              Security Buy Gate         │
              BUY/VERIFY/WATCH/AVOID     │
              total-return calibration  │
              scenario calibration      │
              research VOI              │
                                        ↓
Official Taiwan macro data ─────────→ Elephant
SEGIS structural context ────────────→ Elephant
                                        ↓
                         Macro regime / evidence confidence
                         Validation OS / PIT learning
                         Capital Allocation OS / frontier
                         Browser-local personal portfolio stress
                         REVIEW plan only; no trading
```

There is intentionally no direct Consultant_System → stock scoring path. External consultant research can challenge or contextualize an Elephant view, but it cannot silently create security BUY authority.

## Authority matrix

| Question | Canonical owner | Allowed inputs | Must not do |
| --- | --- | --- | --- |
| Research discovery / provenance health | Consultant_System | Public publisher discovery surfaces | Economic score, security action |
| Security research / valuation / Alpha | stock | Official market data + security-specific first-party evidence | Portfolio sizing, leverage, automatic trading |
| Security BUY / VERIFY / WATCH / AVOID | stock | Deterministic Security Buy Gate | Be overridden by macro optimism or VOI |
| Security realized/probability calibration evidence | stock | Point-in-time forecasts + future market/corporate-action outcomes | Retroactively rewrite history or bypass Buy Gate |
| Security research scheduling | stock | Gate proximity + evidence gap + model uncertainty | Become a probability, score, Buy Gate, or sizing input |
| Macro diagnosis | Elephant | Official economic data | Be changed by consultant narrative |
| Data-quality confidence | Elephant | Provenance/fallback/last-good state | Change deterministic macro/security Scores directly |
| Structural geographic context | Elephant | Validated official SEGIS public machine data | Change deterministic macro/security scores |
| Research Evidence / Contradictions / Risks | Elephant consuming Consultant_System | Validated consultant snapshot | Change deterministic score |
| Cash / debt / leverage / concentration / stress | Elephant | Public model artifacts + browser-local user inputs | Write private portfolio state to GitHub |
| Capital opportunity frontier | Elephant | Comparable expected-return/tail-risk evidence | Override Alpha, Constitution, sizing or production hurdle |
| Model challenger review | Elephant | Revised-history diagnostics + true point-in-time evidence | Auto-promote a challenger without gates/version change |
| Execution | None | Review output only | Place orders automatically |

## Integration invariants

### Consultant_System → Elephant

Elephant must verify before accepting a snapshot:

- supported schema version;
- `contract == research-context-only`;
- `score_influence == false`;
- manifest SHA-256 / byte-size contract;
- required publishers and minimum coverage;
- no upstream `fail` health state;
- valid SQLite header / integrity contract.

A failed sync keeps the last-good Elephant snapshot.

### stock → Elephant

The canonical security artifact remains stock Alpha schema v6 (`security-v6.0.0`). Elephant additionally consumes the decision-science evidence contract and must verify:

- Alpha schema version 6 and supported decision-engine version;
- canonical `base_upside_pct` / `min_base_upside_pct` / `buy_gate.base_upside` names;
- canonical action enum only;
- Screen is fail-closed and explicitly not a Buy Gate;
- total-return performance schema v3 uses `BUY_CANDIDATE` as the primary cohort;
- total return uses the prospective TWSE `TWT48U_ALL` corporate-action ledger;
- intervals before corporate-action coverage or with unsupported actions remain unresolved rather than approximated;
- price return is diagnostic only and cannot satisfy the total-return promotion gate;
- prospective Bear/Base/Bull calibration keeps its ≥30 resolved-sample guardrail;
- research VOI is `authority=false`, `score_influence=false`, `buy_gate_influence=false`;
- the preregistered stock model-promotion contract cannot auto-promote and cannot change without a version bump.

Elephant may attach macro context and portfolio constraints, but must preserve the upstream stock action as security authority.

### SEGIS → Elephant

SEGIS is an official structural-context source, not a deterministic-score input. The canonical product is `114年12月行政區工商家數_鄉鎮市區`.

Elephant accepts a refresh only when the official product remains public/no-application-required, exposes its machine JSON service, passes complete schema/row-count/ID/value/period checks, and produces one coherent official snapshot. Failed refreshes preserve last-good data and never grant score authority.

## Point-in-time evidence contract

`data/vintages.db` is the canonical prospective economic vintage store. It records what was actually observed and when.

For every point-in-time replay:

```text
value(as_of) = latest observation where observed_at <= as_of
```

Rules:

- a later official revision can never leak into an earlier simulated `as_of`;
- SQLite integrity and the look-ahead guardrail must pass;
- observations before vintage collection began remain latest-revised historical reconstructions;
- reconstructed history may screen challengers but can never promote a production model;
- model promotion requires at least 36 distinct true point-in-time snapshot months and separately preregistered evidence gates;
- no historical value is manufactured merely to increase sample size.

## Validation OS v1.2 target contract

A model should be tested against the outcome it claims to measure, not against one universal target.

| Dimension | Primary future validation target | Secondary diagnostic |
| --- | --- | --- |
| Cycle | future aggregate Cycle regime | — |
| Growth Persistence | future growth-persistence composite | future Cycle |
| Domestic Demand | future domestic-demand composite | future Cycle |
| Financial Conditions | future financial-conditions composite | future Cycle |
| AI Concentration | future concentration persistence | — |

Production vs equal-weight challengers are compared on identical common periods and identical dimension-appropriate future outcomes at 3M/6M. A minimum of 36 common observations is required for review, but revised-history evidence alone still cannot promote a model. Promotion is never automatic.

## Data Quality SLO

A pipeline being green does not imply identical evidence quality. Elephant classifies source integrity separately:

```text
A  direct verified production source, no active degradation
B  first-party equivalent recovery/fallback or mixed direct + last-good package
C  explicit degraded / last-good state
D  unknown or stale quality requiring review
F  blocked, failed, or semantic mismatch
```

The SLO may reduce evidence/data confidence. It **must not** change deterministic macro/security Scores directly. TLS verification is never disabled to manufacture an A-grade source.

## Decision attribution

The system reports only causal statements it can support.

Current attribution can exactly report:

- Score deltas;
- risk-budget/posture deltas;
- Alpha action changes;
- official revision events between decision snapshots;
- contemporaneous non-A source-quality states.

It does **not** invent per-component percentage-point causal attribution from correlated snapshot changes. One-factor counterfactual attribution becomes eligible only when sufficient true point-in-time vintages exist.

## stock learning loop

### Base-upside semantics

```text
base_upside_pct = base_fair_value / reference_price - 1
```

The legacy MOS-named field was migrated without changing economics and is not classical margin of safety.

### Realized-return calibration

- primary cohort: actual `BUY_CANDIDATE` entry transitions;
- horizons: 1/4/13/26/52 weeks;
- eligible outcome: cash-distribution-inclusive total return minus TSMC total return;
- TWSE corporate actions are captured prospectively;
- periods before action-ledger coverage remain unresolved;
- minimum sample gate remains ≥30;
- `INSUFFICIENT_HISTORY` is a correct production state.

### Research Value of Information

VOI is a deterministic research-scheduling proxy based on decision-boundary proximity, evidence/freshness gaps, uncertainty and the existence of a concrete next question. It is not a probability, security score, Buy Gate, or sizing authority.

### Scenario-probability calibration

Forecast probabilities/fair values remain frozen prospectively; 52-week outcomes are classified by the original Bear/Base/Bull boundaries; multiclass Brier score is used; forecasts are spaced to reduce pseudo-replication; ≥30 resolved forecasts are required before `CALIBRATED`.

## Capital opportunity frontier

Expected return alone is insufficient for cross-asset dominance. Elephant publishes a diagnostic frontier only where standardized evidence supports comparable expected return and tail-risk quantities.

Missing risk/liquidity evidence is reported explicitly; it is never imputed merely to complete a frontier. The production opportunity hurdle remains unchanged until a separately versioned capital-model decision is validated.

## Canonical browser-local PortfolioState and stress

Canonical private state remains:

```text
elephant.portfolio.v3
        ├─ Command Center
        ├─ Decision Engine
        ├─ Personal Capital
        └─ Portfolio Risk / Stress
```

All state stays in browser `localStorage`. Detailed holdings remain authoritative for equity/largest-position values. Browser stress may compute concentration, broad-equity shock, largest-name shock, Top-3 shock, liquidity shortfall and post-shock debt ratios.

Ticker→AI/sector/FX factor labels are not inferred from names. Factor exposures remain unavailable until backed by a verified public mapping contract. Stress analysis cannot create BUY authority, place trades or write private holdings to GitHub.

## Statistical challenger policy

Simple statistical models may run as non-authoritative diagnostics on latest-revised history:

- expanding-window Ridge;
- EWMA state estimate;
- Bayesian shrinkage mean.

Dynamic Factor Model, MIDAS and broader Bayesian model averaging remain blocked from production use until a sufficiently mature point-in-time mixed-frequency feature matrix exists. Complexity is not evidence; every challenger must beat the simpler champion under the preregistered point-in-time contract before a versioned human review may promote it.

## Model-promotion governance

Promotion rules are registered before future outcomes are known. Changing a target, horizon, threshold or eligible metric after seeing outcomes requires an explicit version bump and cannot retroactively rewrite the old experiment.

No challenger, Validation OS output, VOI rank, consultant claim, macro optimism or portfolio stress result can automatically:

- upgrade a stock to BUY;
- change production model weights;
- change the production hurdle;
- size a private portfolio;
- execute a trade.

## Visualization contract

1. Observed values use straight segments; no invented spline curvature.
2. Y-axis units are visible.
3. Reference lines are semantic.
4. Dual-axis charts warn against direct magnitude/slope comparison.
5. Index level is not growth.
6. Score is not probability.
7. Historical reconstruction is labeled and never presented as point-in-time performance.

## UI information hierarchy

```text
1. What changed / what action is reviewable?
2. Why? Macro + security authority + portfolio constraints
3. What evidence supports or contradicts it?
4. How reliable is the source/model/sample?
5. What changed since the previous decision?
6. Raw data, vintages, provenance and operational health
```

The system is considered engineering-complete when capture, validation, fail-closed gates and audit paths exist. It is considered empirically validated only after the preregistered future evidence actually matures. Those two states must never be conflated.
