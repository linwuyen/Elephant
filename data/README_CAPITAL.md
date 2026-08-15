# Capital Allocation OS data

Generated outputs:
- `capital_allocation.json`
- `deep_research_queue.json`
- `opportunity_set.json`
- `calibration/index.json` and immutable timestamped snapshots

Config inputs:
- `portfolio_policy.json`
- `portfolio_state.json`
- `opportunity_inputs.json`
- `valuation_archetypes.json`

`portfolio_state.json` defaults to `UNCONFIGURED`; Elephant must not infer a user's holdings, debt or leverage from stale conversation context.
