"""One-page summary for an application: site/summary.html (A4, print-ready)
and site/FIZLY_case_summary.pdf, built from the same outputs as the page.

The PDF is printed with headless Microsoft Edge (or Chrome) if one is found.
    python src/build_summary.py
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
SITE = ROOT / "site"
DEMO = "https://seongyooseop.github.io/fizly-launch-measurement/site/"
REPO = "https://github.com/seongyooseop/fizly-launch-measurement"
BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe"]


def j(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def main():
    cmp_, rep, val, sig, rob = j("ch4_compare.json"), j("ch5_report.json"), j("validation.json"), j("signal_loss.json"), j("robustness.json")
    def interval(v):
        return f" <span>[{v['ci'][0]:.2f}, {v['ci'][1]:.2f}]</span>" if v["ci"] else ""

    rows = "".join(
        f"<tr><td>{v['instrument'].replace(' (pixel, 7-day click / 1-day view)', '')}</td><td>{v['window']}</td>"
        f"<td class=n><b>{v['value']:.2f}</b>{interval(v)}</td><td class=n>{v['truth']:.2f}</td></tr>"
        for v in cmp_["video"])
    both = cmp_["video"][-1]
    today = next(r for r in sig["rows"] if abs(r["match"] - sig["today"]) < 1e-9)
    low = min(sig["rows"], key=lambda r: r["match"])
    a, b = rob["first"], rob["final"]
    findings = [
        f"The platform credits <b>{rep['platform_correction']:.1f}x</b> the online orders video adds; conversion lift (people) and the "
        f"geo test's online part (regions) agree on the real number.",
        f"Online alone, video looks like a loss. With store sales and carry-over, both video channels return <b>{both['value']:.1f}</b> "
        f"won of shelf sales per won over the half year, against a break-even of {rep['breakeven']:.1f} at 30% contribution.",
        f"Sustain video sits near break-even and the model runs high on it, so the readout asks for a short-video-only step-down test "
        f"(Q1) instead of a cut. Search and retail media look best in platform reports and fall short of break-even even at the top of their intervals.",
        f"When pixel matching falls from {100 * today['match']:.0f}% to {100 * low['match']:.0f}%, reported ROAS drops from "
        f"{today['platform_reported_roas']:.2f} to {low['platform_reported_roas']:.2f} while the true return stays at {sig['true_online_iroas']:.2f}: "
        f"a privacy change reads as a performance collapse.",
    ]
    checks = (f"<b>{val['inside']} of {val['graded']}</b> headline intervals contain the simulated truth (two misses reported). "
              f"Repeated runs: 40 per study. The unchanged pipeline on the lab's first world (media at {100 * a['ad_to_sales']:.0f}% of sales) "
              f"writes the opposite verdict: launch video {'pays back' if a['video_pays'] else 'has not paid back'} "
              f"({a['video_both_model']:.1f} vs truth {a['video_both_truth']:.1f}).")
    role = ["Agreed the questions, read dates and rules with advertiser and agency before launch",
            "Sized every study from the advertiser's own history (holdouts, regions, sales at risk)",
            "Ran brand lift, conversion lift, a store-level geo test and a vendor tracker in one flight",
            "Reconciled seven answers to one question and tied each to the decision it should drive",
            "Handed over a bilingual readout, a launch playbook, a program view by advertiser tier, and a product memo"]
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>FIZLY Case Summary</title><style>
@page {{ size: A4; margin: 13mm 14mm; }}
:root {{ --ink:#101413; --ink2:#4c5553; --muted:#7f8a87; --grid:#e2e6e4; --est:#0f7b6c; --band:#0f3d3a; --page:#ffffff; }}
body {{ margin:0; background:var(--page); color:var(--ink); font: 9.6pt/1.42 system-ui, -apple-system, "Segoe UI", sans-serif; }}
.wrap {{ max-width: 182mm; margin: 0 auto; padding: 16px; }}
header {{ border-bottom: 3px solid var(--band); padding-bottom: 6px; margin-bottom: 8px; }}
h1 {{ font-size: 16pt; margin: 0; line-height: 1.2; }} h2 {{ font-size: 10.5pt; margin: 9px 0 3px; color: var(--band); }}
.meta {{ color: var(--muted); font-size: 8.4pt; letter-spacing: .04em; text-transform: uppercase; }}
p {{ margin: 3px 0; }} ul, ol {{ margin: 2px 0; padding-left: 16px; }} li {{ margin: 1.5px 0; }}
table {{ border-collapse: collapse; width: 100%; font-size: 8.8pt; }}
th, td {{ text-align: left; padding: 2.5px 6px; border-bottom: 1px solid var(--grid); vertical-align: top; }}
th {{ font-size: 7.6pt; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); font-weight: 600; }}
td.n {{ text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }} td.n span {{ color: var(--muted); }}
tr:last-child td {{ background: #eef2f0; }}
.cols {{ display: grid; grid-template-columns: 1.15fr 1fr; gap: 14px; }}
footer {{ margin-top: 8px; border-top: 1px solid var(--grid); padding-top: 5px; font-size: 8.4pt; color: var(--ink2); }}
a {{ color: var(--est); }}
@media (max-width: 640px) {{ .cols {{ grid-template-columns: 1fr; }} }}
</style></head><body><div class="wrap">
<header><div class="meta">Measurement partner case study · synthetic data · Yooseop Seong</div>
<h1>FIZLY Zero: measuring a store-led drink launch</h1>
<p>A fictional Korean drink brand launches a zero-sugar line with heavy short-form video. Three quarters of sales are in stores, where no pixel looks.
Every number below is graded against the hidden truth of the simulated world.</p></header>
<h2>One question, seven instruments: what does the launch video return per won?</h2>
<table><thead><tr><th>Instrument</th><th>Window</th><th class=n>Estimate [interval]</th><th class=n>Truth</th></tr></thead><tbody>{rows}</tbody></table>
<p style="font-size:8.2pt;color:var(--muted)">Truth is the simulated answer to each instrument's own question: online rows against the true online return, the geo rows against the regions that went dark, the model rows against the half-year return. Short video alone is the one row whose interval misses; the readout reports the two video channels together.</p>
<div class="cols"><div><h2>What the work found</h2><ul>{''.join(f'<li>{x}</li>' for x in findings)}</ul></div>
<div><h2>What a measurement partner did</h2><ol>{''.join(f'<li>{x}</li>' for x in role)}</ol>
<h2>How it was checked</h2><p>{checks}</p></div></div>
<footer>Demo: <a href="{DEMO}">{DEMO}</a> · Code and work log: <a href="{REPO}">{REPO}</a><br>
All brands, regions and numbers are simulated. Methods are platform-neutral; the README maps them to named lift tools.</footer>
</div></body></html>"""
    (SITE / "summary.html").write_text(html, encoding="utf-8")
    exe = next((b_ for b_ in BROWSERS if Path(b_).exists()), None)
    if exe:
        pdf = SITE / "FIZLY_case_summary.pdf"
        subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={pdf}", (SITE / "summary.html").as_uri()],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        print(f"site/FIZLY_case_summary.pdf: {pdf.stat().st_size / 1024:.0f} KB")
    print("site/summary.html written")


if __name__ == "__main__":
    main()
