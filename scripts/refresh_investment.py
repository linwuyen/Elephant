#!/usr/bin/env python3
import json

import build_investment
import source_alpha


def main():
    source = source_alpha.update()
    investment = build_investment.generate()
    print(json.dumps({"alpha_source": source, "investment_status": investment.get("status")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
