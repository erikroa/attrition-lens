-- Naive run-rate lookup (Deal Ledger ID only) vs resolved lookup (via int_id_crosswalk), per customer entity.
select
    r.entity_id,
    r.hierarchy_level,
    r.billing_channel,
    e.dl_tier,
    r.brr_tier,
    r.naive_key,
    r.naive_run_rate_eur,
    r.resolved_key,
    r.resolved_via,
    r.resolved_run_rate_eur,
    r.resolution_outcome,
    r.naive_blank_reason,
    r.resolved_blank_reason
from {{ ref('int_run_rate_resolved') }} r
join {{ ref('stg_deal_ledger__entities') }} e using (entity_id)
order by r.entity_id
