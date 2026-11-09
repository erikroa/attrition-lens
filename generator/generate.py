#!/usr/bin/env python3
"""Synthetic data generator for Kestrel Grid (fictional B2B SaaS, energy monitoring).

Writes the raw source extracts to data/raw/*.csv and every deliberately planted
defect, with its expected label, to data/truth/planted_defects.csv.

Fully deterministic: one fixed seed, no wall-clock input.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20251231
SNAPSHOT = date(2026, 3, 31)            # extract date of all sources
HISTORY_START = date(2023, 1, 1)        # invoices are kept from here on
YEARS = (2023, 2024, 2025)              # reporting years
TIERS = ["Anchor", "Scale", "Standard", "Starter"]
TIER_P = [0.10, 0.25, 0.40, 0.25]
PRICE_PER_SITE_CENTS = {"Anchor": 3900, "Scale": 4900, "Standard": 5900, "Starter": 6900}
SITES = {"Anchor": (120, 400), "Scale": (40, 120), "Standard": (10, 40), "Starter": (2, 10)}

N_GROUPS = 250
N_ENTITIES = 1500
N_PIPELINE = 60
N_PARTNER = 40
DIRECT_CHECKOUT_SHARE = 0.08

# planted cases per reporting year
IND_PER_YEAR = {
    "clean": 40, "rebound": 9, "transfer": 8, "lag_missing": 6,
    "lag_late": 5, "clock_year_shift": 4, "tier_departure": 5,
}
ORPHANS_PER_YEAR = {"active_plan": 4, "post_departure_invoice": 3, "clock_boundary": 3}
GROUP_PER_YEAR = {"clean_group": 10, "member_only": 10, "holding_rebound": 2}
CROSS_TIER_PER_YEAR = 4          # of the member_only groups
N_TIER_MISMATCH_IDLE = 30        # tier mismatches on entities that never depart
N_DUP_SETS = 40
N_DISTINCT_EMAIL = 15

# ---------------------------------------------------------------- names
W1 = ["Amber", "Birch", "Cobalt", "Dune", "Ember", "Fjord", "Granite", "Harbor", "Ivory", "Juniper",
      "Kiln", "Linden", "Marble", "Nettle", "Onyx", "Pine", "Quarry", "Rowan", "Slate", "Tidal",
      "Umber", "Vale", "Willow", "Yarrow", "Zephyr", "Alder", "Basalt", "Cedar", "Delta", "Elm"]
W2 = ["Court", "Yard", "Point", "Row", "Gate", "Square", "Field", "Bank", "Quay", "Ridge",
      "Crest", "Hollow", "Lane", "Mill", "Park", "Reach", "Spire", "Terrace", "Wharf", "Works"]
SUFFIX = ["Properties", "Estates", "Offices", "Campus", "Buildings", "Workspaces", "Venues", "Lofts"]
SYL = ["ka", "lo", "mi", "ren", "tas", "vel", "dor", "sin", "ya", "ul", "bri", "zan", "fe", "nor",
       "ti", "qua", "seb", "or", "lan", "vi"]


class Names:
    def __init__(self, rng: np.random.Generator):
        self.rng = rng
        combos = [f"{a} {b} {c}" for a in W1 for b in W2 for c in SUFFIX]
        self.pool = list(rng.permutation(combos))

    def company(self) -> str:
        return self.pool.pop()

    def person(self) -> tuple[str, str]:
        r = self.rng
        first = "".join(r.choice(SYL, 2)).capitalize()
        last = "".join(r.choice(SYL, 3)).capitalize()
        return first, last


# ---------------------------------------------------------------- helpers
def ts(d: date, hh: int, mm: int) -> str:
    return f"{d.isoformat()}T{hh:02d}:{mm:02d}:00Z"


def rand_date(rng, a: date, b: date) -> date:
    return a + timedelta(days=int(rng.integers(0, (b - a).days + 1)))


def other_tier(rng, tier: str) -> str:
    return str(rng.choice([t for t in TIERS if t != tier]))


@dataclass
class Entity:
    entity_id: str
    name: str
    level: str                    # holding group / member entity / independent
    holding_id: str | None
    tier: str
    channel: str                  # billing core / direct-checkout book / partner biller / none
    created: date
    status: str = "Active"
    dep: date | None = None       # Deal Ledger departure date (exclusive: first day without service)
    reason: str | None = None
    successor: str | None = None
    flips: list = field(default_factory=list)   # (date, hh, mm, from, to)
    brr_tier: str | None = None
    scenario: str | None = None
    scen_year: int | None = None
    link_path: str | None = None
    bc_ids: list = field(default_factory=list)
    partner_id: str | None = None

    @property
    def group_id(self) -> str:
        return self.holding_id or self.entity_id


def main(out_dir: Path) -> None:
    rng = np.random.default_rng(SEED)
    names = Names(rng)
    E: dict[str, Entity] = {}
    seq = {"dl": 0}

    def add(level, holding_id, tier, channel, created) -> Entity:
        seq["dl"] += 1
        e = Entity(f"DL-{seq['dl']:05d}", names.company(), level, holding_id, tier, channel, created)
        E[e.entity_id] = e
        return e

    # ------------------------------------------------ holding groups
    groups: dict[str, list[str]] = {}
    for _ in range(N_GROUPS):
        tier = str(rng.choice(TIERS, p=TIER_P))
        created = rand_date(rng, date(2019, 1, 1), date(2022, 6, 30))
        h = add("holding group", None, tier, "billing core", created)
        k = int(rng.choice([1, 2, 3, 4], p=[0.30, 0.35, 0.20, 0.15]))
        groups[h.entity_id] = []
        for _ in range(k):
            mt = tier if rng.random() > 0.10 else other_tier(rng, tier)
            m = add("member entity", h.entity_id, mt, "billing core",
                    rand_date(rng, created, date(2022, 12, 31)))
            groups[h.entity_id].append(m.entity_id)

    # ------------------------------------------------ independents
    n_transfers = IND_PER_YEAR["transfer"] * len(YEARS)
    n_ind = N_ENTITIES - len(E) - n_transfers
    for i in range(n_ind):
        if i < N_PIPELINE:
            e = add("independent", None, str(rng.choice(TIERS, p=TIER_P)), "none",
                    rand_date(rng, date(2025, 1, 1), date(2026, 3, 1)))
            e.status = "Pipeline"
            continue
        channel = "partner biller" if i < N_PIPELINE + N_PARTNER else (
            "direct-checkout book" if rng.random() < DIRECT_CHECKOUT_SHARE else "billing core")
        add("independent", None, str(rng.choice(TIERS, p=TIER_P)), channel,
            rand_date(rng, date(2019, 1, 1), date(2022, 12, 31)))

    # ------------------------------------------------ scenario assignment
    eligible_ind = [e.entity_id for e in E.values()
                    if e.level == "independent" and e.channel in ("billing core", "direct-checkout book")]
    eligible_ind = list(rng.permutation(eligible_ind))
    holdings = list(rng.permutation(list(groups.keys())))

    def take(pool, n):
        out = pool[:n]
        del pool[:n]
        return out

    for y in YEARS:
        for scen, n in IND_PER_YEAR.items():
            for eid in take(eligible_ind, n):
                E[eid].scenario, E[eid].scen_year = scen, y
        for scen, n in GROUP_PER_YEAR.items():
            for hid in take(holdings, n):
                E[hid].scenario, E[hid].scen_year = scen, y

    def flip(e: Entity, d: date, frm: str, to: str):
        e.flips.append((d, int(rng.integers(8, 18)), int(rng.integers(0, 60)), frm, to))

    def depart(e: Entity, dep: date, flip_date: date | None, reason: str):
        e.dep, e.reason = dep, reason
        if flip_date is not None:
            flip(e, flip_date, "Active", "Departed")
            e.status = "Departed"

    reasons = ["budget", "competitor", "portfolio sale", "site closure", "consolidation"]

    def clean_dates(y):
        dep = rand_date(rng, date(y, 1, 5), date(y, 12, 20))
        return dep, dep + timedelta(days=int(rng.integers(0, 6)))

    orphan_plan: dict[str, str] = {}
    successors_to_make = []
    for e in list(E.values()):
        s, y = e.scenario, e.scen_year
        if s is None:
            continue
        if s in ("clean", "tier_departure"):
            dep, fd = clean_dates(y)
            depart(e, dep, fd, str(rng.choice(reasons)))
        elif s in ("rebound", "holding_rebound"):
            fd = rand_date(rng, date(y, 1, 5), date(y, 11, 30))
            flip(e, fd, "Active", "Departed")
            flip(e, fd + timedelta(days=int(rng.integers(3, 41))), "Departed", "Active")
            e.status = "Active"
        elif s == "transfer":
            dep = rand_date(rng, date(y, 1, 5), date(y, 12, 20))
            depart(e, dep, dep + timedelta(days=int(rng.integers(0, 4))), "entity transfer")
            successors_to_make.append(e)
        elif s == "lag_missing":
            dep = rand_date(rng, date(y, 1, 5), date(y, 12, 20))
            depart(e, dep, None, str(rng.choice(reasons)))       # status never flipped
        elif s == "lag_late":
            dep = rand_date(rng, date(y, 12, 8), date(y, 12, 20))
            depart(e, dep, dep + timedelta(days=int(rng.integers(30, 61))), str(rng.choice(reasons)))
        elif s == "clock_year_shift":
            # contract ends 31 Dec (inclusive) -> Deal Ledger departure 1 Jan; status flipped in late Dec
            depart(e, date(y + 1, 1, 1), date(y, 12, int(rng.integers(29, 32))), str(rng.choice(reasons)))
        elif s == "clean_group":
            dep, fd = clean_dates(y)
            r = str(rng.choice(reasons))
            depart(e, dep, fd, r)
            for mid in groups[e.entity_id]:
                depart(E[mid], dep, fd, r)
                E[mid].flips[-1] = (fd, e.flips[-1][1], e.flips[-1][2], "Active", "Departed")
        elif s == "member_only":
            mids = groups[e.entity_id]
            n_dep = 1 if len(mids) == 1 else int(rng.integers(1, min(2, len(mids)) + 1))
            dep, fd = clean_dates(y)
            for mid in mids[:n_dep]:
                depart(E[mid], dep, fd, str(rng.choice(reasons)))
                E[mid].tier = e.tier            # default: same tier as holding (cross-tier set below)

    # cross-tier partial losses: departing member sits in a different tier than its holding
    for y in YEARS:
        mo = [h for h in holdings_sorted(E, "member_only", y)]
        for hid in mo[:CROSS_TIER_PER_YEAR]:
            for mid in groups[hid]:
                if E[mid].dep is not None:
                    E[mid].tier = other_tier(rng, E[hid].tier)

    # successors of entity transfers (new legal entity, Active, own billing)
    for old in successors_to_make:
        s = add("independent", None, old.tier, "billing core", old.dep)
        old.successor = s.entity_id

    # orphaned billing: chosen among clean independent departures still marked Departed
    for y in YEARS:
        pool = sorted(e.entity_id for e in E.values()
                      if e.scenario == "clean" and e.scen_year == y)
        pool = list(rng.permutation(pool))
        for kind, n in ORPHANS_PER_YEAR.items():
            for eid in take(pool, n):
                orphan_plan[eid] = kind

    # ------------------------------------------------ tiers in BRR
    for e in E.values():
        e.brr_tier = e.tier
    for e in E.values():
        if e.scenario == "tier_departure":
            e.brr_tier = other_tier(rng, e.tier)
    idle = sorted(e.entity_id for e in E.values()
                  if e.status != "Pipeline" and e.channel != "partner biller"
                  and e.scenario is None and e.dep is None and not e.flips
                  and (e.level != "member entity" or E[e.holding_id].scenario is None)
                  )
    tier_idle = list(rng.permutation(idle))[:N_TIER_MISMATCH_IDLE]
    for eid in tier_idle:
        E[eid].brr_tier = other_tier(rng, E[eid].tier)

    # ------------------------------------------------ status history
    hist = []
    for e in E.values():
        if e.status == "Pipeline":
            hist.append((e.entity_id, ts(e.created, 9, 0), "", "Pipeline"))
            continue
        hist.append((e.entity_id, ts(e.created, 9, 0), "Pipeline", "Active"))
        for d, hh, mm, frm, to in e.flips:
            hist.append((e.entity_id, ts(d, hh, mm), frm, to))
    hist_df = pd.DataFrame(hist, columns=["entity_id", "changed_at_utc", "from_status", "to_status"])
    hist_df = hist_df.sort_values(["changed_at_utc", "entity_id"]).reset_index(drop=True)
    hist_df.insert(0, "history_id", [f"SH-{i + 1:06d}" for i in range(len(hist_df))])

    # ------------------------------------------------ billing core: customers, links, plans, invoices
    bc_seq, pl_seq, inv_seq, xw_seq = [100000], [0], [0], [0]
    bc_rows, plan_rows, inv_rows, xw_rows = [], [], [], []
    boundary_invoices: list[tuple[str, str]] = []

    def new_bc(e: Entity, created: date) -> str:
        bc_seq[0] += 1
        bid = f"BC-{bc_seq[0]:06d}"
        bc_rows.append((bid, e.name, ts(created, 7, 30)))
        return bid

    def new_invoice(bid, pid, d, hh, mm, cents):
        inv_seq[0] += 1
        iid = f"INV-{inv_seq[0]:07d}"
        inv_rows.append((iid, bid, pid, ts(d, hh, mm), int(cents)))
        return iid

    def month_starts(start: date, end: date):
        d = date(start.year + (start.month // 12), start.month % 12 + 1, 1)
        while d <= end:
            yield d
            d = date(d.year + (d.month // 12), d.month % 12 + 1, 1)

    def anniversary_after(start: date, ref: date) -> date:
        d = date(ref.year, start.month, start.day)
        if d <= ref:
            d = date(ref.year + 1, start.month, start.day)
        return d - timedelta(days=1)

    entity_mrr: dict[str, int] = {}
    for e in E.values():
        if e.channel not in ("billing core", "direct-checkout book"):
            continue
        u = rng.random()
        if e.scenario == "transfer" or e.created > date(2022, 12, 31):
            path = "direct_ref"
        else:
            path = "direct_ref" if u < 0.75 else ("comma_list" if u < 0.85 else "crosswalk")
        semicolon = path == "crosswalk" and rng.random() < 0.45
        n_bc = 1 if path == "direct_ref" else (int(rng.integers(2, 4)) if path == "comma_list"
                                               else (2 if semicolon else 1))
        e.bc_ids = [new_bc(e, e.created) for _ in range(n_bc)]
        e.link_path = path
        if path == "crosswalk":
            xw_seq[0] += 1
            xw_rows.append((f"XW-{xw_seq[0]:05d}", e.entity_id, "; ".join(e.bc_ids)))

        lo, hi = SITES[e.tier]
        total_sites = int(rng.integers(lo, hi + 1))
        price = PRICE_PER_SITE_CENTS[e.tier]
        plans_per_bc = [int(rng.integers(1, 3)) for _ in e.bc_ids]
        n_plans = sum(plans_per_bc)
        cuts = sorted(rng.choice(np.arange(1, total_sites), size=min(n_plans - 1, total_sites - 1),
                                 replace=False)) if n_plans > 1 else []
        sizes = np.diff([0, *cuts, total_sites]).tolist()
        while len(sizes) < n_plans:
            sizes.append(1)
        mrr_total, pidx, first_plan = 0, 0, True
        for bid, npl in zip(e.bc_ids, plans_per_bc):
            for _ in range(npl):
                pl_seq[0] += 1
                pid = f"PL-{pl_seq[0]:06d}"
                sites = int(sizes[pidx]); pidx += 1
                mrr = sites * price
                mrr_total += mrr
                start = date(e.created.year, e.created.month, min(e.created.day, 28))
                okind = orphan_plan.get(e.entity_id)
                if e.dep is None or (okind == "active_plan" and first_plan):
                    pstatus, end = "active", anniversary_after(start, SNAPSHOT)
                else:
                    pstatus, end = "cancelled", e.dep - timedelta(days=1)   # inclusive last day
                first_plan = False
                plan_rows.append((pid, bid, f"KG-{e.tier[:2].upper()}-SITE", sites, price, mrr,
                                  pstatus, start.isoformat(), end.isoformat()))
                # regular monthly invoices, 1st of month 06:xx UTC (local = same date)
                last = min(end, SNAPSHOT)
                if start >= HISTORY_START and start <= last:
                    new_invoice(bid, pid, start, 6, int(rng.integers(0, 50)), mrr)
                for d in month_starts(start, last):
                    if d >= HISTORY_START:
                        new_invoice(bid, pid, d, 6, int(rng.integers(0, 50)), mrr)
        entity_mrr[e.entity_id] = mrr_total

        # extra invoices around departure
        if e.dep is not None and e.status == "Departed":
            okind = orphan_plan.get(e.entity_id)
            bid0 = e.bc_ids[0]
            pid0 = next(p[0] for p in plan_rows if p[1] == bid0)
            last_day = e.dep - timedelta(days=1)
            if okind == "post_departure_invoice":
                d = date(e.dep.year + (e.dep.month // 12), e.dep.month % 12 + 1, 1)
                new_invoice(bid0, pid0, d, 6, int(rng.integers(0, 50)), entity_mrr[e.entity_id] // 2)
            elif okind == "clock_boundary":
                iid = new_invoice(bid0, pid0, last_day, 23, int(rng.integers(5, 56)),
                                  int(rng.integers(500, 5000)))
                boundary_invoices.append((iid, e.entity_id))
            elif okind is None and e.scenario in ("clean", "tier_departure") and rng.random() < 0.30:
                # final usage invoice on the last service day, daytime UTC: correctly NOT orphaned
                new_invoice(bid0, pid0, last_day, int(rng.integers(9, 15)), int(rng.integers(0, 60)),
                            int(rng.integers(500, 5000)))

    # ------------------------------------------------ partner biller
    pb_rows = []
    for i, e in enumerate([e for e in E.values() if e.channel == "partner biller"]):
        e.partner_id = f"PB-{5001 + i}"
        lo, hi = SITES[e.tier]
        pb_rows.append((e.partner_id, str(rng.choice(["North", "South", "East"])), e.name,
                        int(rng.integers(lo, hi + 1)) * PRICE_PER_SITE_CENTS[e.tier], "active"))

    # ------------------------------------------------ BRR reporting layer
    brr_rows = []
    for e in E.values():
        if e.channel not in ("billing core", "direct-checkout book"):
            continue
        key = f"kl_{e.bc_ids[0]}" if e.channel == "direct-checkout book" else f"kl_{e.entity_id}"
        as_of = (e.dep - timedelta(days=1)) if e.dep else SNAPSHOT
        brr_rows.append((key, e.brr_tier, f"{entity_mrr[e.entity_id] * 12 / 100:.2f}",
                         as_of.strftime("%Y-%m")))

    # ------------------------------------------------ Deal Ledger entities + contracts
    ent_rows, ct_rows = [], []
    for e in E.values():
        ref = ""
        if e.link_path == "direct_ref":
            ref = e.bc_ids[0]
        elif e.link_path == "comma_list":
            ref = ("," if rng.random() < 0.5 else ", ").join(e.bc_ids)
        ent_rows.append((e.entity_id, e.name, e.level, e.holding_id or "", e.tier, e.status, e.channel,
                         ref, e.partner_id or "", e.dep.isoformat() if e.dep else "",
                         e.reason or "", e.successor or "", e.created.isoformat()))
        if e.status != "Pipeline":
            lo, hi = SITES[e.tier]
            ct_rows.append((f"CT-{len(ct_rows) + 1:05d}", e.entity_id, e.created.isoformat(),
                            int(rng.integers(lo, hi + 1))))

    # ------------------------------------------------ Engagement Hub contacts
    contacts = []   # [entity_id, full_name, email, tasks, convs]
    base_by_entity: dict[str, list[int]] = {}
    for e in E.values():
        dom = e.name.lower().replace(" ", "") + ".example"
        used = set()
        for _ in range(int(rng.integers(1, 3))):
            while True:
                f, l = names.person()
                em = f"{f}.{l}@{dom}".lower()
                if em not in used:
                    used.add(em)
                    break
            contacts.append([e.entity_id, f"{f} {l}", em, int(rng.integers(0, 40)), int(rng.integers(0, 25))])
            base_by_entity.setdefault(e.entity_id, []).append(len(contacts) - 1)

    first_contact = [idx[0] for idx in base_by_entity.values()]
    picks = list(rng.permutation(first_contact))[: N_DUP_SETS + N_DISTINCT_EMAIL]
    dup_sets, distinct_pairs = [], []
    for b in picks[:N_DUP_SETS]:
        eid, full, em, _, _ = contacts[b]
        f, l = full.split(" ")
        members = [b]
        for c in range(int(rng.integers(1, 3))):
            nm = full if rng.random() < 0.4 else f"{f[0]}. {l}"
            em2 = em if rng.random() < 0.6 else em.capitalize()     # same address, case differs
            contacts.append([eid, nm, em2, 0, 0])
            members.append(len(contacts) - 1)
        totals = rng.permutation(np.arange(5, 5 + 7 * len(members), 7))   # distinct, no ties
        for idx, tot in zip(members, totals):
            t = int(rng.integers(0, tot + 1))
            contacts[idx][3], contacts[idx][4] = t, int(tot - t)
        dup_sets.append(members)
    for b in picks[N_DUP_SETS:]:
        eid, full, em, _, _ = contacts[b]
        local, dom = em.split("@")
        contacts.append([eid, full, f"{local}.office@{dom}", int(rng.integers(0, 30)), int(rng.integers(0, 20))])
        distinct_pairs.append((b, len(contacts) - 1))

    order = rng.permutation(len(contacts))
    cid = {int(old): f"EH-{new + 1:06d}" for new, old in enumerate(order)}
    contact_rows = [(cid[i], *contacts[i]) for i in sorted(range(len(contacts)), key=lambda i: cid[i])]

    # ------------------------------------------------ write raw
    raw = out_dir / "raw"
    truth = out_dir / "truth"
    raw.mkdir(parents=True, exist_ok=True)
    truth.mkdir(parents=True, exist_ok=True)

    def w(name, rows, cols):
        pd.DataFrame(rows, columns=cols).to_csv(raw / f"{name}.csv", index=False)

    w("deal_ledger_entities", ent_rows,
      ["entity_id", "entity_name", "hierarchy_level", "holding_entity_id", "tier", "status",
       "billing_channel", "billing_customer_ref", "partner_customer_ref", "departure_date",
       "departure_reason", "successor_entity_id", "created_date"])
    hist_df.to_csv(raw / "deal_ledger_status_history.csv", index=False)
    w("deal_ledger_contracts", ct_rows, ["contract_id", "entity_id", "start_date", "metered_sites"])
    w("billing_core_customers", bc_rows, ["billing_customer_id", "payer_name", "created_at_utc"])
    w("billing_core_plans", plan_rows,
      ["plan_id", "billing_customer_id", "plan_code", "metered_sites", "price_per_site_cents",
       "mrr_cents", "plan_status", "term_start_date", "term_end_date"])
    inv_df = pd.DataFrame(inv_rows, columns=["invoice_id", "billing_customer_id", "plan_id",
                                             "issued_at_utc", "amount_cents"])
    inv_df.to_csv(raw / "billing_core_invoices.csv", index=False)
    w("billing_core_crosswalk", xw_rows, ["crosswalk_id", "entity_id", "billing_customer_ids"])
    w("partner_biller_customers", pb_rows,
      ["partner_customer_id", "region", "customer_name", "monthly_fee_cents", "status"])
    w("engagement_hub_contacts", contact_rows,
      ["contact_id", "entity_id", "full_name", "email", "task_count", "conversation_count"])
    w("brr_run_rate", brr_rows, ["brr_key", "reporting_tier", "booked_run_rate_eur", "as_of_month"])

    # ------------------------------------------------ truth manifest
    T = []

    def t(did, dname, stype, sid, label, year=None, tier=None, detail=None):
        T.append((did, dname, stype, sid, label, year, tier, detail))

    ents = sorted(E.values(), key=lambda e: e.entity_id)
    plans_by_bc: dict[str, list] = {}
    for p in plan_rows:
        plans_by_bc.setdefault(p[1], []).append(p)
    for e in ents:   # 1 end-date convention
        if e.dep is None or not e.bc_ids:
            continue
        pl = [p for b in e.bc_ids for p in plans_by_bc[b]]
        if all(p[6] == "cancelled" and p[8] == (e.dep - timedelta(days=1)).isoformat() for p in pl):
            t(1, "end_date_convention", "entity", e.entity_id, "aligned_after_normalisation",
              e.dep.year)
    for e in ents:   # 2 rebounds, 3 transfers
        if e.scenario in ("rebound", "holding_rebound"):
            t(2, "rebound", "entity", e.entity_id, "rebound", e.scen_year, e.tier)
        if e.scenario == "transfer":
            t(3, "entity_transfer", "entity", e.entity_id, "entity_transfer", e.scen_year, e.tier,
              e.successor)
    for e in ents:   # 4 partial group loss
        if e.scenario == "member_only":
            gone = [E[m] for m in groups[e.entity_id] if E[m].dep is not None]
            cross = any(m.tier != e.tier for m in gone)
            t(4, "partial_group_loss", "group", e.entity_id,
              "partial_group_loss_cross_tier" if cross else "partial_group_loss",
              e.scen_year, e.tier, ",".join(m.entity_id for m in gone))
    for e in ents:   # 5 tier mismatch
        if e.brr_tier and e.brr_tier != e.tier and e.channel in ("billing core", "direct-checkout book"):
            t(5, "tier_mismatch", "entity", e.entity_id, "tier_mismatch", None, e.tier, e.brr_tier)
    for e in ents:   # 6 status lag / clock year shift
        lab = {"lag_missing": "status_lag_missing_flip", "lag_late": "status_lag_late_flip",
               "clock_year_shift": "clock_year_shift"}.get(e.scenario or "")
        if lab:
            t(6, "status_lag", "entity", e.entity_id, lab, e.dep.year, e.tier)
    for e in ents:   # 7 orphaned billing
        k = orphan_plan.get(e.entity_id)
        if k:
            t(7, "orphaned_billing", "entity", e.entity_id,
              "active_plan" if k == "active_plan" else "post_departure_invoice", e.dep.year, e.tier)
    for iid, eid in sorted(boundary_invoices):   # 8 clock boundary
        t(8, "clock_boundary_miss", "invoice", iid, "clock_boundary_miss", E[eid].dep.year, None, eid)
    for e in ents:   # 9 messy links
        if e.link_path == "comma_list":
            t(9, "messy_id_link", "entity", e.entity_id, "comma_list")
        elif e.link_path == "crosswalk" and len(e.bc_ids) > 1:
            t(9, "messy_id_link", "entity", e.entity_id, "crosswalk_semicolon")
    for e in ents:   # 10 run-rate blanks
        if e.channel == "direct-checkout book":
            t(10, "run_rate_blank", "entity", e.entity_id, "resolved_via_billing_key")
        elif e.channel == "partner biller":
            t(10, "run_rate_blank", "entity", e.entity_id, "partner_biller_no_brr")
            t(10, "run_rate_blank", "partner_customer", e.partner_id, "no_brr_rows")
    for members in dup_sets:   # 11 duplicate contacts
        tot = [contacts[i][3] + contacts[i][4] for i in members]
        keeper = members[int(np.argmax(tot))]
        for i in members:
            t(11, "duplicate_contact", "contact", cid[i], "keep" if i == keeper else "delete",
              detail=contacts[i][0])
    for a, b in distinct_pairs:
        for i in (a, b):
            t(11, "duplicate_contact", "contact", cid[i], "keep_distinct_email", detail=contacts[i][0])

    # 0 expected variance bridge rows (Basis A -> Basis B), derived from the planted scenarios
    def b(gid, reason, y, tier, side):
        if y in YEARS:
            t(0, "variance_bridge", "group", gid, reason, y, tier, side)

    for e in ents:
        s, y = e.scenario, e.scen_year
        if s is None or e.level == "member entity":
            continue
        if s in ("rebound", "holding_rebound"):
            b(e.entity_id, "rebound", y, e.tier, "removal")
        elif s == "transfer":
            b(e.entity_id, "entity_transfer", y, e.tier, "removal")
        elif s == "lag_missing":
            b(e.entity_id, "status_lag", y, e.brr_tier, "addition")
        elif s == "lag_late":
            b(e.entity_id, "status_lag", y, e.brr_tier, "addition")
            b(e.entity_id, "status_lag", y + 1, e.tier, "removal")
        elif s == "clock_year_shift":
            b(e.entity_id, "clock_year_shift", y, e.tier, "removal")
            b(e.entity_id, "clock_year_shift", y + 1, e.brr_tier, "addition")
        elif s == "tier_departure":
            b(e.entity_id, "tier_source_mismatch", y, e.tier, "removal")
            b(e.entity_id, "tier_source_mismatch", y, e.brr_tier, "addition")
        elif s == "member_only":
            b(e.entity_id, "member_only_departure", y, e.brr_tier, "addition")
        elif s == "clean_group":
            b(e.entity_id, "member_only_departure", y, e.brr_tier, "amount_only")

    tdf = pd.DataFrame(T, columns=["defect_id", "defect_name", "subject_type", "subject_id",
                                   "expected_label", "year", "tier", "detail"])
    tdf["year"] = tdf["year"].astype("Int64")
    tdf.to_csv(truth / "planted_defects.csv", index=False)

    # ------------------------------------------------ summary
    print(f"entities: {len(E)}  holding groups: {len(groups)}  "
          f"plans: {len(plan_rows)}  invoices: {len(inv_rows)}  contacts: {len(contact_rows)}")
    print(tdf.groupby(["defect_id", "defect_name", "expected_label"]).size().to_string())


def holdings_sorted(E, scenario, year):
    return sorted(e.entity_id for e in E.values() if e.scenario == scenario and e.scen_year == year)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data"))
    main(Path(ap.parse_args().out))
