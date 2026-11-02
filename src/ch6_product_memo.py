"""Chapter 6: a one-page product feedback memo from the market to the
measurement product team. Every gap is backed by a number from this lab.

Writes outputs/ch6_product_memo.json and docs/product_feedback_memo.md
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"


def j(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main():
    bl, cl, geo, cmp_, rep = (j("ch1_brand_lift.json"), j("ch2_conversion_lift.json"), j("ch3_offline.json"),
                              j("ch4_compare.json"), j("ch5_report.json"))
    c, g = cl["readout"], geo["readout"]
    both = next(v for v in cmp_["video"] if v["instrument"].startswith("MMM calibrated, both"))
    d20 = next(r for r in bl["design"] if abs(r["control_share"] - 0.2) < 1e-9)
    d30 = next(r for r in bl["design"] if abs(r["control_share"] - 0.3) < 1e-9)
    half = bl["budget"][0]
    mc = bl["montecarlo"]
    ratio = rep["platform_correction"]
    sig = j("signal_loss.json")
    sig_today = next(r for r in sig["rows"] if abs(r["match"] - sig["today"]) < 1e-9)
    sig_low = min(sig["rows"], key=lambda r: r["match"])

    gaps = [
        {"priority": "P1", "gap": "Store sales are invisible to conversion lift",
         "evidence": f"Conversion lift sees online only (about a quarter of sales): video's online return {c['iroas_online']:.2f} "
                     f"vs {g['flagged_dropped']['total']['iroas']:.2f} with stores in the test window and {both['value']:.1f} over the half year.",
         "ask": "Self-serve geo lift: the advertiser uploads its region-week sell-out panel; the tool sizes regions from history, "
                "runs TBR with an in-flight A/A check, and reports stores and online separately.",
         "helps": "Food and beverage, household, OTC: anyone whose sales are mostly in stores"},
        {"priority": "P1", "gap": "Reported ROAS sits next to nothing that corrects it",
         "evidence": f"The platform credited {ratio:.1f} times the online orders video added; an advertiser bidding to reported ROAS over-buys online. "
                     f"And if matching falls from {100 * sig_today['match']:.0f}% to {100 * sig_low['match']:.0f}%, reported ROAS drops from "
                     f"{sig_today['platform_reported_roas']:.2f} to {sig_low['platform_reported_roas']:.2f} while the true return stays at "
                     f"{sig['true_online_iroas']:.2f}: a privacy change reads as a performance collapse.",
         "ask": "Show a calibrated ROAS beside reported ROAS: reported divided by the ratio from the advertiser's latest conversion lift, with its date and interval, "
                "and re-estimate the ratio when the match rate moves.",
         "helps": "Every advertiser that has run one lift study"},
        {"priority": "P2", "gap": "The brand lift planner sells budget, not precision",
         "evidence": f"Answers follow reach: halving the budget moved the awareness MDE only from {100 * d20['awareness']:.1f}pp to "
                     f"{100 * half['awareness']:.1f}pp, while a 30% holdout took it to {100 * d30['awareness']:.1f}pp.",
         "ask": "Planner shows the detectable lift per question for each holdout share and asks the advertiser to name primary metrics before launch.",
         "helps": "Advertisers whose intent or consideration studies come back 'not significant'"},
        {"priority": "P2", "gap": "Brand lift describes heavy users, not everyone reached",
         "evidence": f"Respondents spend more time on the platform: raw ad recall lift ran {mc['ad_recall']['raw_vs_all_exposed_pp']:.1f}pp above the "
                     f"all-reached truth over 40 runs; weighting by poll chance cut that to {abs(mc['ad_recall']['weighted_bias_pp']):.1f}pp.",
         "ask": "Report the weighted lift among everyone reached by default and compute cost per lifted person from it.",
         "helps": "Anyone comparing cost per lifted person across platforms"},
        {"priority": "P2", "gap": "Launch effects outlast the read",
         "evidence": f"Geo read in the window {g['flagged_dropped']['total']['iroas']:.2f}, two weeks later {g['with_cooldown']['total']['iroas']:.2f}, "
                     f"half-year model {both['value']:.1f}.",
         "ask": "A scheduled cooldown read in lift tools, and an export of lift results in the format open-source MMMs take as calibration.",
         "helps": "Launches and seasonal flights"},
        {"priority": "P3", "gap": "Creative splits produce false winners",
         "evidence": f"Where two creatives were truly equal, {100 * mc['creative_false_alarm']:.0f}% of 40 runs showed a 'significant' difference on consideration or intent.",
         "ask": "Ask for creative metrics before launch; flag any other metric as exploratory in the report.",
         "helps": "Creative teams and agencies"},
    ]
    sizing = [
        "Share of the market's top 100 advertisers with most sales offline, and how many ran a geo test last year.",
        "Lift studies per quarter, and the share that come back with no significant metric.",
        "Advertisers who cut spend within 30 days of a lift study whose online read was below 1.",
    ]
    out = {"to": "Measurement product team", "from": "Measurement partner, Korea market",
           "subject": "Six measurement gaps a store-led drink launch exposed",
           "context": "One launch, simulated. The gaps generalize to advertisers whose sales happen mostly in stores.",
           "gaps": gaps, "sizing": sizing,
           "not_asking": "Cross-platform de-duplication or a new attribution model: the gaps above are fixable inside existing lift tools."}
    (OUT / "ch6_product_memo.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    md = [f"# {out['subject']}", "", f"**To:** {out['to']}  ", f"**From:** {out['from']}  ",
          "*Synthetic data. FIZLY is a fictional brand.*", "", out["context"], "",
          "| Priority | Gap | Evidence | Ask | Who it helps |", "|---|---|---|---|---|"]
    md += [f"| {x['priority']} | {x['gap']} | {x['evidence']} | {x['ask']} | {x['helps']} |" for x in gaps]
    md += ["", "**How I would size it before building:**", ""] + [f"- {s}" for s in sizing]
    md += ["", f"**Not asking for:** {out['not_asking']}"]
    (ROOT / "docs" / "product_feedback_memo.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    for x in gaps:
        print(f"{x['priority']} {x['gap']}: {x['evidence']}")


if __name__ == "__main__":
    main()
