-- Status changes. Stored in UTC; the status clock uses the LOCAL reporting date.
select
    history_id,
    entity_id,
    cast(changed_at_utc as timestamptz)                                              as changed_at_utc,
    cast(timezone('{{ var("local_tz") }}', cast(changed_at_utc as timestamptz)) as date) as changed_local_date,
    nullif(trim(from_status), '')                                                    as from_status,
    to_status
from {{ source('raw', 'deal_ledger_status_history') }}
