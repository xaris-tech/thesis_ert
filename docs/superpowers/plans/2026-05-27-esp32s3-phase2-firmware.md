# ESP32-S3 Phase 2 Firmware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build PlatformIO-based ESP32-S3 firmware that scans 8 electrodes through a CD74HC4067 and streams `ert.py`-compatible frames over serial.

**Architecture:** The firmware will keep hardware setup in one `main.cpp` file because the repo is currently tiny, but it will still separate behavior into small functions for mux selection, scan acquisition, serial command handling, and frame emission. The output format will match the Python parser exactly so the user can flash and test immediately.

**Tech Stack:** PlatformIO, Arduino framework for ESP32-S3, Wire, Adafruit MCP4725, Adafruit ADS1X15

---

### Task 1: Scaffold the firmware project

**Files:**
- Create: `C:\Users\Vidad\Documents\ERT\firmware\esp32s3-phase2\platformio.ini`
- Create: `C:\Users\Vidad\Documents\ERT\firmware\esp32s3-phase2\src\main.cpp`
- Create: `C:\Users\Vidad\Documents\ERT\firmware\esp32s3-phase2\README.md`

- [ ] **Step 1: Write the failing test**

Inspect for the missing project files.

- [ ] **Step 2: Run test to verify it fails**

Run: `Test-Path .\firmware\esp32s3-phase2\platformio.ini`
Expected: `False`

- [ ] **Step 3: Write minimal implementation**

Create a PlatformIO project targeting ESP32-S3 with Arduino and declare the Adafruit ADS1115 and MCP4725 libraries.

- [ ] **Step 4: Run test to verify it passes**

Run: `Test-Path .\firmware\esp32s3-phase2\platformio.ini`
Expected: `True`

### Task 2: Add the scan protocol and command loop

**Files:**
- Modify: `C:\Users\Vidad\Documents\ERT\firmware\esp32s3-phase2\src\main.cpp`

- [ ] **Step 1: Write the failing test**

Inspect the source for missing serial frame markers.

- [ ] **Step 2: Run test to verify it fails**

Run: `Select-String -Path .\firmware\esp32s3-phase2\src\main.cpp -Pattern 'Serial.println\("SCAN:"\)'`
Expected: no matches before implementation

- [ ] **Step 3: Write minimal implementation**

Add setup, mux channel selection, ADS1115 differential reads, frame output, and serial commands `s`, `g`, `x`, `p`, `t`, `h`.

- [ ] **Step 4: Run test to verify it passes**

Run: `Select-String -Path .\firmware\esp32s3-phase2\src\main.cpp -Pattern 'Serial.println\("SCAN:"\)'`
Expected: one match

### Task 3: Document flashing and wiring assumptions

**Files:**
- Modify: `C:\Users\Vidad\Documents\ERT\firmware\esp32s3-phase2\README.md`

- [ ] **Step 1: Write the failing test**

Inspect the README for missing upload and monitor commands.

- [ ] **Step 2: Run test to verify it fails**

Run: `Select-String -Path .\firmware\esp32s3-phase2\README.md -Pattern 'pio run -t upload'`
Expected: no matches before implementation

- [ ] **Step 3: Write minimal implementation**

Document required wiring assumptions, dependencies, and the exact PlatformIO commands for upload and serial monitor.

- [ ] **Step 4: Run test to verify it passes**

Run: `Select-String -Path .\firmware\esp32s3-phase2\README.md -Pattern 'pio run -t upload'`
Expected: one match
