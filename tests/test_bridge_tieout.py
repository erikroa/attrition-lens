"""The variance bridge ties out exactly: A + additions - removals (+ run-rate only) = B, to the cent."""
import subprocess
import sys
from decimal import Decimal

from conftest import ROOT

MOVES = ("removal", "addition", "amount_only")


def totals(con, by):
    return con.sql(f"""
        select {by},
               sum(count_delta)       filter (where row_type = 'basis_a') as a_n,
               sum(count_delta)       filter (where row_type in {MOVES}) as m_n,
               sum(count_delta)       filter (where row_type = 'basis_b') as b_n,
               sum(run_rate_eur_delta) filter (where row_type = 'basis_a') as a_eur,
               sum(run_rate_eur_delta) filter (where row_type in {MOVES}) as m_eur,
               sum(run_rate_eur_delta) filter (where row_type = 'basis_b') as b_eur
        from mart_variance_bridge group by {by} order by {by}
    """).fetchall()


def test_ties_out_every_year_to_the_cent(con):
    rows = totals(con, "attrition_year")
    assert [r[0] for r in rows] == [2023, 2024, 2025]
    for year, a_n, m_n, b_n, a_eur, m_eur, b_eur in rows:
        assert isinstance(a_eur, Decimal), "EUR must be exact decimals, not floats"
        assert a_n + m_n == b_n, f"{year}: count {a_n} + {m_n} != {b_n}"
        assert a_eur + m_eur == b_eur, f"{year}: EUR {a_eur} + {m_eur} != {b_eur}"


def test_ties_out_every_year_and_tier(con):
    for key, a_n, m_n, b_n, a_eur, m_eur, b_eur in totals(con, "attrition_year || ' ' || tier"):
        assert (a_n or 0) + (m_n or 0) == (b_n or 0), key
        assert (a_eur or 0) + (m_eur or 0) == (b_eur or 0), key


def test_one_reason_code_per_moving_group(con):
    n = con.sql(f"""
        select count(*) from mart_variance_bridge
        where row_type in {MOVES} and reason_code not in
          ('rebound','entity_transfer','status_lag','member_only_departure','tier_source_mismatch','clock_year_shift')
    """).fetchall()[0][0]
    assert n == 0


def test_basis_b_equals_lens_cell(con):
    """Basis B is exactly the lens cell group_any / contract clock / BRR tier."""
    diff = con.sql("""
        with b as (select attrition_year, tier, count_delta n, run_rate_eur_delta eur
                   from mart_variance_bridge where row_type = 'basis_b'),
             l as (select attrition_year, tier, attrition_count n, run_rate_eur eur from mart_attrition_lens
                   where unit = 'group_any' and date_basis = 'contract clock' and segment_source = 'BRR tier')
        select * from b full outer join l using (attrition_year, tier)
        where b.n is distinct from l.n or b.eur is distinct from l.eur
    """).fetchall()
    assert diff == []


def test_headline_script_ties_out():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "print_headline.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.count("[ties out: count yes, EUR yes]") == 3
