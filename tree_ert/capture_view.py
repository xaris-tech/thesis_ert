"""Pure presentation logic for a live capture: rows, per-frame and per-session summaries.

Separated from any UI toolkit on purpose. The numbers an operator reads while
deciding whether a titration step landed in the instrument's window -- median
current, quality flags, reciprocity, frame-to-frame spread -- are the same
numbers whether they are rendered by Qt, by Tkinter, or by a CLI, and they are
the part worth testing. Everything here is a pure function over already-captured
frames, so the whole module is testable with no board and no display attached.

Frame-to-frame spread (:class:`SessionSummary.noise`) is the measurement that
licenses any detection claim: a change smaller than the spread of repeated
measurements of an unchanged specimen is not a detection. It is computed here
rather than at capture time because ADR-0023 keeps every frame unaveraged.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Iterable, Sequence

import phase3a_unified_reconstruct as unified

PairKey = tuple[tuple[int, int], tuple[int, int]]

# Full-scale millivolts of each ADS1115 PGA range, finest first, mirroring
# VOLTAGE_RANGES in the firmware. The firmware autoranges per measurement and
# does not report which range it used, so the range is inferred here from the
# measured magnitude using the firmware's own selection rule.
VOLTAGE_RANGES_MV = (256.0, 512.0, 1024.0, 2048.0, 4096.0)

# Headroom the firmware keeps above the probed magnitude before trusting a
# range (VOLTAGE_RANGE_HEADROOM in the .ino).
VOLTAGE_RANGE_HEADROOM = 1.25

# The ADS1115 is 16-bit signed, so a range spans +/- full scale in 32768 steps.
ADC_COUNTS_PER_SIDE = 32768.0

# A forward/reverse differential worth fewer than this many ADC steps is not a
# measurement of the specimen, it is a measurement of the converter. The
# failure it catches is recorded in docs/validity-audit.md: on 2026-08-27 the
# worst pairs returned fwd = +60.000 mV and rev = +60.000 mV, a differential of
# exactly zero, because one ADC step was larger than the IR drop -- and sample
# averaging was inert because all 16 samples returned the same count.
#
# Four steps is a judgement call (ADR-0026). One step cannot distinguish a real
# differential from a rounding boundary; four leaves room for the differential
# to change sign and magnitude as the specimen changes, which is what a
# difference image needs.
MIN_DIFFERENTIAL_COUNTS = 4.0

# Fraction of pairs allowed under that floor before the frame is called
# quantisation-limited rather than merely having a few weak pairs. Distant
# pairs in an adjacent sweep are legitimately small, so a handful is normal.
MAX_QUANTISED_PAIR_FRACTION = 0.10


def electrode_label(index: int) -> str:
    return f"E{index + 1}"


def pair_label(key: PairKey) -> str:
    """Human-readable reciprocal-pair name, e.g. 'I:E1,E2 V:E3,E4'."""
    (i_plus, i_minus), (v_plus, v_minus) = key
    return (
        f"I:{electrode_label(i_plus)},{electrode_label(i_minus)} "
        f"V:{electrode_label(v_plus)},{electrode_label(v_minus)}"
    )


def voltage_lsb_mv(magnitude_mv: float) -> float:
    """ADC step size for the PGA range the firmware would pick for this reading.

    Mirrors ``selectVoltageRange()`` in the firmware: the finest range whose
    full scale covers the magnitude with headroom, falling back to the widest.
    Inferred rather than reported because the ``FRAME`` record carries only the
    converted millivolts, not the gain that produced them.
    """
    required = abs(magnitude_mv) * VOLTAGE_RANGE_HEADROOM
    for full_scale in VOLTAGE_RANGES_MV[:-1]:
        if required <= full_scale:
            return full_scale / ADC_COUNTS_PER_SIDE
    return VOLTAGE_RANGES_MV[-1] / ADC_COUNTS_PER_SIDE


@dataclass(frozen=True)
class QuantisationReport:
    """How close the frame's weakest pairs sit to the ADC's own resolution.

    Replaces the fixed transfer-resistance window this module used to carry
    (ADR-0026). That window was set at 200 ohm - 2 kohm on the belief that the
    trunk measured about 2 kohm; the measured baseline median is 9.4 ohm, so it
    flagged every legitimate scan. Resistance was the wrong quantity in any
    case: what limits this instrument is whether the forward/reverse
    differential survives the converter, and that depends on voltage and the
    autoranged PGA, not on resistance.
    """

    pair_count: int
    quantised_pairs: int
    median_counts: float
    min_counts: float

    @property
    def quantised_fraction(self) -> float:
        return self.quantised_pairs / self.pair_count if self.pair_count else 0.0

    @property
    def limited(self) -> bool:
        """True when too much of the frame is at the converter's resolution."""
        if self.pair_count == 0:
            return False
        return self.quantised_fraction > MAX_QUANTISED_PAIR_FRACTION


