-- Partner Biller has no Deal Ledger ID. Cents -> EUR here.
select
    partner_customer_id,
    region,
    customer_name,
    cast(cast(monthly_fee_cents as bigint) / 100 as decimal(18, 2)) as monthly_fee_eur,
    status
from {{ source('raw', 'partner_biller_customers') }}
