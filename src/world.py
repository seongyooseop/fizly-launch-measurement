"""FIZLY world: the true sales process behind every chapter.

FIZLY is a fictional Korean sparkling-drink brand. Its Original line has sold
for 78 weeks; in week 79 it launches FIZLY Zero, a zero-sugar line, with a
heavy short-form video campaign. About three quarters of sales happen in
convenience stores and supermarkets (seen only through a weekly retail
sell-out panel); the rest online (own mall + marketplace, tracked by pixel).

As in a lab, all random noise is drawn once when the World is built, so
simulate(plan) is deterministic: the same world under two plans gives the exact
counterfactual. Analysis scripts read only the observed tables; truth tables go
to data/truth/ and are read only by validation steps.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

START = pd.Timestamp("2024-11-04")  # a Monday; week 79 starts 2026-05-04
N_DAYS = 728                        # 104 weeks
N_GEO = 40
WORLD_SEED = 20261101
PLAN_SEED = 11

CHANNELS = ["short_video", "online_video", "social", "search", "retail_media"]
# The media plan below is written at a reference level; SPEND_SCALE sets the
# real budget. At 0.5 FIZLY spends about 8% of sales on media, typical for a
# drinks brand in a launch year (the first world spent 15%; see the work log).
SPEND_SCALE = 0.5
FLIGHT_VIDEO_M = 8.0 * SPEND_SCALE  # launch-flight short video, M KRW/day nationally

# Timeline (1-based weeks)
HISTORY_WEEKS = 78
LAUNCH_WEEK = 79                 # FIZLY Zero goes on shelf and the launch flight starts
LAUNCH_FLIGHT = (79, 90)         # heavy video flight
BRAND_LIFT_WEEKS = (79, 82)      # chapter 1: brand lift survey on the video platform
CONVERSION_LIFT_WEEKS = (83, 88) # chapter 2: user-level holdout, online purchases
GEO_TEST_WEEKS = (83, 88)        # chapter 3: video off in some regions (offline + online)
COMPETITOR_WEEKS = (84, 88)      # trap 5: a rival zero-sugar launch in a few regions
COMPETITOR_HIT = 0.75            # Zero sales x0.75 where the rival launched

# True response. Spend is in million KRW per day at national-equivalent level
# (geo spend / geo share), so one curve fits every region.
TRUE = {
    "original_rev": 52.0,       # Original line, M KRW/day nationally, no ads
    "original_online": 0.20,    # online share of Original sales
    "zero_potential": 52.0,     # Zero sales at full awareness and full distribution
    "zero_online": 0.25,        # online share of awareness-driven Zero sales
    "growth": 0.04,             # yearly category growth
    "temp_beta": 0.025,         # sales +2.5% per degree C above 20
    # Zero awareness: organic (shelf, word of mouth) + paid (video builds it)
    "aw_organic": (0.10, 0.10, 60.0),  # start, extra at saturation, days to ~63%
    "aw_paid": {"K": 3.0, "slope": 1.2, "decay": 0.97, "max": 0.70,
                "online_video_weight": 0.6},
    "distribution": 28.0,       # days to ~63% of stores stocking Zero
    # direct online response (click-to-buy), online sales only
    "short_video_dr": {"beta": 2.4, "K": 3.0, "slope": 1.0, "decay": 0.6},
    "social": {"beta": 2.0, "K": 1.5, "slope": 1.0, "decay": 0.6},
    "search": {"beta": 2.2, "K": 1.5, "slope": 1.0, "decay": 0.3},
    "retail_media": {"beta": 1.6, "K": 1.5, "slope": 1.0, "decay": 0.2},
    # a small direct lift on the Original line from video and search
    "original_video": {"beta": 1.5, "K": 2.0, "slope": 1.0, "decay": 0.8},
    # brand searches per day nationally; awareness lifts them (trap 6: halo)
    "brand_searches": 9_000, "search_halo": 1.5,
}

# How the platforms report (each counts only what its own pixel or click sees).
REPORTED = {
    "video_online_credit": 0.95,  # share of video's true online lift it credits
    "video_view_capture": 0.50,   # online buyers who saw an ad within 1 day (view-through)
    "search_halo_capture": 0.70,  # searches video created, credited to search
    "search_over": 1.25,
    "retail_media_base_capture": 0.18,  # marketplace buyers who would buy anyway
    "social_over": 1.10,
}


def hill(x: np.ndarray, K: float, slope: float) -> np.ndarray:
    x = np.maximum(x, 0.0)
    xs = x ** slope
    return xs / (xs + K ** slope)


def adstock(x: np.ndarray, decay: float) -> np.ndarray:
    """Normalized geometric carry-over along axis 0 (days)."""
    if decay == 0:
        return x.copy()
    out = np.empty_like(x)
    out[0] = x[0]
    for t in range(1, len(x)):
        out[t] = decay * out[t - 1] + (1 - decay) * x[t]
    return out


@dataclass
class Plan:
    """Daily spend (KRW) per channel and geo, plus geo-day demand shocks."""
    spend: dict[str, np.ndarray]
    shock: np.ndarray = field(default=None)  # (days, geos) multiplier on Zero sales

    def copy(self) -> "Plan":
        return Plan({c: s.copy() for c, s in self.spend.items()},
                    None if self.shock is None else self.shock.copy())


class World:
    def __init__(self, seed: int = WORLD_SEED, noise_seed: int | None = None):
        """noise_seed keeps the regions and redraws only the noise (Monte Carlo)."""
        rng = np.random.default_rng(seed)
        self.dates = pd.date_range(START, periods=N_DAYS, freq="D")
        self.week = np.arange(N_DAYS) // 7 + 1
        self.geo_ids = [f"R{i + 1:02d}" for i in range(N_GEO)]
        pop = rng.lognormal(0.0, 0.7, N_GEO)
        self.share = pop / pop.sum()
        self.geo_eff = rng.uniform(0.85, 1.15, N_GEO)
        self.geo_temp = rng.normal(0.0, 1.5, N_GEO)        # warmer / cooler regions
        self.geo_online = np.clip(rng.normal(1.0, 0.15, N_GEO), 0.6, 1.4)  # online habit
        if noise_seed is not None:
            rng = np.random.default_rng(noise_seed)
        eps = rng.normal(0.0, 0.035, (N_DAYS, N_GEO))
        ar = np.zeros_like(eps)
        for t in range(1, N_DAYS):
            ar[t] = 0.7 * ar[t - 1] + eps[t]
        self.off_noise = ar + rng.normal(0.0, 0.06, (N_DAYS, N_GEO))
        self.on_noise = 0.6 * ar + rng.normal(0.0, 0.10, (N_DAYS, N_GEO))
        self.temp_noise = rng.normal(0.0, 2.5, (N_DAYS, N_GEO))
        self.bsv_noise = rng.normal(0.0, 0.10, (N_DAYS, N_GEO))
        self.temp = self._temperature()
        self.demand = self._demand_curve()

    # ---------------------------------------------------------------- demand
    def _temperature(self) -> np.ndarray:
        doy = self.dates.dayofyear.values
        seasonal = 13.0 - 13.0 * np.cos(2 * np.pi * (doy - 15) / 365)  # ~0C Jan, ~26C Jul
        t = seasonal[:, None] + self.geo_temp[None, :] + self.temp_noise
        return t

    def _demand_curve(self) -> np.ndarray:
        dow = np.array([0.95, 0.96, 0.97, 0.99, 1.05, 1.06, 1.02])[self.dates.dayofweek.values]
        years = np.arange(N_DAYS) / 365.0
        trend = (1 + TRUE["growth"]) ** years
        temp_mult = np.exp(TRUE["temp_beta"] * (self.temp - 20.0))
        return (dow * trend)[:, None] * temp_mult * self.geo_eff[None, :]

    def days_since_launch(self) -> np.ndarray:
        d = np.arange(N_DAYS) - (LAUNCH_WEEK - 1) * 7
        return np.where(d >= 0, d, -1)

    # ------------------------------------------------------------ components
    def zero_awareness(self, plan: Plan) -> tuple[np.ndarray, np.ndarray]:
        """(organic, total) Zero awareness per geo-day; 0 before launch."""
        sh = self.share[None, :]
        pa = TRUE["aw_paid"]
        x = (plan.spend["short_video"] + pa["online_video_weight"] * plan.spend["online_video"]) / sh / 1e6
        launched = (self.days_since_launch() >= 0)[:, None]
        x = np.where(launched, x, 0.0)  # pre-launch video advertised Original, not Zero
        paid = pa["max"] * hill(adstock(x, pa["decay"]), pa["K"], pa["slope"])
        a0, a1, tau = TRUE["aw_organic"]
        dsl = self.days_since_launch()
        organic = np.where(dsl >= 0, a0 + a1 * (1 - np.exp(-np.maximum(dsl, 0) / tau)), 0.0)
        organic = np.broadcast_to(organic[:, None], paid.shape)
        total = organic + (1 - organic) * paid
        return organic, np.where(launched, total, 0.0)

    def simulate(self, plan: Plan) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Return (observed, truth): one row per geo-day. Truth holds the parts
        of sales; per-channel effects come from counterfactual runs."""
        sh = self.share[None, :]
        x = {c: plan.spend[c] / sh / 1e6 for c in CHANNELS}
        shock = np.ones((N_DAYS, N_GEO)) if plan.shock is None else plan.shock
        trend = (1 + TRUE["growth"]) ** (np.arange(N_DAYS) / 365.0)
        scale = sh * trend[:, None]

        def resp(p, xx):
            return scale * p["beta"] * hill(adstock(xx, p["decay"]), p["K"], p["slope"])

        # Original line
        orig = TRUE["original_rev"] * sh * self.demand
        orig_video = resp(TRUE["original_video"], x["short_video"]) * self.demand / self.demand.mean()
        orig_off = (1 - TRUE["original_online"]) * orig * np.exp(self.off_noise)
        orig_on = TRUE["original_online"] * orig * self.geo_online[None, :] * np.exp(self.on_noise)

        # Zero line: awareness-driven sales, stocked as distribution builds
        _, aw = self.zero_awareness(plan)
        dsl = self.days_since_launch()
        dist = np.where(dsl >= 0, 1 - np.exp(-np.maximum(dsl, 0) / TRUE["distribution"]), 0.0)[:, None]
        zero = TRUE["zero_potential"] * sh * self.demand * dist * aw * shock
        zero_off = (1 - TRUE["zero_online"]) * zero * np.exp(self.off_noise)
        zero_on_aw = TRUE["zero_online"] * zero * self.geo_online[None, :] * np.exp(self.on_noise)

        # direct online response (Zero only after launch; Original before)
        launched = (dsl >= 0)[:, None]
        online_mult = self.geo_online[None, :] * np.exp(self.on_noise)
        dr = {c: resp(TRUE[c if c != "short_video" else "short_video_dr"], x[c]) * online_mult
              for c in ["short_video", "social", "search", "retail_media"]}
        dr_total = sum(dr.values())

        offline = orig_off + zero_off + np.where(launched, 0.0, orig_video * 0.8)
        online = orig_on + zero_on_aw + dr_total + np.where(launched, 0.0, orig_video * 0.2)

        # brand searches: Original base + Zero awareness (the halo search gets credit for)
        bsv = (TRUE["brand_searches"] * sh * self.demand
               * (1 + TRUE["search_halo"] * aw) * np.exp(self.bsv_noise))

        R = REPORTED
        zero_on_organic = zero_on_aw  # whole awareness part; video's share of it is in truth runs
        reported = {
            # view-through credit lands on online buyers of either line who
            # happened to see an ad the day before (most would have bought anyway)
            "short_video": (R["video_online_credit"] * dr["short_video"]
                            + R["video_view_capture"] * (orig_on + zero_on_organic)
                            * hill(x["short_video"], 3.0, 1.0)),
            "online_video": 0.25 * zero_on_aw * hill(x["online_video"], 3.0, 1.0),
            "social": R["social_over"] * dr["social"],
            "search": (R["search_over"] * dr["search"]
                       + R["search_halo_capture"] * zero_on_aw * TRUE["search_halo"] * aw
                       / (1 + TRUE["search_halo"] * aw) * hill(x["search"], 1.5, 1.0)),
            "retail_media": dr["retail_media"] + R["retail_media_base_capture"] * (orig_on + zero_on_aw)
                            * hill(x["retail_media"], 1.5, 1.0),
        }

        idx = pd.MultiIndex.from_product([self.dates, self.geo_ids], names=["date", "geo"])
        obs = {"week": np.repeat(self.week, N_GEO),
               "offline_rev": (offline * 1e6).ravel(),
               "online_rev": (online * 1e6).ravel(),
               "brand_search_volume": np.round(bsv.ravel()),
               "temperature": self.temp.ravel().round(1)}
        for c in CHANNELS:
            obs[f"spend_{c}"] = plan.spend[c].ravel()
            obs[f"reported_rev_{c}"] = (reported[c] * 1e6).ravel()
        observed = pd.DataFrame(obs, index=idx).reset_index()

        tr = {"week": np.repeat(self.week, N_GEO),
              "zero_awareness": aw.ravel(),
              "zero_offline": (zero_off * 1e6).ravel(),
              "zero_online": ((zero_on_aw + np.where(launched, dr_total, 0.0)) * 1e6).ravel(),
              "original_rev": ((orig_off + orig_on) * 1e6).ravel()}
        truth = pd.DataFrame(tr, index=idx).reset_index()
        return observed, truth


