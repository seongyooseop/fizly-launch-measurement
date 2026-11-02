"""Chapter 3 design: can a geo test read video's effect on total sales?

A conversion lift study only sees online orders, three quarters of FIZLY's
sales happen in stores. The only way to see store sales move is to switch
video off in some regions and compare with the rest, read from the weekly
sell-out panel plus online sales. Uses only the 78 weeks before launch.

  1. regions ranked by sales in blocks of 10; within each block a share goes dark
  2. A/A tests on past 6-week windows: how often does TBR cry wolf? -> SE factor
     (learned on the earlier half of windows, checked on the later half)
  3. power by injecting a known loss into the go-dark group -> smallest
     detectable drop, then the smallest detectable return on the video budget
  4. two shares compared (30% vs 50% of regions dark): precision vs sales at risk
     in the launch weeks
Writes outputs/ch3_design.json and data/geo_assignment.csv
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from geo_tbr import Z95, calibration_factor, tbr
from observe import weekly_panel, wide
from world import FLIGHT_VIDEO_M, GEO_TEST_WEEKS, HISTORY_WEEKS, World, actual_plan

ROOT = Path(__file__).resolve().parents[1]
PRE_WEEKS = 26
TEST_WEEKS = GEO_TEST_WEEKS[1] - GEO_TEST_WEEKS[0] + 1
DELTAS = np.round(np.arange(0.0, 0.1001, 0.0025), 4)
N_ASSIGN = 40
PLANNED_VIDEO_M = FLIGHT_VIDEO_M   # launch flight, M KRW/day nationally
LAUNCH_UPLIFT = 1.35           # plan: Zero adds ~35% to weekly sales in its first months
PRIOR_IROAS = (0.5, 2.0)
SHARES = [0.3, 0.5]
CHOSEN = 0.3
ASSIGN_SEED = 83


def assign_share(order, share, rng):
    blocks = order.reshape(-1, 10)
    k = int(round(10 * share))
    treat = np.concatenate([rng.choice(b, k, replace=False) for b in blocks])
    return np.sort(treat), np.setdiff1d(order, treat)


def power(Y, order, share, rng):
    n = Y.shape[0]
    starts = range(PRE_WEEKS, n - TEST_WEEKS + 1)
    rows = []
    for s in starts:
        pre, test = slice(s - PRE_WEEKS, s), slice(s, s + TEST_WEEKS)
        for _ in range(N_ASSIGN):
            t, c = assign_share(order, share, rng)
            r = tbr(Y[:, t].sum(1), Y[:, c].sum(1), pre, test)
            rows.append((s, r["effect"], r["se_raw"], r["actual"]))
    s_, e, se_raw, tot = map(np.array, zip(*rows))
    z = e / se_raw
    early = s_ < np.median(s_)
    k_early = calibration_factor(z[early])
    k = calibration_factor(z)
    shifted = e[:, None] - DELTAS[None, :] * tot[:, None]
    detected = (shifted + Z95 * se_raw[:, None] * k) < 0
    pw = detected.mean(0)
    idx = np.where(pw >= 0.8)[0]
    return {"aa_false_positive_uncalibrated": float(np.mean(np.abs(z) > Z95)),
            "aa_mean_z": float(z.mean()), "se_scale": k,
            "aa_false_positive_holdout": float(np.mean(np.abs(z[~early]) > Z95 * k_early)),
            "mde_share": float(DELTAS[idx[0]]) if len(idx) else None,
            "power": pw.round(3).tolist(), "n_sims": len(e)}


def main():
    w = World()
    obs, _ = w.simulate(actual_plan(w))         # history only is used below
    hist = weekly_panel(obs[obs.week <= HISTORY_WEEKS])
    hist["sales"] = hist.store_sales + hist.online_rev
    Y, geos = wide(hist, "sales")
    V, _ = wide(hist, "spend_short_video")
    order = np.argsort(-Y[-52:].sum(0))

    res = {}
    for share in SHARES:
        p = power(Y, order, share, np.random.default_rng(2026))
        rng = np.random.default_rng(ASSIGN_SEED)
        treat, ctrl = assign_share(order, share, rng)
        sales_share = float(Y[-26:, treat].sum() / Y[-26:].sum())
        weekly_dark = Y[-12:, treat].sum(1).mean() * LAUNCH_UPLIFT
        test_rev = weekly_dark * TEST_WEEKS
        withheld = PLANNED_VIDEO_M * 1e6 * sales_share * TEST_WEEKS * 7
        mde_krw = p["mde_share"] * test_rev
        res[share] = {**p, "treat": treat, "ctrl": ctrl, "sales_share": sales_share,
                      "test_revenue_forecast_m": test_rev / 1e6, "video_withheld_m": withheld / 1e6,
                      "mde_krw_m": mde_krw / 1e6, "min_detectable_iroas": mde_krw / withheld,
                      "sales_at_risk_m": [r * withheld / 1e6 for r in PRIOR_IROAS]}
        print(f"go-dark {share:.0%}: A/A false alarms {p['aa_false_positive_uncalibrated']:.1%} raw -> "
              f"SE x{p['se_scale']:.2f} (held-out {p['aa_false_positive_holdout']:.1%}); "
              f"MDE {100 * p['mde_share']:.1f}% = {mde_krw / 1e6:,.0f}M KRW; "
              f"min detectable iROAS {mde_krw / withheld:.2f}; video withheld {withheld / 1e6:,.0f}M; "
              f"sales at risk {PRIOR_IROAS[0] * withheld / 1e6:,.0f}-{PRIOR_IROAS[1] * withheld / 1e6:,.0f}M")

    ch = res[CHOSEN]
    treat, ctrl = ch["treat"], ch["ctrl"]
    pre = slice(len(Y) - PRE_WEEKS, len(Y))
    yt, yc = Y[pre, treat].sum(1), Y[pre, ctrl].sum(1)
    ratio = yt.sum() / yc.sum()
    prefit = {"ratio": float(ratio), "mape": float(np.mean(np.abs(yt - ratio * yc) / yt)),
              "corr": float(np.corrcoef(yt, yc)[0, 1])}
    print(f"chosen: {len(treat)} go-dark regions, {100 * ch['sales_share']:.0f}% of sales; "
          f"pre-period MAPE {100 * prefit['mape']:.2f}%, corr {prefit['corr']:.3f}")

    pd.DataFrame({"geo": geos, "group": ["go_dark" if i in treat else "control" for i in range(len(geos))]}) \
        .to_csv(ROOT / "data" / "geo_assignment.csv", index=False)
    plan_min = (f"{len(treat)} of 40 regions dark ({100 * ch['sales_share']:.0f}% of sales) for {TEST_WEEKS} weeks; "
                f"detects a {100 * ch['mde_share']:.1f}% drop in their sales, i.e. any total iROAS of "
                f"{ch['min_detectable_iroas']:.2f} or more. Half the regions would detect "
                f"{res[0.5]['min_detectable_iroas']:.2f} but put {res[0.5]['sales_at_risk_m'][1]:,.0f}M KRW of launch "
                f"sales at risk (vs {ch['sales_at_risk_m'][1]:,.0f}M)")
    out = {"pre_weeks": PRE_WEEKS, "test_weeks": list(GEO_TEST_WEEKS), "chosen_share": CHOSEN,
           "planned_video_m_per_day": PLANNED_VIDEO_M, "launch_uplift": LAUNCH_UPLIFT, "prior_iroas": PRIOR_IROAS,
           "options": [{k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in r.items()
                        if k not in ("treat", "ctrl", "power")} | {"share": s} for s, r in res.items()],
           "deltas": DELTAS.tolist(), "power_curve": ch["power"],
           "go_dark": [geos[i] for i in treat], "control": [geos[i] for i in ctrl],
           "prefit": prefit, "plan_min": plan_min}
    (ROOT / "outputs").mkdir(exist_ok=True)
    (ROOT / "outputs" / "ch3_design.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
