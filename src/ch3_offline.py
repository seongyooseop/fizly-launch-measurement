"""Chapter 3: the sales a conversion lift cannot see, and awareness in the whole market.

Part A, geo test (weeks 83-88). Video was off in 12 regions. Total sales =
projected store sales from the weekly sell-out panel + online sales.
  1. region diagnostic: does any control region break from the others during
     the test? (flagged regions are checked with the advertiser, then dropped)
  2. TBR readout for the test weeks, total / stores / online
  3. a second read two weeks after video came back (awareness carries over)
  4. 40 re-runs of the world on fresh noise: bias and coverage, with and
     without the flagged regions
Part B, brand tracker. An independent vendor's monthly panel of adults 18-44.

    python src/ch3_offline.py [--mc 40]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from geo_tbr import Z95, tbr
from observe import weekly_panel, wide
from users import make_people, tracker_waves
from world import GEO_TEST_WEEKS, World, actual_plan

ROOT = Path(__file__).resolve().parents[1]
PRE_WEEKS = 26
COOLDOWN = 2
FLAG_Z = 3.0
WAVES = [75, 79, 83, 87, 91, 95, 99, 103]
TRACKER_N = 1000


def inflight_scale(panel, ctrl_geos, n_dark, last_week, draws=200, seed=5):
    """A/A tests inside the test window: split the control regions into fake
    go-dark and control groups (nobody went dark among them) and see how wide
    TBR's errors really are in launch weeks. Pre-launch A/A tests cannot see
    launch-period noise."""
    rng = np.random.default_rng(seed)
    p = panel.copy()
    p["y"] = p.store_sales + p.online_rev
    Y, geos = wide(p, "y")
    weeks = np.sort(p.week.unique())
    i0 = int(np.where(weeks == GEO_TEST_WEEKS[0])[0][0])
    i1 = int(np.where(weeks == last_week)[0][0]) + 1
    c = np.array([geos.index(g) for g in ctrl_geos])
    k = max(2, int(round(n_dark / (n_dark + len(c)) * len(c))))
    z = []
    for _ in range(draws):
        t = rng.choice(c, k, replace=False)
        r = tbr(Y[:, t].sum(1), Y[:, np.setdiff1d(c, t)].sum(1), slice(i0 - PRE_WEEKS, i0), slice(i0, i1))
        z.append(r["effect"] / r["se_raw"])
    return float(np.quantile(np.abs(z), 0.95) / Z95)


def read(panel, dark_geos, ctrl_geos, se_scale, withheld, last_week):
    out = {}
    first = GEO_TEST_WEEKS[0]
    # use the wider of the pre-launch A/A factor and the in-flight one
    se_scale = max(se_scale, inflight_scale(panel, ctrl_geos, len(dark_geos), last_week))
    for name, col in [("total", None), ("stores", "store_sales"), ("online", "online_rev")]:
        p = panel.copy()
        p["y"] = p.store_sales + p.online_rev if col is None else p[col]
        Y, geos = wide(p, "y")
        weeks = np.sort(p.week.unique())
        t = [geos.index(g) for g in dark_geos]
        c = [geos.index(g) for g in ctrl_geos]
        i0 = int(np.where(weeks == first)[0][0])
        i1 = int(np.where(weeks == last_week)[0][0]) + 1
        r = tbr(Y[:, t].sum(1), Y[:, c].sum(1), slice(i0 - PRE_WEEKS, i0), slice(i0, i1), se_scale)
        yt_all, yc_all = Y[:, t].sum(1), Y[:, c].sum(1)
        series = {"week": weeks[i0 - PRE_WEEKS:i1].tolist(), "actual": (yt_all[i0 - PRE_WEEKS:i1] / 1e6).tolist(),
                  "predicted": (r["ratio"] * yc_all[i0 - PRE_WEEKS:i1] / 1e6).tolist()}
        out[name] = {"effect": r["effect"], "ci": [r["ci_low"], r["ci_high"]], "series": series,
                     "iroas": -r["effect"] / withheld, "iroas_ci": [-r["ci_high"] / withheld, -r["ci_low"] / withheld],
                     "pct_of_sales": -r["effect"] / r["counterfactual"], "pre_mape": r["pre_mape"],
                     "se_scale": se_scale,
                     "p": float(2 * (1 - stats.norm.cdf(abs(r["effect"]) / r["se"])))}
    return out


def diagnose(panel, ctrl_geos):
    """Each control region's test-weeks sales relative to its own pre-period
    share of the other controls; robust z across control regions."""
    p = panel.copy()
    p["y"] = p.store_sales + p.online_rev
    Y, geos = wide(p, "y")
    weeks = np.sort(p.week.unique())
    i0 = int(np.where(weeks == GEO_TEST_WEEKS[0])[0][0])
    i1 = int(np.where(weeks == GEO_TEST_WEEKS[1])[0][0]) + 1
    c = [geos.index(g) for g in ctrl_geos]
    dev = []
    for j in c:
        others = [k for k in c if k != j]
        share_pre = Y[i0 - PRE_WEEKS:i0, j].sum() / Y[i0 - PRE_WEEKS:i0, others].sum()
        share_test = Y[i0:i1, j].sum() / Y[i0:i1, others].sum()
        dev.append(share_test / share_pre - 1)
    dev = np.array(dev)
    med = np.median(dev)
    mad = 1.4826 * np.median(np.abs(dev - med))
    z = (dev - med) / mad
    return [{"geo": geos[j], "deviation": float(d), "robust_z": float(zz)} for j, d, zz in zip(c, dev, z)]


def one_world(noise_seed, dark, rival_idx, design, withheld):
    w = World(noise_seed=noise_seed)
    obs, _ = w.simulate(actual_plan(w, go_dark=dark, competitor_geos=rival_idx))
    cf, _ = w.simulate(actual_plan(w, go_dark=dark, competitor_geos=rival_idx, geo_test=False))
    geos = w.geo_ids
    dark_geos = [g for g, d in zip(geos, dark) if d]
    ctrl_geos = [g for g, d in zip(geos, dark) if not d]
    m = obs.week.between(*GEO_TEST_WEEKS) & obs.geo.isin(dark_geos)
    truth = ((cf[m].offline_rev + cf[m].online_rev).sum() - (obs[m].offline_rev + obs[m].online_rev).sum()) / withheld
    panel = weekly_panel(obs)
    diag = diagnose(panel, ctrl_geos)
    flagged = [d["geo"] for d in diag if abs(d["robust_z"]) > FLAG_Z]
    all_r = read(panel, dark_geos, ctrl_geos, design["se_scale"], withheld, GEO_TEST_WEEKS[1])["total"]
    kept = [g for g in ctrl_geos if g not in flagged]
    drop_r = read(panel, dark_geos, kept, design["se_scale"], withheld, GEO_TEST_WEEKS[1])["total"]
    rival_geos = [geos[i] for i in rival_idx]
    return {"truth": truth, "all": all_r, "dropped": drop_r, "flagged": flagged,
            "hit": all(g in flagged for g in rival_geos), "false_flags": len([g for g in flagged if g not in rival_geos])}


def main(mc: int):
    media = json.loads((ROOT / "data" / "media_plan.json").read_text(encoding="utf-8"))
    eff = json.loads((ROOT / "data" / "truth" / "effects.json").read_text(encoding="utf-8"))
    design_all = json.loads((ROOT / "outputs" / "ch3_design.json").read_text(encoding="utf-8"))
    design = next(o for o in design_all["options"] if abs(o["share"] - design_all["chosen_share"]) < 1e-9)
    panel = pd.read_parquet(ROOT / "data" / "weekly_panel.parquet")
    dark_geos, ctrl_geos = media["go_dark"], media["control"]
    withheld = media["geo_test_withheld_video_krw"]
    truth = eff["geo_test"]

    # ---------------- A1 diagnostic
    diag = diagnose(panel, ctrl_geos)
    flagged = [d["geo"] for d in diag if abs(d["robust_z"]) > FLAG_Z]
    print("Control regions far from the others in the test weeks (robust z):")
    for d in sorted(diag, key=lambda d: d["robust_z"])[:4]:
        print(f"  {d['geo']}: {100 * d['deviation']:+.1f}% vs own pre-period share, z={d['robust_z']:+.1f}")
    print(f"Flagged: {flagged} (advertiser confirms a rival launch there: {eff['rival_regions']})")
    kept = [g for g in ctrl_geos if g not in flagged]

    # ---------------- A2/A3 readouts
    se = design["se_scale"]
    res = {"all_controls": read(panel, dark_geos, ctrl_geos, se, withheld, GEO_TEST_WEEKS[1]),
           "flagged_dropped": read(panel, dark_geos, kept, se, withheld, GEO_TEST_WEEKS[1]),
           "with_cooldown": read(panel, dark_geos, kept, se, withheld, GEO_TEST_WEEKS[1] + COOLDOWN)}
    print(f"\nVideo withheld in go-dark regions: {withheld / 1e6:,.0f}M KRW")
    for k, r in res.items():
        tr = truth["test_plus_cooldown" if k == "with_cooldown" else "test"]
        print(f"  {k:16s} total iROAS {r['total']['iroas']:.2f} [{r['total']['iroas_ci'][0]:.2f}, {r['total']['iroas_ci'][1]:.2f}] "
              f"(truth {tr['iroas_total']:.2f}) | stores {r['stores']['iroas']:.2f} (truth {tr['iroas_offline']:.2f}) "
              f"| online {r['online']['iroas']:.2f} (truth {tr['iroas_online']:.2f}) | drop {100 * r['total']['pct_of_sales']:.1f}% of sales")
    print(f"  truth to week 104 (awareness keeps selling after the test): {truth['to_week_104']['iroas_total']:.2f}")

    out = {"withheld_m": withheld / 1e6, "diagnostic": diag, "flagged": flagged, "readout": res,
           "truth": truth, "plan_min": design_all["plan_min"]}

    # ---------------- A4 Monte Carlo on fresh noise
    if mc:
        geos = World().geo_ids
        dark = np.array([g in dark_geos for g in geos])
        rival_idx = [geos.index(g) for g in eff["rival_regions"]]
        runs = [one_world(90_000 + k, dark, rival_idx, design, withheld) for k in range(mc)]
        def summ(key):
            e = np.array([r[key]["iroas"] for r in runs]); tr = np.array([r["truth"] for r in runs])
            lo = np.array([r[key]["iroas_ci"][0] for r in runs]); hi = np.array([r[key]["iroas_ci"][1] for r in runs])
            return {"bias": float((e - tr).mean()), "coverage": float(((lo <= tr) & (tr <= hi)).mean()),
                    "rmse": float(np.sqrt(((e - tr) ** 2).mean()))}
        out["montecarlo"] = {"runs": mc, "all_controls": summ("all"), "flagged_dropped": summ("dropped"),
                             "rival_caught": float(np.mean([r["hit"] for r in runs])),
                             "runs_with_false_flag": float(np.mean([r["false_flags"] > 0 for r in runs]))}
        m = out["montecarlo"]
        print(f"\nMonte Carlo ({mc}): all controls bias {m['all_controls']['bias']:+.2f}, coverage {m['all_controls']['coverage']:.0%}; "
              f"flagged dropped bias {m['flagged_dropped']['bias']:+.2f}, coverage {m['flagged_dropped']['coverage']:.0%}; "
              f"rival caught {m['rival_caught']:.0%}, runs with a false flag {m['runs_with_false_flag']:.0%}")

    # ---------------- B brand tracker
    w = World()
    people = make_people(w)
    waves = tracker_waves(people, np.array(media["tracker_video_spend"]), np.array(media["tracker_weeks"]),
                          np.array(media["tracker_organic_awareness"]), WAVES, TRACKER_N)
    print("\nBrand tracker (aided awareness of FIZLY Zero, adults 18-44):")
    for v in waves:
        print(f"  week {v['week']:3d}: {100 * v['estimate']:4.1f}% [{100 * v['lo']:4.1f}, {100 * v['hi']:4.1f}] | "
              f"truth population {100 * v['truth_population']:4.1f}% (without ads {100 * v['truth_without_ads']:4.1f}%), "
              f"panel frame {100 * v['truth_panel_frame']:4.1f}%, platform users {100 * v['truth_platform_users']:4.1f}%")
    p = 0.3
    wave_mde = (Z95 + stats.norm.ppf(0.8)) * np.sqrt(2 * p * (1 - p) / TRACKER_N)
    out["tracker"] = waves
    out["tracker_min"] = (f"{TRACKER_N:,} adults per monthly wave; margin of error about "
                          f"+-{100 * Z95 * np.sqrt(p * (1 - p) / TRACKER_N):.1f}pp; a change between two waves must "
                          f"exceed {100 * wave_mde:.1f}pp to be read. No holdout: it shows the level, not what caused it")
    (ROOT / "outputs" / "ch3_offline.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", type=int, default=0)
    main(ap.parse_args().mc)
