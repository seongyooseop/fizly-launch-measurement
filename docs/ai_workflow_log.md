# AI workflow log

Built with Claude Code. Each entry is a problem a check caught, what caused it, and the fix. Every number on the page has to survive these checks.

Numbers inside entries 1-15 are as they were when the problem was found. On day 4 the world's media budget was rescaled (entry 16) and every chapter re-ran; the **Result** paragraphs give the final numbers, which match the page.

## Day 1 — world, measurement plan and brand lift (2026-11-01)

**1. The video platform reported less online revenue than video truly added online (ROAS 0.44 vs 0.67).**
The story this lab tests is the usual one: the platform's own report flatters video for online sales, while store sales stay invisible to it. The first reporting layer gave view-through credit only to buyers of the new Zero line, which was too narrow: a view-through window credits anyone who bought from the brand online the day after seeing an ad. Widened the credit to online buyers of both lines. Reported ROAS is now 1.21, against a true online return of 0.67 and a true total return of 1.84. Only the reporting layer changed; the sales the ads cause did not.

**2. Consideration and purchase-intent lifts were larger than real campaigns show (+4.2pp and +3.6pp).**
Published brand lift norms for a single flight are a few points on ad recall and awareness and around a point on intent. Lowered the two effects so that the design question is real: at this budget intent sits near the edge of what a survey can detect.

**3. The raw survey lift describes heavy users, not everyone the campaign reached.**
People who answer in-feed polls spend more time on the platform, so they also saw more ads. In the first readout, ad recall lift among respondents was +16.4pp in truth, but +11.4pp across everyone reached. Cost per lifted person computed from the raw lift would look about 30% better than it is. The platform knows each person's chance of seeing a poll from their time spent, so answers are weighted by one over that chance; the weighted lift targets everyone reached, and cost per lifted person uses it. Over 40 re-runs the raw lift sits 5.0pp above the all-reached truth for ad recall; the weighted lift is off by 0.2pp.

**4. Creative B "lost" on consideration in the first readout (A - B = -2.7pp, p = 0.027), but A and B are identical on consideration in truth.**
Eight comparisons (four metrics, two creatives) at a 5% threshold will throw up a false difference fairly often. Over 40 re-runs, 15% of runs showed a significant creative difference on consideration or intent, where none exists. The plan now names the creative metrics before launch (ad recall and awareness, where the true gap is +6.8pp and +1.8pp), and a difference on any other metric is reported as noise.

**5. Halving the budget barely changes what the survey can detect (awareness: +4.0pp to +4.3pp).**
The first draft of the plan said "at half the budget, read ad recall only". The design step showed otherwise: poll answers come from people reached, and at 78% reach a smaller flight still reaches most of the audience. Precision is bought with the holdout, not the budget: a 30% holdout detects +3.5pp. The plan text now says so.

**Result (final world).** With a 20% holdout, the flight reached 60% of platform users at an average frequency of 2.3. Ad recall (+11.6pp) and awareness (+5.8pp) are read with confidence; in 40 re-runs they are significant 100% and 92% of the time, and the 95% intervals cover the truth 92-95% of the time. Consideration and purchase intent are significant in only 22% and 20% of runs: at this budget they are directional, as the plan said before launch. The naive comparison (people who saw the ad vs people it never reached) overstates awareness lift by 4.8pp on average, because the people the campaign misses are light users who were less aware to begin with. Raw recall lift runs 3.9pp above the all-reached truth; weighted, 0.4pp.

## Day 2 — conversion lift, geo test, tracker, comparison (2026-11-02)

**6. The platform's credited ROAS inside the conversion lift came out at 1.34, above the platform's own report (1.07).**
The readout scaled credited orders up by one over the pixel match rate, as it does for the lift itself. But the platform can only credit orders its pixel matched; there is nothing to scale. Removed the scaling. Credited orders are now 3.2 times the incremental orders (3.0 on average over 40 re-runs), with an online iROAS of 0.31 against a true 0.34. Interval coverage over 40 re-runs: 92%.

**7. Going dark in half the regions buys almost no precision over 30%, and doubles the launch sales at risk.**
On weekly data with regions ranked in blocks of ten, the smallest detectable return is 0.24 with half the regions dark and 0.25 with 30%. The video withheld, and so the sales put at risk during the launch, goes from 98M to 175M KRW. The test uses 12 of 40 regions.

**8. The geo test's 95% interval covered the truth in only 78% of 40 simulated worlds.**
The error factor came from A/A tests on the 78 weeks before launch (x1.10). Launch weeks are noisier: a new line is ramping up in every region at once. Added A/A tests inside the test window itself, splitting the control regions into fake go-dark and control groups; the readout uses the wider of the two factors (x1.5 here). Coverage rose to 95-98%. Left in, the rival-launch region pushes the in-flight factor to x2.2, so the same check doubles as a contamination warning.

**9. The region diagnostic caught the rival launch in only 8% of worlds.**
A rival that takes a quarter of Zero's sales in two regions moves their total sales by about 6% over five weeks, which is inside normal regional noise. In this draw it flagged one of the two (z = -4.3 and -2.4 against a threshold of 3). Across 40 worlds, dropping flagged regions or not gives the same bias (-0.05), so the rule is: drop a region only on confirmed market news, and rely on the in-flight A/A factor for safety.

