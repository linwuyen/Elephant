#!/usr/bin/env python3
"""Documented placeholder hook for future first-party benchmark models.

This module intentionally does not fabricate expected returns for broad-market,
global-equity, cash, or debt alternatives. Those become AVAILABLE only when
reliable inputs are configured or derived from verified portfolio state.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    print("Opportunity placeholders are fail-closed by design.")
