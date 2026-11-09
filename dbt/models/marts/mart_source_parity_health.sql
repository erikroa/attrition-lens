-- Source parity checks, one row per subject per check. Tableau aggregates match rates from is_matched.
with entities as (
    select * from {{ ref('stg_deal_ledger__entities') }}
),
customers as (
    select * from entities where status <> 'Pipeline'
),
xw as (
    select * from {{ ref('int_id_crosswalk') }}
),
rr as (
    select * from {{ ref('int_run_rate_resolved') }}
),

billing_link as (
    select
        'billing_link' as check_name, 'Billing Core' as source_system, 'entity' as subject_type,
        c.entity_id as subject_id, c.entity_id,
        case when bool_or(x.link_path = 'crosswalk' and x.source_value_had_multiple) then 'crosswalk_semicolon'
             else any_value(x.link_path) end                         as outcome,
        cast(null as varchar)                                         as naive_outcome,
        bool_and(x.key_found_in_source)                               as is_matched,
        bool_or(x.source_value_had_multiple)                          as is_issue,
        string_agg(x.billing_key, ',' order by x.billing_key)          as detail
    from customers c
    join xw x on x.entity_id = c.entity_id
    where c.billing_channel in ('billing core', 'direct-checkout book')
    group by c.entity_id
),

brr_run_rate as (
    select 'brr_run_rate', 'BRR', 'entity', entity_id, entity_id,
           resolution_outcome,
           case when naive_run_rate_eur is null then 'blank' else 'found' end,
           resolved_key is not null,
           naive_run_rate_eur is null,
           coalesce(resolved_blank_reason, naive_blank_reason)
    from rr
),

partner_gap as (
    select 'partner_biller_gap', 'Partner Biller', 'partner_customer', p.partner_customer_id, e.entity_id,
           case when b.brr_key is null and be.brr_key is null then 'no_brr_rows' else 'has_brr_rows' end,
           cast(null as varchar),
           b.brr_key is not null or be.brr_key is not null,
           b.brr_key is null and be.brr_key is null,
           p.region
    from {{ ref('stg_partner_biller__customers') }} p
    left join entities e on e.partner_customer_ref = p.partner_customer_id
    left join {{ ref('stg_brr__run_rate') }} b on b.brr_key = 'kl_' || p.partner_customer_id
    left join {{ ref('stg_brr__run_rate') }} be on be.brr_key = 'kl_' || e.entity_id
),

tier_source as (
    select 'tier_source', 'BRR', 'entity', r.entity_id, r.entity_id,
           case when r.brr_tier = e.dl_tier then 'tier_match' else 'tier_mismatch' end,
           cast(null as varchar),
           true,
           r.brr_tier <> e.dl_tier,
           e.dl_tier || ' -> ' || r.brr_tier
    from rr r
    join entities e using (entity_id)
    where r.brr_tier is not null
),

end_date as (
    select 'end_date_convention', 'Billing Core', 'entity', e.entity_id, e.entity_id,
           case when bool_and(p.plan_status = 'cancelled' and p.term_end_date = e.departure_date - 1)
                then 'aligned_after_normalisation' else 'misaligned' end,
           case when max(p.term_end_date) = e.departure_date then 'match' else 'mismatch' end,
           bool_and(p.plan_status = 'cancelled' and p.term_end_date = e.departure_date - 1),
           not bool_and(p.plan_status = 'cancelled' and p.term_end_date = e.departure_date - 1),
           'departure ' || e.departure_date || ', last term end ' || max(p.term_end_date)
    from entities e
    join xw x on x.entity_id = e.entity_id and x.key_system = 'Billing Core'
    join {{ ref('stg_billing_core__plans') }} p on p.billing_customer_id = x.billing_key
    where e.departure_date is not null
    group by e.entity_id, e.departure_date
),

contacts as (
    select *,
           task_count + conversation_count as activity,
           count(*) over (partition by entity_id, email_normalised) as copies,
           first_value(contact_id) over (partition by entity_id, email_normalised
                                         order by task_count + conversation_count desc, contact_id) as keeper_id
    from {{ ref('stg_engagement_hub__contacts') }}
),

duplicate_contact as (
    select 'duplicate_contact', 'Engagement Hub', 'contact', contact_id, entity_id,
           case when contact_id = keeper_id then 'keep' else 'delete' end,
           cast(null as varchar),
           true,
           contact_id <> keeper_id,
           'keeper ' || keeper_id || ', activity ' || activity
    from contacts
    where copies > 1
),

engagement_link as (
    select 'engagement_link', 'Engagement Hub', 'entity', c.entity_id, c.entity_id,
           case when count(k.contact_id) > 0 then 'has_contacts' else 'no_contacts' end,
           cast(null as varchar),
           count(k.contact_id) > 0,
           count(k.contact_id) = 0,
           cast(count(k.contact_id) as varchar) || ' contacts'
    from customers c
    left join {{ ref('stg_engagement_hub__contacts') }} k on k.entity_id = c.entity_id
    group by c.entity_id
),

clock_boundary as (
    select 'clock_boundary', 'Billing Core', 'invoice', i.invoice_id, x.entity_id,
           'clock_boundary_miss',
           'missed_by_utc_compare',
           true,
           true,
           'issued ' || strftime(i.issued_at_utc at time zone 'UTC', '%Y-%m-%d %H:%M') || ' UTC, local date '
               || i.issued_local_date || ', departure ' || e.departure_date
    from {{ ref('stg_billing_core__invoices') }} i
    join xw x on x.billing_key = i.billing_customer_id and x.key_system = 'Billing Core'
    join entities e on e.entity_id = x.entity_id
    where e.departure_date is not null
      and i.issued_utc_date < e.departure_date
      and i.issued_local_date >= e.departure_date
)

select check_name || '|' || subject_id as parity_row_id, *
from (
    select * from billing_link
    union all select * from brr_run_rate
    union all select * from partner_gap
    union all select * from tier_source
    union all select * from end_date
    union all select * from duplicate_contact
    union all select * from engagement_link
    union all select * from clock_boundary
)
order by check_name, subject_id
