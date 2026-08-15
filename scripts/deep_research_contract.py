#!/usr/bin/env python3
"""Deep Research deterministic contract.

Actual evidence collection may be performed by scheduled research automation,
but every candidate must satisfy this schema before it can be handed to the
upstream Alpha Buy Gate. The queue itself has no promotion authority.
"""

REQUIRED_EVIDENCE = [
    "reference_price",
    "earnings_basis",
    "revenue_trend",
    "balance_sheet_cash_flow",
    "material_events",
    "valuation_basis",
]

PROMOTION_AUTHORITY = "NONE"