# ------------------------------------------------------------------- plans
def bau_plan(world: World, seed: int = PLAN_SEED) -> Plan:
    """Media plan for all 104 weeks: modest always-on before launch, a heavy
    launch flight in weeks 79-90, then sustain. Weekly levels wander so the
    MMM has variation to learn from."""
    rng = np.random.default_rng(seed)
    n_weeks = N_DAYS // 7
    wk = np.arange(1, n_weeks + 1)
    jitter = lambda s: np.clip(1 + rng.normal(0, s, n_weeks), 0.4, 1.8)

    flight = (wk >= LAUNCH_FLIGHT[0]) & (wk <= LAUNCH_FLIGHT[1])
    post = wk > LAUNCH_FLIGHT[1]
    pre = wk < LAUNCH_WEEK
    # pre-launch video runs in on/off bursts (Original line)
    bursts = (rng.random(n_weeks) < 0.55).astype(float)
    # after the flight the agency pulses video and online video in alternating
    # two-week blocks (heavy / light), so their effects can be told apart
    phase = ((wk - LAUNCH_FLIGHT[1] - 1) // 2) % 2 == 0
    pulse_v = np.where(post, np.where(phase, 1.35, 0.65), 1.0)
    pulse_o = np.where(post, np.where(phase, 0.65, 1.35), 1.0)
    early = (wk >= LAUNCH_FLIGHT[0]) & (wk < LAUNCH_FLIGHT[0] + 6)  # online video front-loaded
    national_week = {  # million KRW per day
        "short_video": np.where(pre, 2.0 * bursts * jitter(0.25), np.where(flight, 8.0, 4.0 * pulse_v) * jitter(0.08)),
        "online_video": np.where(pre, 1.5 * jitter(0.35),
                                 np.where(flight, np.where(early, 4.0, 1.0), 1.5 * pulse_o) * jitter(0.10)),
        "social": np.where(pre, 1.0, 1.6) * jitter(0.25),
        "search": np.where(pre, 1.2, 1.8) * jitter(0.15),
        "retail_media": np.where(pre, 1.2, np.where(flight, 2.4, 1.8)) * jitter(0.20),
    }
    geo_jitter = rng.normal(1.0, 0.05, (n_weeks, N_GEO))
    spend = {}
    for c, nat in national_week.items():
        weekly = SPEND_SCALE * nat[:, None] * world.share[None, :] * geo_jitter * 1e6
        spend[c] = np.repeat(weekly, 7, axis=0)
    return Plan(spend)


def week_mask(world: World, first: int, last: int) -> np.ndarray:
    return (world.week >= first) & (world.week <= last)


def actual_plan(world: World, go_dark: np.ndarray | None = None,
                competitor_geos: list[int] | None = None,
                geo_test: bool = True, drop: str | list | None = None) -> Plan:
    """What FIZLY actually did. Flags give counterfactuals: geo_test=False is
    the same weeks with video on everywhere; drop=<channel or list> removes
    channels for all 104 weeks."""
    plan = bau_plan(world)
    sp = plan.spend
    if geo_test and go_dark is not None:
        t = week_mask(world, *GEO_TEST_WEEKS)
        sp["short_video"][np.ix_(t, go_dark)] = 0.0
    for c in ([drop] if isinstance(drop, str) else (drop or [])):
        sp[c][:] = 0.0
    shock = np.ones((N_DAYS, N_GEO))
    if competitor_geos:
        shock[np.ix_(week_mask(world, *COMPETITOR_WEEKS), competitor_geos)] = COMPETITOR_HIT
    plan.shock = shock
    return plan
