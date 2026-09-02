#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <Adafruit_MCP4725.h>
#include <math.h>

constexpr uint8_t PIN_SDA = 8;
constexpr uint8_t PIN_SCL = 9;
constexpr uint8_t ELECTRODE_COUNT = 12;
// The MCP4725's A0 pin selects the low bit of its address, so the same board
// answers at 0x60 or 0x61 depending on how A0 is strapped. Bench scans on this
// prototype have returned both, so the address is runtime-settable ('b') and
// bring-up probes the alternate before giving up.
constexpr uint8_t DEFAULT_MCP4725_ADDRESS = 0x61;
constexpr uint8_t ALTERNATE_MCP4725_ADDRESS = 0x60;
constexpr uint8_t MIN_MCP4725_ADDRESS = 0x60;
constexpr uint8_t MAX_MCP4725_ADDRESS = 0x67;
constexpr uint8_t ADS1115_ADDRESS = 0x48;

constexpr float DEFAULT_SHUNT_OHMS = 97.9f;
// Measured noise floor, not a nominal value. A 2026-09-02 null frame captured
// with the OPA2134 supply disconnected - no current physically possible -
// returned shunt-channel readings from 0.000 to 2.554 uA, and 10 of its 20
// measurements cleared the previous 1.0 uA floor and were stamped Q,OK. The
// floor has to sit above that noise or the flag certifies nothing (ADR-0012).
constexpr float MIN_CURRENT_UA = 10.0f;
// The over-current guard is derived per range from the fitted Rs (see
// CURRENT_RANGES) rather than being one flat ceiling. ADR-0011 has the bench
// evidence: a single 1200 uA constant sat above the whole design's 1.0 mA
// maximum, so it could not flag an over-current on LOW (design max 100 uA)
// until the reading was 12x over.
constexpr float CURRENT_GUARD_HEADROOM = 1.25f;
// ADS1115 full scale on GAIN_SIXTEEN, the fixed range readCurrentUa() uses.
constexpr float CURRENT_FULL_SCALE_MV = 256.0f;
constexpr float CURRENT_SATURATION_FRACTION = 0.99f;
constexpr float MAX_MUX_VOLTAGE_MV = 3000.0f;

constexpr uint16_t DEFAULT_DAC_CODE = 100;
constexpr uint16_t DEFAULT_SETTLE_MS = 10;
constexpr uint16_t DEFAULT_DISCHARGE_MS = 0;
constexpr uint16_t DEFAULT_FRAME_PERIOD_MS = 1000;
constexpr uint8_t DEFAULT_SAMPLE_COUNT = 4;

// Current range jumper. Rs is the Howland current-setting resistor; the DAC
// ceiling per range comes from docs/first-working-prototype/
// 03-howland-current-source.md and exists so the firmware cannot command a
// current the fitted hardware was never validated for. Defaults to LOW because
// that document requires bring-up to begin on the lowest range.
// Enumerators are prefixed because Arduino defines HIGH and LOW as
// preprocessor macros, which would otherwise expand inside this declaration.
enum class CurrentRange {
  RANGE_LOW,
  RANGE_MEDIUM,
  RANGE_HIGH,
};

struct CurrentRangeSpec {
  const char* name;
  float rsOhms;
  uint16_t maxDacCode;
  // Current at maxDacCode from Iload = VDAC * 0.02 / Rs with a 3.3 V DAC, i.e.
  // the table in docs/first-working-prototype/03-howland-current-source.md.
  float designMaxUa;
};

const CurrentRangeSpec CURRENT_RANGES[] = {
  {"LOW", 68.0f, 420, 100.0f},
  {"MEDIUM", 22.0f, 680, 500.0f},
  {"HIGH", 10.0f, 620, 1000.0f},
};

// Electrode-voltage PGA ranges, finest first. Measured saline frames put every
// electrode voltage under 250 mV while the fixed GAIN_ONE range is +/-4096 mV,
// so roughly 94 percent of the ADC's resolution was unused: one step was 125 uV,
// larger than the injected IR drop on distant pairs. Forward and reverse then
// landed on the same code and their difference came out exactly zero, which is
// why the offset check flagged 102 of 108 pairs. Picking the tightest range that
// still fits the signal is what makes those pairs resolvable.
struct VoltageRangeSpec {
  adsGain_t gain;
  float fullScaleMv;
};

