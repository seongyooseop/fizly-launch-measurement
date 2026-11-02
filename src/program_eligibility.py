"""Program view: which advertisers can use which study.

FIZLY is one advertiser. A market measurement program needs a rule for the
rest: given an advertiser's monthly video budget and how much of its sales
happen in stores, which studies will be readable, and which one answers its
payback question? The rule reuses each chapter's design math:

  brand lift      answers per question follow reach (users engine, chapter 1)
  conversion lift detectable lift follows matched online orders (chapter 2)
  geo test        detectable return from chapter 3, scaled for smaller brands
                  (regional noise as a share of sales grows as sales shrink)

Assumptions, stated on the page: advertisers' sales scale with their video
budget at FIZLY's ratio; regional noise scales with 1 / sqrt(sales).
Writes outputs/program_eligibility.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ch1_brand_lift import PLAN_BASE, expected_answers, mde
from users import AOV_ONLINE, PIXEL_MATCH, make_people
from world import BRAND_LIFT_WEEKS, World, actual_plan, week_mask

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
TIERS_M = [30, 60, 120, 300]          # monthly short-video budget, M KRW
OFFLINE = [0.25, 0.50, 0.75]          # share of sales in stores
BLS_HOLDOUT, CLS_HOLDOUT = 0.20, 0.10
READ_AWARENESS_PP = 5.0               # typical single-flight awareness lift is 3-7pp
READ_CLS_LIFT = 0.15                  # a lift study that cannot see 15% is not worth running
READ_GEO_IROAS = 1.0
PLATFORM_SHARE = 0.55                 # share of online orders placed by platform users
# Service levels: who does the work, how long it takes, and how many one
# partner can carry in a quarter. Partner days and the quarterly mix are
# planning assumptions (about 50 working days a quarter go to studies; the rest
# to programs, product feedback and enablement), not outputs of the lab.
SERVICE = [
    {"level": "Self-serve", "who": "Advertiser or agency sets it up from the platform's templates; the partner reviews the readout",
     "studies": "Brand lift or conversion lift from a template", "calendar_weeks": "5-7 (flight + readout)",
     "partner_days": 0.5, "per_quarter": 16},
    {"level": "Standard", "who": "Partner sizes the holdout from history, agrees the rules, presents the readout",
     "studies": "Brand lift and conversion lift in one flight", "calendar_weeks": "8-10",
     "partner_days": 3, "per_quarter": 6},
    {"level": "Deep", "who": "Partner plans with advertiser and agency, sizes regions, runs in-flight checks, calibrates the MMM, writes the readout",
     "studies": "Brand lift, conversion lift, geo test on sell-out, MMM calibration (this case)",
     "calendar_weeks": "12-14 (2 design, 4 brand lift, 6 test, 2 cooldown)", "partner_days": 12, "per_quarter": 2},
]
DEEP_MIN_BUDGET_M = 60                # below this a geo test may be readable but is rarely worth a deep engagement yet


def main():
    w = World()
    people = make_people(w)
    plan = actual_plan(w)
    t = week_mask(w, *BRAND_LIFT_WEEKS)
    base_spend = plan.spend["short_video"][t].sum(axis=0)       # FIZLY, 4 weeks
    fizly_month_m = base_spend.sum() / 1e6
    geo = json.loads((OUT / "ch3_design.json").read_text(encoding="utf-8"))
    chosen = next(o for o in geo["options"] if abs(o["share"] - geo["chosen_share"]) < 1e-9)
    obs = w.simulate(plan)[0]
    post = obs.week.between(BRAND_LIFT_WEEKS[0], BRAND_LIFT_WEEKS[1])
    fizly_sales_month = (obs.loc[post, "offline_rev"].sum() + obs.loc[post, "online_rev"].sum()) / 1e6
    sales_per_video_won = fizly_sales_month / fizly_month_m

    tiers = []
    for b in TIERS_M:
        k = b / fizly_month_m
        nt, nc = expected_answers(people, base_spend * k, BLS_HOLDOUT)
        aw_mde = 100 * mde(PLAN_BASE["awareness"], nt, nc)
        rec_mde = 100 * mde(PLAN_BASE["ad_recall"], nt, nc)
        sales_month = b * sales_per_video_won
        geo_iroas = chosen["min_detectable_iroas"] * np.sqrt(fizly_month_m / b)
        row = {"budget_m": b, "sales_month_m": sales_month, "answers_test": nt, "answers_holdout": nc,
               "awareness_mde_pp": aw_mde, "recall_mde_pp": rec_mde, "geo_min_iroas": geo_iroas, "by_offline": []}
        for off in OFFLINE:
            orders = sales_month * 1e6 * 1.5 * (1 - off) / AOV_ONLINE * PLATFORM_SHARE * PIXEL_MATCH  # six weeks
            se_rel = np.sqrt(1 / (orders * (1 - CLS_HOLDOUT)) + 1 / (orders * CLS_HOLDOUT))
            cls_mde = 2.8 * se_rel
            studies = []
            studies.append("Brand lift" if aw_mde <= READ_AWARENESS_PP else "Brand lift (ad recall only)")
            if cls_mde <= READ_CLS_LIFT:
                studies.append("Conversion lift")
            geo_ok = off >= 0.5 and geo_iroas <= READ_GEO_IROAS and b >= DEEP_MIN_BUDGET_M
            if geo_ok:
                studies.append("Geo test on sell-out")
            payback = ("Geo test (stores + online)" if geo_ok
                       else "Conversion lift" if off < 0.5 and cls_mde <= READ_CLS_LIFT
                       else "Online only for now: stores need a geo test, worth it once the budget grows"
                       if off >= 0.5 else "Not readable yet: pool flights, or wait for MMM history")
            service = "Deep" if geo_ok else "Self-serve" if b <= TIERS_M[0] else "Standard"
            row["by_offline"].append({"offline": off, "cls_mde_rel": cls_mde, "studies": studies,
                                      "payback_answer": payback, "service": service})
        tiers.append(row)
    days = sum(x["partner_days"] * x["per_quarter"] for x in SERVICE)
    out = {"tiers": tiers, "offline": OFFLINE, "fizly_month_m": fizly_month_m, "service_levels": SERVICE,
           "quarter_mix": {x["level"]: x["per_quarter"] for x in SERVICE}, "quarter_partner_days": days,
           "assumptions": ["Sales scale with video budget at FIZLY's ratio "
                           f"({sales_per_video_won:.0f} won of sales per won of monthly video budget).",
                           "Regional noise as a share of sales grows as 1 / sqrt(sales) for smaller brands.",
                           f"Readable: awareness detectable at {READ_AWARENESS_PP:.0f}pp or less; conversion lift detects a "
                           f"{100 * READ_CLS_LIFT:.0f}% lift; geo test detects a total return of {READ_GEO_IROAS:.1f}.",
                           "A geo test needs region-level store data, so it is offered only where stores are half of sales or more.",
                           f"Service level: deep where a geo test answers payback and the budget is {DEEP_MIN_BUDGET_M}M KRW a month or more; "
                           f"self-serve at {TIERS_M[0]}M; standard otherwise. Partner days per study are planning assumptions."]}
    (OUT / "program_eligibility.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for r in tiers:
        print(f"{r['budget_m']:>4}M/month: awareness MDE {r['awareness_mde_pp']:.1f}pp, recall {r['recall_mde_pp']:.1f}pp, "
              f"geo min iROAS {r['geo_min_iroas']:.2f}")
        for c in r["by_offline"]:
            print(f"    stores {c['offline']:.0%}: {c['service']:10s} CLS MDE {100 * c['cls_mde_rel']:.1f}% | {', '.join(c['studies'])} | payback: {c['payback_answer']}")
    print(f"A quarter for one partner: {out['quarter_mix']} = {days:.0f} partner days")


if __name__ == "__main__":
    main()
