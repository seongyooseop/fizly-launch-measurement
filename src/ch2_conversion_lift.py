"""Chapter 2: conversion lift on online orders (weeks 83-88).

Platform users in the regions where video runs are split before the flight:
a holdout never sees FIZLY ads. The study counts online orders the brand's
pixel can match to a user, so the lift is the gap between the two groups.

  1. design: holdout size vs the smallest detectable lift and online return
  2. readout: incremental orders and revenue, online iROAS, against the
     orders the platform credits to its ads (7-day click / 1-day view)
  3. 40 re-runs (new holdout draw and orders): bias and interval coverage

The truth is the expected extra orders among the test group, known from each
person's two potential outcomes.

    python src/ch2_conversion_lift.py [--mc 40]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import stats

from users import AOV_ONLINE, PIXEL_MATCH, WEIGHT, make_people, run_conversion_lift
from world import CONVERSION_LIFT_WEEKS, World

ROOT = Path(__file__).resolve().parents[1]
Z = stats.norm.ppf(0.975)
Z_POWER = stats.norm.ppf(0.80)
HOLDOUT = 0.10
PLAN_LIFT = (0.05, 0.30)   # plausible relative lift before the test


def readout(run, spend: float) -> dict:
    t, c = run.test, run.eligible & ~run.test
    nt, nc = t.sum(), c.sum()
    yt, yc = run.orders_obs[t].sum(), run.orders_obs[c].sum()
    rt, rc = yt / nt, yc / nc                       # matched orders per person
    incr_matched = (rt - rc) * nt                    # in the test group
    # variance of per-person order counts (0..WEIGHT)
    vt, vc = run.orders_obs[t].var(ddof=1), run.orders_obs[c].var(ddof=1)
    se = np.sqrt(vt / nt + vc / nc) * nt
    scale = 1 / PIXEL_MATCH                          # matched orders -> all orders
    incr = incr_matched * scale
    attributed = run.attributed[t].sum()             # the platform can only credit matched orders
    return {"n_test": int(nt), "n_holdout": int(nc), "orders_test": int(yt), "orders_holdout": int(yc),
            "lift_rel": float((rt - rc) / rc), "lift_rel_lo": float((rt - rc - Z * se / nt) / rc),
            "lift_rel_hi": float((rt - rc + Z * se / nt) / rc),
            "incr_orders": float(incr), "incr_lo": float(incr - Z * se * scale), "incr_hi": float(incr + Z * se * scale),
            "p": float(2 * (1 - stats.norm.cdf(abs(incr_matched) / se))),
            "iroas_online": float(incr * AOV_ONLINE / spend),
            "iroas_lo": float((incr - Z * se * scale) * AOV_ONLINE / spend),
            "iroas_hi": float((incr + Z * se * scale) * AOV_ONLINE / spend),
            "attributed_orders": float(attributed), "attributed_roas": float(attributed * AOV_ONLINE / spend),
            "attributed_over_incremental": float(attributed / incr) if incr > 0 else None,
            "truth_incr_orders": run.true_incr_expected,
            "truth_iroas_online": run.true_incr_expected * AOV_ONLINE / spend}


def main(mc: int):
    eff = json.loads((ROOT / "data" / "truth" / "effects.json").read_text(encoding="utf-8"))["conversion_lift"]
    media = json.loads((ROOT / "data" / "media_plan.json").read_text(encoding="utf-8"))
    spend_geo = np.array(media["conversion_lift_spend_by_geo"])
    spend = spend_geo.sum()
    w = World()
    people = make_people(w)
    kw = dict(base_orders=eff["base_orders_platform"], incr_orders=eff["incremental_orders"],
              attributed_orders=eff["attributed_orders"])

    # ---------------- design: the advertiser's forecast of orders, no outcomes used
    base_matched = eff["base_orders_platform"] * PIXEL_MATCH        # forecast from last month's pixel orders
    eligible_n = (people.on_platform & (spend_geo[people.geo] > 0)).sum()
    design = []
    for h in [0.05, 0.10, 0.20]:
        nt, nc = eligible_n * (1 - h), eligible_n * h
        p = base_matched / eligible_n / WEIGHT                      # per real person
        se_rel = np.sqrt((1 / (nt * WEIGHT * p)) + (1 / (nc * WEIGHT * p)))
        mde_rel = (Z + Z_POWER) * se_rel
        mde_orders = mde_rel * base_matched * (1 - h) / PIXEL_MATCH
        lost = h * np.array(PLAN_LIFT) * eff["base_orders_platform"] * AOV_ONLINE  # sales given up in the holdout
        design.append({"holdout": h, "mde_rel": float(mde_rel),
                       "min_detectable_iroas_online": float(mde_orders * AOV_ONLINE / (spend * (1 - h))),
                       "online_sales_given_up_m": (lost / 1e6).tolist()})
        print(f"holdout {h:.0%}: detects a {100 * mde_rel:.1f}% lift in online orders = online iROAS "
              f"{design[-1]['min_detectable_iroas_online']:.2f}; online sales given up "
              f"{lost[0] / 1e6:.1f}-{lost[1] / 1e6:.1f}M KRW")

    run = run_conversion_lift(people, spend_geo, HOLDOUT, seed=202, **kw)
    spend_test = spend * (1 - HOLDOUT)
    r = readout(run, spend_test)
    print(f"\nVideo spend in the test group {spend_test / 1e6:,.0f}M KRW (weeks {CONVERSION_LIFT_WEEKS[0]}-{CONVERSION_LIFT_WEEKS[1]})")
    print(f"Orders matched: test {r['orders_test']:,} of {r['n_test']:,} people, holdout {r['orders_holdout']:,} of {r['n_holdout']:,}")
    print(f"Lift {100 * r['lift_rel']:+.1f}% [{100 * r['lift_rel_lo']:+.1f}, {100 * r['lift_rel_hi']:+.1f}], p={r['p']:.4f}")
    print(f"Incremental orders {r['incr_orders']:,.0f} [{r['incr_lo']:,.0f}, {r['incr_hi']:,.0f}] vs truth {r['truth_incr_orders']:,.0f}")
    print(f"Online iROAS {r['iroas_online']:.2f} [{r['iroas_lo']:.2f}, {r['iroas_hi']:.2f}] vs truth {r['truth_iroas_online']:.2f}")
    print(f"Platform-credited orders {r['attributed_orders']:,.0f} -> ROAS {r['attributed_roas']:.2f}: "
          f"{r['attributed_over_incremental']:.1f}x the incremental orders")

    out = {"holdout": HOLDOUT, "spend_test_m": spend_test / 1e6, "aov": AOV_ONLINE, "pixel_match": PIXEL_MATCH,
           "design": design, "readout": r,
           "plan_min": (f"{HOLDOUT:.0%} user holdout in the campaign regions; detects a "
                        f"{100 * design[1]['mde_rel']:.1f}% lift in online orders (online iROAS "
                        f"{design[1]['min_detectable_iroas_online']:.2f}). Needs the brand's purchase events "
                        f"shared through the pixel (about {100 * PIXEL_MATCH:.0f}% of orders match a user)")}
    if mc:
        rows = []
        for k in range(mc):
            rk = run_conversion_lift(people, spend_geo, HOLDOUT, seed=7000 + k, **kw)
            rr = readout(rk, spend_test)
            rows.append((rr["iroas_online"], rr["iroas_lo"], rr["iroas_hi"], rr["truth_iroas_online"],
                         rr["attributed_over_incremental"], rr["p"]))
        a = np.array(rows, dtype=float)
        out["montecarlo"] = {"runs": mc, "bias": float((a[:, 0] - a[:, 3]).mean()),
                             "coverage": float(((a[:, 1] <= a[:, 3]) & (a[:, 3] <= a[:, 2])).mean()),
                             "attributed_over_incremental_mean": float(np.nanmean(a[:, 4])),
                             "significant": float((a[:, 5] < 0.05).mean())}
        m = out["montecarlo"]
        print(f"\nMonte Carlo ({mc}): iROAS bias {m['bias']:+.3f}, coverage {m['coverage']:.0%}, "
              f"significant {m['significant']:.0%}, credited / incremental {m['attributed_over_incremental_mean']:.1f}x")
    (ROOT / "outputs" / "ch2_conversion_lift.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", type=int, default=0)
    main(ap.parse_args().mc)