def quantisation_report(frame: unified.UnifiedFrame) -> QuantisationReport:
    """Score every forward/reverse pair by how many ADC steps separate them.

    Only pairs with both polarities are scored; a lone record has no
    differential. Records the firmware flagged are skipped, since their voltage
    is not trustworthy enough to judge anything by.
    """
    forward: dict[PairKey, float] = {}
    reverse: dict[PairKey, float] = {}
    for record in frame.records:
        if record.quality != "OK":
            continue
        key = unified.canonical_measurement_key(record)
        (forward if record.polarity == "FWD" else reverse)[key] = record.voltage_mv

    counts: list[float] = []
    for key in forward.keys() & reverse.keys():
        fwd = forward[key]
        rev = reverse[key]
        differential = abs(fwd - rev)
        # The range is chosen from the larger magnitude, since that is what the
        # firmware probed when it picked the gain for these readings.
        lsb = voltage_lsb_mv(max(abs(fwd), abs(rev)))
        counts.append(differential / lsb if lsb > 0 else 0.0)

    if not counts:
        return QuantisationReport(0, 0, 0.0, 0.0)
    return QuantisationReport(
        pair_count=len(counts),
        quantised_pairs=sum(1 for c in counts if c < MIN_DIFFERENTIAL_COUNTS),
        median_counts=statistics.median(counts),
        min_counts=min(counts),
    )


@dataclass(frozen=True)
class RecordRow:
    """One measurement as displayed. Mirrors the raw record, plus derived values."""

    polarity: str
    i_plus: str
    i_minus: str
    v_plus: str
    v_minus: str
    voltage_mv: float
    current_ua: float
    resistance_kohm: float | None
    quality: str

    @property
    def ok(self) -> bool:
        return self.quality == "OK"


def record_rows(frame: unified.UnifiedFrame) -> list[RecordRow]:
    """Every record of one frame, in capture order.

    Capture order matters and is preserved: the firmware interleaves forward and
    reverse per sense pair, so a table that sorts by pair would hide a polarity
    sequence that had stopped alternating -- the signature of the polarisation
    fault the interleaving exists to prevent.

    ``resistance_kohm`` is the single-record V/I, not the forward/reverse
    averaged transfer resistance. It is None on a zero-current record rather
    than an infinity, so the table can say "no current" instead of showing a
    number that looks measured.
    """
    rows: list[RecordRow] = []
    for record in frame.records:
        current = abs(record.current_ua)
        rows.append(
            RecordRow(
                polarity=record.polarity,
                i_plus=electrode_label(record.i_pair[0]),
                i_minus=electrode_label(record.i_pair[1]),
                v_plus=electrode_label(record.v_pair[0]),
                v_minus=electrode_label(record.v_pair[1]),
                voltage_mv=record.voltage_mv,
                current_ua=record.current_ua,
                # mV/uA is numerically kOhm.
                resistance_kohm=(record.voltage_mv / current) if current > 0 else None,
                quality=record.quality,
            )
        )
    return rows


@dataclass(frozen=True)
class FrameSummary:
    """What an operator checks after a single scan, before trusting it."""

    record_count: int
    ok_count: int
    quality_counts: dict[str, int]
    median_current_ua: float
    min_current_ua: float
    max_current_ua: float
    median_resistance_kohm: float | None
    polarity_alternates: bool
    quantisation: QuantisationReport

    @property
    def ok_fraction(self) -> float:
        return self.ok_count / self.record_count if self.record_count else 0.0

    @property
    def quantisation_limited(self) -> bool:
        """Whether too much of the frame sits at the converter's resolution."""
        return self.quantisation.limited


def frame_summary(frame: unified.UnifiedFrame) -> FrameSummary:
    """Per-frame health, computed leniently so a bad frame still reports.

    Uses the lenient transfer-resistance path: a frame that would raise in the
    CLI's strict mode is the frame the operator most needs to see summarised,
    not the one that should vanish behind an exception.
    """
    records = frame.records
    quality_counts: dict[str, int] = {}
    for record in records:
        quality_counts[record.quality] = quality_counts.get(record.quality, 0) + 1

    currents = [abs(record.current_ua) for record in records]
    resistances = [
        abs(value)
        for value in unified.paired_transfer_resistance(frame, strict=False).values()
    ]

    return FrameSummary(
        record_count=len(records),
        ok_count=quality_counts.get("OK", 0),
        quality_counts=quality_counts,
        median_current_ua=statistics.median(currents) if currents else 0.0,
        min_current_ua=min(currents) if currents else 0.0,
        max_current_ua=max(currents) if currents else 0.0,
        median_resistance_kohm=statistics.median(resistances) if resistances else None,
        polarity_alternates=_polarity_alternates(records),
        quantisation=quantisation_report(frame),
    )


