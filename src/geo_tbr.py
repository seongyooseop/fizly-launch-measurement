"""Time-based regression (TBR) for geo experiments, with A/A calibration.

TBR (Kerman, Wang & Vaver, 2017) fits treatment-group totals on control-group
totals in the pre-period, predicts what the treatment group would have done in
the test period, and reads the cumulative gap as the causal effect. Here the
inputs are weekly totals, because store sales arrive as a weekly panel.

Two changes from the textbook fit, both found by A/A tests in an earlier lab
of mine (PAWLY) and kept here:
  * No intercept (proportional form). With an intercept, daily noise in the
    control total flattens the slope (regression dilution); whenever revenue
    grows between pre-period and test, the prediction lags and a fake positive
    effect appears (mean A/A z = +0.95).
  * The AR(1)-adjusted interval is still too narrow because group gaps drift
    slowly (ad-response and growth differences across regions). The standard
    error is multiplied by a factor learned from historical A/A tests of the
    same length, so that 95% of no-effect windows fall inside the interval.
"""
from __future__ import annotations

import numpy as np

Z95 = 1.959964


def tbr(y_treat: np.ndarray, y_ctrl: np.ndarray, pre: slice, test: slice,
        se_scale: float = 1.0) -> dict:
    """y_* are group totals per period. Returns cumulative effect and 95% interval."""
    yp, xp = y_treat[pre], y_ctrl[pre]
    ratio = yp.sum() / xp.sum()
    resid = yp - ratio * xp
    n_pre = len(yp)
    sigma2 = resid @ resid / (n_pre - 1)
    rho = np.clip(np.corrcoef(resid[:-1], resid[1:])[0, 1], 0.0, 0.95)
    lr = (1 + rho) / (1 - rho)  # long-run variance factor under AR(1)

    yt, xt = y_treat[test], y_ctrl[test]
    pred = ratio * xt
    effect = float(np.sum(yt - pred))
    var_ratio = sigma2 * lr / (xp @ xp)
    se_raw = float(np.sqrt(len(yt) * sigma2 * lr + xt.sum() ** 2 * var_ratio))
    se = se_raw * se_scale
    return {"effect": effect, "se": se, "se_raw": se_raw,
            "ci_low": effect - Z95 * se, "ci_high": effect + Z95 * se,
            "counterfactual": float(pred.sum()), "actual": float(yt.sum()),
            "pre_mape": float(np.mean(np.abs(resid) / yp)), "rho": float(rho),
            "ratio": float(ratio)}


def calibration_factor(z_raw: np.ndarray) -> float:
    """SE multiplier so that 95% of A/A z-scores fall inside +-1.96."""
    return float(max(1.0, np.quantile(np.abs(z_raw), 0.95) / Z95))
