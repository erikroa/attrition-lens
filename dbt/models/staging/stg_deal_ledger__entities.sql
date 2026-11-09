-- Deal Ledger entities. departure_date is EXCLUSIVE: the first day without service.
select
    entity_id,
    entity_name,
    hierarchy_level,
    nullif(trim(holding_entity_id), '')                         as holding_entity_id,
    coalesce(nullif(trim(holding_entity_id), ''), entity_id)    as group_id,
    tier                                                         as dl_tier,
    status,
    billing_channel,
    nullif(trim(billing_customer_ref), '')                       as billing_customer_ref,
    nullif(trim(partner_customer_ref), '')                       as partner_customer_ref,
    cast(nullif(departure_date, '') as date)                     as departure_date,
    nullif(trim(departure_reason), '')                           as departure_reason,
    nullif(trim(successor_entity_id), '')                        as successor_entity_id,
    cast(created_date as date)                                   as created_date
from {{ source('raw', 'deal_ledger_entities') }}
