#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <Adafruit_MCP4725.h>
#include <math.h>

constexpr uint8_t PIN_SDA = 8;
constexpr uint8_t PIN_SCL = 9;
constexpr uint8_t ELECTRODE_COUNT = 12;
constexpr uint8_t MCP4725_ADDRESS = 0x60;
constexpr uint8_t ADS1115_ADDRESS = 0x48;

constexpr float SHUNT_OHMS = 100.0f;
constexpr float MIN_CURRENT_UA = 1.0f;
constexpr float MAX_CURRENT_UA = 1200.0f;
constexpr float MAX_MUX_VOLTAGE_MV = 3000.0f;

constexpr uint16_t DEFAULT_DAC_CODE = 100;
constexpr uint16_t MAX_DAC_CODE = 620;
constexpr uint16_t DEFAULT_SETTLE_MS = 10;
constexpr uint16_t DEFAULT_FRAME_PERIOD_MS = 1000;
constexpr uint8_t DEFAULT_SAMPLE_COUNT = 4;

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
  OPPOSITE,
};

Adafruit_ADS1115 ads;
Adafruit_MCP4725 dac;

DrivePattern drivePattern = DrivePattern::ADJACENT;
bool continuousMode = false;
uint16_t requestedDacCode = DEFAULT_DAC_CODE;
uint16_t muxSettleMs = DEFAULT_SETTLE_MS;
uint16_t framePeriodMs = DEFAULT_FRAME_PERIOD_MS;
uint8_t sampleCount = DEFAULT_SAMPLE_COUNT;
unsigned long lastFrameMs = 0;
uint32_t frameId = 0;

uint8_t wrapElectrode(int value) {
  while (value < 0) value += ELECTRODE_COUNT;
  return static_cast<uint8_t>(value % ELECTRODE_COUNT);
}

const char* patternName() {
  return drivePattern == DrivePattern::ADJACENT ? "ADJACENT" : "OPPOSITE";
}

uint8_t injectionDistance() {
  return drivePattern == DrivePattern::ADJACENT ? 1 : ELECTRODE_COUNT / 2;
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
  dac.setVoltage(min<uint16_t>(code, MAX_DAC_CODE), false);
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
  const int16_t averageCounts = static_cast<int16_t>(
      static_cast<float>(totalCounts) / sampleCount);
  return ads.computeVolts(averageCounts) * 1000.0f;
}

float readVoltageMv() {
  ads.setGain(GAIN_ONE);  // +/-4.096 V; mux signals must remain below 3.3 V.
  return readAveragedDifferentialMv(0);
}

float readCurrentUa() {
  ads.setGain(GAIN_SIXTEEN);  // +/-0.256 V for the 100-ohm shunt.
  const float shuntMv = readAveragedDifferentialMv(1);
  return shuntMv / SHUNT_OHMS * 1000.0f;
}

const char* qualityFlag(float voltageMv, float currentUa) {
  if (fabsf(currentUa) < MIN_CURRENT_UA) return "I_LOW";
  if (fabsf(currentUa) > MAX_CURRENT_UA) return "I_HIGH";
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

void emitPolarity(
    const char* polarity,
    uint8_t iSrc,
    uint8_t iRet) {
  for (uint8_t vp = 0; vp < ELECTRODE_COUNT; ++vp) {
    const uint8_t vn = wrapElectrode(vp + 1);
    if (electrodeOverlaps(vp, vn, iSrc, iRet)) continue;

    configureDriveAndSense(iSrc, iRet, vp, vn);
    const float currentUa = readCurrentUa();
    const float voltageMv = readVoltageMv();
    printMeasurement(polarity, iSrc, iRet, vp, vn, voltageMv, currentUa);
    enterSafeIdle();
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
    emitPolarity("FWD", iSrc, iRet);
    emitPolarity("REV", iRet, iSrc);
  }

  enterSafeIdle();
  Serial.print("END,");
  Serial.println(frameId);
}

void setRequestedDac(uint16_t code) {
  requestedDacCode = min<uint16_t>(code, MAX_DAC_CODE);
  enterSafeIdle();
  Serial.print("[DAC] requested=");
  Serial.print(requestedDacCode);
  Serial.println(" idle_output=0");
  if (code > MAX_DAC_CODE) {
    Serial.println("[LIMIT] clipped to code 620");
  }
}

void printStatus() {
  Serial.print("STATUS,2,MODE,");
  Serial.print(patternName());
  Serial.print(",DAC,");
  Serial.print(requestedDacCode);
  Serial.print(",SETTLE,");
  Serial.print(muxSettleMs);
  Serial.print(",SAMPLES,");
  Serial.print(sampleCount);
  Serial.print(",SHUNT_OHMS,");
  Serial.print(SHUNT_OHMS, 1);
  Serial.print(",MIN_CURRENT_UA,");
  Serial.print(MIN_CURRENT_UA, 1);
  Serial.print(",MAX_CURRENT_UA,");
  Serial.println(MAX_CURRENT_UA, 1);
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
  Serial.println("mo      select opposite drive");
  Serial.println("pN      set requested DAC code 0..620; output remains idle");
  Serial.println("tN      set mux settle time in ms");
  Serial.println("nN      set samples per ADC reading, 1..32");
  Serial.println("g       continuous frames on");
  Serial.println("x       stop and force safe idle");
  Serial.println("rN      set continuous frame interval in ms");
  Serial.println("i       scan I2C bus for MCP4725 and ADS1115");
  Serial.println("?       print status");
  Serial.println("h       print help");
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
  if (line == "mo") {
    drivePattern = DrivePattern::OPPOSITE;
    enterSafeIdle();
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
    case 'n': sampleCount = constrain(value, 1, 32); printStatus(); break;
    case 'r': framePeriodMs = max<uint16_t>(value, 100); printStatus(); break;
    case 'i': printI2CScan(); break;
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
  if (!dac.begin(MCP4725_ADDRESS)) {
    Serial.println("[FATAL] MCP4725 not found at 0x60");
    while (true) delay(1000);
  }
  setDacRaw(0);

  if (!ads.begin(ADS1115_ADDRESS, &Wire)) {
    Serial.println("[FATAL] ADS1115 not found at 0x48");
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
}

void loop() {
  if (Serial.available()) handleCommand(Serial.readStringUntil('\n'));
  if (continuousMode && millis() - lastFrameMs >= framePeriodMs) {
    emitFrame();
    lastFrameMs = millis();
  }
}
