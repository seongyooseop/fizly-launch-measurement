# FIZLY Launch Measurement (synthetic data)

A measurement partner's case study for a **fictional** Korean drink brand, FIZLY, launching a zero-sugar line ("Zero")
with a heavy short-form video campaign. About three quarters of its sales happen in convenience stores and supermarkets,
seen only through a weekly retail sell-out panel; the rest online, where a pixel can see them.

The lab follows the work in order: agree a measurement plan with the advertiser and agency, run a brand lift survey, a
conversion lift, a geo test on store sales and an independent brand tracker, reconcile their answers, write the
readout (English and Korean), and send the product team a feedback memo. All data is simulated from a known process,
so every estimate is graded against the truth.

**Live demo:** https://seongyooseop.github.io/fizly-launch-measurement/site/ (or open `site/index.html`: one
self-contained file, nine tabs, each with a "How to read this tab" guide). The cached MMM fits in `models/` (about 7.5 MB)
are included so the pipeline runs end to end without refitting.

## At a glance: one question, seven instruments

How much does the launch video return per won of media?

| Instrument | What it counts | Estimate | Truth for that question |
|---|---|---|---|
| Platform report (7-day click / 1-day view) | Online orders by people who clicked or saw an ad | 1.51 | 0.73 (online) |
| Conversion lift, 10% user holdout | Extra online orders | **0.70** (95%: 0.54-0.85) | 0.73 |
| Geo test, online part | Online sales lost where video went dark | 0.68 (0.59-0.78) | 0.75 |
| Geo test, stores + online | All sales lost in 12 dark regions, 6 weeks | **1.68** (1.32-2.04) | 1.92 |
| Geo test + 2-week cooldown | Read again after video came back | 2.27 (1.82-2.72) | 2.62 |
| MMM calibrated to the geo test, short video alone | Half-year average return | 5.97 (90%: 5.19-6.77) | 4.48 (miss) |
| MMM calibrated, both video channels together | Half-year average return | **4.50** (3.93-5.12) | 4.14 |

Each number is right for its own question. The platform credits 2.2 times the online orders video adds; two
independent designs (people and regions) agree on the online return; stores more than double it; awareness built in
the launch keeps selling after the flight. Sales here are shelf value: at an assumed 30% contribution, break-even is
3.3, and the launch video clears it once stores and carry-over are counted. Search and retail media, which look best in
platform reports (ROAS about 1.9), do not clear their break-even even at the top of their intervals.

9 of 11 headline intervals contain the truth; the two misses are reported, not tuned away. The unchanged pipeline was
also run on the lab's first world (media at 15% of sales): there the readout says the launch video has not paid back,
written by the same code (`src/robustness.py`).

## Chapters

