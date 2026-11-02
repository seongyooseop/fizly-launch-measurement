"""What the advertiser can actually see.

Store sales come from a weekly retail sell-out panel: the vendor projects its
sample of stores to each region's total, with a fixed projection error per
region and a little weekly noise. Online sales come from the brand's own mall
and marketplace reports (daily, complete). Platform reports are as the
platforms give them.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from world import CHANNELS, N_GEO

PANEL_SEED = 77
PANEL_REGION_ERR = 0.06   # sd of the fixed projection error per region
PANEL_WEEK_ERR = 0.02     # sd of weekly sampling noise


def weekly_panel(daily_obs: pd.DataFrame) -> pd.DataFrame:
    """Geo-week table: projected store sales, online sales, spend, reports."""
    rng = np.random.default_rng(PANEL_SEED)
    region_err = dict(zip(sorted(daily_obs.geo.unique()), np.exp(rng.normal(0, PANEL_REGION_ERR, N_GEO))))
    agg = {"offline_rev": "sum", "online_rev": "sum", "brand_search_volume": "sum", "temperature": "mean"}
    agg.update({f"spend_{c}": "sum" for c in CHANNELS})
    agg.update({f"reported_rev_{c}": "sum" for c in CHANNELS})
    wk = daily_obs.groupby(["week", "geo"], as_index=False).agg(agg)
    noise = np.exp(np.random.default_rng(PANEL_SEED + 1).normal(0, PANEL_WEEK_ERR, len(wk)))
    wk["store_sales"] = wk["offline_rev"] * wk["geo"].map(region_err) * noise
    return wk.drop(columns="offline_rev")


def wide(df: pd.DataFrame, col: str) -> tuple[np.ndarray, list]:
    w = df.pivot(index="week", columns="geo", values=col).sort_index()
    return w.to_numpy(), list(w.columns)
