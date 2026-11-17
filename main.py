"""Forecast GTA VI's launch-day Twitch viewers, hour by hour, from hour 1.

Competition: gta6-twitch-ccu-forecast-01 (make.fun). The program reads every
``*.in`` case in the input directory (schema ``makefun/twitch-ccu-case/v1``)
and writes one ``<id>.out`` forecast per case: five quantiles (5/25/50/75/95%)
of Twitch concurrent viewers for each of hours 2..24 of the release day.

Method
------
Hour 1 of a rolling-midnight launch only catches the first regions to unlock
(New Zealand, central Europe, the UK), so the audience is small at 00:00 UTC
and grows steeply as North America wakes up and plays, peaking in the US
evening (hours ~19-22 UTC), then easing off. A flat persistence forecast
misses that whole shape, so this program learns the shape from the case's own
``comparables``: past big launches' hourly Twitch curves.

For every comparable launch with a complete release day (hours 1..24 all
present, viewers > 0) the log ratio ``r_h = ln(viewers_h / viewers_1)`` is
computed for h = 2..24. The forecast for the target launch is then

    q_tau(h) = p1 * exp(m_h + z_tau * s_h)

where p1 is the target's hour-1 print, m_h is the (smoothed) median of r_h
across the fitted comparables, s_h is the spread of r_h (inter-quartile
range / 1.349, smoothed, widened by 1.15), and z_tau is the standard
normal quantile at each scored level. Quantiles are rounded half-up to 2
decimals and forced non-decreasing.

Which comparables are fitted depends on the target's own hour-1 print,
because a tiny hour 1 means the game had not unlocked yet at 00:00 UTC and
its curve explodes later, while a large hour 1 means the launch was already
live in major regions and its curve is the gentle rise-and-fall shape:

  * p1 >= 20,000  -> fit only comparables with p1 >= 20,000
  * p1 >= 5,000   -> fit only comparables with p1 >= 5,000
  * otherwise     -> fit all usable comparables

GTA VI's hour 1 already holds the UK midnight unlock plus New Zealand and
central Europe, so it lands in the first tier. If a tier holds fewer than 8
launches, the program falls back to all usable comparables; if the case
carries no usable comparables at all, it falls back to constants fitted
offline on the kit's 37 usable comparables (same rule, p1 >= 20,000 tier),
listed in FALLBACK_MED_LOG / FALLBACK_SIGMA below.

Backtest (leave-one-comparable-out on the kit's 37 usable launches, scored
with the contest's pinball loss on the log scale; see STRATEGY.md):
targets with p1 >= 20,000 (the GTA VI-like regime, n = 27) score
loss 0.283, typical miss 56.4%, 90% coverage 0.902, against the house
persistence baseline's 0.321 / 63.0% / 0.792 on the same targets.

Only the Python standard library is used. No network, no randomness, no
wall-clock reads: two runs on the same input write byte-identical output.
"""

import json
import math
import os
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

# The grader runs with -P, which leaves this file's directory off sys.path;
# nothing beside this file is imported, so no path fix is needed.
INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# Standard normal quantiles at the scored levels.
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
# Hour-1 print tiers that select which comparables are fitted (see docstring).
TIER_BIG = 20000
TIER_MID = 5000
MIN_FIT = 8
# Spread widening: the IQR-based sigma is multiplied by this so the 90%
# band covers about 0.90 of held-out hours (LOCO: 0.902 at 1.15).
SIGMA_MULT = 1.15
SIGMA_FLOOR = 0.15
MAX_VIEWERS = 1e9

# Offline fit on the kit's 37 usable comparables, p1 >= 20,000 tier
# (27 launches), hours 2..24: smoothed median log ratio to hour 1, and the
# smoothed IQR-based log spread times SIGMA_MULT. Used only when the case
# carries no usable comparables. See STRATEGY.md for how these were computed.
FALLBACK_MED_LOG = [
    -0.2224, -0.2498, -0.2906, -0.2420, -0.2177, -0.2306, -0.2754,
    -0.3188, -0.3064, -0.2316, -0.1347, -0.0408, 0.0396, 0.1303,
    0.1996, 0.2559, 0.3236, 0.3846, 0.4114, 0.4353, 0.4664,
    0.3901, 0.3472,
]
FALLBACK_SIGMA = [
    0.2176, 0.2812, 0.3225, 0.4001, 0.4482, 0.5067, 0.5469,
    0.5739, 0.6194, 0.6184, 0.5961, 0.5868, 0.5992, 0.6372,
    0.6559, 0.6564, 0.6849, 0.7077, 0.6968, 0.6605, 0.6477,
    0.6710, 0.6781,
]


