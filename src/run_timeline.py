"""Run all 104 weeks as FIZLY actually ran them, plus the counterfactual for
each study. Analysis scripts read data/observed_*; validation reads data/truth/.

    observed_daily.parquet   geo-day: online sales, spend, platform reports, temperature
    weekly_panel.parquet     geo-week: projected store sales (sell-out panel) + the above
    truth/effects.json       true effect behind every chapter
    media_plan.json          spend facts the advertiser knows (budgets, test regions)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from observe import weekly_panel
from users import AOV_ONLINE
from world import (CHANNELS, COMPETITOR_WEEKS, CONVERSION_LIFT_WEEKS, GEO_TEST_WEEKS,
                   LAUNCH_WEEK, TRUE, World, actual_plan, week_mask)

ROOT = Path(__file__).resolve().parents[1]
DATA, TRUTH = ROOT / "data", ROOT / "data" / "truth"
PLATFORM_SHARE_OF_ONLINE = 0.55   # share of FIZLY's online orders placed by platform users
COOLDOWN_WEEKS = 2


def main():
    TRUTH.mkdir(parents=True, exist_ok=True)
    w = World()
    asg = pd.read_csv(DATA / "geo_assignment.csv")
    geos = list(asg.geo)
    dark = np.array([g == "go_dark" for g in asg.group])
    ctrl_idx = np.where(~dark)[0]
    # trap 5: a rival zero-sugar drink launches in two mid-sized control regions
    by_size = ctrl_idx[np.argsort(-w.share[ctrl_idx])]
    rival = [int(by_size[3]), int(by_size[9])]

    plan = actual_plan(w, go_dark=dark, competitor_geos=rival)
    obs, tru = w.simulate(plan)
    obs.to_parquet(DATA / "observed_daily.parquet", index=False)
    panel = weekly_panel(obs)
    panel.to_parquet(DATA / "weekly_panel.parquet", index=False)
    tru.to_parquet(TRUTH / "truth_daily.parquet", index=False)

    def total(df, mask_rows, regions):
        sub = df[mask_rows & df.geo.isin([geos[i] for i in regions])]
        return float(sub.offline_rev.sum()), float(sub.online_rev.sum())

    eff = {"rival_regions": [geos[i] for i in rival]}

    # chapter 3 geo test: same world with video left on in the dark regions
    cf, _ = w.simulate(actual_plan(w, go_dark=dark, competitor_geos=rival, geo_test=False))
    dark_idx = np.where(dark)[0]
    t = (obs.week >= GEO_TEST_WEEKS[0]) & (obs.week <= GEO_TEST_WEEKS[1])
    t_cool = (obs.week >= GEO_TEST_WEEKS[0]) & (obs.week <= GEO_TEST_WEEKS[1] + COOLDOWN_WEEKS)
    t_all = obs.week >= GEO_TEST_WEEKS[0]
    withheld = float(cf[t & cf.geo.isin([geos[i] for i in dark_idx])].spend_short_video.sum())
    geo = {"withheld_video_krw": withheld}
    for name, m in [("test", t), ("test_plus_cooldown", t_cool), ("to_week_104", t_all)]:
        a_off, a_on = total(obs, m, dark_idx)
        c_off, c_on = total(cf, m, dark_idx)
        geo[name] = {"loss_offline": c_off - a_off, "loss_online": c_on - a_on,
                     "iroas_total": (c_off - a_off + c_on - a_on) / withheld,
                     "iroas_online": (c_on - a_on) / withheld, "iroas_offline": (c_off - a_off) / withheld}
    # rival's effect on control-region sales during the test (what contaminates the read)
    no_rival, _ = w.simulate(actual_plan(w, go_dark=dark, competitor_geos=None))
    r_off, r_on = total(obs, t, rival)
    n_off, n_on = total(no_rival, t, rival)
    geo["rival_loss_in_control"] = (n_off + n_on) - (r_off + r_on)
    eff["geo_test"] = geo

    # chapter 2 conversion lift: video off in the control (campaign) regions for the
    # lift weeks shows how many online orders the ads add there in that window
    on_idx = np.where(~dark)[0]
    p_cl = actual_plan(w, go_dark=dark, competitor_geos=rival)
    lw = week_mask(w, *CONVERSION_LIFT_WEEKS)
    p_cl.spend["short_video"][np.ix_(lw, on_idx)] = 0.0
    cf_cl, _ = w.simulate(p_cl)
    l = (obs.week >= CONVERSION_LIFT_WEEKS[0]) & (obs.week <= CONVERSION_LIFT_WEEKS[1])
    a_off, a_on = total(obs, l, on_idx)
    c_off, c_on = total(cf_cl, l, on_idx)
    spend_cl = float(obs[l & obs.geo.isin([geos[i] for i in on_idx])].spend_short_video.sum())
    reported = float(obs[l & obs.geo.isin([geos[i] for i in on_idx])].reported_rev_short_video.sum())
    eff["conversion_lift"] = {
        "regions": [geos[i] for i in on_idx], "video_spend_krw": spend_cl,
        "online_incremental_krw": a_on - c_on, "offline_incremental_krw": a_off - c_off,
        "base_orders_platform": PLATFORM_SHARE_OF_ONLINE * c_on / AOV_ONLINE,
        "incremental_orders": (a_on - c_on) / AOV_ONLINE,
        "attributed_orders": reported / AOV_ONLINE, "reported_rev_krw": reported,
        "iroas_online": (a_on - c_on) / spend_cl, "iroas_total": (a_on - c_on + a_off - c_off) / spend_cl,
        "reported_roas": reported / spend_cl}

    # chapter 4: each channel removed for all weeks (true average return)
    post = obs.week >= LAUNCH_WEEK
    roi = {}
    # both video channels feed one awareness pool, so their single-channel
    # returns do not add up; "video_combined" removes both at once
    groups = {c: [c] for c in CHANNELS} | {"video_combined": ["short_video", "online_video"]}
    for c, members in groups.items():
        o2, _ = w.simulate(actual_plan(w, go_dark=dark, competitor_geos=rival, drop=members))
        roi[c] = {}
        for name, m in [("history", obs.week < LAUNCH_WEEK), ("post_launch", post), ("all", obs.week > 0)]:
            sp = float(sum(obs.loc[m, f"spend_{k}"].sum() for k in members))
            d_off = float(obs.loc[m, "offline_rev"].sum() - o2.loc[m, "offline_rev"].sum())
            d_on = float(obs.loc[m, "online_rev"].sum() - o2.loc[m, "online_rev"].sum())
            rep = float(sum(obs.loc[m, f"reported_rev_{k}"].sum() for k in members))
            roi[c][name] = {"spend": sp, "incr_offline": d_off, "incr_online": d_on,
                            "roi_total": (d_off + d_on) / sp, "roi_online": d_on / sp, "reported_roas": rep / sp}
    eff["channel_roi"] = roi

    # chapter 3 tracker: weekly video spend by region and the awareness the launch earns without ads
    weeks = np.arange(75, 105)
    vid = obs.pivot_table(index="week", columns="geo", values="spend_short_video", aggfunc="sum")[geos]
    a0, a1, tau = TRUE["aw_organic"]
    dsl = (weeks - LAUNCH_WEEK) * 7 + 3
    organic = np.where(dsl >= 0, a0 + a1 * (1 - np.exp(-np.maximum(dsl, 0) / tau)), 0.0)
    media = {"go_dark": [geos[i] for i in dark_idx], "control": [geos[i] for i in on_idx],
             "geo_test_withheld_video_krw": withheld,
             "tracker_weeks": weeks.tolist(), "tracker_video_spend": vid.loc[weeks].to_numpy().tolist(),
             "tracker_organic_awareness": organic.tolist(), "conversion_lift_spend_by_geo":
             obs[l].groupby("geo").spend_short_video.sum().reindex(geos).fillna(0).tolist()}
    (DATA / "media_plan.json").write_text(json.dumps(media), encoding="utf-8")
    (TRUTH / "effects.json").write_text(json.dumps(eff, indent=1), encoding="utf-8")

    g = eff["geo_test"]
    print(f"Geo test truth: withheld {withheld / 1e6:,.0f}M; iROAS in window {g['test']['iroas_total']:.2f} "
          f"(online {g['test']['iroas_online']:.2f}), +cooldown {g['test_plus_cooldown']['iroas_total']:.2f}, "
          f"to week 104 {g['to_week_104']['iroas_total']:.2f}; rival cut control sales by {g['rival_loss_in_control'] / 1e6:,.0f}M")
    c = eff["conversion_lift"]
    print(f"Conversion lift truth: online iROAS {c['iroas_online']:.2f}, total {c['iroas_total']:.2f}, "
          f"reported ROAS {c['reported_roas']:.2f}; incremental orders {c['incremental_orders']:,.0f}, "
          f"attributed {c['attributed_orders']:,.0f}, platform-user base {c['base_orders_platform']:,.0f}")
    for ch, r in roi.items():
        print(f"  {ch:13s} post-launch ROI {r['post_launch']['roi_total']:.2f} (online {r['post_launch']['roi_online']:.2f}) "
              f"reported {r['post_launch']['reported_roas']:.2f} | history ROI {r['history']['roi_total']:.2f}")


if __name__ == "__main__":
    main()