const VoltageRangeSpec VOLTAGE_RANGES[] = {
  {GAIN_SIXTEEN, 256.0f},
  {GAIN_EIGHT, 512.0f},
  {GAIN_FOUR, 1024.0f},
  {GAIN_TWO, 2048.0f},
  {GAIN_ONE, 4096.0f},
};

// Keep this much room above the probed magnitude before trusting a range. A
// tree presents a far higher impedance than the saline tank, so the selected
// range has to be able to grow as well as shrink.
constexpr float VOLTAGE_RANGE_HEADROOM = 1.25f;

struct MuxPins {
  uint8_t s0;
  uint8_t s1;
  uint8_t s2;
  uint8_t s3;
  uint8_t en;
};

const MuxPins MUX_I_SRC = {4, 5, 6, 7, 37};
const MuxPins MUX_I_RET = {10, 11, 12, 13, 38};
const MuxPins MUX_VP = {15, 16, 17, 18, 39};
const MuxPins MUX_VN = {36, 35, 41, 42, 40};

const char* ELECTRODES[ELECTRODE_COUNT] = {
  "E1", "E2", "E3", "E4", "E5", "E6",
  "E7", "E8", "E9", "E10", "E11", "E12"
};

enum class DrivePattern {
  ADJACENT,
  SKIP_1,
  SKIP_2,
  OPPOSITE,
};

Adafruit_ADS1115 ads;
Adafruit_MCP4725 dac;

DrivePattern drivePattern = DrivePattern::ADJACENT;
CurrentRange currentRange = CurrentRange::RANGE_LOW;
// Rs is a physical jumper the firmware cannot read back. False until the
// operator selects a range this session with el/em/eh, which is the only
// evidence the firmware has that its assumed Rs matches the fitted one.
bool rangeDeclared = false;
bool continuousMode = false;
uint16_t requestedDacCode = DEFAULT_DAC_CODE;
uint16_t muxSettleMs = DEFAULT_SETTLE_MS;
uint16_t dischargeMs = DEFAULT_DISCHARGE_MS;
uint16_t framePeriodMs = DEFAULT_FRAME_PERIOD_MS;
uint8_t sampleCount = DEFAULT_SAMPLE_COUNT;
float shuntOhms = DEFAULT_SHUNT_OHMS;
uint8_t dacAddress = DEFAULT_MCP4725_ADDRESS;
bool voltageAutorange = true;
float lastVoltageFullScaleMv = 4096.0f;
unsigned long lastFrameMs = 0;
uint32_t frameId = 0;

const CurrentRangeSpec& rangeSpec() {
  return CURRENT_RANGES[static_cast<uint8_t>(currentRange)];
}

uint16_t maxDacCode() {
  return rangeSpec().maxDacCode;
}

// Guard ceiling for the selected range. The headroom absorbs component
// tolerance on Rs and the DAC reference so a legitimately full-scale drive is
// not flagged, while still catching the order-of-magnitude faults that a flat
// ceiling missed (ADR-0011).
float maxCurrentUa() {
  return rangeSpec().designMaxUa * CURRENT_GUARD_HEADROOM;
}

uint8_t wrapElectrode(int value) {
  while (value < 0) value += ELECTRODE_COUNT;
  return static_cast<uint8_t>(value % ELECTRODE_COUNT);
}

const char* patternName() {
  switch (drivePattern) {
    case DrivePattern::ADJACENT: return "ADJACENT";
    case DrivePattern::SKIP_1: return "SKIP-1";
    case DrivePattern::SKIP_2: return "SKIP-2";
    case DrivePattern::OPPOSITE: return "OPPOSITE";
  }
  return "UNKNOWN";
}

uint8_t injectionDistance() {
  switch (drivePattern) {
    case DrivePattern::ADJACENT: return 1;
    case DrivePattern::SKIP_1: return 2;
    case DrivePattern::SKIP_2: return 3;
    case DrivePattern::OPPOSITE: return ELECTRODE_COUNT / 2;
  }
  return 1;
}

void writeMuxAddress(const MuxPins& mux, uint8_t channel) {
  digitalWrite(mux.s0, (channel & 0x01) ? HIGH : LOW);
  digitalWrite(mux.s1, (channel & 0x02) ? HIGH : LOW);
  digitalWrite(mux.s2, (channel & 0x04) ? HIGH : LOW);
  digitalWrite(mux.s3, (channel & 0x08) ? HIGH : LOW);
}

