# Consultant_System × stock × Elephant — system contract

## First-principles objective

The three repositories answer three different questions and must remain directionally coupled but authority-separated:

```text
Consultant_System: What external research context exists, and is its provenance healthy?
stock:             Does this security deserve BUY CANDIDATE status on its own evidence?
Elephant:          Given macro, liquidity, debt, concentration and portfolio risk, what capital action is reviewable?
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
              prospective calibration   │
                                        ↓
Official Taiwan macro data ─────────→ Elephant
SEGIS structural context ────────────→ Elephant
                                        ↓
                         Macro regime / risk envelope
                         Capital Allocation OS
                         Browser-local personal portfolio
                         REVIEW plan only; no trading
```

There is intentionally no direct Consultant_System → stock scoring path. External consultant research can challenge or contextualize an Elephant view, but it cannot silently create security BUY authority.

## Authority matrix

| Question | Canonical owner | Allowed inputs | Must not do |
| --- | --- | --- | --- |
| Research discovery / provenance health | Consultant_System | Public publisher discovery surfaces | Economic score, security action |
| Security research / valuation / Alpha | stock | Official market data + security-specific first-party evidence | Portfolio sizing, leverage, automatic trading |
| Security BUY / VERIFY / WATCH / AVOID | stock | Deterministic Security Buy Gate | Be overridden by macro optimism |
| Security realized/probability calibration evidence | stock | Point-in-time forecasts + future market outcomes | Retroactively rewrite historical priors or bypass Buy Gate |
| Macro diagnosis | Elephant | Official economic data | Be changed by consultant narrative |
| Structural geographic context | Elephant | Validated official SEGIS public machine data | Change deterministic macro/security scores |
| Research Evidence / Contradictions / Risks | Elephant consuming Consultant_System | Validated consultant snapshot | Change deterministic score |
| Cash / debt / leverage / concentration / sizing | Elephant | Public model artifacts + browser-local user inputs | Write private portfolio state to GitHub |
| Model challenger review | Elephant | Point-in-time/common-sample validation evidence | Auto-promote a challenger without sample gates/version change |
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

The canonical security artifact is stock Alpha schema v6 (`security-v6.0.0`). Elephant must verify before accepting it:

- Alpha schema version 6 and supported decision-engine version;
- canonical `base_upside_pct` / `min_base_upside_pct` / `buy_gate.base_upside` names;
- researched security score and confidence ranges;
- canonical action enum only;
- Screen is fail-closed and explicitly not a Buy Gate;
- discovery candidates carry no portfolio action;
- market-complete promotion contract is satisfied;
- performance calibration uses the BUY_CANDIDATE primary cohort;
- prospective Bear/Base/Bull calibration preserves a minimum resolved-sample guardrail.

Elephant may attach macro context and portfolio constraints, but must preserve the upstream stock action as security authority. Elephant republishes the quantity as `base_upside_pct`; it does not reintroduce the legacy MOS name.

### SEGIS → Elephant

SEGIS is an official **structural-context** source, not a deterministic-score input. The current canonical product is `114年12月行政區工商家數_鄉鎮市區`.

Elephant accepts a refresh only when:

- the official product page still declares the exact product public and no-application-required;
- the page itself advertises and exposes the JSON machine service URL;
- `Info`, `ColumnList` and `RowDataList` are present and machine-decodable;
- declared `OutTotal` equals the actual row count;
- `INFO_TIME`, county/town IDs and names, and `C_CNT` are present;
- township IDs are unique;
- counts are finite and non-negative;
- the snapshot contains one coherent official period.

The normalized artifact is `data/segis.json`. Administrative coverage follows the official product; missing geography is never imputed. SEGIS remains non-critical to deterministic macro scoring, and a failed refresh preserves last-good data.

## Visualization contract

Every dynamic visualization must answer one question and expose the scale needed to read it correctly.

1. **Observed values are connected with straight segments.** No spline smoothing is used for monthly / quarterly official observations because curvature between observations is not measured data.
2. **Units are visible on the Y axis.** A tooltip or table-only unit is insufficient.
3. **Reference lines are semantic, not decorative.** Examples: 0% for signed growth rates, 50 for PMI/NMI, 0 for Elephant -100…+100 direction scores, 60/75 for AI Concentration labels.
4. **Dual-axis charts carry an explicit warning.** They may show timing relationships but must not invite direct slope or height comparison across different units.
5. **Index level is not growth.** Base-year 100 is labeled as the reference level and must not be read as a normal/neutral economic threshold.
6. **Score is not probability.** Alpha Score, Confidence, Expected Return, Cycle Score and AI Concentration are different quantities and must never share ambiguous language.
7. **Historical reconstruction is labeled.** Revised-series reconstruction is not presented as point-in-time forecast performance.

## UI information hierarchy

The user should be able to move from action to evidence without mixing authority:

```text
1. What changed / what action is reviewable?
2. Why? Macro + security authority + portfolio constraints
3. What evidence supports or contradicts it?
4. How reliable is the model / sample?
5. Raw data, provenance, SQL and operational health
```

