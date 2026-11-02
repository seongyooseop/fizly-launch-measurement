"""Chapter 4a: a weekly marketing mix model, before and after calibration.

National weekly sales (store panel + online) on media, temperature and
distribution (share of stores stocking Zero, which the advertiser knows).

Two choices come from the launch itself:
  * video before and after launch are separate terms: before week 79 video
    advertised the Original line, after it the new Zero line. One ROI for both
    would average two different campaigns.
  * distribution is a control. The launch flight starts the week Zero reaches
    shelves; without it, the model would credit shelf build-up to video.

Two fits:
  uncalibrated  - sales likelihood only
  calibrated    - plus the geo test: the model's predicted sales loss in the
                  test and cooldown weeks, had video stayed on in the go-dark
                  regions, must match what chapter 3 measured (within its CI)
Writes outputs/ch4_mmm.json; fits cached in models/ (--refit to redo).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd
import pymc as pm
import pytensor.tensor as pt

from world import GEO_TEST_WEEKS, LAUNCH_WEEK, TRUE

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ["video_original", "video_zero", "online_video", "social", "search", "retail_media"]
LAGS = 12
COOLDOWN = 2
MODELS = {"uncalibrated": (False, 31), "calibrated": (True, 32)}


def weekly() -> pd.DataFrame:
    p = pd.read_parquet(ROOT / "data" / "weekly_panel.parquet")
    g = p.groupby("week").agg(sales=("store_sales", "sum"), online=("online_rev", "sum"),
                              temp=("temperature", "mean"),
                              **{c: (f"spend_{c}", "sum") for c in
                                 ["short_video", "online_video", "social", "search", "retail_media"]}).reset_index()
    g["sales"] = (g.sales + g.online) / 1e6
    for c in ["short_video", "online_video", "social", "search", "retail_media"]:
        g[c] = g[c] / 1e6
    post = g.week >= LAUNCH_WEEK
    g["video_original"] = np.where(post, 0.0, g.short_video)
    g["video_zero"] = np.where(post, g.short_video, 0.0)
    dsl = (g.week - LAUNCH_WEEK) * 7 + 3
    g["distribution"] = np.where(dsl >= 0, 1 - np.exp(-np.maximum(dsl, 0) / TRUE["distribution"]), 0.0)
    # a new line also grows on its own once stocked (repeat buyers, word of mouth):
    # a simple linear maturity term on top of distribution, capped at half a year
    g["maturity"] = g.distribution * np.clip((g.week - LAUNCH_WEEK) / 26, 0, 1)
    return g


def lag_matrix(x, lags=LAGS):
    T = len(x)
    out = np.zeros((T, lags + 1))
    for l in range(lags + 1):
        out[l:, l] = x[: T - l]
    return out


def fit(df, calibrate, target, seed):
    y = df.sales.to_numpy()
    spend = {c: df[c].to_numpy() for c in MEDIA}
    med = {c: np.median(spend[c][spend[c] > 0]) for c in MEDIA}
    L = {c: lag_matrix(spend[c]) for c in MEDIA}
    t = np.arange(len(df)) / 52.0
    temp = (df.temp.to_numpy() - 15) / 10
    dist = df.distribution.to_numpy()
    mat = df.maturity.to_numpy()
    with pm.Model(coords={"media": MEDIA}):
        roi = pm.LogNormal("roi", 0.0, 0.7, dims="media")
        lam = pm.Beta("lam", 2.0, 2.0, dims="media")
        kappa = pm.LogNormal("kappa", 0.0, 0.5, dims="media")
        c0 = pm.Normal("c0", y[:52].mean(), 100.0)
        c_temp = pm.Normal("c_temp", 0.0, 100.0)
        c_dist = pm.Normal("c_dist", 0.0, 150.0)
        c_mat = pm.Normal("c_mat", 0.0, 150.0)
        c_t = pm.Normal("c_t", 0.0, 50.0)
        sigma = pm.HalfNormal("sigma", 30.0)
        lags = np.arange(LAGS + 1)
        contrib, betas, Ks, ws = [], [], [], []
        for j, c in enumerate(MEDIA):
            w = (1 - lam[j]) * lam[j] ** lags
            w = w / w.sum()
            a = pt.dot(L[c], w)
            K = kappa[j] * med[c]
            h = a / (a + K)
            beta = roi[j] * spend[c].sum() / pt.maximum(h.sum(), 1e-6)
            contrib.append(beta * h); betas.append(beta); Ks.append(K); ws.append(w)
        pm.Deterministic("beta", pt.stack(betas), dims="media")
        pm.Deterministic("K", pt.stack(Ks), dims="media")
        pm.Deterministic("lam_w", lam, dims="media")
        mu = c0 + c_temp * temp + c_dist * dist + c_mat * mat + c_t * t + pt.stack(contrib, axis=1).sum(axis=1)
        pm.Deterministic("mu", mu)
        pm.Normal("y", mu, sigma, observed=y)
        # the geo test, as the model sees it. Video went to zero in the go-dark
        # regions (share s of the market); everywhere else it ran as planned.
        # A national model must score that as "share s of the market falls from
        # the planned level to zero", not as "the whole market gets the withheld
        # money on top": on a saturating curve the first is much larger.
        j = MEDIA.index("video_zero")
        tw = ((df.week >= GEO_TEST_WEEKS[0]) & (df.week <= GEO_TEST_WEEKS[1])).to_numpy()
        x_obs = spend["video_zero"]
        x_cf = x_obs.copy()
        x_cf[tw] += target["withheld"] / tw.sum()              # national spend had nobody gone dark
        s = target["withheld"] / x_cf[tw].sum()                 # go-dark share of the market
        x_dark = x_cf.copy()
        x_dark[tw] = 0.0                                        # the go-dark regions' own path
        def h_of(x):
            a = pt.dot(lag_matrix(x), ws[j])
            return a / (a + Ks[j])
        read = ((df.week >= GEO_TEST_WEEKS[0]) & (df.week <= GEO_TEST_WEEKS[1] + COOLDOWN)).to_numpy()
        lift = (s * betas[j] * (h_of(x_cf) - h_of(x_dark)))[read].sum()
        pm.Deterministic("lift_geo", lift)
        if calibrate:
            pm.Normal("cal_geo", lift, target["se"], observed=target["lift"])
        idata = pm.sample(1000, tune=1500, chains=4, target_accept=0.95, random_seed=seed, progressbar=False)
    return idata


def summarize(idata):
    post = idata.posterior.to_dataset().stack(s=("chain", "draw"))
    s = az.summary(idata, var_names=["roi", "lam", "kappa", "sigma"])
    return {"roi": post["roi"].values.T, "lam": post["lam_w"].values.T, "K": post["K"].values.T,
            "beta": post["beta"].values.T, "mu": post["mu"].values.T, "lift_geo": post["lift_geo"].values,
            "max_rhat": np.array(float(s["r_hat"].max())),
            "divergences": np.array(int(idata.sample_stats["diverging"].values.sum()))}


def contributions(spend, d):
    """(S, T, M) weekly contribution per draw for a spend path."""
    S = d["beta"].shape[0]
    T = len(spend[MEDIA[0]])
    out = np.empty((S, T, len(MEDIA)))
    lags = np.arange(LAGS + 1)
    for j, c in enumerate(MEDIA):
        lam = d["lam"][:, j]
        w = (1 - lam[:, None]) * lam[:, None] ** lags[None, :]
        w = w / w.sum(1, keepdims=True)
        a = w @ lag_matrix(spend[c]).T
        out[:, :, j] = d["beta"][:, j][:, None] * a / (a + d["K"][:, j][:, None])
    return out


def main():
    df = weekly()
    geo = json.loads((ROOT / "outputs" / "ch3_offline.json").read_text(encoding="utf-8"))
    r = geo["readout"]["with_cooldown"]["total"]
    withheld = geo["withheld_m"]
    target = {"withheld": withheld, "lift": r["iroas"] * withheld,
              "se": (r["iroas_ci"][1] - r["iroas_ci"][0]) / (2 * 1.96) * withheld}
    eff = json.loads((ROOT / "data" / "truth" / "effects.json").read_text(encoding="utf-8"))
    refit = "--refit" in sys.argv
    out = {"media": MEDIA, "calibration_target_m": target, "models": {}}
    truth_roi = {"video_original": eff["channel_roi"]["short_video"]["history"]["roi_total"],
                 "video_zero": eff["channel_roi"]["short_video"]["post_launch"]["roi_total"]}
    for c in ["online_video", "social", "search", "retail_media"]:
        truth_roi[c] = eff["channel_roi"][c]["all"]["roi_total"]
    out["truth_roi"] = truth_roi
    spend = {c: df[c].to_numpy() for c in MEDIA}
    for name, (cal, seed) in MODELS.items():
        path = ROOT / "models" / f"ch4_{name}.npz"
        if path.exists() and not refit:
            d = dict(np.load(path))
        else:
            path.parent.mkdir(exist_ok=True)
            d = summarize(fit(df, cal, target, seed))
            np.savez_compressed(path, **d)
        contrib = contributions(spend, d)                      # (S, T, M)
        post = (df.week >= LAUNCH_WEEK).to_numpy()
        roi = {}
        for j, c in enumerate(MEDIA):
            q = np.quantile(d["roi"][:, j], [0.05, 0.5, 0.95])
            roi[c] = {"median": float(q[1]), "ci90": [float(q[0]), float(q[2])], "truth": truth_roi[c],
                      "truth_inside": bool(q[0] <= truth_roi[c] <= q[2])}
        incr_post = {c: np.median(contrib[:, post, j].sum(1)) for j, c in enumerate(MEDIA)}
        # both video channels build the same awareness: the model can size them
        # together far better than it can split them
        jv, jo = MEDIA.index("video_zero"), MEDIA.index("online_video")
        both = contrib[:, post, jv].sum(1) + contrib[:, post, jo].sum(1)
        sp_both = spend["video_zero"][post].sum() + spend["online_video"][post].sum()
        qb = np.quantile(both / sp_both, [0.05, 0.5, 0.95])
        tb = eff["channel_roi"]["video_combined"]["post_launch"]["roi_total"]
        roi["video_combined"] = {"median": float(qb[1]), "ci90": [float(qb[0]), float(qb[2])], "truth": tb,
                                 "truth_inside": bool(qb[0] <= tb <= qb[2])}
        lg = np.quantile(d["lift_geo"], [0.05, 0.5, 0.95])
        y = df.sales.to_numpy()
        out["models"][name] = {"roi": roi, "max_rhat": float(d["max_rhat"]), "divergences": int(d["divergences"]),
                               "fit_mape_pct": float(100 * np.mean(np.abs(y - d["mu"].mean(0)) / y)),
                               "geo_lift_model_m": [float(v) for v in lg],
                               "incremental_post_launch_m": {c: float(v) for c, v in incr_post.items()}}
        print(f"\n{name}: R-hat {float(d['max_rhat']):.3f}, divergences {int(d['divergences'])}, "
              f"fit MAPE {out['models'][name]['fit_mape_pct']:.1f}%; geo-test loss the model predicts "
              f"{lg[1]:.0f}M [{lg[0]:.0f}, {lg[2]:.0f}] vs measured {target['lift']:.0f}M")
        for c, v in roi.items():
            print(f"  {c:15s} ROI {v['median']:.2f} [{v['ci90'][0]:.2f}, {v['ci90'][1]:.2f}] truth {v['truth']:.2f}"
                  f"{'' if v['truth_inside'] else '  <- outside'}")
    (ROOT / "outputs" / "ch4_mmm.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
