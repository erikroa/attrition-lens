-- Invoices. Both the UTC date and the local reporting date are kept so the two can be compared.
select
    invoice_id,
    billing_customer_id,
    plan_id,
    cast(issued_at_utc as timestamptz)                                                    as issued_at_utc,
    cast(timezone('UTC', cast(issued_at_utc as timestamptz)) as date)                     as issued_utc_date,
    cast(timezone('{{ var("local_tz") }}', cast(issued_at_utc as timestamptz)) as date)   as issued_local_date,
    cast(cast(amount_cents as bigint) / 100 as decimal(18, 2))                            as amount_eur
from {{ source('raw', 'billing_core_invoices') }}