void enableMux(const MuxPins& mux, bool enabled) {
  digitalWrite(mux.en, enabled ? LOW : HIGH);
}

void disableAllMuxes() {
  enableMux(MUX_I_SRC, false);
  enableMux(MUX_I_RET, false);
  enableMux(MUX_VP, false);
  enableMux(MUX_VN, false);
}

void setDacRaw(uint16_t code) {
  dac.setVoltage(min<uint16_t>(code, maxDacCode()), false);
}

void enterSafeIdle() {
  setDacRaw(0);
  delay(1);
  disableAllMuxes();
}

bool electrodeOverlaps(uint8_t vp, uint8_t vn, uint8_t iSrc, uint8_t iRet) {
  return vp == vn || vp == iSrc || vp == iRet || vn == iSrc || vn == iRet;
}

void configureDriveAndSense(
    uint8_t iSrc,
    uint8_t iRet,
    uint8_t vp,
    uint8_t vn) {
  setDacRaw(0);
  delay(1);
  disableAllMuxes();

  writeMuxAddress(MUX_I_SRC, iSrc);
  writeMuxAddress(MUX_I_RET, iRet);
  writeMuxAddress(MUX_VP, vp);
  writeMuxAddress(MUX_VN, vn);

  enableMux(MUX_I_RET, true);
  enableMux(MUX_I_SRC, true);
  enableMux(MUX_VP, true);
  enableMux(MUX_VN, true);

  setDacRaw(requestedDacCode);
  delay(muxSettleMs);
}

float readAveragedDifferentialMv(uint8_t pair) {
  long totalCounts = 0;
  for (uint8_t index = 0; index < sampleCount; ++index) {
    totalCounts += pair == 0
        ? ads.readADC_Differential_0_1()
        : ads.readADC_Differential_2_3();
    delay(1);
  }

  // Scale the fractional mean by the size of one LSB rather than casting it
  // back to an integer count. Re-quantising here discarded the fractional part,
  // so output granularity stayed at exactly one LSB however large sampleCount
  // was and averaging bought no resolution at all (validity-audit D-04). The
  // ADS runs at its noisiest data rate, so there is real dither to average
  // against and n16 should give roughly a 4x improvement.
  const float lsbMv = ads.computeVolts(1) * 1000.0f;
  const float averageCounts = static_cast<float>(totalCounts) / sampleCount;
  return averageCounts * lsbMv;
}

int16_t readDifferentialCounts(uint8_t pair) {
  return pair == 0
      ? ads.readADC_Differential_0_1()
      : ads.readADC_Differential_2_3();
}

// Widest range, used both as the autorange probe and as the fallback. Mux
// analog signals cannot legally exceed the 3.3 V rail, so this always fits.
constexpr size_t VOLTAGE_RANGE_FALLBACK =
    sizeof(VOLTAGE_RANGES) / sizeof(VOLTAGE_RANGES[0]) - 1;

size_t selectVoltageRange(float magnitudeMv) {
  const float required = magnitudeMv * VOLTAGE_RANGE_HEADROOM;
  for (size_t index = 0; index < VOLTAGE_RANGE_FALLBACK; ++index) {
    if (required <= VOLTAGE_RANGES[index].fullScaleMv) return index;
  }
  return VOLTAGE_RANGE_FALLBACK;
}

