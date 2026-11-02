# Six measurement gaps a store-led drink launch exposed

**To:** Measurement product team  
**From:** Measurement partner, Korea market  
*Synthetic data. FIZLY is a fictional brand.*

One launch, simulated. The gaps generalize to advertisers whose sales happen mostly in stores.

| Priority | Gap | Evidence | Ask | Who it helps |
|---|---|---|---|---|
| P1 | Store sales are invisible to conversion lift | Conversion lift sees online only (about a quarter of sales): video's online return 0.70 vs 1.68 with stores in the test window and 4.5 over the half year. | Self-serve geo lift: the advertiser uploads its region-week sell-out panel; the tool sizes regions from history, runs TBR with an in-flight A/A check, and reports stores and online separately. | Food and beverage, household, OTC: anyone whose sales are mostly in stores |
| P1 | Reported ROAS sits next to nothing that corrects it | The platform credited 2.2 times the online orders video added; an advertiser bidding to reported ROAS over-buys online. And if matching falls from 75% to 30%, reported ROAS drops from 1.52 to 0.60 while the true return stays at 0.73: a privacy change reads as a performance collapse. | Show a calibrated ROAS beside reported ROAS: reported divided by the ratio from the advertiser's latest conversion lift, with its date and interval, and re-estimate the ratio when the match rate moves. | Every advertiser that has run one lift study |
| P2 | The brand lift planner sells budget, not precision | Answers follow reach: halving the budget moved the awareness MDE only from 4.3pp to 4.8pp, while a 30% holdout took it to 3.7pp. | Planner shows the detectable lift per question for each holdout share and asks the advertiser to name primary metrics before launch. | Advertisers whose intent or consideration studies come back 'not significant' |
| P2 | Brand lift describes heavy users, not everyone reached | Respondents spend more time on the platform: raw ad recall lift ran 3.9pp above the all-reached truth over 40 runs; weighting by poll chance cut that to 0.4pp. | Report the weighted lift among everyone reached by default and compute cost per lifted person from it. | Anyone comparing cost per lifted person across platforms |
| P2 | Launch effects outlast the read | Geo read in the window 1.68, two weeks later 2.27, half-year model 4.5. | A scheduled cooldown read in lift tools, and an export of lift results in the format open-source MMMs take as calibration. | Launches and seasonal flights |
| P3 | Creative splits produce false winners | Where two creatives were truly equal, 10% of 40 runs showed a 'significant' difference on consideration or intent. | Ask for creative metrics before launch; flag any other metric as exploratory in the report. | Creative teams and agencies |

**How I would size it before building:**

- Share of the market's top 100 advertisers with most sales offline, and how many ran a geo test last year.
- Lift studies per quarter, and the share that come back with no significant metric.
- Advertisers who cut spend within 30 days of a lift study whose online read was below 1.

**Not asking for:** Cross-platform de-duplication or a new attribution model: the gaps above are fixable inside existing lift tools.
