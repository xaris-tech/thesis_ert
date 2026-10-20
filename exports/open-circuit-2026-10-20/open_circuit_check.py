import sys, time, statistics as st
from dataclasses import replace
sys.path.insert(0, r"D:\Here\asd")
from tree_ert.acquisition import SerialAcquisition
from tree_ert.settings import UiSettings
acq = SerialAcquisition()
base = UiSettings(port="COM7", current_range="high", pattern="adjacent", settle_ms=10, samples=16, lenient_quality=True)
acq.connect(base)
time.sleep(2)
try:
    for rnd in range(1, (int(sys.argv[1]) if len(sys.argv) > 1 else 6) + 1):
        for dac in (620, 100):
            acq.configure(replace(base, dac=dac)); time.sleep(0.3)
            acq._serial.reset_input_buffer()
            for k in range(3):
                f = acq.capture_frame()
                by = {}
                for r in f.records:
                    by.setdefault(r.i_pair[0], []).append(abs(r.current_ua))
                med = {e: st.median(v) for e, v in sorted(by.items())}
                allm = st.median([abs(r.current_ua) for r in f.records])
                q = sum(r.quality != "OK" for r in f.records)
                print(f"round{rnd} dac{dac} frame{k+1} med {allm:7.1f} uA  max {max(abs(r.current_ua) for r in f.records):7.1f}  nonOK {q:3} | " +
                      " ".join(f"E{e}:{m:.0f}" for e, m in med.items()), flush=True)
finally:
    acq.close()