float readVoltageMv() {
  if (!voltageAutorange) {
    ads.setGain(VOLTAGE_RANGES[VOLTAGE_RANGE_FALLBACK].gain);
    lastVoltageFullScaleMv = VOLTAGE_RANGES[VOLTAGE_RANGE_FALLBACK].fullScaleMv;
    return readAveragedDifferentialMv(0);
  }

  // One throwaway conversion on the widest range sizes the signal, then the
  // averaged read runs on the tightest range that still fits it.
  ads.setGain(VOLTAGE_RANGES[VOLTAGE_RANGE_FALLBACK].gain);
  const float probeMv = ads.computeVolts(readDifferentialCounts(0)) * 1000.0f;
  const size_t selected = selectVoltageRange(fabsf(probeMv));
  ads.setGain(VOLTAGE_RANGES[selected].gain);
  lastVoltageFullScaleMv = VOLTAGE_RANGES[selected].fullScaleMv;

  const float measuredMv = readAveragedDifferentialMv(0);
  // If the signal grew between the probe and the averaged read the tighter
  // range can clip, so fall back rather than report a saturated value.
  if (fabsf(measuredMv) >= VOLTAGE_RANGES[selected].fullScaleMv * 0.99f
      && selected != VOLTAGE_RANGE_FALLBACK) {
    ads.setGain(VOLTAGE_RANGES[VOLTAGE_RANGE_FALLBACK].gain);
    lastVoltageFullScaleMv = VOLTAGE_RANGES[VOLTAGE_RANGE_FALLBACK].fullScaleMv;
    return readAveragedDifferentialMv(0);
  }
  return measuredMv;
}

// Unlike readVoltageMv() the current channel has no autoranging fallback, so a
// railed shunt reading would otherwise be reported as a precise-looking number
// (255.9 mV / 97.9 ohm = 2613.636 uA) indistinguishable from a real
// over-current. Record the clip so qualityFlag() can say so (ADR-0011).
bool lastCurrentSaturated = false;

float readCurrentUa() {
  ads.setGain(GAIN_SIXTEEN);  // +/-0.256 V across the current-sense shunt.
  const float shuntMv = readAveragedDifferentialMv(1);
  lastCurrentSaturated =
      fabsf(shuntMv) >= CURRENT_FULL_SCALE_MV * CURRENT_SATURATION_FRACTION;
  return shuntMv / shuntOhms * 1000.0f;
}

const char* qualityFlag(float voltageMv, float currentUa) {
  if (lastCurrentSaturated) return "I_SAT";
  if (fabsf(currentUa) < MIN_CURRENT_UA) return "I_LOW";
  if (fabsf(currentUa) > maxCurrentUa()) return "I_HIGH";
  if (currentUa < 0.0f) return "I_REVERSED";
  if (fabsf(voltageMv) > MAX_MUX_VOLTAGE_MV) return "V_RANGE";
  return "OK";
}

void printMeasurement(
    const char* polarity,
    uint8_t iSrc,
    uint8_t iRet,
    uint8_t vp,
    uint8_t vn,
    float voltageMv,
    float currentUa) {
  Serial.print("M,P,");
  Serial.print(polarity);
  Serial.print(",I+,");
  Serial.print(ELECTRODES[iSrc]);
  Serial.print(",I-,");
  Serial.print(ELECTRODES[iRet]);
  Serial.print(",V+,");
  Serial.print(ELECTRODES[vp]);
  Serial.print(",V-,");
  Serial.print(ELECTRODES[vn]);
  Serial.print(",V,");
  Serial.print(voltageMv, 3);
  Serial.print(",I,");
  Serial.print(currentUa, 3);
  Serial.print(",Q,");
  Serial.println(qualityFlag(voltageMv, currentUa));
}

void emitMeasurement(
    const char* polarity,
    uint8_t iSrc,
    uint8_t iRet,
    uint8_t vp,
    uint8_t vn) {
  configureDriveAndSense(iSrc, iRet, vp, vn);
  const float currentUa = readCurrentUa();
  const float voltageMv = readVoltageMv();
  printMeasurement(polarity, iSrc, iRet, vp, vn, voltageMv, currentUa);
  enterSafeIdle();
  if (dischargeMs > 0) delay(dischargeMs);
}

// Forward and reverse are captured back to back for each sense pair so net DC
// per electrode stays near zero across the frame. Running every forward
// measurement before any reverse measurement lets an ionic double layer build
// up on the electrodes, which shows up as current decaying across a fixed
// injection pair and as forward/reverse voltages that stop inverting - the
// latter collapses paired_transfer_resistance() toward zero on the host side.
void emitInjectionPair(uint8_t iSrc, uint8_t iRet) {
  for (uint8_t vp = 0; vp < ELECTRODE_COUNT; ++vp) {
    const uint8_t vn = wrapElectrode(vp + 1);
    if (electrodeOverlaps(vp, vn, iSrc, iRet)) continue;

    emitMeasurement("FWD", iSrc, iRet, vp, vn);
    emitMeasurement("REV", iRet, iSrc, vp, vn);
  }
}

