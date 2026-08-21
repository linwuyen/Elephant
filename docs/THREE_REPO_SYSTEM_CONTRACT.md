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
TWSE / TPEx → stock → alpha.json ─→ Elephant
              Security Buy Gate        │
              BUY/VERIFY/WATCH/AVOID   │
                                       ↓
Official Taiwan macro data ────────→ Elephant
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
| Macro diagnosis | Elephant | Official economic data | Be changed by consultant narrative |
| Research Evidence / Contradictions / Risks | Elephant consuming Consultant_System | Validated consultant snapshot | Change deterministic score |
| Cash / debt / leverage / concentration / sizing | Elephant | Public model artifacts + browser-local user inputs | Write private portfolio state to GitHub |
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

Elephant must validate before accepting Alpha artifacts:

- supported Alpha / Screen / Performance schema versions;
- researched security score and confidence ranges;
- canonical action enum only;
- Screen is fail-closed and explicitly not a Buy Gate;
- discovery candidates carry no portfolio action;
- market-complete promotion contract is satisfied;
- performance calibration uses the BUY_CANDIDATE primary cohort.

Elephant may attach macro context and portfolio constraints, but must preserve the upstream stock action as security authority.

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

## Model-semantics contract and remaining debt

These are not display bugs; they are explicit modeling assumptions or legacy names and must not be presented as objective economic facts.

- **Elephant score weights and linear transforms are hand-defined heuristics.** They are deterministic and inspectable, but the chosen weights / saturation points remain hypotheses until challenger / prospective validation demonstrates information value.
- **Domestic Demand real-growth components use exact multiplicative deflation.** Real wage and credit-card spending use `(1 + nominal YoY)/(1 + CPI YoY) - 1`; CPI missing means the real-growth component is missing rather than silently falling back to nominal growth.
- **USD/TWD is diagnostic-only in Financial Conditions.** Exchange-rate direction is not assumed monotonic because competitiveness, imported inflation, capital flow and risk-off effects can conflict. Its deterministic score weight remains zero until explicit validation supports promotion.
- **stock `margin_of_safety_pct` is a legacy field name.** Its current formula is `base_fair_value / reference_price - 1`, i.e. base-case price upside, not the classical safety discount `(fair_value - price) / fair_value`. UI displays `Base upside` until a versioned schema migration changes the field.
- **stock Expected Return is scenario-probability weighted fair-value upside.** The scenario probabilities are model inputs; the number is not a statistically calibrated probability forecast unless prospective calibration establishes that claim.
- **stock Alpha / Confidence are scores, not probabilities.** Current performance data can remain `INSUFFICIENT_HISTORY`; no score should be described as validated predictive skill before minimum sample requirements are met.

## Canonical browser-local PortfolioState

Elephant uses one canonical browser-local state contract:

```text
elephant.portfolio.v2
        ↓
PortfolioState schema v2
        ├─ Command Center
        ├─ Decision Engine portfolio envelope
        └─ Personal Capital v3
```

Rules:

- legacy `elephant.portfolio.v1` and `elephant.personal.capital.v3` are migrated into schema v2 and remain temporary compatibility aliases;
- writes are merged into the canonical state instead of replacing unrelated fields;
- when detailed holdings are present, `equity` and `largest` are derived from those holdings and are authoritative;
- a simplified calculator may update common fields such as total, cash or drawdown tolerance, but cannot overwrite holdings-derived equity / largest with contradictory values;
- Personal Capital fields such as debt, collateral, maintenance threshold, liquidity need, human capital and transaction frictions remain preserved when simpler views write;
- all of this state stays in browser `localStorage`; it is never written to GitHub or public artifacts;
- PortfolioState only supplies private inputs to review models. It does not grant security BUY authority and does not place trades.

The compatibility aliases are migration scaffolding, not additional sources of truth. A later cleanup may remove them only after the deployed population no longer depends on legacy keys.
