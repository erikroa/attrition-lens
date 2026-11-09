-- Entities Departed in Deal Ledger that Billing Core still bills.
-- End-date convention normalised: last_service_date = departure_date - 1 (Billing Core term end is inclusive).
-- Invoices are compared on the LOCAL reporting date.
with departed as (
    select e.entity_id, e.dl_tier, ev.brr_tier, e.departure_date,
           e.departure_date - 1 as last_service_date
    from {{ ref('stg_deal_ledger__entities') }} e
    left join {{ ref('int_attrition_events') }} ev on ev.entity_id = e.entity_id
    where e.status = 'Departed' and e.departure_date is not null
),

keys as (
    select entity_id, billing_key, link_path
    from {{ ref('int_id_crosswalk') }}
    where key_system = 'Billing Core'
),

plans as (
    select p.*, k.entity_id
    from {{ ref('stg_billing_core__plans') }} p
    join keys k on k.billing_key = p.billing_customer_id
),

active_after as (
    select pl.entity_id, pl.plan_id, pl.mrr_eur
    from plans pl
    join departed d using (entity_id)
    where pl.plan_status = 'active' or pl.term_end_date > d.last_service_date
),

invoices_after as (
    select i.*, k.entity_id
    from {{ ref('stg_billing_core__invoices') }} i
    join keys k on k.billing_key = i.billing_customer_id
    join departed d on d.entity_id = k.entity_id
    where i.issued_local_date >= d.departure_date
),

per_entity as (
    select
        d.*,
        (select count(*) from active_after a where a.entity_id = d.entity_id)                as active_plan_count,
        (select coalesce(sum(mrr_eur), 0) from active_after a where a.entity_id = d.entity_id) as active_plan_mrr_eur,
        (select count(*) from invoices_after i where i.entity_id = d.entity_id)              as post_departure_invoice_count,
        (select coalesce(sum(amount_eur), 0) from invoices_after i where i.entity_id = d.entity_id) as post_departure_invoice_eur,
        (select count(*) from invoices_after i
          where i.entity_id = d.entity_id and i.issued_utc_date >= d.departure_date)       as invoices_seen_by_utc_compare,
        (select coalesce(sum(p.mrr_eur), 0) from plans p
          where p.entity_id = d.entity_id
            and p.plan_id in (select plan_id from invoices_after i where i.entity_id = d.entity_id)) as invoiced_plan_mrr_eur,
        (select string_agg(distinct k.link_path, ',' order by k.link_path) from keys k where k.entity_id = d.entity_id) as link_path
    from departed d
)

select
    entity_id,
    dl_tier,
    brr_tier,
    departure_date,
    last_service_date,
    case when active_plan_count > 0 then 'active_plan' else 'post_departure_invoice' end as orphan_type,
    active_plan_count,
    post_departure_invoice_count,
    cast(post_departure_invoice_eur as decimal(18, 2))                                   as post_departure_invoice_eur,
    cast(case when active_plan_count > 0 then active_plan_mrr_eur
              else invoiced_plan_mrr_eur end as decimal(18, 2))                          as mrr_at_risk_eur,
    date_diff('day', departure_date, cast('{{ var("snapshot_date") }}' as date))         as days_since_departure,
    link_path,
    (active_plan_count > 0 or invoices_seen_by_utc_compare > 0)                          as caught_by_utc_compare
from per_entity
where active_plan_count > 0 or post_departure_invoice_count > 0
order by mrr_at_risk_eur desc, entity_id
