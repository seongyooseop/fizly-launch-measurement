"""Chapter 0: the measurement plan agreed with FIZLY and its agency before launch.

One row per business question: the KPI, the study that answers it, when it
runs, what it needs to be readable, and the decision it feeds. Minimums are
read from each chapter's design step (outputs/ch*_*.json) so the plan and the
studies always use the same numbers; a study not yet designed shows as pending.

    python src/ch0_plan.py
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "outputs"


def load(name):
    p = OUT / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main():
    bl = load("ch1_brand_lift.json")
    cl = load("ch2_conversion_lift.json")
    geo = load("ch3_offline.json")

    if bl:
        d = next(r for r in bl["design"] if abs(r["control_share"] - bl["control_share"]) < 1e-9)
        half = bl["budget"][0]
        big = next(r for r in bl["design"] if abs(r["control_share"] - 0.30) < 1e-9)
        # answers follow reach, not spend: a smaller budget barely changes precision,
        # a larger holdout does
        bl_min = (f"{d['answers_test']:,.0f} test / {d['answers_control']:,.0f} holdout answers per question; "
                  f"detects +{100 * d['awareness']:.1f}pp awareness, +{100 * d['ad_recall']:.1f}pp recall. "
                  f"Answers follow reach, not spend: half the budget ({half['spend_m']:,.0f}M KRW) still detects "
                  f"+{100 * half['awareness']:.1f}pp; a 30% holdout would detect +{100 * big['awareness']:.1f}pp")
    else:
        bl_min = "pending (chapter 1 design)"
    cl_min = cl["plan_min"] if cl else "pending (chapter 2 design)"
    geo_min = geo["plan_min"] if geo else "pending (chapter 3 design)"
    tracker_min = geo["tracker_min"] if geo and "tracker_min" in geo else "pending (chapter 3 design)"

    rows = [
        {"objective": "Awareness among people reached", "question": "Is the launch video building awareness of Zero among the people it reaches, and which creative does it better?",
         "kpi": "Ad recall, aided awareness (primary); consideration, purchase intent (directional only)",
         "study": "Brand lift survey on the video platform (randomized holdout)", "weeks": "79-82",
         "minimum": bl_min, "decision": "Keep or shift creative weight between A and B; keep the flight weight",
         "owner": "Measurement partner designs and reads it; the platform runs the polls; the agency fixes the holdout before launch"},
        {"objective": "Awareness in the whole market", "question": "Is awareness growing across the market, including people the platform never reached?",
         "kpi": "Aided awareness, all adults 18-44", "study": "Brand tracking survey by an independent research vendor (monthly waves)",
         "weeks": "75-104 (monthly)", "minimum": tracker_min, "decision": "Brand health against competitors; sanity check on platform lift",
         "owner": "Advertiser's research vendor; measurement partner aligns its question wording with the brand lift"},
        {"objective": "Online sales", "question": "How many online purchases did the ads add, beyond what the pixel credits?",
         "kpi": "Incremental online purchases and revenue; online iROAS", "study": "Conversion lift (user-level holdout)",
         "weeks": "83-88", "minimum": cl_min, "decision": "Online bidding targets; how far to trust pixel ROAS week to week",
         "owner": "Measurement partner designs and reads it; advertiser shares purchase events through the pixel"},
        {"objective": "Total sales, stores included", "question": "Do the ads pay back once convenience-store and supermarket sales are counted?",
         "kpi": "Incremental revenue (stores + online); total iROAS", "study": "Geo experiment: video off in matched regions, read from the retail sell-out panel and online sales",
         "weeks": "83-88, read again at 90", "minimum": geo_min, "decision": "Whether the launch weight pays back; budget for the second half",
         "owner": "Measurement partner sizes the regions; agency holds video off there; advertiser shares the sell-out panel"},
        {"objective": "Budget across channels", "question": "How should the second-half budget be split across video, search, social and retail media?",
         "kpi": "Marginal return per channel", "study": "Marketing mix model of total sales, calibrated with the geo test (conversion lift sees online only, so it checks the model rather than calibrating it)",
         "weeks": "after 90", "minimum": "78 weeks of history, the launch weeks and the geo test with its cooldown read", "decision": "Second-half channel split",
         "owner": "Advertiser analytics with the agency; measurement partner supplies the calibration"},
        {"objective": "Everyday optimisation", "question": "Which platform-reported numbers can the team use for weekly optimisation, and with what correction?",
         "kpi": "Reported / incremental ratio per channel", "study": "Cross-check of platform reports against the studies above",
         "weeks": "after 88", "minimum": "Results of chapters 1-3", "decision": "Correction factors for the weekly dashboard",
         "owner": "Agency applies the corrections; measurement partner updates them after each study"},
    ]
    rules = [
        "Primary metrics and holdout sizes are fixed before launch; no metric is promoted to primary after the results are in.",
        "Creative A vs B is judged on ad recall and awareness only. Consideration and intent are too small to split by creative at this budget.",
        "No early reads: brand lift is read after week 82, conversion lift and the geo test after week 88; the geo test is read again at week 90, two weeks after video returns, because launch awareness keeps selling.",
        "If studies disagree, the study closest to the decision wins: the geo test for total payback, conversion lift for online bidding, brand lift for creative.",
        "Success thresholds agreed in advance: awareness lift at least +3pp among people reached; for payback, the long-run sales return (MMM calibrated to the geo test) is compared with break-even at FIZLY's contribution margin, not with 1.0. Sales here are shelf value, so a return of 1.0 loses money.",
    ]
    out = {"rows": rows, "rules": rules}
    OUT.mkdir(exist_ok=True)
    (OUT / "ch0_plan.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for r in rows:
        print(f"- {r['objective']} | {r['study']} | weeks {r['weeks']}\n    min: {r['minimum']}")


if __name__ == "__main__":
    main()