void emitFrame() {
  ++frameId;
  Serial.print("FRAME,2,");
  Serial.print(frameId);
  Serial.print(",");
  Serial.print(patternName());
  Serial.print(",DAC,");
  Serial.print(requestedDacCode);
  Serial.print(",SETTLE,");
  Serial.print(muxSettleMs);
  Serial.print(",SAMPLES,");
  Serial.println(sampleCount);

  const uint8_t distance = injectionDistance();
  for (uint8_t iSrc = 0; iSrc < ELECTRODE_COUNT; ++iSrc) {
    const uint8_t iRet = wrapElectrode(iSrc + distance);
    emitInjectionPair(iSrc, iRet);
  }

  enterSafeIdle();
  Serial.print("END,");
  Serial.println(frameId);
}

void setRequestedDac(uint16_t code) {
  const uint16_t ceiling = maxDacCode();
  requestedDacCode = min<uint16_t>(code, ceiling);
  enterSafeIdle();
  Serial.print("[DAC] requested=");
  Serial.print(requestedDacCode);
  Serial.println(" idle_output=0");
  if (code > ceiling) {
    Serial.print("[LIMIT] clipped to code ");
    Serial.print(ceiling);
    Serial.print(" for range ");
    Serial.println(rangeSpec().name);
  }
}

void setCurrentRange(CurrentRange range) {
  currentRange = range;
  rangeDeclared = true;
  if (requestedDacCode > maxDacCode()) {
    requestedDacCode = maxDacCode();
    Serial.print("[LIMIT] DAC lowered to ");
    Serial.print(requestedDacCode);
    Serial.print(" for range ");
    Serial.println(rangeSpec().name);
  }
  enterSafeIdle();
}

void printStatus() {
  Serial.print("STATUS,2,MODE,");
  Serial.print(patternName());
  Serial.print(",DAC,");
  Serial.print(requestedDacCode);
  Serial.print(",SETTLE,");
  Serial.print(muxSettleMs);
  Serial.print(",DISCHARGE,");
  Serial.print(dischargeMs);
  Serial.print(",SAMPLES,");
  Serial.print(sampleCount);
  Serial.print(",RANGE,");
  Serial.print(rangeSpec().name);
  Serial.print(",RS_OHMS,");
  Serial.print(rangeSpec().rsOhms, 1);
  Serial.print(",MAX_DAC_CODE,");
  Serial.print(maxDacCode());
  Serial.print(",SHUNT_OHMS,");
  Serial.print(shuntOhms, 2);
  Serial.print(",DAC_ADDR,0x");
  Serial.print(dacAddress, HEX);
  Serial.print(",VGAIN_AUTO,");
  Serial.print(voltageAutorange ? 1 : 0);
  Serial.print(",VRANGE_MV,");
  Serial.print(lastVoltageFullScaleMv, 1);
  Serial.print(",MIN_CURRENT_UA,");
  Serial.print(MIN_CURRENT_UA, 1);
  Serial.print(",MAX_CURRENT_UA,");
  Serial.print(maxCurrentUa(), 1);
  Serial.print(",RS_DECLARED,");
  Serial.println(rangeDeclared ? 1 : 0);
}

// Rebinds the DAC driver to `address` and parks the output at zero. The bus is
// probed directly first: some Adafruit_MCP4725 versions return success from
// begin() without ever addressing the part, and setDacRaw() discards
// setVoltage()'s return, so an unacknowledged address would otherwise leave the
// current source stuck at whatever code its EEPROM powered up with while the
// firmware reported the commanded value. dacAddress is left untouched on
// failure so the caller can fall back.
bool attachDac(uint8_t address) {
  if (address < MIN_MCP4725_ADDRESS || address > MAX_MCP4725_ADDRESS) return false;
  Wire.beginTransmission(address);
  if (Wire.endTransmission() != 0) return false;
  if (!dac.begin(address)) return false;
  dacAddress = address;
  setDacRaw(0);
  return true;
}