def _polarity_alternates(records: Sequence[unified.MeasurementRecord]) -> bool:
    """Whether polarities run FWD, REV, FWD, REV as the firmware interleaves them.

    A frame that stops alternating is the polarisation signature described in
    AGENTS.md: holding one polarity across a drive pair builds electrode
    polarisation and collapses the transfer resistance toward zero.
    """
    if len(records) < 2:
        return True
    return all(
        first.polarity != second.polarity
        for first, second in zip(records, records[1:])
    )


@dataclass(frozen=True)
class ReciprocitySummary:
    """Reciprocity across a set of frames. The bisect number (ADR-0021)."""

    pair_count: int
    median_error_percent: float
    max_error_percent: float
    sign_flip_count: int

    @property
    def sign_flip_fraction(self) -> float:
        return self.sign_flip_count / self.pair_count if self.pair_count else 0.0


@dataclass(frozen=True)
class NoiseSummary:
    """Frame-to-frame spread of an unchanged specimen: the detection floor.

    A later difference smaller than this is not a detection. Reported as both an
    absolute and a relative figure because the absolute number alone is
    meaningless without the signal it sits on -- the mistake recorded as D-03.
    """

    frame_count: int
    pair_count: int
    median_pair_std_kohm: float
    max_pair_std_kohm: float
    median_pair_relative_percent: float


@dataclass(frozen=True)
class SessionSummary:
    frame_count: int
    reciprocity: ReciprocitySummary | None
    noise: NoiseSummary | None
    suspect_electrodes: tuple[tuple[int, float], ...] = ()
    """(zero-based electrode, median reciprocity error of the pairs touching it),
    worst first, for electrodes far worse than the rest (ADR-0032)."""


SUSPECT_ELECTRODE_FACTOR = 2.0
"""An electrode is suspect when the pairs touching it are this many times worse
than all pairs together (ADR-0032). On 2026-09-22 E2 read 70% against an 11%
median; the healthy electrodes sat at 8-11%."""

SUSPECT_ELECTRODE_FLOOR_PERCENT = 15.0
"""...and worse than this in absolute terms, so a uniformly excellent run (say
0.1% overall, 0.3% on one electrode) does not raise a warning over nothing.
Equal to the reconstruction gate, deliberately: below it nothing is refused."""


def electrode_reciprocity(
    frames: Sequence[unified.UnifiedFrame],
) -> dict[int, float]:
    """Median reciprocity error of the pairs touching each electrode.

    A median over the whole run hides a single bad contact: every pair has four
    electrodes, so one bad nail spoils a third of the pairs and still leaves the
    median looking tolerable. Scored per electrode, the bad one stands out -- and
    its neighbours rise too, because they share pairs with it.
    """
    scores = unified.reciprocity_scores(average_pair_values(frames))
    touching: dict[int, list[float]] = {}
    for (i_pair, v_pair), score in scores.items():
        for electrode in set(i_pair) | set(v_pair):
            touching.setdefault(electrode, []).append(score.error_percent)
    return {electrode: statistics.median(errors) for electrode, errors in touching.items()}


def suspect_electrodes(
    per_electrode: dict[int, float], overall_median_percent: float
) -> tuple[tuple[int, float], ...]:
    limit = max(
        SUSPECT_ELECTRODE_FACTOR * overall_median_percent,
        SUSPECT_ELECTRODE_FLOOR_PERCENT,
    )
    flagged = [(e, err) for e, err in per_electrode.items() if err > limit]
    return tuple(sorted(flagged, key=lambda item: -item[1]))


def reciprocity_summary(frames: Sequence[unified.UnifiedFrame]) -> ReciprocitySummary | None:
    """Reciprocity of the frame-averaged values, or None if nothing scorable.

    Averaging across frames before scoring, rather than scoring each frame and
    averaging the scores, keeps random noise out of the reciprocity number:
    reciprocity is a systematic property and the question is whether it is
    violated systematically.
    """
    values = average_pair_values(frames)
    if not values:
        return None
    scores = unified.reciprocity_scores(values)
    if not scores:
        return None
    errors = [score.error_percent for score in scores.values()]
    return ReciprocitySummary(
        pair_count=len(scores),
        median_error_percent=statistics.median(errors),
        max_error_percent=max(errors),
        sign_flip_count=sum(1 for score in scores.values() if score.sign_flipped),
    )


