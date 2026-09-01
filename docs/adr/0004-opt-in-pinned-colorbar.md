# ADR-0004: Colorbar pinning is opt-in per run set, not the default

- **Status:** Accepted
- **Date:** 2026-09-01
- **Affects:** `phase3a_unified_reconstruct.py` (`save_reconstruction_images`,
  `--colorbar-limit`); how every saved reconstruction image must be read
- **Related:** `docs/validity-audit.md` (image-reading caveats)

## Context

`save_reconstruction_images` set `vmin`/`vmax` from `max(abs(values))` over the frames in that
one call. Every run therefore stretched to fill the same red-blue palette regardless of signal
magnitude.

Observed runs span roughly ±0.003 to ±0.3 in relative conductivity change — two orders of
magnitude. A pure-noise run at ±0.003 rendered with exactly the same visual drama as a run with
real contrast at ±0.04. Comparing two images from different runs was meaningless, and nothing
on the figure indicated that.

This interacts badly with the substitution bias fixed in ADR-0002: the previous behaviour
produced images that were both falsely smooth *and* falsely vivid.

## Decision

`--colorbar-limit` pins `vmin`/`vmax` to ±the given value across both the per-frame contact
sheet and the average image. Omitted, the previous auto-scaling behaviour is unchanged.

## Rationale

A fixed default limit cannot be chosen honestly. The right value depends on the medium (saline
phantom versus living trunk), the drive pattern, and the current actually delivered — which per
L-01 is itself unresolved. Hard-coding a number would replace a visible scaling problem with an
invisible clipping one: real signal above the limit would silently saturate, which is worse
than an over-stretched noise image because it is undetectable by eye.

Auto-scaling is also genuinely right for a single exploratory run where the question is "is
there structure anywhere in this frame", as opposed to "is run B stronger than run A".

Making it a per-invocation flag puts the choice where the knowledge is: the operator knows
whether they are looking at one run or comparing a set, and picks one value across that set.

Alternatives rejected:

- **Always pin to a fixed constant.** Silent clipping, as above.
- **Pin to the maximum across a directory of runs.** Requires the tool to know about sibling
  runs, and a single outlier run would flatten every other image in the set.
- **Always annotate the limit and keep auto-scaling.** The limit is already on the colorbar; the
  problem is that reading it requires noticing it, and side-by-side comparison remains invalid.

## Consequences

Comparability is now an operator responsibility. Nothing prevents someone generating a run set
with mismatched limits, or forgetting the flag entirely and drawing conclusions from
auto-scaled images — which is the exact failure this addresses.

When the flag is used and real signal exceeds the chosen limit, that signal clips without
warning. Values should be chosen from a first auto-scaled pass over the run set.

Any thesis figure comparing runs must state the pinned limit used, or the comparison is not
defensible.

## Verification

`save_reconstruction_images` takes `fixed_limit`; existing image-saving tests cover the
default (auto-scaled) path unchanged. The flag rejects non-positive values at argument-parse
time. Visually falsifiable: run the same capture twice with different `--colorbar-limit` values
and the rendered intensity must change while the underlying CSV does not.
