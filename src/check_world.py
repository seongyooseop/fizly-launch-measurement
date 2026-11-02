"""Sanity check of the world: sizes, shares and true returns by channel.

Prints the numbers the design targets (not used by any chapter)."""
import numpy as np

from world import CHANNELS, LAUNCH_FLIGHT, World, actual_plan, week_mask

w = World()
obs, tru = w.simulate(actual_plan(w))
obs["rev"] = obs.offline_rev + obs.online_rev
yr2 = obs.week > 52
print(f"Year-2 revenue: KRW {obs.loc[yr2, 'rev'].sum() / 1e8:,.0f} x100M, "
      f"online share {obs.loc[yr2, 'online_rev'].sum() / obs.loc[yr2, 'rev'].sum():.1%}")
spend_cols = [f"spend_{c}" for c in CHANNELS]
print(f"Year-2 ad spend / revenue: {obs.loc[yr2, spend_cols].sum().sum() / obs.loc[yr2, 'rev'].sum():.1%}")
fl = (obs.week >= LAUNCH_FLIGHT[0]) & (obs.week <= LAUNCH_FLIGHT[1])
z = tru.loc[fl, "zero_offline"].sum() + tru.loc[fl, "zero_online"].sum()
print(f"Zero share of sales in the launch flight: {z / obs.loc[fl, 'rev'].sum():.1%}")
print(f"Zero awareness end of flight: {tru.loc[tru.week == LAUNCH_FLIGHT[1], 'zero_awareness'].mean():.2f}")

print("\nTrue return per channel (drop the channel for all weeks; weeks 79-104):")
post = obs.week >= 79
for c in CHANNELS:
    o2, _ = w.simulate(actual_plan(w, drop=c))
    d_off = obs.loc[post, "offline_rev"].sum() - o2.loc[post, "offline_rev"].sum()
    d_on = obs.loc[post, "online_rev"].sum() - o2.loc[post, "online_rev"].sum()
    sp = obs.loc[post, f"spend_{c}"].sum()
    rep = obs.loc[post, f"reported_rev_{c}"].sum()
    print(f"  {c:13s} spend {sp / 1e8:5.1f} | iROAS total {(d_off + d_on) / sp:4.2f} "
          f"(online {d_on / sp:4.2f}, offline {d_off / sp:4.2f}) | reported {rep / sp:4.2f}")
