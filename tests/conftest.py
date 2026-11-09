from pathlib import Path

import duckdb
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "dbt" / "attrition_lens.duckdb"
RAW = ROOT / "data" / "raw"
TRUTH = ROOT / "data" / "truth" / "planted_defects.csv"


@pytest.fixture(scope="session")
def con():
    assert DB.exists(), "run `make generate dbt` first"
    c = duckdb.connect(str(DB), read_only=True)
    yield c
    c.close()


@pytest.fixture(scope="session")
def q(con):
    """Run SQL against the built marts and return a DataFrame."""
    return lambda sql: con.sql(sql).df()


@pytest.fixture(scope="session")
def truth():
    df = pd.read_csv(TRUTH, dtype=str).fillna("")
    return df


def as_set(df: pd.DataFrame) -> set:
    """Rows as a set of string tuples, with NaN/None as '' and years without '.0'."""
    out = df.copy()
    for col in out.columns:
        out[col] = out[col].map(lambda v: "" if pd.isna(v) else str(int(v)) if isinstance(v, float) else str(v))
    return set(map(tuple, out.values))


def assert_same(truth_rows: pd.DataFrame, detected: pd.DataFrame, what: str):
    t, d = as_set(truth_rows), as_set(detected)
    missing, extra = sorted(t - d), sorted(d - t)
    assert not missing and not extra, (
        f"{what}: {len(missing)} missing, {len(extra)} extra\n"
        f"  missing (first 5): {missing[:5]}\n  extra (first 5): {extra[:5]}"
    )
    assert len(t) > 0, f"{what}: truth manifest has no rows"
