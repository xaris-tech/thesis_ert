# Control Drift Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a same-condition diagnostic mode that quantifies frame, measurement-pair, and electrode instability without producing misleading reconstructions.

**Architecture:** Reuse the existing warm-up, baseline validation, frame parser, and normalized transfer-resistance vectors. A pure analysis function produces ranked stability records, while a CSV writer persists them and `--control` selects the diagnostic acquisition path.

**Tech Stack:** Python, NumPy, CSV, unittest, pyserial.

---

### Task 1: Pure control analysis

**Files:**
- Modify: `phase3a_unified_reconstruct.py`
- Test: `tests/test_phase3a_unified_reconstruct.py`

- [ ] Write failing tests using synthetic vectors with one intentionally unstable protocol measurement.
- [ ] Verify tests fail because control analysis is absent.
- [ ] Implement per-frame RMS/correlation, ranked measurement-pair RMS, and electrode aggregation.
- [ ] Verify focused tests pass.

### Task 2: Report and CLI workflow

**Files:**
- Modify: `phase3a_unified_reconstruct.py`
- Test: `tests/test_phase3a_unified_reconstruct.py`

- [ ] Write failing tests for the report path and CSV record types.
- [ ] Add `--control`, skip target/reconstruction in that mode, and save the stability CSV.
- [ ] Run the complete test suite, import smoke test, and CLI help smoke test.
