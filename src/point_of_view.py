"""A one-page point of view for a market audience (a post or a short talk),
written from this lab's numbers so it cannot drift from them.

Writes outputs/point_of_view.json and docs/point_of_view.md
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"


def j(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main():
    cl, geo, cmp_, rep = j("ch2_conversion_lift.json"), j("ch3_offline.json"), j("ch4_compare.json"), j("ch5_report.json")
    c, g = cl["readout"], geo["readout"]
    both = next(v for v in cmp_["video"] if v["instrument"].startswith("MMM calibrated, both"))
    online, window, cool = c["iroas_online"], g["flagged_dropped"]["total"]["iroas"], g["with_cooldown"]["total"]["iroas"]
    title = "Store-led brands are judged on the quarter of sales a pixel can see"
    lead = (f"In a simulated drink launch, short-form video returned {online:.2f} won per won if you counted online orders and "
            f"{window:.2f} if you added store sales over six weeks; over half a year, with online video alongside, the video "
            f"campaign returned {both['value']:.1f}. "
            f"Break-even was {rep['breakeven']:.1f}. Judged online, the campaign looks like a loss; judged properly, it paid back.")
    points = [
        ("Count where the sales are.",
         "For food, drink and household brands most sales happen in stores. A conversion lift is the right tool for online "
         "bidding and the wrong one for payback. A geo test read from the retailer's sell-out panel is the only experiment that sees stores."),
        ("Read launches twice.",
         f"Awareness built in a flight keeps selling after it. The geo read rose from {window:.2f} to {cool:.2f} two weeks after "
         f"video returned. Plan the second read before launch, and let a model calibrated to it carry the rest."),
        ("Correct the report, don't ignore it.",
         f"The platform credited {rep['platform_correction']:.1f} times the online orders the ads added. That ratio, measured "
         "once, turns a reported ROAS into a usable bidding target for months."),
        ("Calibrate the model the way the test was run.",
         "A geo test switches video off in part of the market. A national model has to score it as that region going to zero, "
         "not as extra money at the margin; otherwise calibration inflates the very number it is meant to fix."),
    ]
    close = ("None of this needs a new attribution model. It needs a plan agreed before launch, three experiments sized from the "
             "advertiser's own history, and the discipline to give each decision the number that answers it.")
    out = {"title": title, "lead": lead, "points": [{"head": h, "body": b} for h, b in points], "close": close}
    (OUT / "point_of_view.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    md = [f"# {title}", "", "*From a simulated case; FIZLY is a fictional brand.*", "", lead, ""]
    md += [f"**{i}. {h}** {b}" + "\n" for i, (h, b) in enumerate(points, 1)]
    md += [close]
    (ROOT / "docs" / "point_of_view.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(lead)
    print(f"{len(' '.join([lead] + [h + ' ' + b for h, b in points] + [close]).split())} words")


if __name__ == "__main__":
    main()
