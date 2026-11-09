-- Every Unit x Date x Segment source x tier x year -> attrition count + run-rate EUR.
--   status clock  : every flip to Departed counts (rebounds and entity transfers included)
--   contract clock: contracted departure dates, entity transfers excluded
with ev as (
    select * from {{ ref('int_attrition_events') }}
),

years as (
    select unnest({{ var('reporting_years') }}) as attrition_year
),

clocks as (
    select entity_id, holding_group_id, 'status clock' as date_basis, year(status_clock_date) as attrition_year,
           run_rate_eur, dl_tier, brr_tier, group_dl_tier, group_brr_tier
    from ev where status_clock_date is not null
    union all
    select entity_id, holding_group_id, 'contract clock', year(contract_clock_date),
           run_rate_eur, dl_tier, brr_tier, group_dl_tier, group_brr_tier
    from ev where contract_clock_date is not null and not entity_transfer_flag
),

group_size as (
    select holding_group_id, count(*) as n_entities from ev group by holding_group_id
),

group_any as (
    select holding_group_id, date_basis, attrition_year,
           any_value(group_dl_tier) as group_dl_tier, any_value(group_brr_tier) as group_brr_tier,
           sum(run_rate_eur) as run_rate_eur
    from clocks
    group by holding_group_id, date_basis, attrition_year
),

group_full as (
    select c.holding_group_id, c.date_basis, max(c.attrition_year) as attrition_year,
           any_value(c.group_dl_tier) as group_dl_tier, any_value(c.group_brr_tier) as group_brr_tier,
           sum(c.run_rate_eur) as run_rate_eur
    from clocks c
    join group_size s on s.holding_group_id = c.holding_group_id
    group by c.holding_group_id, c.date_basis, s.n_entities
    having count(*) = s.n_entities
),

counted as (
    select 'entity' as unit, date_basis, 'Deal Ledger tier' as segment_source, dl_tier as tier, attrition_year, run_rate_eur from clocks
    union all
    select 'entity', date_basis, 'BRR tier', brr_tier, attrition_year, run_rate_eur from clocks
    union all
    select 'group_any', date_basis, 'Deal Ledger tier', group_dl_tier, attrition_year, run_rate_eur from group_any
    union all
    select 'group_any', date_basis, 'BRR tier', group_brr_tier, attrition_year, run_rate_eur from group_any
    union all
    select 'group_full', date_basis, 'Deal Ledger tier', group_dl_tier, attrition_year, run_rate_eur from group_full
    union all
    select 'group_full', date_basis, 'BRR tier', group_brr_tier, attrition_year, run_rate_eur from group_full
),

agg as (
    select unit, date_basis, segment_source, tier, attrition_year,
           count(*) as attrition_count, sum(run_rate_eur) as run_rate_eur
    from counted
    group by all
),

spine as (
    select u.unit, d.date_basis, s.segment_source, t.tier, y.attrition_year
    from (values ('entity'), ('group_any'), ('group_full')) u(unit)
    cross join (values ('status clock'), ('contract clock')) d(date_basis)
    cross join (values ('Deal Ledger tier'), ('BRR tier')) s(segment_source)
    cross join (values ('Anchor'), ('Scale'), ('Standard'), ('Starter')) t(tier)
    cross join years y
)

select
    sp.unit || '|' || sp.date_basis || '|' || sp.segment_source || '|' || sp.tier || '|' || sp.attrition_year as lens_row_id,
    sp.unit,
    sp.date_basis,
    sp.segment_source,
    sp.tier,
    sp.attrition_year,
    coalesce(a.attrition_count, 0)                              as attrition_count,
    cast(coalesce(a.run_rate_eur, 0) as decimal(18, 2))         as run_rate_eur
from spine sp
left join agg a using (unit, date_basis, segment_source, tier, attrition_year)
order by sp.unit, sp.date_basis, sp.segment_source, sp.tier, sp.attrition_year
