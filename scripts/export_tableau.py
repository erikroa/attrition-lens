#!/usr/bin/env python3
"""Export every mart from the local DuckDB file to tableau/<mart>.csv (one CSV per mart)."""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "dbt" / "attrition_lens.duckdb"
OUT = ROOT / "tableau"
MARTS = [
    "mart_attrition_lens",
    "mart_variance_bridge",
    "mart_orphaned_billing",
    "mart_run_rate_resolution",
    "mart_source_parity_health",
]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB), read_only=True)
    for mart in MARTS:
        df = con.sql(f"select * from {mart}").df()
        path = OUT / f"{mart}.csv"
        df.to_csv(path, index=False, float_format="%.2f")
        print(f"{path.relative_to(ROOT)}: {len(df)} rows")


if __name__ == "__main__":
    main()
