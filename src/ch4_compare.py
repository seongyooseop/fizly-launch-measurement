"""Chapter 4b: one question, several instruments. Which number for which decision?

  1. Video's return, as five instruments see it: platform report, conversion
     lift, geo test (test weeks), geo test with cooldown, calibrated MMM.
     Each answers a narrower or wider question; the gaps between them are
     explained, not averaged away.
  2. Awareness: the platform's brand lift (people reached) against the
     vendor's tracker (whole market), bridged by reach and audience share.
  3. Every channel: what the platform reports against what the calibrated
     model says it added.
  4. The decision table.
Reads outputs/ch1-ch4 and the truth (for grading only).
"""
from __future__ import annotations

import json
from pathlib import Path

from users import N_OFFPLATFORM, N_PLATFORM

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"


def wave_mde(n, p=0.3):
    """Smallest change between two tracker waves of n people (80% power, 5% two-sided), in pp."""
    return 100 * (1.959964 + 0.841621) * (2 * p * (1 - p) / n) ** 0.5


def j(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main():
    bl, cl, geo, mmm = j("ch1_brand_lift.json"), j("ch2_conversion_lift.json"), j("ch3_offline.json"), j("ch4_mmm.json")
    eff = json.loads((ROOT / "data" / "truth" / "effects.json").read_text(encoding="utf-8"))
    c, g = cl["readout"], geo["readout"]
    cal = mmm["models"]["calibrated"]["roi"]["video_zero"]
    unc = mmm["models"]["uncalibrated"]["roi"]["video_zero"]
    both = mmm["models"]["calibrated"]["roi"]["video_combined"]
    both_unc = mmm["models"]["uncalibrated"]["roi"]["video_combined"]
    tg = eff["geo_test"]

    video = [
        {"instrument": "Platform report (pixel, 7-day click / 1-day view)", "counts": "Online orders by people who clicked or saw an ad",
         "window": "weeks 83-88", "value": c["attributed_roas"], "ci": None, "truth": c["truth_iroas_online"],
         "truth_label": "true online return", "use": "Daily bidding and creative rotation, after a correction"},
        {"instrument": "Conversion lift (user holdout)", "counts": "Extra online orders vs people who never saw an ad",
         "window": "weeks 83-88", "value": c["iroas_online"], "ci": [c["iroas_lo"], c["iroas_hi"]],
         "truth": c["truth_iroas_online"], "truth_label": "true online return", "use": "Online bidding targets; the correction for the platform report"},
        {"instrument": "Geo test, online part", "counts": "Online sales lost in regions where video went dark",
         "window": "weeks 83-88", "value": g["flagged_dropped"]["online"]["iroas"], "ci": g["flagged_dropped"]["online"]["iroas_ci"],
         "truth": tg["test"]["iroas_online"], "truth_label": "true online return", "use": "Cross-check on conversion lift (an independent method)"},
        {"instrument": "Geo test, stores + online", "counts": "All sales lost in the go-dark regions",
         "window": "weeks 83-88", "value": g["flagged_dropped"]["total"]["iroas"], "ci": g["flagged_dropped"]["total"]["iroas_ci"],
         "truth": tg["test"]["iroas_total"], "truth_label": "true total return in the window", "use": "Short-term payback including stores"},
        {"instrument": "Geo test with 2-week cooldown", "counts": "As above, read two weeks after video came back",
         "window": "weeks 83-90", "value": g["with_cooldown"]["total"]["iroas"], "ci": g["with_cooldown"]["total"]["iroas_ci"],
         "truth": tg["test_plus_cooldown"]["iroas_total"], "truth_label": "true return incl. cooldown", "use": "Calibration target for the MMM"},
        {"instrument": "MMM calibrated to the geo test", "counts": "Average return of launch short video, carry-over included",
         "window": "weeks 79-104", "value": cal["median"], "ci": cal["ci90"],
         "truth": cal["truth"], "truth_label": "true long-run return", "use": "Not on its own: see the next row"},
        {"instrument": "MMM calibrated, both video channels together", "counts": "Short video + online video, which build the same awareness",
         "window": "weeks 79-104", "value": both["median"], "ci": both["ci90"],
         "truth": both["truth"], "truth_label": "true long-run return of both", "use": "Second-half video budget and the payback verdict"},
    ]
    gaps = [
        {"between": "Platform report and conversion lift",
         "ratio": c["attributed_roas"] / c["iroas_online"],
         "why": "View-through credit goes to anyone who bought online the day after seeing an ad; most of them would have bought anyway."},
        {"between": "Conversion lift and the geo test's online part",
         "ratio": g["flagged_dropped"]["online"]["iroas"] / c["iroas_online"],
         "why": "Two independent designs (people vs regions) agree on online. That agreement is what lets the geo test's store number be trusted."},
        {"between": "Online and stores + online (geo test)",
         "ratio": g["flagged_dropped"]["total"]["iroas"] / g["flagged_dropped"]["online"]["iroas"],
         "why": "About three quarters of sales are in stores; no pixel sees them. Judged on online alone, video looks like it loses money."},
        {"between": "Test window and the long run",
         "ratio": both["median"] / g["flagged_dropped"]["total"]["iroas"],
         "why": "Awareness built in the launch keeps selling after the flight. A six-week read sees only the start of it; the cooldown read sees a little more."},
    ]

    # ---- awareness bridge
    w = bl["readout"]["awareness"]["weighted"]
    reach = bl["reach"]
    platform_share = N_PLATFORM / (N_PLATFORM + N_OFFPLATFORM)
    implied = w["lift"] * reach * platform_share
    wave = {v["week"]: v for v in geo["tracker"]}
    t83, t79 = wave[83], wave[79]
    awareness = {
        "brand_lift_weighted_pp": 100 * w["lift"], "brand_lift_ci_pp": [100 * w["lo"], 100 * w["hi"]],
        "reach_of_platform_users": reach, "platform_share_of_adults": platform_share,
        "implied_population_lift_pp": 100 * implied,
        "tracker_change_79_83_pp": 100 * (t83["estimate"] - t79["estimate"]),
        "truth_paid_lift_week83_pp": 100 * (t83["truth_population"] - t83["truth_without_ads"]),
        "truth_organic_change_79_83_pp": 100 * (t83["truth_without_ads"] - t79["truth_without_ads"]),
    }

    # ---- every channel: reported vs calibrated model vs truth (post-launch)
    chan = []
    names = {"video_zero": "short_video", "online_video": "online_video", "video_combined": "video_combined",
             "social": "social", "search": "search", "retail_media": "retail_media"}
    for m, ch in names.items():
        tr = eff["channel_roi"][ch]["post_launch"]
        model = mmm["models"]["calibrated"]["roi"][m]
        chan.append({"channel": ch, "reported_roas": tr["reported_roas"], "model_roi": model["median"],
                     "model_ci90": model["ci90"], "truth_roi": tr["roi_total"],
                     "reported_over_model": tr["reported_roas"] / model["median"]})

    decisions = [
        {"decision": "Does the launch weight pay back?", "use": "Calibrated MMM, anchored by the geo test with cooldown",
         "not": "Platform ROAS (online only, over-credited) or a six-week window read (misses carry-over)"},
        {"decision": "Online bid targets this month", "use": f"Platform ROAS divided by {gaps[0]['ratio']:.1f} (from conversion lift)",
         "not": "Raw platform ROAS"},
        {"decision": "Which creative to scale", "use": "Brand lift on ad recall and awareness (pre-registered)",
         "not": "Consideration or intent split by creative (too few answers)"},
        {"decision": "Is the brand growing in the market?", "use": "Vendor tracker trend", "not": "Brand lift (only people reached)"},
        {"decision": "Second-half split across channels", "use": "Calibrated MMM, moving budget only where its interval is clear",
         "not": "Platform-reported ROAS by channel (search and retail media look best and are not)"},
    ]
    # brief for the advertiser's research vendor, so the tracker and the brand lift can be compared next time
    last = geo["tracker"][-1]
    vendor_brief = [
        "Ask aided awareness with the same brand list and wording as the platform's in-feed poll. The vendor's longer list "
        "reads lower, so today the two cannot be set side by side without a bridge.",
        f"Add a boost sample of heavy platform users, or weight by time spent on the platform. The panel under-recruits them: "
        f"by week 103 the panel frame reads {100 * last['truth_panel_frame']:.1f}% where the whole population is at "
        f"{100 * last['truth_population']:.1f}%.",
        "Time the waves to the plan's read dates (launch, end of brand lift, end of the geo test) and double the sample in "
        f"launch months: 2,000 a wave detects a {wave_mde(2000):.1f}pp change between waves, 1,000 needs {wave_mde(1000):.1f}pp.",
    ]
    out = {"video": video, "gaps": gaps, "awareness": awareness, "channels": chan, "decisions": decisions,
           "vendor_brief": vendor_brief,
           "uncalibrated_video_zero": unc, "uncalibrated_video_combined": both_unc}
    (OUT / "ch4_compare.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    print("Video, one question, six instruments (iROAS):")
    for v in video:
        ci = f" [{v['ci'][0]:.2f}, {v['ci'][1]:.2f}]" if v["ci"] else ""
        print(f"  {v['instrument']:46s} {v['value']:.2f}{ci}  truth {v['truth']:.2f} ({v['truth_label']})")
    for gp in gaps:
        print(f"  gap {gp['between']}: x{gp['ratio']:.2f}")
    a = awareness
    print(f"\nAwareness: brand lift {a['brand_lift_weighted_pp']:.1f}pp among reached x reach {a['reach_of_platform_users']:.0%} "
          f"x platform share {a['platform_share_of_adults']:.0%} = {a['implied_population_lift_pp']:.1f}pp in the market; "
          f"tracker moved {a['tracker_change_79_83_pp']:+.1f}pp (weeks 79-83), of which ads truly {a['truth_paid_lift_week83_pp']:.1f}pp, "
          f"organic {a['truth_organic_change_79_83_pp']:.1f}pp")
    print("\nChannels (post-launch): reported ROAS | calibrated model ROI | truth")
    for r in chan:
        print(f"  {r['channel']:13s} {r['reported_roas']:.2f} | {r['model_roi']:.2f} [{r['model_ci90'][0]:.2f}, {r['model_ci90'][1]:.2f}] | {r['truth_roi']:.2f}")


if __name__ == "__main__":
    main()
