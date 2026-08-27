# Phase 3A Soldering & QA Checklist

**Instructions:** 
This is a standard Markdown file. You can open this in your IDE (like VS Code), Obsidian, or GitHub. Because it is a physical file, marking an `x` in the brackets (like `[x]`) physically saves the state to your hard drive. It is completely immune to browser cache clears.

---

## 1. ESP32-S3 Microcontroller

### Power & I2C
- [ ] **Soldered** | [ ] **Verified** | `3V3` -> MCP4725 VDD, ADS1115 VDD, 4x MUX VCC
- [ ] **Soldered** | [ ] **Verified** | `GND` -> All module GNDs
- [ ] **Soldered** | [ ] **Verified** | `GPIO8` -> I2C SDA (DAC & ADC)
- [ ] **Soldered** | [ ] **Verified** | `GPIO9` -> I2C SCL (DAC & ADC)

### MUX_I_SRC (Source Current)
- [ ] **Soldered** | [ ] **Verified** | `GPIO37` -> MUX_I_SRC EN
- [ ] **Soldered** | [ ] **Verified** | `GPIO4`  -> MUX_I_SRC S0
- [ ] **Soldered** | [ ] **Verified** | `GPIO5`  -> MUX_I_SRC S1
- [ ] **Soldered** | [ ] **Verified** | `GPIO6`  -> MUX_I_SRC S2
- [ ] **Soldered** | [ ] **Verified** | `GPIO7`  -> MUX_I_SRC S3

### MUX_I_RET (Return Current)
- [ ] **Soldered** | [ ] **Verified** | `GPIO38` -> MUX_I_RET EN
- [ ] **Soldered** | [ ] **Verified** | `GPIO10` -> MUX_I_RET S0
- [ ] **Soldered** | [ ] **Verified** | `GPIO11` -> MUX_I_RET S1
- [ ] **Soldered** | [ ] **Verified** | `GPIO12` -> MUX_I_RET S2
- [ ] **Soldered** | [ ] **Verified** | `GPIO13` -> MUX_I_RET S3

### MUX_VP (Voltage Positive)
- [ ] **Soldered** | [ ] **Verified** | `GPIO39` -> MUX_VP EN
- [ ] **Soldered** | [ ] **Verified** | `GPIO15` -> MUX_VP S0
- [ ] **Soldered** | [ ] **Verified** | `GPIO16` -> MUX_VP S1
- [ ] **Soldered** | [ ] **Verified** | `GPIO17` -> MUX_VP S2
- [ ] **Soldered** | [ ] **Verified** | `GPIO18` -> MUX_VP S3

### MUX_VN (Voltage Negative)
- [ ] **Soldered** | [ ] **Verified** | `GPIO40` -> MUX_VN EN
- [ ] **Soldered** | [ ] **Verified** | `GPIO36` -> MUX_VN S0
- [ ] **Soldered** | [ ] **Verified** | `GPIO35` -> MUX_VN S1
- [ ] **Soldered** | [ ] **Verified** | `GPIO41` -> MUX_VN S2
- [ ] **Soldered** | [ ] **Verified** | `GPIO42` -> MUX_VN S3

---

## 2. CD74HC4067 Multiplexers

### MUX_I_SRC (Source Current)
- [ ] **Soldered** | [ ] **Verified** | `VCC` -> ESP32 3V3
- [ ] **Soldered** | [ ] **Verified** | `GND` -> System GND
- [ ] **Soldered** | [ ] **Verified** | `SIG/COM` -> OPA2134PA Pin 5 Junction (Current output)
- [ ] **Soldered** | [ ] **Verified** | `C0 - C11` -> Electrodes E1-E12 Bus

### MUX_I_RET (Return Current)
- [ ] **Soldered** | [ ] **Verified** | `VCC` -> ESP32 3V3
- [ ] **Soldered** | [ ] **Verified** | `GND` -> System GND
- [ ] **Soldered** | [ ] **Verified** | `SIG/COM` -> System GND (or 100Ω shunt to GND)
- [ ] **Soldered** | [ ] **Verified** | `C0 - C11` -> Electrodes E1-E12 Bus

### MUX_VP (Voltage Positive)
- [ ] **Soldered** | [ ] **Verified** | `VCC` -> ESP32 3V3
- [ ] **Soldered** | [ ] **Verified** | `GND` -> System GND
- [ ] **Soldered** | [ ] **Verified** | `SIG/COM` -> ADS1115 A0
- [ ] **Soldered** | [ ] **Verified** | `C0 - C11` -> Electrodes E1-E12 Bus

### MUX_VN (Voltage Negative)
- [ ] **Soldered** | [ ] **Verified** | `VCC` -> ESP32 3V3
- [ ] **Soldered** | [ ] **Verified** | `GND` -> System GND
- [ ] **Soldered** | [ ] **Verified** | `SIG/COM` -> ADS1115 A1
- [ ] **Soldered** | [ ] **Verified** | `C0 - C11` -> Electrodes E1-E12 Bus

---

## 3. MCP4725 (DAC)
- [ ] **Soldered** | [ ] **Verified** | `VDD` -> ESP32 3V3
- [ ] **Soldered** | [ ] **Verified** | `GND` -> System GND
- [ ] **Soldered** | [ ] **Verified** | `SDA` -> ESP32 GPIO8
- [ ] **Soldered** | [ ] **Verified** | `SCL` -> ESP32 GPIO9
- [ ] **Soldered** | [ ] **Verified** | `ADDR` -> GND
- [ ] **Soldered** | [ ] **Verified** | `VOUT` -> Resistor R3 (5kΩ to OPA2134PA Pin 3)

---

## 4. ADS1115 (ADC)
- [ ] **Soldered** | [ ] **Verified** | `VDD` -> ESP32 3V3
- [ ] **Soldered** | [ ] **Verified** | `GND` -> System GND
- [ ] **Soldered** | [ ] **Verified** | `SDA` -> ESP32 GPIO8
- [ ] **Soldered** | [ ] **Verified** | `SCL` -> ESP32 GPIO9
- [ ] **Soldered** | [ ] **Verified** | `ADDR` -> GND
- [ ] **Soldered** | [ ] **Verified** | `A0` -> MUX_VP SIG/COM
- [ ] **Soldered** | [ ] **Verified** | `A1` -> MUX_VN SIG/COM

---

## 5. OPA2134PA Current Pump (TI Design 2)
- [ ] **Soldered** | [ ] **Verified** | **R1 (5kΩ)** -> Between Pin 2 and GND
- [ ] **Soldered** | [ ] **Verified** | **R2 (100Ω)** -> Between Pin 1 and Pin 2
- [ ] **Soldered** | [ ] **Verified** | **R3 (5kΩ)** -> Between DAC VOUT and Pin 3
- [ ] **Soldered** | [ ] **Verified** | **R4 (100Ω)** -> Between Pin 7 and Pin 3
- [ ] **Soldered** | [ ] **Verified** | **Rs (68Ω)** -> Between Pin 1 and Pin 5
- [ ] **Soldered** | [ ] **Verified** | `Pin 4 (V-)` -> System GND (or Negative Supply)
- [ ] **Soldered** | [ ] **Verified** | `Pin 6 (Inv B)` -> Tied directly to Pin 7
- [ ] **Soldered** | [ ] **Verified** | `Pin 8 (V+)` -> Positive Supply (+9V)
- [ ] **Soldered** | [ ] **Verified** | `Pin 5 Junction` -> MUX_I_SRC SIG/COM
