"""Live E2-as-V- check: per pair of frames, misfit with all records vs without E2 as V-.
A big gap = the V- mux path for E2 is misbehaving at that moment."""
import sys, time
from dataclasses import replace
sys.path.insert(0, r"D:\Here\asd")
from tree_ert import absolute
from tree_ert.acquisition import SerialAcquisition
from tree_ert.settings import UiSettings

s = UiSettings(port="COM7", pattern="adjacent", current_range="high", dac=620, settle_ms=10, samples=16).validate()
acq = SerialAcquisition(); acq.connect(s); acq.configure(s)
try:
    acq.capture_frame()
    for k in range(int(sys.argv[1]) if len(sys.argv) > 1 else 12):
        frames = [acq.capture_frame(), acq.capture_frame()]
        full = absolute.reconstruct_absolute(frames, s).residual_percent
        cut = absolute.reconstruct_absolute(
            [replace(f, records=[r for r in f.records if r.v_pair[1] != 1]) for f in frames], s).residual_percent
        print(f"{time.strftime('%H:%M:%S')} pair {k+1}: misfit {full:5.1f}%  without E2-as-V- {cut:5.1f}%  "
              f"gap {full - cut:+5.1f}  {'E2 V- FAULTY' if full - cut > 10 else 'ok'}", flush=True)
finally:
    acq.close()