def average_pair_values(
    frames: Iterable[unified.UnifiedFrame],
) -> dict[PairKey, float]:
    """Mean transfer resistance per pair across frames, lenient about bad records.

    A pair measured in only some frames is averaged over the frames that have
    it, rather than dropped. Dropping it would silently shrink the pair set
    whenever one frame had a single weak record.
    """
    collected: dict[PairKey, list[float]] = {}
    for frame in frames:
        for key, value in unified.paired_transfer_resistance(frame, strict=False).items():
            collected.setdefault(key, []).append(value)
    return {key: statistics.fmean(values) for key, values in collected.items()}


def noise_summary(frames: Sequence[unified.UnifiedFrame]) -> NoiseSummary | None:
    """Per-pair standard deviation across frames. Needs at least two frames."""
    if len(frames) < 2:
        return None
    collected: dict[PairKey, list[float]] = {}
    for frame in frames:
        for key, value in unified.paired_transfer_resistance(frame, strict=False).items():
            collected.setdefault(key, []).append(value)

    repeated = {key: values for key, values in collected.items() if len(values) >= 2}
    if not repeated:
        return None

    stds: list[float] = []
    relatives: list[float] = []
    for values in repeated.values():
        std = statistics.stdev(values)
        stds.append(std)
        mean = abs(statistics.fmean(values))
        if mean > 0:
            relatives.append(std / mean * 100.0)

    return NoiseSummary(
        frame_count=len(frames),
        pair_count=len(repeated),
        median_pair_std_kohm=statistics.median(stds),
        max_pair_std_kohm=max(stds),
        median_pair_relative_percent=(
            statistics.median(relatives) if relatives else 0.0
        ),
    )


def session_summary(frames: Sequence[unified.UnifiedFrame]) -> SessionSummary:
    reciprocity = reciprocity_summary(frames)
    suspects: tuple[tuple[int, float], ...] = ()
    if reciprocity is not None:
        suspects = suspect_electrodes(
            electrode_reciprocity(frames), reciprocity.median_error_percent
        )
    return SessionSummary(
        frame_count=len(frames),
        reciprocity=reciprocity,
        noise=noise_summary(frames),
        suspect_electrodes=suspects,
    )


def format_frame_summary(summary: FrameSummary) -> str:
    """One-line operator readout. Deliberately dense: it updates per frame."""
    parts = [
        f"{summary.ok_count}/{summary.record_count} OK",
        f"I med {summary.median_current_ua:.1f} uA "
        f"({summary.min_current_ua:.1f}-{summary.max_current_ua:.1f})",
    ]
    if summary.median_resistance_kohm is None:
        parts.append("R med n/a")
    else:
        parts.append(f"R med {summary.median_resistance_kohm:.4f} kohm")
    quantisation = summary.quantisation
    if quantisation.pair_count:
        detail = f"dV med {quantisation.median_counts:.0f} LSB"
        if quantisation.limited:
            detail += (
                f" QUANTISATION LIMITED "
                f"({quantisation.quantised_pairs}/{quantisation.pair_count} pairs "
                f"under {MIN_DIFFERENTIAL_COUNTS:.0f})"
            )
        parts.append(detail)
    flags = sorted(
        (quality, count)
        for quality, count in summary.quality_counts.items()
        if quality != "OK"
    )
    if flags:
        parts.append("flags " + " ".join(f"{q}x{c}" for q, c in flags))
    if not summary.polarity_alternates:
        parts.append("POLARITY NOT INTERLEAVED")
    return " | ".join(parts)


def format_session_summary(summary: SessionSummary) -> str:
    """Multi-line readout of the numbers the tank session exists to produce."""
    lines = [f"Frames captured: {summary.frame_count}"]
    if summary.reciprocity is None:
        lines.append("Reciprocity: no reciprocal pairs captured")
    else:
        rec = summary.reciprocity
        lines.append(
            f"Reciprocity: median {rec.median_error_percent:.1f}%  "
            f"max {rec.max_error_percent:.1f}%  "
            f"sign flips {rec.sign_flip_count}/{rec.pair_count}"
        )
        if summary.suspect_electrodes:
            worst = ", ".join(
                f"E{electrode + 1} {error:.0f}%"
                for electrode, error in summary.suspect_electrodes
            )
            lines.append(
                f"Check electrode contact: {worst} "
                f"(all pairs median {rec.median_error_percent:.0f}%)"
            )
    if summary.noise is None:
        lines.append("Noise floor: needs at least 2 frames")
    else:
        noise = summary.noise
        lines.append(
            f"Noise floor: median pair sd {noise.median_pair_std_kohm:.5f} kohm "
            f"({noise.median_pair_relative_percent:.2f}%)  "
            f"max {noise.max_pair_std_kohm:.5f} kohm over {noise.pair_count} pairs"
        )
    return "\n".join(lines)
