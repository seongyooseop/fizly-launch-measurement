"""User-level layer of the FIZLY world: who is on the video platform, who sees
the ads, and what each person would answer or buy with and without them.

Every person carries fixed random draws, so both potential outcomes (shown the
ads / not shown) are known exactly. Lift studies only see what a real study
would see: the answers of the people who responded, by group.

Simulated people stand for WEIGHT real people each.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from world import N_GEO, World

WEIGHT = 5                 # real people per simulated person
N_PLATFORM = 1_800_000     # platform users aged 18-44 (the campaign's audience)
N_OFFPLATFORM = 1_200_000  # adults 18-44 not reachable on the platform
CPM = 9_000                # KRW per 1,000 impressions
USER_SEED = 4242

METRICS = ["ad_recall", "awareness", "consideration", "purchase_intent"]
# baseline (no ads) share answering yes, and how strongly it rises with the
# latent "trend" score u (heavy platform users score higher)
BASE = {"ad_recall": (0.08, 0.3), "awareness": (0.18, 0.5),
        "consideration": (0.10, 0.6), "purchase_intent": (0.06, 0.7)}
# logit shift at saturating frequency; g(f) = 1 - exp(-f / F_HALF)
EFFECT = {"ad_recall": 1.60, "awareness": 0.50, "consideration": 0.22, "purchase_intent": 0.16}
F_HALF = 3.0
# two creatives: A opens on the product in the first second, B on a lifestyle scene
CREATIVE = {"A": {"ad_recall": 1.15, "awareness": 1.12, "consideration": 1.00, "purchase_intent": 1.05},
            "B": {"ad_recall": 0.85, "awareness": 0.88, "consideration": 1.00, "purchase_intent": 0.95}}
SURVEY_RATE = 0.012        # poll answered per unit of heaviness (heavy users answer more)


def logit(p):
    return np.log(p / (1 - p))


def expit(z):
    return 1 / (1 + np.exp(-z))


@dataclass
class People:
    geo: np.ndarray
    on_platform: np.ndarray
    heavy: np.ndarray      # daily sessions relative to the average user (0 off-platform)
    u: np.ndarray          # latent trend score
    draws: dict            # metric -> uniform draw, fixed per person


def make_people(world: World, seed: int = USER_SEED) -> People:
    rng = np.random.default_rng(seed)
    n = N_PLATFORM + N_OFFPLATFORM
    geo = rng.choice(N_GEO, size=n, p=world.share)
    on = np.zeros(n, bool)
    on[:N_PLATFORM] = True
    z = rng.normal(0, 1, n)
    log_h = 0.9 * z - 0.9 ** 2 / 2          # mean heaviness 1
    heavy = np.where(on, np.exp(log_h), 0.0)
    u = np.where(on, 0.5 * z + np.sqrt(1 - 0.25) * rng.normal(0, 1, n),
                 rng.normal(-0.3, 1, n))
    draws = {m: rng.random(n) for m in METRICS + ["purchase", "respond", "question", "creative", "click"]}
    return People(geo, on, heavy, u, draws)


def impressions(people: People, spend_by_geo: np.ndarray, seed: int) -> np.ndarray:
    """Ad impressions per person over a flight, from spend (KRW per geo, whole
    flight). Delivery follows heaviness: heavy users see more ads."""
    rng = np.random.default_rng(seed)
    real_imps = spend_by_geo / CPM * 1000
    sim_imps = real_imps / WEIGHT
    w = people.heavy
    per_geo_w = np.bincount(people.geo, weights=w, minlength=N_GEO)
    lam = sim_imps[people.geo] * w / np.maximum(per_geo_w[people.geo], 1e-9)
    return rng.poisson(lam)


def p_answer(people: People, metric: str, freq: np.ndarray, creative: np.ndarray | None) -> np.ndarray:
    base, slope = BASE[metric]
    z = logit(base) + slope * people.u
    g = 1 - np.exp(-freq / F_HALF)
    mult = 1.0 if creative is None else np.where(creative == "A", CREATIVE["A"][metric], CREATIVE["B"][metric])
    return expit(z + EFFECT[metric] * g * mult)


@dataclass
class BrandLiftRun:
    test: np.ndarray        # True = could be shown ads; False = holdout (control)
    freq: np.ndarray        # impressions delivered (test) or that would have been (control)
    creative: np.ndarray    # "A" / "B" for test users
    responded: np.ndarray
    question: np.ndarray    # which metric each respondent was asked (one question each)
    answer: np.ndarray      # observed yes/no
    true_yes1: dict         # metric -> P(yes | shown) per person
    true_yes0: dict         # metric -> P(yes | not shown) per person


def run_brand_lift(people: People, spend_by_geo: np.ndarray, control_share: float,
                   seed: int = 101) -> BrandLiftRun:
    """A randomized brand lift survey: platform users are split into test and
    holdout before the flight; polls go to people who were (or, in the holdout,
    would have been) served the ad; each respondent answers one question."""
    rng = np.random.default_rng(seed)
    on = people.on_platform
    test = on & (rng.random(len(on)) >= control_share)
    freq = np.where(on, impressions(people, spend_by_geo, seed + 1), 0)
    creative = np.where(people.draws["creative"] < 0.5, "A", "B")
    # poll chance grows with time spent on the platform
    p_resp = 1 - np.exp(-SURVEY_RATE * people.heavy)
    responded = on & (people.draws["respond"] < p_resp)
    question = np.array(METRICS)[np.minimum((people.draws["question"] * 4).astype(int), 3)]
    shown = np.where(test, freq, 0)
    yes1, yes0, answer = {}, {}, np.zeros(len(on), bool)
    for m in METRICS:
        p1 = p_answer(people, m, freq, creative)
        p0 = p_answer(people, m, np.zeros_like(freq), None)
        yes1[m], yes0[m] = p1, p0
        p_obs = np.where(shown > 0, p1, p0)
        answer |= (question == m) & (people.draws[m] < p_obs)
    return BrandLiftRun(test, freq, creative, responded, question, answer, yes1, yes0)


# ------------------------------------------------------------------ conversion lift
AOV_ONLINE = 16_000        # KRW per online order (a multi-can pack)
PIXEL_MATCH = 0.75         # share of online orders the brand's pixel / events can match to a user
PURCHASE_U = 0.6           # trend-score slope of the chance to buy online


def solve(f, lo, hi, n=60):
    """Bisection for an increasing f with f(lo) < 0 < f(hi)."""
    for _ in range(n):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    return (lo + hi) / 2


@dataclass
class ConversionLiftRun:
    test: np.ndarray
    eligible: np.ndarray       # platform users in regions where the campaign ran
    freq: np.ndarray
    orders_obs: np.ndarray     # orders the pixel matched (what the study counts)
    attributed: np.ndarray     # orders the platform credits to an ad (click 7d / view 1d)
    true_incr_expected: float  # expected incremental orders in the test group (all orders, not only matched)
    true_incr_realized: float
    params: dict


def run_conversion_lift(people: People, spend_by_geo: np.ndarray, holdout_share: float,
                        base_orders: float, incr_orders: float, attributed_orders: float,
                        seed: int = 202) -> ConversionLiftRun:
    """User-level holdout on online orders. The world (world.py) fixes how many
    orders platform users place without ads (base_orders), how many the ads
    add (incr_orders) and how many the platform credits (attributed_orders),
    all for the whole audience; this layer spreads them across people.
    Each simulated person stands for WEIGHT people, so orders are binomial."""
    rng = np.random.default_rng(seed)
    eligible = people.on_platform & (spend_by_geo[people.geo] > 0)
    test = eligible & (rng.random(len(eligible)) >= holdout_share)
    freq = np.where(eligible, impressions(people, spend_by_geo, seed + 1), 0)
    g = 1 - np.exp(-freq / F_HALF)
    z0 = PURCHASE_U * people.u
    # baseline level: expected orders without ads match the world
    b = solve(lambda c: WEIGHT * expit(c + z0[eligible]).sum() - base_orders, -15, 0)
    p0 = np.where(eligible, expit(b + z0), 0.0)
    # effect size: expected incremental orders if everyone eligible were shown ads
    e = solve(lambda k: WEIGHT * (expit(b + z0[eligible] + k * g[eligible]) - p0[eligible]).sum() - incr_orders, 0, 5)
    p1 = np.where(eligible, expit(b + z0 + e * g), 0.0)
    # orders: K0 without ads; ads add extra buyers among the rest (exact coupling)
    k0 = rng.binomial(WEIGHT, p0)
    extra = rng.binomial(WEIGHT - k0, np.clip((p1 - p0) / np.maximum(1 - p0, 1e-12), 0, 1))
    k = np.where(test, k0 + extra, k0)
    orders_obs = rng.binomial(k, PIXEL_MATCH)
    # platform credit: a matched order by someone shown ads, more likely the more ads they saw
    shown = test & (freq > 0)
    reach_w = np.where(shown, 1 - np.exp(-freq / 2.0), 0.0)
    exp_matched_shown = (WEIGHT * PIXEL_MATCH * p1 * reach_w).sum()
    a = min(attributed_orders * (1 - holdout_share) / max(exp_matched_shown, 1e-9), 1.0)
    attributed = rng.binomial(orders_obs, np.where(shown, a * (1 - np.exp(-freq / 2.0)), 0.0))
    true_exp = WEIGHT * (p1 - p0)[test].sum()
    return ConversionLiftRun(test, eligible, freq, orders_obs, attributed, float(true_exp),
                             float(extra[test].sum()), {"base_logit": b, "effect": e, "attr_scale": a})


# ------------------------------------------------------------------ 3P brand tracker
TRACKER_SHIFT = -0.35      # aided awareness from a long brand list reads lower than an in-feed poll
TRACKER_RETENTION = 0.93   # weekly memory of ads seen
PANEL_SKEW = 0.5           # online panels under-recruit heavy platform users: weight (1 + heavy)^-0.5


def tracker_waves(people: People, weekly_spend: np.ndarray, weeks: np.ndarray, organic: np.ndarray,
                  waves: list[int], n_per_wave: int = 1000, seed: int = 303) -> list[dict]:
    """Monthly brand tracker by an independent research vendor: a fresh panel
    sample of adults 18-44 each wave (on and off the platform), asked aided
    awareness of FIZLY Zero. weekly_spend is (weeks, geos) of video spend for the
    weeks in `weeks`; organic is the awareness the launch earns without ads."""
    rng = np.random.default_rng(seed)
    stock = np.zeros(len(people.geo))
    sel = (1 + people.heavy) ** -PANEL_SKEW
    sel = sel / sel.sum()
    base_slope = BASE["awareness"][1]
    out = []
    for i, wk in enumerate(weeks):
        if weekly_spend[i].sum() > 0:
            stock = TRACKER_RETENTION * stock + impressions(people, weekly_spend[i], seed + 1000 + int(wk))
        else:
            stock = TRACKER_RETENTION * stock
        if wk not in waves:
            continue
        org = max(organic[i], 0.02)  # a few people always "recognize" a new name
        z0 = logit(org) + TRACKER_SHIFT + base_slope * (people.u - people.u.mean())
        p0 = expit(z0)
        p1 = expit(z0 + EFFECT["awareness"] * (1 - np.exp(-stock / F_HALF)))
        sample = rng.choice(len(people.geo), size=n_per_wave, replace=False, p=sel)
        yes = rng.random(n_per_wave) < p1[sample]
        est = yes.mean()
        se = np.sqrt(est * (1 - est) / n_per_wave)
        on = people.on_platform
        out.append({"week": int(wk), "estimate": float(est), "lo": float(est - 1.96 * se), "hi": float(est + 1.96 * se),
                    "truth_population": float(p1.mean()), "truth_without_ads": float(p0.mean()),
                    "truth_platform_users": float(p1[on].mean()), "truth_panel_frame": float((sel * p1).sum()),
                    "reached_share": float((stock[on] > 0).mean())})
    return out
