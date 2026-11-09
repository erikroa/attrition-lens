# Methodology

How `attrition-lens` counts gross revenue attrition, why the counts differ, and how every difference is explained. All data is synthetic. The company, its systems and its customers are fictional.

## 1. The fictional setup

Kestrel Grid sells energy monitoring for commercial buildings, priced per metered site, in EUR. The local reporting timezone is Europe/Amsterdam. Snapshot (extract) date: 2026-03-31. Reporting years: 2023, 2024 and 2025.

| System | Role | Quirks that matter |
|---|---|---|
| Deal Ledger | Commercial contracts | Holds hierarchy, tier, status, status history and departure date. **The departure date is exclusive**: it is the first day without service. |
| Billing Core | Subscription billing | One payer, many plans. Amounts are integer cents. Timestamps are UTC. **Term end is inclusive**: it is the last day of service. |
| Partner Biller | Regional reseller billing | No Deal Ledger ID and no BRR rows. |
| Engagement Hub | CS platform | Contacts with task and conversation counts; contains duplicates. |
| BRR | Booked Run-Rate reporting layer | Keys are `kl_` + source ID. Carries its own reporting tier. |

## 2. The three counting choices

| Choice | Options | Definition |
|---|---|---|
| **Unit** | `entity` | Each legal entity counts once in the year its clock date falls. |
| | `group_any` | A holding group counts in a year if **any** of its entities has a clock date in that year. Independents are their own group. |
| | `group_full` | A holding group counts once, in the year of its **last** clock date, only if **every** entity in it has a clock date. |
| **Date** | `status clock` | The local date of the latest flip to Departed in Deal Ledger status history. Every flip counts: rebounds and entity transfers included. This is what a status-based report sees. |
| | `contract clock` | The Deal Ledger contracted departure date. Entity transfers are excluded, because a transfer is not attrition. |
| **Segment source** | `Deal Ledger tier` | The tier on the Deal Ledger entity (for groups, the holding entity's tier). |
| | `BRR tier` | The reporting tier in BRR, which can differ. |

`mart_attrition_lens` holds every combination (3 × 2 × 2) by tier and year: 144 rows.

## 3. Date conventions

1. **End-date convention.** Deal Ledger `departure_date` = Billing Core `term_end_date` + 1 day. A naive equality test reports every departed entity as misaligned. The models normalise with `last_service_date = departure_date - 1` and compare against the inclusive term end.
2. **Local dates.** Every UTC timestamp is converted explicitly in staging with `timezone('Europe/Amsterdam', ts)`. Billing comparisons use the local date. An invoice issued 23:00–23:59 UTC on the last service day falls on the departure date locally (UTC+1 in winter, UTC+2 in summer). A UTC comparison misses it.
3. **Clock tolerance.** The two clocks are "aligned" when they are at most 7 days apart (`var('clock_tolerance_days')`). Beyond that, the status flip is lagging (or missing), which is a data-entry problem rather than a calendar effect.

`int_attrition_events.clock_alignment` labels every entity:

| Label | Rule |
|---|---|
| `no_departure` | No contract date and no flip to Departed. |
| `rebound_no_contract_departure` | Flipped to Departed, then back to Active; no contract date. |
| `status_only` | Flipped to Departed without a contract date, and not a rebound. |
| `status_lag_missing_flip` | Contract date exists, but the status never flipped. |
| `status_lag_late_flip` | The flip is more than 7 days after the contract date. |
| `status_lag_early_flip` | The flip is more than 7 days before the contract date. |
| `clock_year_shift` | Within 7 days, but in different calendar years (for example, a flip on 30 Dec with a contract departure on 1 Jan). |
| `aligned` | Within 7 days, same year. |

## 4. Variance bridge

**Basis A**: entity unit, status clock, Deal Ledger tier, member entities excluded. Each row is a holding entity or an independent, so A is a count of groups.

**Basis B**: group_any unit, contract clock, BRR tier, entity transfers excluded.

Grain: group × year × tier. A group sitting in a different tier on each side is one removal plus one addition, which is how `tier_source_mismatch` becomes visible.

Each group in A only (removal) or B only (addition) gets exactly **one** reason code. The first rule that matches wins, so the priority is fixed:

| Priority | Reason code | Removal (A only) when… | Addition (B only) when… |
|---|---|---|---|
| 1 | `rebound` | The holding/independent flipped back to Active after the flip. | — |
| 2 | `entity_transfer` | The departure reason is entity transfer. | — |
| 3 | `status_lag` | The clock alignment is any `status_lag_*` or `status_only`. | The contract date is in the year and the alignment is `status_lag_*`. |
| 4 | `member_only_departure` | — | The holding has no contract date in the year; only member entities departed. |
| 5 | `tier_source_mismatch` | The group is in B the same year, under another tier. | The group is in A the same year, under another tier. |
| 6 | `clock_year_shift` | The alignment is `clock_year_shift`. | The alignment is `clock_year_shift`. |

**Run-rate on matched groups.** A group present in both bases can still differ in EUR: Basis A carries only the holding's run-rate, while Basis B also carries the members that departed in the same year. That difference is booked as an `amount_only` row with reason `member_only_departure`, and only when it equals the members' run-rate exactly. Anything else stays unexplained and fails the tests.

**Tie-out.** With signed deltas, `basis_a + removals + additions + amount_only = basis_b` must hold, both in count and to the cent in EUR, for every year × tier and every year. Two dbt tests enforce this: `assert_variance_bridge_ties_out` and `assert_no_unexplained_bridge_rows`. The `accepted_values` test on `reason_code` rejects anything outside the six codes.

## 5. ID resolution and run-rate

`int_id_crosswalk` resolves each entity to its billing keys through every path and records which one matched:

| Path | Source shape |
|---|---|
| `direct_ref` | One Billing Core ID in the Deal Ledger entity field. |
| `comma_list` | Several IDs in that field, separated by `,` or `, `. |
| `crosswalk` | A row in the Billing Core crosswalk table. Some rows hold two IDs joined by `"; "` (flagged `source_value_had_multiple`). |
| `partner_biller` | Partner Biller customer reference (one-way, Deal Ledger → Partner Biller). |
| `unlinked` | Pipeline entities with no billing. |

**Run-rate lookups:**
- **Naive:** BRR key = `kl_` + Deal Ledger ID. It comes back blank for direct-checkout book customers (BRR is keyed on their Billing Core ID) and for Partner Biller customers (no BRR rows at all).
- **Resolved:** try the Deal Ledger key first, then every Billing Core key from the crosswalk. Partner Biller entities stay blank, with reason `partner_biller_has_no_brr_rows`.

The run-rate at departure used in all attrition EUR figures is the resolved BRR booked run-rate. Blanks count as 0.

## 6. Orphaned billing

An entity with status Departed and a departure date is orphaned when either of these holds:

- **`active_plan`**: a Billing Core plan is still active, or its inclusive term end is later than `departure_date - 1`.
- **`post_departure_invoice`**: an invoice has a local issue date on or after the departure date.

`active_plan` wins when both apply. **MRR at risk** = MRR of the active plans (`active_plan`) or of the plans that were invoiced after departure (`post_departure_invoice`). `days_since_departure` is counted to the snapshot date. `caught_by_utc_compare` shows whether a UTC-date comparison would have found the case.

## 7. Duplicate contacts

A duplicate is two or more Engagement Hub contacts with the same `lower(trim(email))` on the same entity.

**Keeper rule:** keep the copy with the most tasks + conversations, and delete the rest even if the names differ. Ties break on the lowest contact ID; the synthetic data has no ties. A contact with a different email is a different contact and is kept, even when the name matches.

## 8. Verification

`data/truth/planted_defects.csv` lists every planted case and its expected label. pytest checks that each mart detects exactly those IDs with those labels: no misses and no extras. It also checks that a UTC comparison misses the clock-boundary invoices while the local comparison catches them, that the bridge ties out to the cent, and that none of the banned vocabulary appears in the repo.

## 9. Limitations

- Returns (a departed customer coming back under a new contract) are part of the vocabulary but are not modelled.
- Partner Biller entities never depart in the synthetic book, because they have no BRR tier to segment by.
- Run-rate is a single booked value per BRR key, not a monthly series. Run-rate compression is out of scope.
- Synthetic prices are whole euros per site, so run-rate figures are round numbers.
