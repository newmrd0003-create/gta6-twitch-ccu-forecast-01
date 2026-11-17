# STRATEGY — GTA VI Twitch CCU forecast

Entry for make.fun `gta6-twitch-ccu-forecast-01`: forecast Twitch concurrent
viewers in the Grand Theft Auto VI category for hours 2–24 of release day
2026-11-19 (UTC), as five quantiles per hour, from the hour-1 print.
Score: mean pinball loss on the log scale. Prize needs a loss strictly
below the best house entry (persistence baseline: practice loss ~0.387,
typical miss ~82.8%; plus a house model forecast).

## 1. The shape of the problem

GTA VI unlocks at rolling local midnight: New Zealand 11:00Z 18 Nov,
central Europe 23:00Z, UK 00:00Z, US East 05:00Z, US Pacific 08:00Z.
Hour 1 (00:00–01:00 UTC) therefore only catches the UK midnight unlock
plus regions already live (NZ, CET). Viewers then:

- dip slightly in hours 2–9 (night in Europe, US still asleep),
- rise from hour ~10 as the US wakes and plays,
- peak in hours ~19–22 (18:00–21:00 UTC = 13:00–16:00 ET / 10:00–13:00 PT
  afternoon plus the EU evening),
- ease off in hours 23–24.

A flat persistence median is wrong by ~60% for most of the day, which is
why the house baseline scores 0.387 on the practice despite its spread.

## 2. Model

For each comparable launch in the case with a complete release day
(hours 1–24 all present, viewers > 0), compute the log ratio to hour 1:

    r_h = ln(viewers_h / viewers_1),  h = 2..24

Forecast:

    q_tau(h) = p1 * exp(m_h + z_tau * s_h)

- `p1`: the target case's hour-1 print (floored at 1).
- `m_h`: median of `r_h` across the fitted pool, smoothed with a 3-hour
  moving average (edges use 2 points). Smoothing removes single-hour
  noise (e.g. the raw median dips at hour 24 in the big-launch pool).
- `s_h`: (inter-quartile range of `r_h` / 1.349), smoothed the same way,
  multiplied by 1.15, floored at 0.15. The 1.15 widening was chosen on the
  backtest: it lifts 90% coverage from 0.882 to 0.902 at no loss cost
  (1.30 widening already costs loss: 0.2850 vs 0.2829).
- `z_tau`: standard normal quantiles (-1.645, -0.674, 0, 0.674, 1.645).
- Quantiles are rounded half-up to 2 decimals, forced non-decreasing
  (running maximum), and clipped to (0, 1e9].

### Which comparables are fitted (the key choice)

A tiny hour 1 means the game had **not unlocked yet** at 00:00 UTC
(e.g. Hollow Knight: Silksong, p1 = 164, global unlock later that day;
Black Myth: Wukong, p1 = 4,941) and its curve explodes 100–200× later.
A large hour 1 means the launch was already live in major regions and
its curve is the gentle rise-and-fall shape. Pooling both regimes gives a
median that is wrong for both. So the pool is tiered on the target's own
`p1`:

- `p1 >= 20,000` → fit only comparables with `p1 >= 20,000` (27 of the
  kit's 37 usable launches; in the final case, 31 of 42, since the 4
  practice launches all have p1 ≥ 20,000).
- `p1 >= 5,000` → fit only comparables with `p1 >= 5,000`.
- otherwise → fit all usable comparables.

