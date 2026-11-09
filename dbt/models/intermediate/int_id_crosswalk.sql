-- Resolves every Deal Ledger entity to its billing keys through every link path.
-- Grain: one row per entity x billing key (one row with a null key for unlinked entities).
with entities as (
    select * from {{ ref('stg_deal_ledger__entities') }}
),

direct_ref as (
    select entity_id, billing_customer_ref as billing_key, 'direct_ref' as link_path,
           false as source_value_had_multiple
    from entities
    where billing_customer_ref is not null and billing_customer_ref not like '%,%'
),

comma_list as (
    select entity_id, trim(unnest(string_split(billing_customer_ref, ','))) as billing_key,
           'comma_list' as link_path, true as source_value_had_multiple
    from entities
    where billing_customer_ref like '%,%'
),

crosswalk as (
    select entity_id, trim(unnest(string_split(billing_customer_ids, ';'))) as billing_key,
           'crosswalk' as link_path, billing_customer_ids like '%;%' as source_value_had_multiple
    from {{ ref('stg_billing_core__crosswalk') }}
),

billing_core_links as (
    select l.*, 'Billing Core' as key_system,
           c.billing_customer_id is not null as key_found_in_source
    from (select * from direct_ref union all select * from comma_list union all select * from crosswalk) l
    left join {{ ref('stg_billing_core__customers') }} c on c.billing_customer_id = l.billing_key
),

partner_links as (
    select e.entity_id, e.partner_customer_ref as billing_key, 'partner_biller' as link_path,
           false as source_value_had_multiple, 'Partner Biller' as key_system,
           p.partner_customer_id is not null as key_found_in_source
    from entities e
    left join {{ ref('stg_partner_biller__customers') }} p on p.partner_customer_id = e.partner_customer_ref
    where e.partner_customer_ref is not null
),

linked as (
    select * from billing_core_links
    union all
    select * from partner_links
),

unlinked as (
    select e.entity_id, cast(null as varchar) as billing_key, 'unlinked' as link_path,
           false as source_value_had_multiple, cast(null as varchar) as key_system,
           false as key_found_in_source
    from entities e
    where e.entity_id not in (select entity_id from linked)
)

select
    entity_id || '|' || coalesce(billing_key, '-') as crosswalk_row_id,
    *
from (select * from linked union all select * from unlinked)
