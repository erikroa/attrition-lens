-- Entity grain. Both clocks side by side, plus the flags that explain why they disagree.
--   contract clock = Deal Ledger departure_date (exclusive, first day without service)
--   status clock   = local date of the latest flip to Departed in status history
with entities as (
    select * from {{ ref('stg_deal_ledger__entities') }} where status <> 'Pipeline'
),

flips as (
    select
        entity_id,
        max(changed_local_date) filter (where to_status = 'Departed')                       as status_clock_date,
        max(changed_at_utc)     filter (where to_status = 'Departed')                       as last_departed_at,
        max(changed_at_utc)     filter (where from_status = 'Departed' and to_status = 'Active') as last_back_to_active_at
    from {{ ref('stg_deal_ledger__status_history') }}
    group by entity_id
),

run_rate as (
    select * from {{ ref('int_run_rate_resolved') }}
),

base as (
    select
        e.entity_id,
        e.group_id                                                   as holding_group_id,
        e.hierarchy_level,
        e.status                                                     as current_status,
        e.dl_tier,
        rr.brr_tier,
        e.departure_date                                             as contract_clock_date,
        f.status_clock_date,
        e.departure_reason,
        coalesce(e.departure_reason = 'entity transfer', false)      as entity_transfer_flag,
        coalesce(f.last_back_to_active_at > f.last_departed_at, false) as rebound_flag,
        coalesce(rr.resolved_run_rate_eur, 0)                        as run_rate_eur,
        rr.resolution_outcome
    from entities e
    left join flips f on f.entity_id = e.entity_id
    left join run_rate rr on rr.entity_id = e.entity_id
)

select
    b.*,
    h.dl_tier                                                       as group_dl_tier,
    h.brr_tier                                                      as group_brr_tier,
    date_diff('day', b.contract_clock_date, b.status_clock_date)    as clock_gap_days,
    case
        when b.contract_clock_date is null and b.status_clock_date is null then 'no_departure'
        when b.contract_clock_date is null and b.rebound_flag              then 'rebound_no_contract_departure'
        when b.contract_clock_date is null                                 then 'status_only'
        when b.status_clock_date is null                                   then 'status_lag_missing_flip'
        when date_diff('day', b.contract_clock_date, b.status_clock_date) > {{ var('clock_tolerance_days') }}
                                                                           then 'status_lag_late_flip'
        when date_diff('day', b.contract_clock_date, b.status_clock_date) < -{{ var('clock_tolerance_days') }}
                                                                           then 'status_lag_early_flip'
        when year(b.contract_clock_date) <> year(b.status_clock_date)      then 'clock_year_shift'
        else 'aligned'
    end                                                             as clock_alignment
from base b
left join base h on h.entity_id = b.holding_group_id