If a tier holds fewer than 8 launches, fall back to all usable
comparables; if the case has fewer than 8 usable comparables at all,
fall back to the embedded offline constants (same rule, p1 ≥ 20,000
tier, fitted on the kit's 37 usable launches). GTA VI's hour 1 already
holds the UK unlock plus NZ/CET, so it lands in the first tier.

Alternatives tested and rejected (LOCO, see §4):

- Pooled fit over all 37 launches: loss 0.803 overall, 0.337 on big
  targets — worse than the tiered fit (0.283) because the tiny-p1
  launches drag the median up and blow up the spread (sigma up to 1.8).
- Per-hour OLS regression of `r_h` on `ln(p1)`: 0.329 on big targets —
  worse; the tiering captures the regime switch better than a line.
- Restricting to rolling-midnight launches only (n = 12): 0.310 on big
  targets — noisier than the p1 ≥ 20,000 pool (n = 27).
- Excluding "early access" launches from the pool: 0.294 on big targets
  — worse; the flag is noisy (many unlock notes mention early access
  for a different edition) and it shrinks the pool to 15.
- Empirical per-hour quantiles instead of median + normal spread: 0.282
  on big targets (a tie on loss) but 90% coverage only 0.839 — the
  normal spread with ×1.15 is better calibrated.

## 3. Fitted values (offline fit, kit data, p1 ≥ 20,000 tier, n = 27)

Median ratio to hour 1 by hour (smoothed):

| hour | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ratio | 0.80 | 0.78 | 0.75 | 0.79 | 0.80 | 0.79 | 0.76 | 0.73 | 0.74 | 0.79 | 0.87 |

| hour | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ratio | 0.96 | 1.04 | 1.14 | 1.22 | 1.29 | 1.38 | 1.47 | 1.51 | 1.55 | **1.59** | 1.48 | 1.42 |

Peak median at **hour 22, ratio 1.59× hour 1**; trough at hour 9,
ratio 0.73×. Log spread `s_h` rises from 0.22 (hour 2) to ~0.71
(hour 19), i.e. the 90% band at the peak spans roughly
`exp(±1.645 × 0.71)` ≈ 0.31×–3.2× the median.

How they were computed: from the kit's `input/*.in` files only — for
each of the 38 comparables, take the hourly points on its `day_start`
(24 hourly points, 14 days before to 3 days after release are in the
file), keep the 37 with all 24 release-day hours present and viewers > 0
(the 38th is the GTA VI pre-release category, not a launch: its
`day_start` is 2026-08-27 and it has no release-day hours), take the
p1 ≥ 20,000 subset (27 launches), then per hour the median and IQR of
`ln(viewers_h / viewers_1)`, 3-hour smoothed, spread ×1.15. The exact
log values are embedded as `FALLBACK_MED_LOG` / `FALLBACK_SIGMA` in
`main.py`; at runtime the same computation is redone from the case's
own comparables, so the final case (42 comparables) refits on the
larger pool.

## 4. Backtest — leave-one-comparable-out (LOCO)

Protocol: for each of the 37 usable comparables in turn, fit the model
on the other 36 (same tiering rule, same smoothing) and score the held-out
launch's hours 2–24 with the contest pinball loss
`2·max(tau·d, (tau−1)·d)`, `d = ln(y) − ln(q)`, averaged over all hours
and quantiles; typical miss = `100·(exp(mean|ln y − ln q50|) − 1)`;
coverage = share of hours with `q05 ≤ y ≤ q95`. Baseline = house
persistence (`q = p1·exp(z·0.15·sqrt(h−1))`). Script:
`~/workspace/scratch/gta6-ccu-backtest/backtest.py` (+ `backtest2.py`,
`backtest3.py`, `backtest4.py` for the variants).

| Targets | Model loss | Baseline loss | Model miss | Baseline miss | Model cov90 | Baseline cov90 |
|---|---|---|---|---|---|---|
| p1 ≥ 20,000 (n = 27, GTA VI-like) | **0.283** | 0.321 | 56.4% | 63.0% | 0.902 | 0.792 |
| Rolling-midnight (n = 12) | 0.322 | 0.357 | 65.0% | 71.7% | 0.859 | 0.790 |
| All 37 | 0.757 | 0.930 | 183.4% | 213.3% | 0.737 | 0.624 |

The "all 37" row is dominated by 10 tiny-p1 launches whose hour 1 is
pre-unlock (losses 1.2–3.9 for every model, baseline included); no model
can predict a 200× explosion from a 164-viewer hour 1, and GTA VI is
not in that regime. The decision-relevant row is p1 ≥ 20,000: the model
beats the baseline by 0.038 loss (12% relative), with better coverage.

Per-case losses on the big targets (model vs baseline): ELDEN RING
0.21/0.21, Resident Evil Requiem 1.21/1.27, Hogwarts Legacy 0.21/0.29,
Cyberpunk 2077 0.26/0.23, Ghost of Yōtei 0.38/0.47, Monster Hunter Wilds
0.39/0.43, CoD Black Ops 6 0.23/0.26, CoD MW III 0.15/0.15, CoD BO7
0.15/0.17, CoD MW4 0.19/0.24, 007 First Light 0.25/0.35, Forza Horizon 6
0.33/0.41, Zelda: TotK 0.25/0.31, Starfield 0.33/0.29, Diablo IV
0.15/0.13, Borderlands 4 0.25/0.25, AC Shadows 0.29/0.35, DOOM: TDA
0.19/0.26, Elden Ring Nightreign 0.23/0.25, Death Stranding 2 0.14/0.18,
FFVII Rebirth 0.16/0.17, TLOU Part II 0.18/0.25, Ghost of Tsushima
0.17/0.23, Halo Infinite 0.57/0.63, Forza Horizon 5 0.23/0.33, Stellar
Blade 0.26/0.37, Marvel Rivals 0.25/0.21. The model wins on 21 of the
27 and loses on 6 (ELDEN RING is effectively tied at 0.211/0.211) — the
mean win comes from the cases where persistence is wrong (Requiem,
Yōtei, Halo, Ghost of Tsushima-style US-evening peaks), while on flat
launches persistence is hard to beat. This is the honest shape of the
edge: a modest but real mean improvement in the regime GTA VI sits in.

### Note on the practice cases

The kit's four practice cases (p00–p03) cannot be scored from the kit
alone: their answers (hours 2–24 of Wolverine / RDR2 / GoW Ragnarök /
Spider-Man 2) are not in any `.in` file — all four cases ship the same
38 comparables, which exclude all four practice launches, and there is
no `reference/` directory in the kit. The LOCO backtest above is
therefore the verification, not a practice score. The house baseline's
practice loss of ~0.387 (from `competition.yaml`) is over those four
cases; on the LOCO big-target set the same baseline scores 0.321, so
the two numbers are not directly comparable.

## 5. Local verification (2026-11-17)

- `main.py` run on all four practice cases: 4/4 `.out` files valid
  (23 rows, hours 2–24, 5 quantiles each, non-decreasing, ≤ 65,536
  bytes). Practice p1 values: 23,357 / 116,550 / 269,517 / 119,087 —
  all in the p1 ≥ 20,000 tier.
- Determinism: two runs byte-identical (diff empty).
- Timing: ~0.2 s per case locally (cap 8 s).
- Forecast shape on the practice cases: median ratio trough ~0.73 at
  hour 9, peak ~1.59 at hour 22 — the fitted curve from §3.

## 6. Limits

- The model conditions only on hour 1 and the comparable pool. It does
  not use `history`, `streams`, or `categories_hourly`: at the
  checkpoint those add little beyond hour 1 (pre-release GTA VI
  category traffic is hype, not gameplay) and the comparable curves
  already encode the launch-day shape.
- If GTA VI's hour 1 is far outside the comparable range (e.g. > 1M
  viewers — plausible for GTA), the tier still applies (p1 ≥ 20,000
  pool, whose own p1 spans 20k–875k); the ratio shape is assumed
  scale-free, which the backtest supports across that range.
- The final is a single case; the LOCO mean is the best available
  estimate, not a guarantee — a flat launch day would favour
  persistence, a strong US-evening peak favours this model.