void setDacAddress(uint8_t address) {
  const uint8_t previous = dacAddress;
  if (address < MIN_MCP4725_ADDRESS || address > MAX_MCP4725_ADDRESS) {
    Serial.print("[ERROR] DAC address must be 0x");
    Serial.print(MIN_MCP4725_ADDRESS, HEX);
    Serial.print(" to 0x");
    Serial.println(MAX_MCP4725_ADDRESS, HEX);
    return;
  }
  continuousMode = false;
  enterSafeIdle();
  if (!attachDac(address)) {
    Serial.print("[ERROR] no MCP4725 acknowledged at 0x");
    Serial.println(address, HEX);
    attachDac(previous);
    Serial.print("[INFO] still on 0x");
    Serial.println(dacAddress, HEX);
    return;
  }
  Serial.print("[INFO] MCP4725 attached at 0x");
  Serial.println(dacAddress, HEX);
  printStatus();
}

void printI2CScan() {
  Serial.println("I2C_SCAN,BEGIN");
  uint8_t found = 0;
  for (uint8_t address = 1; address < 127; ++address) {
    Wire.beginTransmission(address);
    const uint8_t error = Wire.endTransmission();
    if (error == 0) {
      Serial.print("I2C_DEVICE,0x");
      if (address < 16) Serial.print("0");
      Serial.println(address, HEX);
      ++found;
    }
  }
  Serial.print("I2C_SCAN,END,FOUND,");
  Serial.println(found);
}

void printHelp() {
  Serial.println();
  Serial.println("ESP32-S3 Phase 3A Unified ERT Scanner v2");
  Serial.println("s       capture one forward/reverse frame");
  Serial.println("ma      select adjacent drive");
  Serial.println("ms      select skip-1 drive");
  Serial.println("mk      select skip-2 drive");
  Serial.println("mo      select opposite drive");
  Serial.println("pN      set requested DAC code, clipped to the range ceiling; output remains idle");
  Serial.println("tN      set mux settle time in ms");
  Serial.println("cN      set post-measurement discharge time in ms, 0 disables");
  Serial.println("nN      set samples per ADC reading, 1..32");
  Serial.println("el      select LOW current range, Rs 68 ohm, DAC ceiling 420");
  Serial.println("em      select MEDIUM current range, Rs 22 ohm, DAC ceiling 680");
  Serial.println("eh      select HIGH current range, Rs 10 ohm, DAC ceiling 620");
  Serial.println("        el/em/eh must match the fitted Rs jumper; STATUS RS_DECLARED shows it");
  Serial.println("jN.N    set current-sense shunt value in ohms");
  Serial.println("a1 / a0 enable or disable electrode-voltage PGA autoranging");
  Serial.println("g       continuous frames on");
  Serial.println("x       stop and force safe idle");
  Serial.println("rN      set continuous frame interval in ms");
  Serial.println("i       scan I2C bus for MCP4725 and ADS1115");
  Serial.println("bNN     set MCP4725 I2C address in hex, e.g. b60 or b61; b alone reports");
  Serial.println("d       DEBUG HOLD: turn on DAC and MUX E1/E2 permanently for multimeter testing");
  Serial.println("?       print status");
  Serial.println("h       print help");
}

void debugHold() {
  // Hold E1(0) and E2(1) as current source/return, and E3(2), E4(3) as voltage sense.
  configureDriveAndSense(0, 1, 2, 3); 
  Serial.println("[DEBUG] Holding E1 (I+), E2 (I-), E3 (V+), E4 (V-) ON at current DAC level.");
  Serial.println("[DEBUG] Use your multimeter now! Send 'x' to stop and idle.");
}

