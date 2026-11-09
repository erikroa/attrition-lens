-- Billing Core plans. term_end_date is INCLUSIVE: the last day of service. Cents -> EUR here.
select
    plan_id,
    billing_customer_id,
    plan_code,
    cast(metered_sites as integer)                              as metered_sites,
    cast(cast(price_per_site_cents as bigint) / 100 as decimal(18, 2)) as price_per_site_eur,
    cast(cast(mrr_cents as bigint) / 100 as decimal(18, 2))            as mrr_eur,
    plan_status,
    cast(term_start_date as date)                               as term_start_date,
    cast(term_end_date as date)                                 as term_end_date
from {{ source('raw', 'billing_core_plans') }}
