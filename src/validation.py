"""Grade every headline number against the simulated truth, next to the
answer a team would get without the study. Also collects the repeated-run
checks (bias and interval coverage) from each chapter.

Writes outputs/validation.json
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"


def j(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def row(chapter, claim, est, lo, hi, truth, naive_label, naive, unit="", interval="95%"):
    inside = None if lo is None else bool(lo <= truth <= hi)
    return {"chapter": chapter, "claim": claim, "estimate": est, "lo": lo, "hi": hi, "interval": interval,
            "truth": truth, "inside": inside, "naive_label": naive_label, "naive": naive, "unit": unit}


def main():
    bl, cl, geo, mmm, cmp_, rep = (j("ch1_brand_lift.json"), j("ch2_conversion_lift.json"), j("ch3_offline.json"),
                                   j("ch4_mmm.json"), j("ch4_compare.json"), j("ch5_report.json"))
    eff = json.loads((ROOT / "data" / "truth" / "effects.json").read_text(encoding="utf-8"))
    r = bl["readout"]
    rec, aw, cd = r["ad_recall"], r["awareness"], r["ad_recall"]["creative_diff"]
    c, g = cl["readout"], geo["readout"]
    cal, unc = mmm["models"]["calibrated"]["roi"], mmm["models"]["uncalibrated"]["roi"]
    tg = eff["geo_test"]
    a = cmp_["awareness"]
    rows = [
        row("1", "Ad recall lift among respondents", 100 * rec["lift"], 100 * rec["lo"], 100 * rec["hi"],
            100 * rec["truth_respondents"], "Saw vs never reached", 100 * rec["naive"], "pp"),
        row("1", "Awareness lift, everyone reached (weighted)", 100 * aw["weighted"]["lift"], 100 * aw["weighted"]["lo"],
            100 * aw["weighted"]["hi"], 100 * aw["truth_all_exposed"], "Raw respondents' lift", 100 * aw["lift"], "pp"),
        row("1", "Creative A minus B, ad recall", 100 * cd["diff"], 100 * cd["lo"], 100 * cd["hi"], 100 * cd["truth"],
            None, None, "pp"),
        row("2", "Online iROAS of video (conversion lift)", c["iroas_online"], c["iroas_lo"], c["iroas_hi"],
            c["truth_iroas_online"], "Platform-reported ROAS", c["attributed_roas"]),
        row("3", "Total iROAS in the test weeks (geo test)", g["flagged_dropped"]["total"]["iroas"],
            *g["flagged_dropped"]["total"]["iroas_ci"], tg["test"]["iroas_total"], "Online only (conversion lift)", c["iroas_online"]),
        row("3", "Total iROAS with a two-week cooldown", g["with_cooldown"]["total"]["iroas"], *g["with_cooldown"]["total"]["iroas_ci"],
            tg["test_plus_cooldown"]["iroas_total"], "Window read only", g["flagged_dropped"]["total"]["iroas"]),
        row("4", "Both video channels, half-year return (calibrated MMM)", cal["video_combined"]["median"],
            *cal["video_combined"]["ci90"], cal["video_combined"]["truth"], "Uncalibrated MMM", unc["video_combined"]["median"],
            interval="90%"),
        row("4", "Short video alone, half-year return (calibrated MMM)", cal["video_zero"]["median"], *cal["video_zero"]["ci90"],
            cal["video_zero"]["truth"], "Uncalibrated MMM", unc["video_zero"]["median"], interval="90%"),
        row("4", "Search, half-year return (calibrated MMM)", cal["search"]["median"], *cal["search"]["ci90"],
            cal["search"]["truth"], "Platform-reported ROAS", eff["channel_roi"]["search"]["all"]["reported_roas"], interval="90%"),
        row("4", "Retail media, half-year return (calibrated MMM)", cal["retail_media"]["median"], *cal["retail_media"]["ci90"],
            cal["retail_media"]["truth"], "Platform-reported ROAS", eff["channel_roi"]["retail_media"]["all"]["reported_roas"], interval="90%"),
        row("5", "Marginal return of sustain video (calibrated MMM)", rep["sustain_marginal"]["median"], *rep["sustain_marginal"]["ci90"],
            rep["playbook"]["value_lab_check"]["true_return"], None, None, interval="90%"),
        row("4", "Market awareness moved by ads, from brand lift x reach", a["implied_population_lift_pp"], None, None,
            a["truth_paid_lift_week83_pp"], "Tracker change, weeks 79-83", a["tracker_change_79_83_pp"], "pp"),
    ]
    reps = [
        {"chapter": "1", "study": "Brand lift, ad recall", "runs": bl["montecarlo"]["runs"],
         "bias": bl["montecarlo"]["ad_recall"]["bias_pp"], "coverage": bl["montecarlo"]["ad_recall"]["coverage"], "unit": "pp"},
        {"chapter": "1", "study": "Brand lift, awareness", "runs": bl["montecarlo"]["runs"],
         "bias": bl["montecarlo"]["awareness"]["bias_pp"], "coverage": bl["montecarlo"]["awareness"]["coverage"], "unit": "pp"},
        {"chapter": "1", "study": "Brand lift, purchase intent", "runs": bl["montecarlo"]["runs"],
         "bias": bl["montecarlo"]["purchase_intent"]["bias_pp"], "coverage": bl["montecarlo"]["purchase_intent"]["coverage"], "unit": "pp"},
        {"chapter": "2", "study": "Conversion lift, online iROAS", "runs": cl["montecarlo"]["runs"],
         "bias": cl["montecarlo"]["bias"], "coverage": cl["montecarlo"]["coverage"], "unit": ""},
        {"chapter": "3", "study": "Geo test, total iROAS (flagged region dropped)", "runs": geo["montecarlo"]["runs"],
         "bias": geo["montecarlo"]["flagged_dropped"]["bias"], "coverage": geo["montecarlo"]["flagged_dropped"]["coverage"], "unit": ""},
    ]
    inside = [x["inside"] for x in rows if x["inside"] is not None]
    out = {"rows": rows, "repeated_runs": reps, "inside": sum(inside), "graded": len(inside)}
    (OUT / "validation.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for x in rows:
        ci = f"[{x['lo']:.2f}, {x['hi']:.2f}]" if x["lo"] is not None else "(no interval)"
        flag = "" if x["inside"] is None else ("inside" if x["inside"] else "MISS")
        print(f"  ch{x['chapter']} {x['claim']:55s} {x['estimate']:6.2f} {ci:18s} truth {x['truth']:6.2f} {flag}")
    print(f"{sum(inside)} of {len(inside)} intervals contain the truth")


if __name__ == "__main__":
    main()
