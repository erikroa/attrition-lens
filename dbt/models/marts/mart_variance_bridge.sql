-- Variance bridge from Basis A to Basis B, at year x tier x group grain.
--   Basis A: entity unit, status clock, Deal Ledger tier, member entities excluded
--   Basis B: group_any unit, contract clock, BRR tier, entity transfers excluded
-- Tie-out: basis_a + removals + additions + amount_only = basis_b (count and EUR, signed deltas).
with ev as (
    select * from {{ ref('int_attrition_events') }}
),

years as (
    select unnest({{ var('reporting_years') }}) as attrition_year
),

tiers as (
    select * from (values ('Anchor'), ('Scale'), ('Standard'), ('Starter')) t(tier)
),

basis_a as (
    select holding_group_id as group_id, year(status_clock_date) as attrition_year,
           dl_tier as tier, run_rate_eur as eur
    from ev
    where hierarchy_level <> 'member entity'
      and status_clock_date is not null
      and year(status_clock_date) in (select attrition_year from years)
),

basis_b as (
    select holding_group_id as group_id, year(contract_clock_date) as attrition_year,
           any_value(group_brr_tier) as tier, sum(run_rate_eur) as eur
    from ev
    where contract_clock_date is not null
      and not entity_transfer_flag
      and year(contract_clock_date) in (select attrition_year from years)
    group by holding_group_id, year(contract_clock_date)
),

matched as (
    select
        coalesce(a.group_id, b.group_id)              as group_id,
        coalesce(a.attrition_year, b.attrition_year)  as attrition_year,
        coalesce(a.tier, b.tier)                      as tier,
        a.eur                                         as a_eur,
        b.eur                                         as b_eur,
        case
            when a.group_id is not null and b.group_id is null then 'removal'
            when a.group_id is null and b.group_id is not null then 'addition'
            else 'amount_only'
        end                                           as row_type
    from basis_a a
    full outer join basis_b b
      on a.group_id = b.group_id and a.attrition_year = b.attrition_year and a.tier = b.tier
),

member_run_rate as (
    select holding_group_id as group_id, year(contract_clock_date) as attrition_year,
           sum(run_rate_eur) as eur,
           bool_or(dl_tier <> group_dl_tier) as cross_tier
    from ev
    where hierarchy_level = 'member entity' and contract_clock_date is not null and not entity_transfer_flag
    group by holding_group_id, year(contract_clock_date)
),

holding as (
    select * from ev where entity_id = holding_group_id
),

movements as (
    select
        m.*,
        case
            when m.row_type = 'removal' and h.rebound_flag then 'rebound'
            when m.row_type = 'removal' and h.entity_transfer_flag then 'entity_transfer'
            when m.row_type = 'removal'
                 and (h.clock_alignment like 'status_lag%' or h.clock_alignment = 'status_only') then 'status_lag'
            when m.row_type = 'addition' and year(h.contract_clock_date) = m.attrition_year
                 and h.clock_alignment like 'status_lag%' then 'status_lag'
            when m.row_type = 'addition'
                 and (h.contract_clock_date is null or year(h.contract_clock_date) <> m.attrition_year)
                 then 'member_only_departure'
            when m.row_type = 'amount_only' and m.b_eur - m.a_eur = coalesce(mr.eur, 0)
                 then 'member_only_departure'
            when m.row_type = 'removal' and exists (
                     select 1 from basis_b x where x.group_id = m.group_id and x.attrition_year = m.attrition_year)
                 then 'tier_source_mismatch'
            when m.row_type = 'addition' and exists (
                     select 1 from basis_a x where x.group_id = m.group_id and x.attrition_year = m.attrition_year)
                 then 'tier_source_mismatch'
            when m.row_type in ('removal', 'addition') and h.clock_alignment = 'clock_year_shift'
                 then 'clock_year_shift'
            else 'unexplained'
        end                                                       as reason_code,
        case when m.row_type = 'addition' and mr.cross_tier then 'cross_tier' end as detail
    from matched m
    left join holding h on h.entity_id = m.group_id
    left join member_run_rate mr on mr.group_id = m.group_id and mr.attrition_year = m.attrition_year
    where not (m.row_type = 'amount_only' and m.a_eur = m.b_eur)
),

totals as (
    select y.attrition_year, t.tier, 'basis_a' as row_type,
           (select count(*) from basis_a a where a.attrition_year = y.attrition_year and a.tier = t.tier) as count_delta,
           (select coalesce(sum(eur), 0) from basis_a a where a.attrition_year = y.attrition_year and a.tier = t.tier) as eur_delta
    from years y cross join tiers t
    union all
    select y.attrition_year, t.tier, 'basis_b',
           (select count(*) from basis_b b where b.attrition_year = y.attrition_year and b.tier = t.tier),
           (select coalesce(sum(eur), 0) from basis_b b where b.attrition_year = y.attrition_year and b.tier = t.tier)
    from years y cross join tiers t
),

unioned as (
    select attrition_year, tier, row_type, cast(null as varchar) as reason_code, cast(null as varchar) as group_id,
           count_delta, eur_delta, cast(null as varchar) as detail
    from totals
    union all
    select attrition_year, tier, row_type, reason_code, group_id,
           case row_type when 'removal' then -1 when 'addition' then 1 else 0 end,
           case row_type when 'removal' then -a_eur when 'addition' then b_eur else b_eur - a_eur end,
           detail
    from movements
),

ordered as (
    select
        *,
        case row_type when 'basis_a' then 0 when 'basis_b' then 9 else
            case reason_code
                when 'rebound' then 1 when 'entity_transfer' then 2 when 'status_lag' then 3
                when 'member_only_departure' then 4 when 'tier_source_mismatch' then 5
                when 'clock_year_shift' then 6 else 8 end
        end as step_order
    from unioned
)

select
    attrition_year || '|' || tier || '|' || row_type || '|' || coalesce(group_id, '-') as bridge_row_id,
    attrition_year,
    tier,
    row_type,
    step_order,
    -- sortable waterfall label, e.g. "3 status lag (in)"
    case row_type
        when 'basis_a' then '0 Basis A'
        when 'basis_b' then '9 Basis B'
        else step_order || ' ' || replace(reason_code, '_', ' ')
             || case row_type when 'removal' then ' (out)' when 'addition' then ' (in)' else ' (run-rate)' end
    end                                                  as step_label,
    reason_code,
    group_id,
    count_delta,
    cast(eur_delta as decimal(18, 2))                    as run_rate_eur_delta,
    detail
from ordered
order by attrition_year, tier, step_order, group_id
