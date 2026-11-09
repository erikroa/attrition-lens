-- BRR reporting layer. Keys are 'kl_' + a source ID (Deal Ledger ID or Billing Core customer ID).
select
    brr_key,
    substr(brr_key, 4)                                  as source_id,
    reporting_tier                                      as brr_tier,
    cast(booked_run_rate_eur as decimal(18, 2))         as booked_run_rate_eur,
    as_of_month
from {{ source('raw', 'brr_run_rate') }}
