-- Every moving group must carry exactly one reason code from the fixed list.
select *
from {{ ref('mart_variance_bridge') }}
where row_type in ('removal', 'addition', 'amount_only')
  and (reason_code is null or group_id is null)
