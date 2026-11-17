# GTA VI Twitch CCU forecast — make.fun entry

[![gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/competitions/gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/newmrd0003-create/gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/competitions/gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/newmrd0003-create/gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/competitions/gta6-twitch-ccu-forecast-01)

Forecasts how many people watch Grand Theft Auto VI live on Twitch in each
hour of its release day (2026-11-19 UTC), as five quantiles per hour
(5% / 25% / 50% / 75% / 95%), from the viewer count of the day's first hour.

Entry for the [make.fun competition `gta6-twitch-ccu-forecast-01`](https://make.fun/competitions/gta6-twitch-ccu-forecast-01)
($250, 20 places; a prize needs a pinball loss below the best house entry).

## How it works

Hour 1 of a rolling-midnight launch only catches the first regions to unlock
(New Zealand, central Europe, the UK), so the audience starts small at
00:00 UTC and grows steeply as North America wakes up and plays, peaking in
the US evening (hours ~19–22 UTC). A flat persistence forecast misses that
whole shape.

`main.py` learns the shape from the case's own `comparables` — past big
launches' hourly Twitch curves (SullyGnome hourly category averages, as
shipped in the kit):

1. For every comparable with a complete release day (hours 1–24, viewers
   > 0), compute the log ratio `r_h = ln(viewers_h / viewers_1)`.
2. Pick the fitting pool by the target's own hour-1 print `p1`: launches
   with `p1 >= 20,000` are fitted only on comparables with `p1 >= 20,000`
   (a large hour 1 means the launch was already live in major regions, so
   its curve is the gentle rise-and-fall shape; a tiny hour 1 means the
   game had not unlocked yet and its curve explodes later). Tiers at 5,000
   and below fall back to wider pools; fewer than 8 launches in a pool
   falls back to all usable comparables, and no usable comparables at all
   falls back to constants fitted offline on the kit (embedded in `main.py`).
3. Per hour: median log ratio (3-hour moving-average smoothed) and spread
   (inter-quartile range / 1.349, smoothed, widened ×1.15, floor 0.15).
4. `q_tau(h) = p1 * exp(median_h + z_tau * sigma_h)`, rounded half-up to
   2 decimals, forced non-decreasing, clipped to (0, 1e9].

See `STRATEGY.md` for the full model description and the backtest numbers.

## Running it

Python 3.13, standard library only, no network:

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

The grader runs `python3 -P -s /bot/main.py`, reading every `*.in` file in
`/input` (or `$MAKEFUN_INPUT_DIR`) and writing `/output/<id>.out`
(or `$MAKEFUN_OUTPUT_DIR/<id>.out`) per case: JSON
`{"hours": [{"hour": 2, "q": [q05, q25, q50, q75, q95]}, ...]}` for
hours 2–24. Deterministic: two runs on the same case write byte-identical
output. Each case runs in well under the 8-second cap (measured ~0.2 s
per practice case locally, including the runtime fit over 38 comparables).

## Backtest (leave-one-comparable-out, kit data)

On the 27 GTA VI-like comparables (hour-1 print ≥ 20,000):

| | pinball loss | typical miss | 90% coverage |
|---|---|---|---|
| This model | **0.283** | 56.4% | 0.902 |
| House persistence baseline | 0.321 | 63.0% | 0.792 |

Full numbers and per-case losses are in `STRATEGY.md`.

## Files

- `main.py` — the entry (Python 3.13, stdlib only).
- `STRATEGY.md` — model, fit, and backtest.
- `LICENSE` — MIT.
- `.makefun/owner.json` — payout wallet.
