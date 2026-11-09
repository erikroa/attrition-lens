-- Run-rate lookup per customer entity: naive (Deal Ledger ID only) vs resolved (any linked key).
with entities as (
    select * from {{ ref('stg_deal_ledger__entities') }} where status <> 'Pipeline'
),

brr as (
    select * from {{ ref('stg_brr__run_rate') }}
),

candidates as (
    select entity_id, 'kl_' || entity_id as brr_key, 'deal_ledger_id' as resolved_via, 1 as preference
    from entities
    union all
    select entity_id, 'kl_' || billing_key, 'billing_key', 2
    from {{ ref('int_id_crosswalk') }}
    where key_system = 'Billing Core'
),

resolved as (
    select c.entity_id, c.brr_key, c.resolved_via, b.booked_run_rate_eur, b.brr_tier
    from candidates c
    join brr b on b.brr_key = c.brr_key
    qualify row_number() over (partition by c.entity_id order by c.preference, c.brr_key) = 1
)

select
    e.entity_id,
    e.hierarchy_level,
    e.billing_channel,
    'kl_' || e.entity_id                     as naive_key,
    n.booked_run_rate_eur                    as naive_run_rate_eur,
    r.brr_key                                as resolved_key,
    r.resolved_via,
    r.booked_run_rate_eur                    as resolved_run_rate_eur,
    r.brr_tier,
    case
        when n.brr_key is not null then 'naive_match'
        when r.brr_key is not null then 'resolved_via_billing_key'
        when e.billing_channel = 'partner biller' then 'partner_biller_no_brr'
        else 'unresolved'
    end                                       as resolution_outcome,
    case
        when n.brr_key is not null then null
        when r.brr_key is not null then 'brr_keyed_on_billing_customer_id'
        when e.billing_channel = 'partner biller' then 'partner_biller_has_no_brr_rows'
        else 'no_brr_row_on_any_key'
    end                                       as naive_blank_reason,
    case
        when r.brr_key is not null then null
        when e.billing_channel = 'partner biller' then 'partner_biller_has_no_brr_rows'
        else 'no_brr_row_on_any_key'
    end                                       as resolved_blank_reason
from entities e
left join brr n on n.brr_key = 'kl_' || e.entity_id
left join resolved r on r.entity_id = e.entity_id