The overview should not duplicate every downstream tool. Detailed model validation, research SQL and raw coverage belong in dedicated tabs or expandable evidence surfaces.

## Model semantics and validation state

These are explicit model contracts. “Implementation complete” does not mean “empirically proven.” Evidence-dependent promotion remains fail-closed until future samples mature.

### Elephant deterministic macro Scores

- Score weights and transforms are deterministic, inspectable production heuristics.
- Domestic Demand real-growth components use exact multiplicative deflation: `(1 + nominal YoY)/(1 + CPI YoY) - 1`; CPI missing means the real component is missing.
- USD/TWD is diagnostic-only in Financial Conditions with deterministic weight zero because its economic direction is not monotonic.
- Validation OS v1.1 compares production weights against a predeclared equal-weight challenger on identical common score months and identical future Cycle outcomes at 3M/6M.
- A winner cannot be declared below 36 common observations at both horizons. Challenger promotion is never automatic and requires a versioned model decision.

Therefore the challenger **infrastructure is implemented**; statistical evidence remains prospective/ongoing by nature.

### stock Alpha schema v6

The legacy MOS-named field has been migrated without changing economics:

```text
base_upside_pct = base_fair_value / reference_price - 1
```

The schema is now:

```text
margin_of_safety_pct       → base_upside_pct
min_margin_of_safety_pct   → min_base_upside_pct
buy_gate.margin_of_safety  → buy_gate.base_upside
```

This migration does not implement classical margin of safety `(fair_value - price) / fair_value` and does not retune the Buy Gate.

### Alpha realized-return calibration

- Primary cohort: actual `BUY_CANDIDATE` entry transitions.
- Outcomes: forward stock price return minus TSMC price return at 1/4/13/26/52 weeks.
- Minimum sample requirement remains fail-closed.
- `INSUFFICIENT_HISTORY` is a correct production state and must not be relabeled as predictive skill.

The calibration **pipeline is implemented**; evidence cannot be manufactured before sufficient future observations exist.

### Scenario-probability calibration

stock owns a prospective Bear/Base/Bull forecast ledger:

- forecast probabilities and fair values are frozen prospectively;
- 52-week realized prices are classified using the midpoint between Bear/Base and Base/Bull fair values;
- multiclass Brier score measures probability quality;
- repeated same-security forecasts are spaced by at least 28 days;
- outcome resolution allows at most 14 days from the declared due date;
- at least 30 resolved forecasts are required before status may become `CALIBRATED`.

Elephant consumes this ledger as **calibration evidence only**. It may support a future separately versioned challenger but cannot silently rewrite upstream scenario probabilities, Buy Gate authority or portfolio sizing.

## Canonical browser-local PortfolioState

Elephant uses one canonical browser-local state contract:

```text
elephant.portfolio.v3
        ↓
PortfolioState schema v3
        ├─ Command Center
        ├─ Decision Engine portfolio envelope
        └─ Personal Capital
```

Rules:

- `elephant.portfolio.v2` is the authoritative previous-version migration source when present;
- only browsers without v2 fall back to the older `elephant.portfolio.v1` + `elephant.personal.capital.v3` pair, where detailed holdings/debt semantics win;
- migration writes and verifies `elephant.portfolio.v3` before deleting all migration-source keys;
- old keys are no longer live aliases and post-migration writes to them cannot change canonical state;
- all three browser consumers read/write only through `window.ElephantPortfolioState`;
- writes are merged into the canonical state instead of replacing unrelated fields;
- when detailed holdings are present, `equity` and `largest` are derived from those holdings and are authoritative;
- a simplified calculator may update common fields such as total, cash or drawdown tolerance, but cannot overwrite holdings-derived equity / largest with contradictory values;
- Personal Capital fields such as debt, collateral, maintenance threshold, liquidity need, human capital and transaction frictions remain preserved when simpler views write;
- all state stays in browser `localStorage`; it is never written to GitHub or public artifacts;
- PortfolioState only supplies private inputs to review models. It does not grant security BUY authority and does not place trades.

Migration is covered by both deterministic storage tests and a real Chromium E2E that starts from legacy state, loads the deployed application shell, writes through Command Center and Decision Engine, reloads, and confirms all views rehydrate from one v3 key.

## External-source constraints

A public-data connector is “complete” only if it is reproducible, first-party/official where required, machine-verifiable, and fail-closed/last-good safe. TLS verification must never be disabled merely to make a source green.

Current source policy:

- DGBAS wage/employment XML may fall back to equivalent official publication/news semantics when the XML transport certificate fails validation.
- MOEA live structural tables and official fallbacks are preferred over dead legacy endpoints; last-good retention is explicit.
- non-critical benchmark pages may retain last-good first-party observations when a current parse fails.
- SEGIS uses the JSON service URL advertised by the official canonical product page, validates the complete machine schema, and writes normalized township/district business counts to `data/segis.json`. It is structural context only and never changes deterministic score authority.

Degraded states remain explicit integrity controls, not permission to weaken verification.
