"""Every mart's detections must equal the planted truth manifest: same IDs, same labels, no extras, no misses."""
from conftest import assert_same


def T(truth, defect_id, cols=("subject_id", "expected_label"), **filters):
    df = truth[truth.defect_id == str(defect_id)]
    for k, v in filters.items():
        df = df[df[k] == v]
    return df[list(cols)]


def parity(q, check):
    return q(f"select * from mart_source_parity_health where check_name = '{check}'")


def test_1_end_date_convention(truth, q):
    p = parity(q, "end_date_convention")
    aligned = p[p.outcome == "aligned_after_normalisation"]
    assert_same(T(truth, 1), aligned[["subject_id", "outcome"]], "end-date convention")
    # the naive equality test (term end == departure date) is off by one day for every one of them
    assert (aligned.naive_outcome == "mismatch").all()


def test_2_rebounds(truth, q):
    ev = q("select entity_id, 'rebound' as l, year(status_clock_date) as y from int_attrition_events where rebound_flag")
    assert_same(T(truth, 2, ("subject_id", "expected_label", "year")), ev, "rebounds")


def test_3_entity_transfers(truth, q):
    ev = q("""select entity_id, 'entity_transfer' as l, year(contract_clock_date) as y
              from int_attrition_events where entity_transfer_flag""")
    assert_same(T(truth, 3, ("subject_id", "expected_label", "year")), ev, "entity transfers")


def test_4_partial_group_loss(truth, q):
    b = q("""select group_id,
                    case when detail = 'cross_tier' then 'partial_group_loss_cross_tier' else 'partial_group_loss' end,
                    attrition_year
             from mart_variance_bridge
             where row_type = 'addition' and reason_code = 'member_only_departure'""")
    assert_same(T(truth, 4, ("subject_id", "expected_label", "year")), b, "partial group loss")


def test_5_tier_mismatch(truth, q):
    p = parity(q, "tier_source")
    p = p[p.outcome == "tier_mismatch"].copy()
    p["dl"] = p.detail.str.split(" -> ").str[0]
    p["brr"] = p.detail.str.split(" -> ").str[1]
    assert_same(T(truth, 5, ("subject_id", "expected_label", "tier", "detail")),
                p[["subject_id", "outcome", "dl", "brr"]], "tier mismatch")


def test_6_status_lag_and_clock_year_shift(truth, q):
    ev = q("""select entity_id, clock_alignment, year(contract_clock_date)
              from int_attrition_events
              where clock_alignment in ('status_lag_missing_flip', 'status_lag_late_flip', 'clock_year_shift')""")
    assert_same(T(truth, 6, ("subject_id", "expected_label", "year")), ev, "status lag")


def test_7_orphaned_billing(truth, q):
    o = q("select entity_id, orphan_type, year(departure_date) from mart_orphaned_billing")
    assert_same(T(truth, 7, ("subject_id", "expected_label", "year")), o, "orphaned billing")


def test_8_clock_boundary(truth, q):
    p = parity(q, "clock_boundary")
    assert_same(T(truth, 8, ("subject_id", "expected_label", "detail")),
                p[["subject_id", "outcome", "entity_id"]], "clock-boundary invoices")


def test_9_messy_id_links(truth, q):
    p = parity(q, "billing_link")
    p = p[p.outcome.isin(["comma_list", "crosswalk_semicolon"])]
    assert_same(T(truth, 9), p[["subject_id", "outcome"]], "messy ID links")


def test_10_run_rate_blanks(truth, q):
    r = q("select entity_id, resolution_outcome from mart_run_rate_resolution where naive_run_rate_eur is null")
    assert_same(T(truth, 10, subject_type="entity"), r, "naive run-rate blanks")
    still_blank = q("select entity_id from mart_run_rate_resolution where resolved_run_rate_eur is null")
    assert set(still_blank.entity_id) == set(T(truth, 10, ("subject_id",), expected_label="partner_biller_no_brr").subject_id)


def test_10_partner_biller_gaps(truth, q):
    p = parity(q, "partner_biller_gap")
    assert_same(T(truth, 10, subject_type="partner_customer"), p[["subject_id", "outcome"]], "Partner Biller gaps")


def test_11_duplicate_contacts(truth, q):
    p = parity(q, "duplicate_contact")
    t = T(truth, 11, ("subject_id", "expected_label", "detail"))
    assert_same(t[t.expected_label != "keep_distinct_email"], p[["subject_id", "outcome", "entity_id"]],
                "duplicate contacts")
    distinct = set(t[t.expected_label == "keep_distinct_email"].subject_id)
    assert distinct and not distinct & set(p.subject_id), "a different-email contact was treated as a duplicate"


def test_0_variance_bridge_rows(truth, q):
    b = q("""select group_id, reason_code, attrition_year, tier, row_type
             from mart_variance_bridge where row_type in ('removal', 'addition', 'amount_only')""")
    assert_same(T(truth, 0, ("subject_id", "expected_label", "year", "tier", "detail")), b, "variance bridge")
