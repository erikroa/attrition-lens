-- Fails (returns rows) if Basis A + movements != Basis B, by count or by the cent, per year x tier and per year.
with b as (
    select * from {{ ref('mart_variance_bridge') }}
),
by_tier as (
    select
        attrition_year, tier,
        sum(case when row_type = 'basis_a' then count_delta else 0 end)                      as a_count,
        sum(case when row_type in ('removal', 'addition', 'amount_only') then count_delta else 0 end) as move_count,
        sum(case when row_type = 'basis_b' then count_delta else 0 end)                      as b_count,
        sum(case when row_type = 'basis_a' then run_rate_eur_delta else 0 end)               as a_eur,
        sum(case when row_type in ('removal', 'addition', 'amount_only') then run_rate_eur_delta else 0 end) as move_eur,
        sum(case when row_type = 'basis_b' then run_rate_eur_delta else 0 end)               as b_eur
    from b
    group by attrition_year, tier
),
by_year as (
    select attrition_year, 'ALL' as tier, sum(a_count) a_count, sum(move_count) move_count, sum(b_count) b_count,
           sum(a_eur) a_eur, sum(move_eur) move_eur, sum(b_eur) b_eur
    from by_tier group by attrition_year
)
select * from (select * from by_tier union all select * from by_year)
where a_count + move_count <> b_count
   or a_eur + move_eur <> b_eur
