-- One row per entity; billing_customer_ids may hold two IDs joined by "; ".
select
    crosswalk_id,
    entity_id,
    billing_customer_ids
from {{ source('raw', 'billing_core_crosswalk') }}