**10. A six-week geo read understates what the same spend earns.**
In truth, the video withheld in the test would have returned 0.74 within the six weeks, 0.94 including two more weeks, and 1.33 by week 104: awareness built in a launch keeps selling. The readout found 0.62 and 0.77. The plan already scheduled a second read at week 90; the payback verdict comes from the MMM calibrated to that read, not from the window.

**11. The MMM gave launch video five times the true return before any fix (ROI 5.60 vs 1.89).**
Two causes. Video ran every week from the day Zero reached shelves, so the model could not tell the line's own growth (stores stocking it, repeat buyers) from advertising. And online video went on and off in the same weeks as short video, so the two could not be told apart. Changed the media plan to what an agency would do after a launch flight: alternate heavy and light two-week blocks, with the two video channels out of phase. Added a distribution term (share of stores stocking Zero, which the advertiser knows) and a simple linear maturity term for the new line. Uncalibrated video ROI fell to 3.85; calibrated to 2.79, true 2.07, still outside the interval.

**12. Single-channel truth was the wrong yardstick for the two video channels.**
Short video and online video build one stock of awareness, and that stock saturates. Removing either alone loses less than its share, so single-channel returns do not add up. Added a joint truth (both removed). The calibrated model sizes the two together at 2.13 [1.81, 2.51] against a true 2.01; the uncalibrated model says 2.91 [2.40, 3.53], outside. Calibration fixed the size of video; no model here can split it between the two channels, and the readout says so instead of reporting the split.

**13. Before-launch video (Original line) is also over-credited (2.41 vs 0.91, outside the interval).**
Its bursts were small, about 2% of weekly sales against 1.3% fit error, and no experiment covered that period. Reported as a known miss; no decision in this lab uses it.

**Result (final world).** On video, seven instruments answer different questions. The platform credits 2.2 times the online orders video adds. Conversion lift (0.70) and the geo test's online part (0.68) agree, from people and from regions, against a true 0.73. Stores more than double the return (1.68 in the window, true 1.92), the two-week cooldown adds more (2.27, true 2.62), and over the half year the calibrated model puts both video channels at 4.50 [3.93, 5.12] (true 4.14). The vendor tracker moved +3.0pp between weeks 79 and 83, below the 5.7pp it needs to read a change, and in truth only 1.1pp of it came from the ads.

## Day 3 — readout, product memo, page (2026-11-02)

**14. The first readout said "the launch video pays back" on a sales return of 2.1.**
Sales in this lab are shelf value. FIZLY keeps roughly 60% of shelf price after the retailer and about half of that after cost of goods, so a won of shelf sales is worth about 0.30 won of contribution, and break-even is a sales return of 3.3, not 1.0. Rewrote the bottom line: within the half year the launch video does not pay back in profit; it does only if the awareness it built earns another 56% after week 104. The same correction turned "hold search and retail media" into "cut them": their model intervals reach 1.4-1.6, under the online break-even of 2.2 (45% contribution), so the decision is clear even though the estimates are not. The margins are labelled as assumptions for FIZLY to confirm.

**15. The model over-states the return of sustain video.**
Asked what halving video after the flight would lose, the calibrated MMM says 1.7 won of sales per won saved (90%: 1.5-1.9); the true world says 1.2. Both sit far below break-even, so the recommendation (step sustain video down, measured by a geo test in Q1) holds, and the Q1 test is there to measure the number the model gets wrong.

## Day 4 — review against the job: rescaled world, calibration fix (2026-11-02)

**16. The first world was mis-specified: FIZLY spent 15% of sales on media and nothing paid back.**
A review of entry 14's conclusion asked the obvious question: what drinks brand spends 15% of sales on media at returns below break-even in every channel? None would. That was the world's set-up, not a finding. Halved the media budget (now 7.7% of sales) and let video build awareness a little faster (saturation level 0.6 to 0.7, half-saturation spend 4 to 3, Zero's potential sales 46 to 52), then re-ran every chapter from the design step on. No estimator changed. What held: the platform over-credits online orders (2.2x), online-only reads understate video, respondents skew heavy, the launch confounds the MMM, pre-launch A/A tests are too narrow for launch weeks. What changed: launch video now pays back in profit (4.5 against a break-even of 3.3), search and retail media still do not, and sustain video sits near break-even.

**17. Calibration scored the geo test as a national top-up, which forced the model's video return up.**
On the rescaled world the calibrated model put both video channels at 4.86, outside its interval (true 4.14), while its predicted geo-test loss sat above the measured one. The calibration term added the withheld budget on top of national spend. But the test switched video off completely in 29% of the market: on a saturating curve, going from the planned level to zero loses far more than the same money added at the margin. To match the measured loss through the wrong counterfactual, the model had to inflate video's return. Rewrote the term as "29% of the market falls from the planned level to zero" (with its own carry-over path). Calibrated: 4.50 [3.93, 5.12], true 4.14. Uncalibrated: 6.28, outside.

**18. On sustain video the model says "hold" where the truth says "step down".**
Halving sustain video would lose 3.7 won of sales per won saved according to the model (90%: 3.3-4.1); the true world says 3.0, below the 3.3 break-even. Because the model's interval touches break-even, the readout calls it "near the edge" and recommends a step-down geo test in Q1 rather than a cut. That test is exactly what would find the true number. Short video alone (5.97 vs 4.48) and before-launch video (3.64 vs 1.14) also miss; neither drives a decision.