0. **Measurement plan.** One row per business question: KPI, study, weeks, what each study needs to be readable (from
   its design step on the advertiser's own history), the decision it feeds, who does what, and rules agreed before
   launch. A program view applies the same design math to other advertisers: which study each budget tier and sales
   mix can read, and which one answers its payback question.
1. **Brand lift survey** (weeks 79-82). Randomized 20% holdout; one question per respondent. Design shows that precision
   follows the holdout share, not the budget. Ad recall +11.6pp and awareness +5.8pp; consideration and intent
   directional as planned. Respondents are heavy users, so answers are re-weighted by poll chance to describe everyone
   reached. Creative A (product in the first second) beats B on recall. 40 re-runs: intervals cover the truth 92-95%.
2. **Conversion lift** (weeks 83-88). 10% user holdout in the campaign regions, pixel-matched orders. Online iROAS 0.70
   against a platform-credited 1.51. 40 re-runs: bias +0.007, coverage 100%. Signal loss: at match rates from 90% to
   30% the study stays unbiased and gets noisier, while the platform's reported ROAS falls from 1.82 to 0.60 with the
   true return unchanged.
3. **Stores and tracker.** Geo test: video off in 12 of 40 regions (30% detects nearly the same return as 50% and puts
   half the launch sales at risk). TBR on weekly sell-out + online. Pre-launch A/A tests under-stated launch-week
   noise; in-flight A/A tests among control regions fixed it (92-98% coverage over 40 simulated worlds). A rival launch
   in two control regions is flagged in one. The vendor tracker shows the level of awareness but cannot attribute it.
4. **One question, many answers.** The table above, the gaps between instruments explained, a bridge from platform
   brand lift to market awareness (lift x reach x audience share), every channel's platform report against the
   calibrated model, a brief for the research vendor's next tracker waves, and a decision table.
5. **Readout and playbook** (English and Korean). Bottom line with contribution margin, recommendations for the first
   half of 2027, a quarterly learning agenda, what the advertiser needs to provide, and a reusable launch measurement
   playbook with the cost of measuring. Every recommendation is chosen in code by comparing an estimate and its
   interval with break-even. A one-page point of view for a market audience
   ([`docs/point_of_view.md`](docs/point_of_view.md)) is written from the same numbers.
6. **Product feedback memo.** Six gaps this launch exposed in standard lift tools, each with its evidence from the lab,
   the ask, who it helps, and how to size it.

## What did not go to plan

- **The first world was mis-specified.** It spent 15% of sales on media and nothing paid back, which no drinks brand
  would do. The budget was halved and every chapter re-ran; no estimator changed (work log entry 16).
- **The MMM first gave launch video five times its true return.** Video ran every week from the day Zero reached
  shelves, and online video moved with it. Fixed with a flighted media plan and distribution and maturity terms.
- **Calibration first scored the geo test as a national top-up** instead of 29% of the market going to zero, which
  pushed the model's video return up (4.86, outside). Corrected: 4.50, true 4.14 (entry 17).
- **The model splits video wrongly between the two video channels** (short video alone 5.97 vs 4.48); the readout
  reports the two together.
- **On sustain video the model says "hold" (3.7) where the truth is below break-even (3.0).** The readout's step-down
  test is what would catch it (entry 18).
- **Six-week geo reads understate a launch.** The same withheld spend returns 1.92 in the window, 2.62 with cooldown and
  3.81 by week 104.

Every problem the checks caught is in [`docs/ai_workflow_log.md`](docs/ai_workflow_log.md) (20 entries).

## How the methods map to platform tools

The lab is written in platform-neutral terms. The closest named tools on a short-form video platform:

| This lab | TikTok |
|---|---|
| Brand lift survey with randomized holdout | Brand Lift Study |
| Conversion lift with user holdout | Conversion Lift Study |
| Pixel-matched orders, server-side events | TikTok Pixel, Events API |
| Platform-credited conversions (click / view windows) | Ads Manager attribution settings |
| Geo test on store sell-out | Geo-based lift with a measurement partner |
| MMM calibrated to experiments | MMM with measurement partners |
| Independent brand tracker | Third-party brand tracking (research vendors) |

## Pipeline

```
python src/check_world.py          # world sizes and true returns (sanity check)
python src/ch3_design.py           # geo test design on the 78 weeks before launch
python src/run_timeline.py         # all 104 weeks + counterfactual truth for every study
python src/ch1_brand_lift.py --mc 40
python src/ch2_conversion_lift.py --mc 40
python src/ch3_offline.py --mc 40  # geo test readout + tracker
python src/ch4_mmm.py              # PyMC fits cached in models/ (--refit to redo)
python src/ch4_compare.py
python src/ch0_plan.py             # reads the design outputs above
python src/program_eligibility.py  # program view for other advertisers
python src/ch5_report.py           # readout, English and Korean
python src/ch6_product_memo.py
python src/point_of_view.py        # one-page point of view
python src/signal_loss.py          # conversion lift at lower pixel match rates
python src/robustness.py           # same pipeline on the first world (about 5 minutes)
python src/validation.py
python src/build_page.py           # site/index.html
```

Python 3.12, numpy, pandas, scipy, statsmodels, PyMC. Set `PYTHONUTF8=1` on Windows.

## Known limits

- Store sales are simulated as a projected panel with fixed regional error; real panels have coverage changes and
  late restatements.
- Awareness in the survey layer and in the sales layer are separate models that agree only roughly.
- Contribution margins (30% of shelf sales, 45% online) are assumptions for the readout, not outputs.
- The program view assumes sales scale with video budget and regional noise with 1 / sqrt(sales).
- The geo test uses TBR with A/A calibration; Trimmed Match or synthetic control would be the next comparison.

Built with Claude Code. All brands, regions and numbers are simulated.
