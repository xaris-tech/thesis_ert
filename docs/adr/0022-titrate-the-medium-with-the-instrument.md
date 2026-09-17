# ADR-0022: Titrate the tank with the instrument rather than mixing to a fixed recipe

- **Status:** Accepted
- **Date:** 2026-09-11
- **Affects:** how the saline phantom is prepared, what operating point every tank measurement is
  taken at, reproducibility of the phantom
- **Related:** prepares the medium for [ADR-0021](0021-saline-tank-as-the-deferred-phantom.md);
  [ADR-0011](0011-current-guard-derives-from-fitted-rs.md),
  [ADR-0012](0012-current-floor-from-measured-noise.md);
  recorded per run by [ADR-0023](0023-per-run-folders-with-a-conditions-sheet.md)
- **Evidence:** firmware `CURRENT_RANGES` and `MAX_MUX_VOLTAGE_MV`; the 2026-08-27 quantisation
  finding in `docs/validity-audit.md`

## Context

The tank's conductivity sets the operating point of every measurement taken in it, and the
instrument's usable window is narrow and specific to this build:

- Compliance is capped at `MAX_MUX_VOLTAGE_MV = 3000`. Drive voltage above that is flagged
  `V_RANGE`.
- Current ranges are LOW (Rs 68 Ω, ≤100 µA), MEDIUM (Rs 22 Ω, ≤500 µA), HIGH (Rs 10 Ω, ≤1000 µA).
- The trunk presented transfer resistances around 2 kΩ, at 360–820 µA on HIGH.

Both ends of the window have already caused real failures on this project:

- **Too conductive.** Sense voltages collapse toward the ADC step size. The 2026-08-27 probe
  found forward and reverse readings identical to the microvolt — `fwd=+60.000 mV`,
  `rev=+60.000 mV`, `differential=0.000 mV` — because one ADC count exceeded the IR drop. The
  transfer resistance collapsed to zero for those pairs and the sample averaging was inert,
  because all sixteen samples returned the same count. That produced the PGA-autoranging work.
- **Too resistive.** The drive hits the 3 V compliance ceiling, the current source starves, and
  measured current falls under `MIN_CURRENT_UA` into `I_LOW`.

Salt concentration is the control for this, and intuition points the wrong way: the instinctive
"add plenty of salt" lands squarely in the first failure.

## Decision

The tank is **titrated using the instrument as the meter**, not mixed to a predetermined recipe.

Procedure: fill with tap water, scan, read the transfer resistances. Add salt in small measured
increments, rescanning after each, and stop when readings land in a tree-like band of roughly
200 Ω to 2 kΩ with drive voltage comfortably below the 3 V cap and no `I_HIGH` or `I_LOW`
quality flags.

Cumulative grams per litre is recorded at every step in `Conditions.saline_g_per_l`, together
with water temperature and fill depth, so the final working concentration is a reproducible
recipe rather than a one-off mixture.

**Every titration step is kept as a run**, not only the final one.

## Rationale

**Why the instrument is the right meter.** The quantity that matters is not conductivity in
absolute units — it is whether *this* instrument, with its fitted Rs, its 3 V compliance, its
shunt and its ADC, can measure the medium well. Only the instrument can report that. A
conductivity meter would measure the medium correctly and still not answer the question, and none
is available here in any case.

**Why the titration series is itself evidence.** Resistance should track dilution smoothly and
monotonically. The series is therefore a free linearity and dynamic-range check across the
instrument's whole usable span — a genuine methods-chapter figure obtained at no extra cost,
which is why intermediate steps are retained rather than discarded once the target is reached.

**Why a tree-like target band.** The tank is a stand-in for the trunk (ADR-0021). Setting it to
the regime the trunk actually presents means the instrument is exercised at the same currents,
the same PGA ranges and the same signal-to-noise as in real use. A tank that is far more
conductive than a tree would pass checks the tree would fail.

**Why not a fixed literature recipe.** Standard EIT phantom concentrations exist and would make
the phantom directly comparable with published work. Rejected because those recipes are chosen
for instruments with different compliance and current capability; there is no reason to expect
a standard concentration to land inside *this* instrument's window, and landing outside it makes
the phantom useless regardless of how comparable it is on paper.

**Why not tap water alone.** It is the starting point, not the endpoint. Tap water conductivity
varies substantially by source and drifts as it warms, so it is not reproducible, and it is
likely resistive enough to hit the compliance ceiling.

**Known imperfection.** The 200 Ω–2 kΩ target band is a judgement call anchored on the trunk's
observed ~2 kΩ and on keeping clear of both failure modes. It is not derived from a noise
calculation. Grams per litre is also a weaker specification than conductivity: it does not
account for the starting conductivity of the tap water or for temperature, so the recipe is
reproducible on this bench rather than universally.

## Consequences

**Easier.** The phantom is guaranteed to sit inside the instrument's measurable window, because
the instrument chose the endpoint. The working concentration becomes a written recipe that can be
remixed. The linearity sweep comes free.

**Harder.** Session setup grows a titration loop of many short captures, each needing its own
metadata — which is what made ADR-0023 a prerequisite rather than a nicety. Salt does not
redissolve instantly, so each step needs stirring and a settling pause, and impatience here shows
up as a non-monotonic point in the series.

**Committed to.** Tank measurements are comparable across sessions only when the recipe is
reproduced, so `saline_g_per_l`, `fill_depth_mm` and `water_temp_c` must be recorded every time.
The phantom is now defined by an operating point rather than by a standard concentration, which
must be stated in the methods section for anyone trying to reproduce it.

**Will bite later.** Evaporation concentrates the tank over a long session, so conductivity drifts
upward during exactly the long-duration drift run that is meant to measure instrument stability.
Those two effects are not separable from the measurement alone — water temperature and fill depth
recorded per run are the only handle on it. Temperature is a documented major confound in tree
ERT for the same reason.

## Verification

- Per-run: `conditions.json` carries `saline_g_per_l`, `water_temp_c` and `fill_depth_mm`;
  `run_record.Conditions.validate()` flags negative values.
- Per-step, from the captured frames: median transfer resistance inside 200 Ω–2 kΩ, no `I_HIGH`
  or `I_LOW` in the quality column, and drive voltage below `MAX_MUX_VOLTAGE_MV`.
- Across the series: transfer resistance decreasing monotonically with cumulative g/L. A
  non-monotonic point means either incomplete mixing or an instrument nonlinearity — and
  distinguishing those two is itself worth a measurement.
- Falsifiable: if no concentration places the readings inside the target band without a quality
  flag, the assumption that this instrument can measure a tree-like medium at all is wrong, and
  the current range or shunt needs revisiting before any tank result is meaningful.
