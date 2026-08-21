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

## Known architecture debt

Elephant currently contains multiple browser-local portfolio interfaces (`Command Center`, Decision Engine portfolio envelope, Personal Capital v3). They serve related but not identical models and do not share one canonical state schema. Until consolidated, the UI should treat Personal Capital v3 as the most complete ruin/liquidity/leverage analysis surface and avoid implying that the smaller calculators are equivalent optimizers.

The next structural cleanup should establish one browser-local `PortfolioState` contract and let other views become read-only projections of that state.