void handleCommand(String line) {
  line.trim();
  line.toLowerCase();
  if (!line.length()) return;

  if (line == "ma") {
    drivePattern = DrivePattern::ADJACENT;
    enterSafeIdle();
    printStatus();
    return;
  }
  if (line == "ms") {
    drivePattern = DrivePattern::SKIP_1;
    enterSafeIdle();
    printStatus();
    return;
  }
  if (line == "mk") {
    drivePattern = DrivePattern::SKIP_2;
    enterSafeIdle();
    printStatus();
    return;
  }
  if (line == "mo") {
    drivePattern = DrivePattern::OPPOSITE;
    enterSafeIdle();
    printStatus();
    return;
  }
  if (line == "el") {
    setCurrentRange(CurrentRange::RANGE_LOW);
    printStatus();
    return;
  }
  if (line == "em") {
    setCurrentRange(CurrentRange::RANGE_MEDIUM);
    printStatus();
    return;
  }
  if (line == "eh") {
    setCurrentRange(CurrentRange::RANGE_HIGH);
    printStatus();
    return;
  }

  const char command = line.charAt(0);
  const long parsedValue = line.length() > 1 ? line.substring(1).toInt() : 0;
  const uint16_t value = parsedValue < 0 ? 0 : static_cast<uint16_t>(parsedValue);

  switch (command) {
    case 's': emitFrame(); break;
    case 'g': continuousMode = true; Serial.println("[MODE] continuous enabled"); break;
    case 'x': continuousMode = false; enterSafeIdle(); Serial.println("[MODE] stopped; current idle"); break;
    case 'p': setRequestedDac(value); break;
    case 't': muxSettleMs = max<uint16_t>(value, 1); printStatus(); break;
    case 'c': dischargeMs = value; printStatus(); break;
    case 'j': {
      const float parsedShunt = line.substring(1).toFloat();
      if (parsedShunt <= 0.0f) {
        Serial.println("[ERROR] shunt must be greater than zero");
      } else {
        shuntOhms = parsedShunt;
      }
      printStatus();
      break;
    }
    case 'a': voltageAutorange = value != 0; printStatus(); break;
    case 'b': {
      // Hex, not decimal: the argument is read straight off an I2C scan line.
      const String argument = line.substring(1);
      if (!argument.length()) {
        printStatus();
        break;
      }
      setDacAddress(static_cast<uint8_t>(strtol(argument.c_str(), nullptr, 16)));
      break;
    }
    case 'n': sampleCount = constrain(value, 1, 32); printStatus(); break;
    case 'r': framePeriodMs = max<uint16_t>(value, 100); printStatus(); break;
    case 'i': printI2CScan(); break;
    case 'd': debugHold(); break;
    case '?': printStatus(); break;
    case 'h': printHelp(); break;
    default: Serial.println("[ERROR] unknown command; send h"); break;
  }
}

void configureMuxPins(const MuxPins& mux) {
  pinMode(mux.en, OUTPUT);
  enableMux(mux, false);
  pinMode(mux.s0, OUTPUT);
  pinMode(mux.s1, OUTPUT);
  pinMode(mux.s2, OUTPUT);
  pinMode(mux.s3, OUTPUT);
  writeMuxAddress(mux, 0);
}

void configurePins() {
  configureMuxPins(MUX_I_SRC);
  configureMuxPins(MUX_I_RET);
  configureMuxPins(MUX_VP);
  configureMuxPins(MUX_VN);
  disableAllMuxes();
}

void configureI2CDevices() {
  Wire.begin(PIN_SDA, PIN_SCL);
  if (!attachDac(DEFAULT_MCP4725_ADDRESS)
      && !attachDac(ALTERNATE_MCP4725_ADDRESS)) {
    Serial.print("[FATAL] MCP4725 not found at 0x");
    Serial.print(DEFAULT_MCP4725_ADDRESS, HEX);
    Serial.print(" or 0x");
    Serial.println(ALTERNATE_MCP4725_ADDRESS, HEX);
    Serial.println("[FATAL] send i on a working build to scan, or check the A0 strap");
    while (true) delay(1000);
  }
  Serial.print("[INFO] MCP4725 attached at 0x");
  Serial.println(dacAddress, HEX);

  if (!ads.begin(ADS1115_ADDRESS, &Wire)) {
    Serial.print("[FATAL] ADS1115 not found at 0x");
    Serial.println(ADS1115_ADDRESS, HEX);
    while (true) delay(1000);
  }
  ads.setDataRate(RATE_ADS1115_860SPS);
}

void setup() {
  Serial.begin(115200);
  delay(1200);
  configurePins();
  configureI2CDevices();
  enterSafeIdle();
  printHelp();
  printStatus();
  Serial.println("[WARN] Rs is a physical jumper the firmware cannot read back.");
  Serial.print("[WARN] Assuming range ");
  Serial.print(rangeSpec().name);
  Serial.print(" (Rs ");
  Serial.print(rangeSpec().rsOhms, 1);
  Serial.println(" ohm) until el/em/eh confirms the fitted jumper.");
}

void loop() {
  if (Serial.available()) handleCommand(Serial.readStringUntil('\n'));
  if (continuousMode && millis() - lastFrameMs >= framePeriodMs) {
    emitFrame();
    lastFrameMs = millis();
  }
}