def round_half_up_2(x):
    """Round to 2 decimals, half up, returning an int for whole numbers."""
    scaled = x * 100.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100.0
    return int(value) if value.is_integer() else value


def parse_time(text):
    """Parse an ISO-8601 UTC timestamp (with a trailing Z) to a datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def release_day_points(comparable):
    """Return the comparable's 24 release-day viewer counts, or None.

    Hour 1 is the hour starting at the comparable's ``day_start``; every
    hour 1..24 must be present with viewers > 0, otherwise the launch is
    unusable for fitting (sparse SullyGnome sampling leaves gaps).
    """
    try:
        start = parse_time(comparable["day_start"])
    except (KeyError, TypeError, ValueError):
        return None
    by_hour = {}
    for point in comparable.get("hourly") or []:
        try:
            viewers = point["viewers"]
            at = parse_time(point["from"])
        except (KeyError, TypeError, ValueError):
            continue
        if isinstance(viewers, (int, float)) and viewers > 0:
            by_hour[at] = float(viewers)
    day = []
    for offset in range(24):
        value = by_hour.get(start + timedelta(hours=offset))
        if value is None:
            return None
        day.append(value)
    return day


def quantile(sorted_values, tau):
    """Linear-interpolation quantile of an already sorted list."""
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    pos = tau * (n - 1)
    low = int(math.floor(pos))
    high = min(low + 1, n - 1)
    frac = pos - low
    return sorted_values[low] * (1.0 - frac) + sorted_values[high] * frac


def smooth(values):
    """Three-point moving average over hours 2..24 (edges use 2 points)."""
    out = []
    for i in range(len(values)):
        window = values[max(0, i - 1):min(len(values), i + 2)]
        out.append(sum(window) / len(window))
    return out


def fit_shape(days, p1):
    """Fit (median log ratio, log spread) per hour from fitted launch days.

    ``days`` is a list of 24-count release-day lists; the tier is chosen
    from the target's own hour-1 print (see module docstring).
    """
    if p1 >= TIER_BIG:
        pool = [d for d in days if d[0] >= TIER_BIG]
    elif p1 >= TIER_MID:
        pool = [d for d in days if d[0] >= TIER_MID]
    else:
        pool = list(days)
    if len(pool) < MIN_FIT:
        pool = list(days)
    medians = []
    sigmas = []
    for h in range(1, 24):
        ratios = sorted(math.log(d[h] / d[0]) for d in pool)
        medians.append(statistics.median(ratios))
        iqr = quantile(ratios, 0.75) - quantile(ratios, 0.25)
        sigmas.append(max(SIGMA_FLOOR, (iqr / 1.349) * SIGMA_MULT))
    return smooth(medians), smooth(sigmas)


def hour_quantiles(p1, med_log, sigma):
    """The five quantiles for one hour, rounded and forced non-decreasing."""
    quantiles = []
    prev = 0.0
    for z in Z:
        value = p1 * math.exp(med_log + z * sigma)
        value = min(max(value, 0.01), MAX_VIEWERS)
        value = round_half_up_2(value)
        if value < prev:
            value = prev
        quantiles.append(value)
        prev = value
    return quantiles


def forecast_case(case, name):
    """Build the {"hours": [...]} forecast for one case dict."""
    known = case.get("known") or []
    first = next((k for k in known if k.get("hour") == 1), None)
    if first is None:
        raise ValueError(name + " has no hour-1 print")
    p1 = first.get("viewers")
    if not isinstance(p1, (int, float)) or not math.isfinite(p1) or p1 < 1:
        p1 = 1
    p1 = float(p1)
    hours = [row["hour"] for row in case.get("forecast") or []]
    if not hours:
        hours = list(range(2, 25))

    try:
        days = []
        for comparable in case.get("comparables") or []:
            day = release_day_points(comparable)
            if day is not None:
                days.append(day)
        if len(days) >= MIN_FIT:
            med_log, sigma = fit_shape(days, p1)
        else:
            raise ValueError("too few usable comparables")
    except Exception:
        med_log, sigma = FALLBACK_MED_LOG, FALLBACK_SIGMA

    rows = []
    for h in hours:
        idx = h - 2
        if 0 <= idx < len(med_log):
            row_med, row_sig = med_log[idx], sigma[idx]
        else:
            row_med, row_sig = 0.0, SIGMA_FLOOR
        rows.append({"hour": h, "q": hour_quantiles(p1, row_med, row_sig)})
    rows.sort(key=lambda row: row["hour"])
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        text = json.dumps(forecast, separators=(",", ":")) + "\n"
        (OUTPUT_DIR / (path.stem + ".out")).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
