#!/usr/bin/env python3
"""Print the headline variance bridge as compact equation lines, one block per reporting year.

Exits non-zero if any year does not tie out (count or EUR).
"""
import sys
from decimal import Decimal
from pathlib import Path

import duckdb

DB = Path(__file__).resolve().parent.parent / "dbt" / "attrition_lens.duckdb"
LABEL = {
    "rebound": "rebounds", "entity_transfer": "entity transfers", "status_lag": "status lag",
    "member_only_departure": "member-only departures", "tier_source_mismatch": "tier source mismatch",
    "clock_year_shift": "clock-year shift",
}
SIDE = {"removal": "out", "addition": "in"}


def eur(x: Decimal) -> str:
    return f"EUR {x:,.2f}"


def main() -> int:
    con = duckdb.connect(str(DB), read_only=True)
    rows = con.sql("""
        select attrition_year, row_type, reason_code, min(step_order) as step_order,
               sum(count_delta) as n, sum(run_rate_eur_delta) as eur
        from mart_variance_bridge
        group by all
        order by attrition_year, step_order, row_type desc
    """).fetchall()
    ok = True
    for year in sorted({r[0] for r in rows}):
        yr = [r for r in rows if r[0] == year]
        a = next(r for r in yr if r[1] == "basis_a")
        b = next(r for r in yr if r[1] == "basis_b")
        moves = [r for r in yr if r[1] in ("removal", "addition")]
        run_only = sum((r[5] for r in yr if r[1] == "amount_only"), Decimal(0))
        terms = " ".join(f"{'+' if r[4] > 0 else '-'} {abs(r[4])} {LABEL[r[2]]} ({SIDE[r[1]]})" for r in moves)
        count_ok = a[4] + sum(r[4] for r in moves) == b[4]
        eur_ok = a[5] + sum(r[5] for r in yr if r[1] in ("removal", "addition", "amount_only")) == b[5]
        ok &= count_ok and eur_ok
        print(f"A = {a[4]} groups ({eur(a[5])}), counted by entity status flipped to Departed in {year}, "
              f"Deal Ledger tier, member entities excluded")
        print(f"B = {b[4]} = {a[4]} {terms}, counted by contract clock in {year}, group_any, BRR tier, "
              f"entity transfers excluded")
        print(f"    run-rate: {eur(b[5])} = {eur(a[5])} + {eur(sum(r[5] for r in moves))} group moves "
              f"+ {eur(run_only)} member run-rate that Basis A excludes"
              f"   [ties out: count {'yes' if count_ok else 'NO'}, EUR {'yes' if eur_ok else 'NO'}]")
        print()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
