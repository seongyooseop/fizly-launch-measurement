"""Same pipeline, two worlds: does the readout follow the data?

The first version of this lab's world spent 15% of sales on media and video
built awareness more slowly; the final one spends 7.7% (work log, entry 16).
This script re-runs the unchanged pipeline on the first world in a scratch
copy and sets its readout next to the final one. If the decision rules are
honest, the conclusions should flip with the world, written by the same code.

    python src/robustness.py       # about 5 minutes (refits the MMM for the first world)
Writes outputs/robustness.json
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / ".robustness_first_world"
FIRST_WORLD = {  # (text in world.py, replacement)
    "SPEND_SCALE = 0.5": "SPEND_SCALE = 1.0",
    '"zero_potential": 52.0': '"zero_potential": 46.0',
    '"aw_paid": {"K": 3.0, "slope": 1.2, "decay": 0.97, "max": 0.70':
        '"aw_paid": {"K": 4.0, "slope": 1.2, "decay": 0.97, "max": 0.60',
}
STEPS = ["ch3_design.py", "run_timeline.py", "ch1_brand_lift.py", "ch2_conversion_lift.py",
         "ch3_offline.py", "ch4_mmm.py --refit", "ch4_compare.py", "ch5_report.py"]


def build_first_world():
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    shutil.copytree(ROOT / "src", SCRATCH / "src", ignore=shutil.ignore_patterns("__pycache__"))
    for d in ["data", "outputs", "models", "docs"]:
        (SCRATCH / d).mkdir(parents=True, exist_ok=True)
    w = (SCRATCH / "src" / "world.py").read_text(encoding="utf-8")
    for a, b in FIRST_WORLD.items():
        assert a in w, a
        w = w.replace(a, b)
    (SCRATCH / "src" / "world.py").write_text(w, encoding="utf-8")
    env = dict(os.environ, PYTHONUTF8="1")
    for step in STEPS:
        print(f"[first world] {step}", flush=True)
        subprocess.run([sys.executable, *step.split()], cwd=SCRATCH / "src", env=env, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def summary(base: Path) -> dict:
    o = lambda n: json.loads((base / "outputs" / n).read_text(encoding="utf-8"))  # noqa: E731
    eff = json.loads((base / "data" / "truth" / "effects.json").read_text(encoding="utf-8"))
    cl, geo, mmm, rep = o("ch2_conversion_lift.json"), o("ch3_offline.json"), o("ch4_mmm.json"), o("ch5_report.json")
    both = mmm["models"]["calibrated"]["roi"]["video_combined"]
    roi = eff["channel_roi"]
    spend = sum(roi[c]["post_launch"]["spend"] for c in ["short_video", "online_video", "social", "search", "retail_media"])
    return {
        "video_spend_post_launch_m": (roi["short_video"]["post_launch"]["spend"] + roi["online_video"]["post_launch"]["spend"]) / 1e6,
        "media_spend_post_launch_m": spend / 1e6,
        "platform_over_incremental": rep["platform_correction"],
        "conversion_lift_online": cl["readout"]["iroas_online"],
        "geo_window": geo["readout"]["flagged_dropped"]["total"]["iroas"],
        "geo_cooldown": geo["readout"]["with_cooldown"]["total"]["iroas"],
        "video_both_model": both["median"], "video_both_ci90": both["ci90"], "video_both_truth": both["truth"],
        "video_both_inside": both["truth_inside"],
        "sustain_model": rep["sustain_marginal"]["median"], "sustain_truth": rep["playbook"]["value_lab_check"]["true_return"],
        "breakeven": rep["breakeven"], "video_pays": rep["video_pays"], "sustain_call": rep["sustain_call"],
        "first_line": rep["bottom_line"][0], "second_line": rep["bottom_line"][1],
        "search_action": next(r["action"] for r in rep["recommendation"] if r["line"] == "Search"),
        "retail_action": next(r["action"] for r in rep["recommendation"] if r["line"] == "Retail media"),
    }


def ad_to_sales(base: Path) -> float:
    import pandas as pd
    p = pd.read_parquet(base / "data" / "observed_daily.parquet")
    y2 = p.week > 52
    sp = p.loc[y2, [c for c in p.columns if c.startswith("spend_")]].sum().sum()
    return float(sp / (p.loc[y2, "offline_rev"].sum() + p.loc[y2, "online_rev"].sum()))


def main():
    if "--reuse" not in sys.argv:
        build_first_world()
    first, final = summary(SCRATCH), summary(ROOT)
    first["ad_to_sales"], final["ad_to_sales"] = ad_to_sales(SCRATCH), ad_to_sales(ROOT)
    out = {"first": first, "final": final,
           "what_changed": (f"Media budget ({100 * first['ad_to_sales']:.1f}% of sales -> {100 * final['ad_to_sales']:.1f}%) and how fast "
                            "video builds awareness. No estimator, design rule or decision rule changed.")}
    (ROOT / "outputs" / "robustness.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for k in ["ad_to_sales", "platform_over_incremental", "conversion_lift_online", "geo_window", "geo_cooldown",
              "video_both_model", "video_both_truth", "video_both_inside", "sustain_model", "sustain_truth",
              "video_pays", "sustain_call", "search_action", "retail_action"]:
        print(f"{k:28s} first: {first[k]!s:40.40s} final: {final[k]!s:40.40s}")


if __name__ == "__main__":
    main()
