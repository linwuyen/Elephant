# Consultant research integration

Elephant consumes `linwuyen/Consultant_System` as an upstream research-ingestion service.

## Boundary

- Elephant official economic data and deterministic scores remain authoritative for numeric facts and scoring.
- Consultant_System supplies external strategy/research context from McKinsey, BCG, Deloitte and PwC.
- Consultant research **must not** directly change Cycle Score, Growth Persistence, Domestic Demand or Financial Conditions.
- Research may later be used to explain, challenge or contextualize a deterministic Elephant signal, with provenance preserved.

## Data flow

```text
McKinsey / BCG / Deloitte / PwC
        ↓
Consultant_System crawler
        ↓
reports.json / reports.csv / consultant.db
        ↓
Elephant sync_consultant_research.py
        ↓
data/consultant/*
        ↓
Elephant Research tab + SQLite SQL console
```

## Update cadence

- Consultant_System refreshes its research database independently.
- Elephant synchronizes the published artifacts daily at 10:17 Asia/Taipei and can be run manually.
- The sync validates JSON shape, minimum row count, SQLite magic header, SQLite integrity and table contract before publishing.
- A failed sync leaves the last-good Elephant snapshot untouched.

## Published Elephant artifacts

- `data/consultant/reports.json`
- `data/consultant/reports.csv`
- `data/consultant/consultant.db`
- `data/consultant/status.json`

`status.json` explicitly records `score_influence: false`.
