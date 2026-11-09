select
    billing_customer_id,
    payer_name,
    cast(created_at_utc as timestamptz) as created_at_utc
from {{ source('raw', 'billing_core_customers') }}
