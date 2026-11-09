select
    contract_id,
    entity_id,
    cast(start_date as date)        as start_date,
    cast(metered_sites as integer)  as metered_sites
from {{ source('raw', 'deal_ledger_contracts') }}
