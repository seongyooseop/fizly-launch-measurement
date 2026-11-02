"""Chapter 1: brand lift survey on the video platform (weeks 79-82).

Design first (before the flight): how many answers each question will get,
the smallest lift each can detect under different holdout sizes, and which
metrics can carry a decision. Then the readout: lift per metric with 95%
intervals, creative A vs B, lift by frequency, and the naive comparison an
advertiser often sees (people who saw the ad vs people who did not).

Every estimate is set against the truth: the average effect of the ads on the
same people, known exactly from each person's two potential answers.

    python src/ch1_brand_lift.py          # design + readout
    python src/ch1_brand_lift.py --mc 40  # + 40 re-runs (new random holdout and answers)
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import stats

from users import CPM, METRICS, WEIGHT, make_people, run_brand_lift, SURVEY_RATE
from world import BRAND_LIFT_WEEKS, World, actual_plan, week_mask

OUT = Path(__file__).resolve().parents[1] / "outputs"
Z = stats.norm.ppf(0.975)
Z_POWER = stats.norm.ppf(0.80)

# Planning assumptions for the design, taken before any data: typical "yes"
# rates among unexposed respondents for a new drink in its first month.
PLAN_BASE = {"ad_recall": 0.10, "awareness": 0.20, "consideration": 0.13, "purchase_intent": 0.07}
CONTROL_SHARE = 0.20  # chosen in the design step below
LABEL = {"ad_recall": "Ad recall", "awareness": "Aided awareness",
         "consideration": "Consideration", "purchase_intent": "Purchase intent"}


def mde(p: float, n_test: float, n_ctrl: float) -> float:
    """Smallest absolute lift detectable at 80% power, 5% two-sided."""
    return (Z + Z_POWER) * np.sqrt(p * (1 - p) * (1 / n_test + 1 / n_ctrl))


def expected_answers(people, spend_by_geo, control_share):
    """Poll answers per question the platform can forecast before launch:
    reach comes from delivery, response from time spent; no outcomes used."""
    run = run_brand_lift(people, spend_by_geo, control_share, seed=7)
    reached = run.freq > 0
    p_resp = 1 - np.exp(-SURVEY_RATE * people.heavy)
    n_test = (p_resp * (run.test & reached)).sum() / 4
    n_ctrl = (p_resp * (~run.test & people.on_platform & reached)).sum() / 4
    return n_test, n_ctrl


def lift(a_yes, a_n, b_yes, b_n):
    pa, pb = a_yes / a_n, b_yes / b_n
    se = np.sqrt(pa * (1 - pa) / a_n + pb * (1 - pb) / b_n)
    d = pa - pb
    return {"exposed": pa, "control": pb, "lift": d, "lo": d - Z * se, "hi": d + Z * se,
            "rel": d / pb, "p": 2 * (1 - stats.norm.cdf(abs(d) / se)), "n_exposed": int(a_n), "n_control": int(b_n)}


def weighted_lift(y, wts, a, b):
    """Difference of weighted yes-rates with Kish effective sample sizes."""
    out = {}
    for k, m in (("a", a), ("b", b)):
        ww = wts[m]
        p = np.average(y[m], weights=ww)
        n_eff = ww.sum() ** 2 / (ww ** 2).sum()
        out[k] = (p, n_eff)
    (pa, na), (pb, nb) = out["a"], out["b"]
    d = pa - pb
    se = np.sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb)
    return {"lift": d, "lo": d - Z * se, "hi": d + Z * se, "n_eff_exposed": na, "n_eff_control": nb}


def readout(run, people):
    on = people.on_platform
    exp_t = run.test & (run.freq > 0) & run.responded
    ctl = on & ~run.test & (run.freq > 0) & run.responded       # would-have-been-exposed holdout
    unexp = run.test & (run.freq == 0) & run.responded
    exposed_all = run.test & (run.freq > 0)
    res = {}
    for m in METRICS:
        q = run.question == m
        r = lift(run.answer[exp_t & q].sum(), (exp_t & q).sum(), run.answer[ctl & q].sum(), (ctl & q).sum())
        eff = run.true_yes1[m] - run.true_yes0[m]
        r["truth_respondents"] = float(eff[exp_t].mean())   # same kind of people who answered
        r["truth_all_exposed"] = float(eff[exposed_all].mean())
        # Respondents are heavy users (they see more polls and more ads), so the
        # raw lift describes them, not everyone reached. The platform knows each
        # person's poll chance from time spent: weight answers by 1 / that chance.
        p_poll = 1 - np.exp(-SURVEY_RATE * people.heavy)
        wts = np.divide(1.0, p_poll, out=np.zeros_like(p_poll), where=p_poll > 0)
        r["weighted"] = weighted_lift(run.answer, wts, exp_t & q, ctl & q)
        # naive: people who saw the ad vs test-group people the ad never reached
        r["naive"] = lift(run.answer[exp_t & q].sum(), (exp_t & q).sum(),
                          run.answer[unexp & q].sum(), (unexp & q).sum())["lift"]
        # creatives (users were split 50/50 between A and B)
        r["creative"] = {}
        for c in ["A", "B"]:
            cm = exp_t & q & (run.creative == c)
            cr = lift(run.answer[cm].sum(), cm.sum(), run.answer[ctl & q].sum(), (ctl & q).sum())
            # truth: everyone in the exposed group shown creative c
            from users import p_answer
            p1c = p_answer(people, m, run.freq, np.full(len(run.freq), c))
            cr["truth"] = float((p1c - run.true_yes0[m])[exp_t].mean())
            r["creative"][c] = cr
        a, b = r["creative"]["A"], r["creative"]["B"]
        diff = a["exposed"] - b["exposed"]
        se = np.sqrt(a["exposed"] * (1 - a["exposed"]) / a["n_exposed"] + b["exposed"] * (1 - b["exposed"]) / b["n_exposed"])
        r["creative_diff"] = {"diff": diff, "lo": diff - Z * se, "hi": diff + Z * se,
                              "p": 2 * (1 - stats.norm.cdf(abs(diff) / se)), "truth": a["truth"] - b["truth"]}
        # frequency: compare each exposed bucket with holdout people who would
        # have seen the same number of ads (right) vs with the whole holdout (naive)
        r["frequency"] = []
        for lo_f, hi_f, lab in [(1, 1, "1"), (2, 3, "2-3"), (4, 6, "4-6"), (7, 10_000, "7+")]:
            band = (run.freq >= lo_f) & (run.freq <= hi_f)
            e = exp_t & q & band
            cb = ctl & q & band
            right = lift(run.answer[e].sum(), e.sum(), run.answer[cb].sum(), cb.sum())
            naive_f = run.answer[e].mean() - run.answer[ctl & q].mean()
            r["frequency"].append({"band": lab, "lift": right["lift"], "lo": right["lo"], "hi": right["hi"],
                                   "naive": naive_f, "truth": float(eff[exp_t & band].mean()),
                                   "n_exposed": int(e.sum())})
        res[m] = r
    return res


def main(mc: int):
    w = World()
    plan = actual_plan(w)
    t = week_mask(w, *BRAND_LIFT_WEEKS)
    spend = plan.spend["short_video"][t].sum(axis=0)
    people = make_people(w)

    # ---------------- design
    design = []
    for share in [0.10, 0.20, 0.30]:
        nt, nc = expected_answers(people, spend, share)
        row = {"control_share": share, "answers_test": nt, "answers_control": nc}
        for m in METRICS:
            row[m] = mde(PLAN_BASE[m], nt, nc)
            row[m + "_per_creative"] = mde(PLAN_BASE[m], nt / 2, nc)
        design.append(row)
    budget = []
    for mult in [0.5, 1.0, 2.0]:
        nt, nc = expected_answers(people, spend * mult, CONTROL_SHARE)
        budget.append({"spend_m": spend.sum() * mult / 1e6, "answers_test": nt, "answers_control": nc,
                       **{m: mde(PLAN_BASE[m], nt, nc) for m in METRICS}})
    print(f"Flight spend {spend.sum() / 1e6:,.0f}M KRW (weeks {BRAND_LIFT_WEEKS[0]}-{BRAND_LIFT_WEEKS[1]})")
    print("Design: minimum detectable lift (percentage points), one question per respondent")
    for r in design:
        print(f"  holdout {r['control_share']:.0%}: answers/question test {r['answers_test']:,.0f} "
              f"control {r['answers_control']:,.0f} | " +
              " ".join(f"{m[:6]} {100 * r[m]:.1f}" for m in METRICS))

    # ---------------- readout
    run = run_brand_lift(people, spend, CONTROL_SHARE, seed=101)
    res = readout(run, people)
    reached = run.freq[people.on_platform] > 0
    real_reached = (run.test & (run.freq > 0)).sum() * WEIGHT
    print(f"\nReach {reached.mean():.0%} of platform users, average frequency "
          f"{run.freq[people.on_platform][reached].mean():.1f}")
    print("Readout (pp): lift [95% CI] vs truth for respondents | naive exposed-vs-unexposed")
    for m in METRICS:
        r = res[m]
        print(f"  {m:16s} {100 * r['control']:5.1f}% -> {100 * r['exposed']:5.1f}%  lift {100 * r['lift']:+5.1f} "
              f"[{100 * r['lo']:+5.1f}, {100 * r['hi']:+5.1f}] p={r['p']:.3f} | truth {100 * r['truth_respondents']:+5.1f} "
              f"(all exposed {100 * r['truth_all_exposed']:+5.1f}) | naive {100 * r['naive']:+5.1f}")
    print("Creative A - B, exposed rate difference (pp):")
    for m in METRICS:
        d = res[m]["creative_diff"]
        print(f"  {m:16s} {100 * d['diff']:+5.1f} [{100 * d['lo']:+5.1f}, {100 * d['hi']:+5.1f}] p={d['p']:.3f} truth {100 * d['truth']:+5.1f}")
    print("Awareness lift by frequency (pp): matched holdout | naive | truth")
    for f in res["awareness"]["frequency"]:
        print(f"  {f['band']:>3s}: {100 * f['lift']:+5.1f} [{100 * f['lo']:+5.1f}, {100 * f['hi']:+5.1f}] | "
              f"{100 * f['naive']:+5.1f} | {100 * f['truth']:+5.1f}  (n={f['n_exposed']})")
    print("Weighted to everyone reached (pp): lift [95% CI] vs truth for all exposed")
    for m in METRICS:
        r = res[m]["weighted"]
        print(f"  {m:16s} {100 * r['lift']:+5.1f} [{100 * r['lo']:+5.1f}, {100 * r['hi']:+5.1f}] "
              f"truth {100 * res[m]['truth_all_exposed']:+5.1f}")
    # cost per lifted person uses the lift for everyone reached, not the heavy-user respondents
    cost = {m: spend.sum() / max(res[m]["weighted"]["lift"] * real_reached, 1) for m in ["ad_recall", "awareness"]}
    print(f"Cost per extra person recalling the ad: KRW {cost['ad_recall']:,.0f}; per newly aware person: KRW {cost['awareness']:,.0f}")

    out = {"spend_m": spend.sum() / 1e6, "cpm": CPM, "control_share": CONTROL_SHARE,
           "plan_base": PLAN_BASE, "design": design, "budget": budget,
           "reach": float(reached.mean()), "avg_freq": float(run.freq[people.on_platform][reached].mean()),
           "real_reached": int(real_reached), "readout": res, "cost_per_lifted": cost}

    # ---------------- Monte Carlo: same flight, a fresh draw of people, holdout and answers
    if mc:
        rows = []
        for k in range(mc):
            pk = make_people(w, seed=5000 + k)
            rk = run_brand_lift(pk, spend, CONTROL_SHARE, seed=900 + k)
            rr = readout(rk, pk)
            wl = {m: rr[m]["weighted"] for m in METRICS}
            fp = sum(rr[m]["creative_diff"]["p"] < 0.05 for m in ["consideration", "purchase_intent"])
            rows.append({m: (rr[m]["lift"], rr[m]["lo"], rr[m]["hi"], rr[m]["truth_respondents"],
                             rr[m]["p"], rr[m]["naive"], wl[m]["lift"], wl[m]["lo"], wl[m]["hi"],
                             rr[m]["truth_all_exposed"], fp) for m in METRICS})
        summ = {}
        for m in METRICS:
            a = np.array([r[m] for r in rows])
            summ[m] = {"bias_pp": float(100 * (a[:, 0] - a[:, 3]).mean()),
                       "coverage": float(((a[:, 1] <= a[:, 3]) & (a[:, 3] <= a[:, 2])).mean()),
                       "detected": float((a[:, 4] < 0.05).mean()),
                       "naive_bias_pp": float(100 * (a[:, 5] - a[:, 3]).mean()),
                       "weighted_bias_pp": float(100 * (a[:, 6] - a[:, 9]).mean()),
                       "weighted_coverage": float(((a[:, 7] <= a[:, 9]) & (a[:, 9] <= a[:, 8])).mean()),
                       "raw_vs_all_exposed_pp": float(100 * (a[:, 0] - a[:, 9]).mean())}
        # creative "differences" on metrics where A and B truly match (consideration, intent)
        summ["creative_false_alarm"] = float(np.mean([r["consideration"][10] > 0 for r in rows]))
        print(f"\nMonte Carlo ({mc} runs): bias, 95% CI coverage, share significant, naive bias")
        for m in METRICS:
            s = summ[m]
            print(f"  {m:16s} bias {s['bias_pp']:+.2f}pp  coverage {s['coverage']:.0%}  "
                  f"significant {s['detected']:.0%}  naive bias {s['naive_bias_pp']:+.1f}pp | "
                  f"raw vs all-exposed {s['raw_vs_all_exposed_pp']:+.1f}pp, weighted bias {s['weighted_bias_pp']:+.2f}pp "
                  f"coverage {s['weighted_coverage']:.0%}")
        print(f"  runs where creative A and B 'differ' on consideration or intent (truly equal): "
              f"{summ['creative_false_alarm']:.0%}")
        out["montecarlo"] = {"runs": mc, **summ}

    OUT.mkdir(exist_ok=True)
    (OUT / "ch1_brand_lift.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", type=int, default=0)
    main(ap.parse_args().mc)
