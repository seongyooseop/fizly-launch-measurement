"""Build the page: one self-contained HTML file, nine tabs.

Injects every chapter's output and the work log into site/template.html and
writes site/index.html. No server or library needed to open it.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"


def worklog():
    text = (ROOT / "docs" / "ai_workflow_log.md").read_text(encoding="utf-8")
    entries = re.findall(r"\*\*(\d+\. [^*]+)\*\*\n(.+?)(?=\n\n|\Z)", text, flags=re.S)
    return [{"title": t.strip(), "body": b.strip().replace("\n", " ")} for t, b in entries]


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main():
    data = {"plan": load("ch0_plan.json"), "ch1": load("ch1_brand_lift.json"), "ch2": load("ch2_conversion_lift.json"),
            "ch3d": load("ch3_design.json"), "ch3": load("ch3_offline.json"), "compare": load("ch4_compare.json"),
            "report": load("ch5_report.json"), "memo": load("ch6_product_memo.json"), "validation": load("validation.json"),
            "program": load("program_eligibility.json"), "pov": load("point_of_view.json"),
            "signal": load("signal_loss.json"), "robust": load("robustness.json"),
            "log": worklog()}
    # the per-person frequency and diagnostic detail is not needed on the page
    data["ch3"].pop("diagnostic", None)
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    html = (ROOT / "site" / "template.html").read_text(encoding="utf-8").replace("/*__DATA__*/", blob)
    (ROOT / "site" / "index.html").write_text(html, encoding="utf-8")
    print(f"site/index.html: {len(html) / 1024:.0f} KB, {len(data['log'])} log entries")


if __name__ == "__main__":
    main()
