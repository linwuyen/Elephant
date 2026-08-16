# Elephant Decision Command Center v1

The Command Center is the **decision surface**, not a new model.

Its job is to compress Elephant's existing evidence into five questions a user can act on immediately:

1. **What should I do now?**
2. **How much aggregate equity risk is justified?**
3. **How is that different from the last prospective baseline?**
4. **Why is the answer what it is?**
5. **What observable condition would change the answer?**

## Authority contract

The Command Center creates no new decision authority.

- Risk Budget v1 remains the champion / authoritative aggregate-risk rule.
- Risk Budget v2.1 remains the market-aware challenger.
- The displayed `operating zone` is simply the interval between those two already-published outputs; it is not a third target.
- Validation OS may reduce reviewed confidence but cannot rewrite a Score, Risk Budget, Alpha action or trade.
- Only the upstream Alpha Buy Gate may create a security-level `BUY` candidate.
- Personal holdings stay browser-local and are never written to GitHub.
- No automatic trading exists.

## Command policy

The compiler deliberately separates **risk capacity** from **capital deployment**.

- Above the operating zone: reduce aggregate equity exposure toward the upper bound.
- Inside the zone: normally hold; a BUY candidate permits selective deployment or rotation, not automatic levering to the upper bound.
- Below the zone with no BUY candidate: preserve cash / low-risk assets. Risk capacity does not force stock purchases.
- Below the zone with a BUY candidate: deployment capacity is capped by the lower review bound and still requires security-level sizing review.
- If critical data are unavailable, the command is blocked rather than produced with fake precision.

## Decision Delta

`decision_delta` compares the current command inputs with the most recent genuine prospective Validation Journal snapshot. It reports changes in:

- v1 equity budget;
- v2.1 equity review budget;
- Cycle;
- Growth Persistence;
- Domestic Demand;
- Financial Conditions;
- AI Concentration.

It never manufactures historical prospective snapshots.

## Counterfactual engine

The Command Center reuses the exact v2.1 historical training set and changes only a declared state to answer practical sensitivity questions:

- market 6M momentum reset to zero;
- AI Concentration reset to 50;
- all four directional macro Scores down 15 points;
- a market-correction scenario;
- all four directional macro Scores up 10 points.

Each result is a **model sensitivity**, not a causal estimate and not a promised forecast. Training samples are held identical so differences are attributable to the declared counterfactual state within the model.

## What Changes My Mind

Triggers are intentionally observable policy gates rather than prose predictions. Examples:

- at least one security passes the Alpha Buy Gate;
- v2.1 risk budget converges toward the v1 champion;
- Structural Break falls from `HIGH`;
- v2.1 falls to 60% or below;
- broad macro support deteriorates;
- Effective Data Confidence falls below 75.

These gates tell the user what to watch next without pretending to know when the event will occur.

## Private portfolio translation

The homepage reads the existing `elephant.portfolio.v1` browser `localStorage` state and translates the public operating zone into an amount-level message. No personal value is present in `data/decision_command.json` or any repository artifact.
