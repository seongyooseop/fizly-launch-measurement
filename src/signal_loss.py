"""When signals get thin: conversion lift at lower pixel match rates.

Browser and OS privacy changes cut the share of online orders a platform can
match to a user. A conversion lift only counts matched orders, so its
precision falls with the match rate; the platform's own credited orders fall
too. A geo test reads sales by region and needs no user-level signal.

For match rates of 90%, 75% (FIZLY today), 50% and 30%, the same study is
re-run on the same people, holdout and ads (15 runs each):
  - width of the 95% interval on online iROAS, bias, share of runs significant
  - smallest online return the design can detect
and set against the geo test, whose detectable return does not depend on matching.

    python src/signal_loss.py
Writes outputs/signal_loss.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import ch2_conversion_lift as ch2
import users
from users import WEIGHT, make_people, run_conversion_lift
from world import World

ROOT = Path(__file__).resolve().parents[1]
RATES = [0.90, 0.75, 0.50, 0.30]
RUNS = 15
TODAY = 0.75


def main():
    eff = json.loads((ROOT / "data" / "truth" / "effects.json").read_text(encoding="utf-8"))["conversion_lift"]
    media = json.loads((ROOT / "data" / "media_plan.json").read_text(encoding="utf-8"))
    geo = json.loads((ROOT / "outputs" / "ch3_design.json").read_text(encoding="utf-8"))
    geo_min = next(o for o in geo["options"] if abs(o["share"] - geo["chosen_share"]) < 1e-9)["min_detectable_iroas"]
    spend_geo = np.array(media["conversion_lift_spend_by_geo"])
    spend_test = spend_geo.sum() * (1 - ch2.HOLDOUT)
    people = make_people(World())
    eligible_n = (people.on_platform & (spend_geo[people.geo] > 0)).sum()
    rows = []
    for m in RATES:
        users.PIXEL_MATCH = m      # the study and the platform both see only matched orders
        ch2.PIXEL_MATCH = m
        kw = dict(base_orders=eff["base_orders_platform"], incr_orders=eff["incremental_orders"],
                  attributed_orders=eff["attributed_orders"] * m / TODAY)
        est = []
        for k in range(RUNS):
            r = ch2.readout(run_conversion_lift(people, spend_geo, ch2.HOLDOUT, seed=8000 + k, **kw), spend_test)
            est.append((r["iroas_online"], r["iroas_hi"] - r["iroas_lo"], r["p"] < 0.05, r["truth_iroas_online"], r["attributed_roas"]))
        a = np.array(est, dtype=float)
        # design: detectable relative lift from matched orders, as in chapter 2
        matched = eff["base_orders_platform"] * m
        p = matched / eligible_n / WEIGHT
        nt, nc = eligible_n * (1 - ch2.HOLDOUT), eligible_n * ch2.HOLDOUT
        mde_rel = (ch2.Z + ch2.Z_POWER) * np.sqrt(1 / (nt * WEIGHT * p) + 1 / (nc * WEIGHT * p))
        min_iroas = mde_rel * eff["base_orders_platform"] * (1 - ch2.HOLDOUT) * users.AOV_ONLINE / spend_test
        rows.append({"match": m, "ci_width": float(a[:, 1].mean()), "bias": float((a[:, 0] - a[:, 3]).mean()),
                     "significant": float(a[:, 2].mean()), "estimate_sd": float(a[:, 0].std(ddof=1)),
                     "min_detectable_online_iroas": float(min_iroas), "mde_rel": float(mde_rel),
                     "platform_reported_roas": float(a[:, 4].mean()), "truth": float(a[:, 3].mean())})
        print(f"match {m:.0%}: CI width {rows[-1]['ci_width']:.2f}, bias {rows[-1]['bias']:+.3f}, significant "
              f"{rows[-1]['significant']:.0%}, detectable online iROAS {min_iroas:.2f}, platform-reported {rows[-1]['platform_reported_roas']:.2f}")
    users.PIXEL_MATCH = ch2.PIXEL_MATCH = TODAY
    out = {"rows": rows, "runs": RUNS, "today": TODAY, "geo_min_detectable_total_iroas": geo_min,
           "true_online_iroas": rows[0]["truth"],
           "notes": ["The study stays unbiased as matching falls: the holdout loses the same share of orders as the test group. It gets noisier.",
                     "The platform's credited ROAS falls with matching, because it can only credit orders it sees: a drop in reported ROAS after a privacy change is partly a measurement change, not a performance change.",
                     f"A geo test reads regional sales and needs no user match; its detectable total return ({geo_min:.2f}) is the same at any match rate."]}
    (ROOT / "outputs" / "signal_loss.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
