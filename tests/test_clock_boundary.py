"""A UTC date compare misses the clock-boundary invoices; a local (Europe/Amsterdam) date compare catches them."""
import pandas as pd

from conftest import RAW


def boundary_frame(truth):
    inv = pd.read_csv(RAW / "billing_core_invoices.csv", dtype=str)
    ent = pd.read_csv(RAW / "deal_ledger_entities.csv", dtype=str)
    t = truth[truth.defect_id == "8"][["subject_id", "detail"]]
    df = t.merge(inv, left_on="subject_id", right_on="invoice_id").merge(ent, left_on="detail", right_on="entity_id")
    ts = pd.to_datetime(df.issued_at_utc, utc=True)
    df["utc_date"] = ts.dt.date
    df["local_date"] = ts.dt.tz_convert("Europe/Amsterdam").dt.date
    df["departure"] = pd.to_datetime(df.departure_date).dt.date
    return df


def test_utc_compare_misses_boundary_invoices(truth):
    df = boundary_frame(truth)
    assert len(df) == len(truth[truth.defect_id == "8"]) > 0
    assert (df.utc_date < df.departure).all(), "a UTC compare would have flagged some boundary invoices"


def test_local_compare_catches_boundary_invoices(truth):
    df = boundary_frame(truth)
    assert (df.local_date >= df.departure).all()
    assert (df.local_date == df.departure).all()


def test_marts_use_local_dates(truth, q):
    ents = set(truth[truth.defect_id == "8"].detail)
    o = q("select entity_id, caught_by_utc_compare from mart_orphaned_billing")
    hit = o[o.entity_id.isin(ents)]
    assert set(hit.entity_id) == ents, "orphaned billing missed a clock-boundary case"
    assert not hit.caught_by_utc_compare.any(), "these cases should be invisible to a UTC compare"
    others = o[~o.entity_id.isin(ents)]
    assert others.caught_by_utc_compare.all()
