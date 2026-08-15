# Elephant Validation OS v1

Validation OS is a **non-authoritative evidence layer**. It exists to challenge Elephant's models, not to create a second decision authority.

## Contracts

- Production deterministic Scores remain unchanged.
- Decision Engine v1 remains authoritative.
- Risk Budget v2.1 remains a challenger.
- Capital OS, Alpha and the Investment Constitution remain authoritative in their existing scopes.
- Validation OS cannot trade or self-promote any model.

## 1. Effective Data Confidence

A Score having every component is not the same as having perfect evidence. Validation OS decomposes each of the five diagnosis dimensions into:

1. **Completeness** — production component coverage.
2. **Freshness** — weighted lag of component periods relative to the Score period.
3. **Source reliability** — current official-source pipeline health.
4. **Revision evidence maturity** — how much genuine point-in-time Vintage history has accumulated.

The published effective confidence is a weighted geometric combination. Revision evidence begins conservatively and approaches full maturity only after six months of prospective collection. Zero observed revisions on day one is never interpreted as proof of stability.

## 2. Structural Break Monitor

The monitor combines three distinct questions:

- How similar is the current five-dimensional state to its nearest historical states?
- How unusual is each current dimension versus its trailing 60-month median/MAD distribution?
- How much has the recent 24-month cross-dimension correlation structure moved versus the prior window?

It reports `NORMAL`, `WATCH`, or `HIGH`. The result can inform reviewed confidence but cannot rewrite a Score or allocation.

## 3. Score Champion / Challenger

Growth Persistence, Domestic Demand and Financial Conditions are benchmarked against a deliberately simple **equal-weight challenger**. The component transforms and definitions are held fixed; only the weights change to 20% each. The challenger is compared with the production champion on its historical relationship to future Cycle at 3M and 6M.

The challenger can only become `CHALLENGER_WORTH_REVIEW` if a predeclared improvement threshold is met. It can never auto-promote. Cycle and AI Concentration are excluded because they do not share the same like-for-like directional composite contract.

## 4. Prospective Validation Journal

`data/validation_journal.json` starts a separate prospective-only evidence trail. Each snapshot records:

- the five Scores and the latest periods known at capture time;
- current Decision Engine v2 forecast probabilities;
- current market state;
- v1 and v2.1 aggregate equity budgets;
- researched Alpha actions and point-in-time reference prices.

Outcomes are counted only when they were genuinely unknown at snapshot time. No historical row is backfilled and called prospective evidence.

The scorecards are separated into:

- **Macro** — direction/Brier results for the five forecast dimensions;
- **Risk** — realized market drawdown and the risk budgets used;
- **Portfolio envelope** — v1/v2/static-60 scaled market outcomes, not the user's private portfolio;
- **Alpha** — later observed researched-security returns and market-relative outcomes when point-in-time follow-up prices exist.

Personal holdings and debt remain browser-local and are never written into this journal.
