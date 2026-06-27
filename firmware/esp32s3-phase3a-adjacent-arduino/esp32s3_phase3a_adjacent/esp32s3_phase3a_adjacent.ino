#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <Adafruit_MCP4725.h>

constexpr uint8_t PIN_SDA = 8;
constexpr uint8_t PIN_SCL = 9;
constexpr uint8_t ELECTRODE_COUNT = 12;
constexpr uint8_t INJECTION_DISTANCE = 1;
constexpr uint8_t SAMPLE_COUNT = 4;
constexpr uint16_t DEFAULT_DAC_CODE = 300;
constexpr uint16_t DEFAULT_SETTLE_MS = 10;
constexpr uint16_t DEFAULT_FRAME_PERIOD_MS = 500;
constexpr uint8_t MCP4725_ADDRESS = 0x60;
constexpr uint8_t ADS1115_ADDRESS = 0x48;

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

Adafruit_ADS1115 ads;
Adafruit_MCP4725 dac;

bool continuousMode = false;
uint16_t dacCode = DEFAULT_DAC_CODE;
uint16_t muxSettleMs = DEFAULT_SETTLE_MS;
uint16_t framePeriodMs = DEFAULT_FRAME_PERIOD_MS;
unsigned long lastFrameMs = 0;

uint8_t wrapElectrode(int value) {
  while (value < 0) value += ELECTRODE_COUNT;
  return static_cast<uint8_t>(value % ELECTRODE_COUNT);
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

void selectMux(const MuxPins& mux, uint8_t electrode) {
  writeMuxAddress(mux, electrode);
  enableMux(mux, true);
}

bool electrodeOverlaps(uint8_t vp, uint8_t vn, uint8_t iSrc, uint8_t iRet) {
  return vp == vn || vp == iSrc || vp == iRet || vn == iSrc || vn == iRet;
}

float readDifferentialMv() {
  delay(muxSettleMs);
  long totalCounts = 0;
  for (uint8_t index = 0; index < SAMPLE_COUNT; ++index) {
    totalCounts += ads.readADC_Differential_0_1();
    delay(1);
  }
  const float averageCounts = static_cast<float>(totalCounts) / SAMPLE_COUNT;
  return ads.computeVolts(static_cast<int16_t>(averageCounts)) * 1000.0f;
}

void printMeasurement(uint8_t iSrc, uint8_t iRet, uint8_t vp, uint8_t vn, float mv) {
  Serial.print("I+,");
  Serial.print(ELECTRODES[iSrc]);
  Serial.print(",I-,");
  Serial.print(ELECTRODES[iRet]);
  Serial.print(",V+,");
  Serial.print(ELECTRODES[vp]);
  Serial.print(",V-,");
  Serial.print(ELECTRODES[vn]);
  Serial.print(",V,");
  Serial.println(mv, 3);
}

void emitFrame() {
  Serial.println("FRAME:");
  for (uint8_t iSrc = 0; iSrc < ELECTRODE_COUNT; ++iSrc) {
    const uint8_t iRet = wrapElectrode(iSrc + INJECTION_DISTANCE);
    selectMux(MUX_I_SRC, iSrc);
    selectMux(MUX_I_RET, iRet);

    for (uint8_t vp = 0; vp < ELECTRODE_COUNT; ++vp) {
      const uint8_t vn = wrapElectrode(vp + 1);
      if (electrodeOverlaps(vp, vn, iSrc, iRet)) continue;
      selectMux(MUX_VP, vp);
      selectMux(MUX_VN, vn);
      printMeasurement(iSrc, iRet, vp, vn, readDifferentialMv());
    }
  }
  disableAllMuxes();
  Serial.println("END");
}

void updateDac(uint16_t newCode) {
  dacCode = min<uint16_t>(newCode, 4095);
  dac.setVoltage(dacCode, false);
  Serial.print("[DAC] raw code set to ");
  Serial.println(dacCode);
}

void printHelp() {
  Serial.println();
  Serial.println("ESP32-S3 Phase 3A Adjacent ERT Scanner");
  Serial.println("Commands: s=single frame, g=continuous, x=stop, p<number>=DAC, t<number>=settle ms, r<number>=period ms, h=help");
  Serial.println();
}

void handleCommand(String line) {
  line.trim();
  if (!line.length()) return;
  const char command = static_cast<char>(tolower(line.charAt(0)));
  const uint16_t value = line.length() > 1 ? static_cast<uint16_t>(line.substring(1).toInt()) : 0;

  switch (command) {
    case 's': emitFrame(); break;
    case 'g': continuousMode = true; Serial.println("[Mode] continuous enabled"); break;
    case 'x': continuousMode = false; disableAllMuxes(); Serial.println("[Mode] continuous disabled"); break;
    case 'p': updateDac(value); break;
    case 't': muxSettleMs = max<uint16_t>(value, 1); Serial.println("[Timing] settle updated"); break;
    case 'r': framePeriodMs = max<uint16_t>(value, 100); Serial.println("[Timing] period updated"); break;
    case 'h': printHelp(); break;
    default: Serial.println("[Error] unknown command, use h"); break;
  }
}

void configureMuxPins(const MuxPins& mux) {
  pinMode(mux.s0, OUTPUT);
  pinMode(mux.s1, OUTPUT);
  pinMode(mux.s2, OUTPUT);
  pinMode(mux.s3, OUTPUT);
  pinMode(mux.en, OUTPUT);
  writeMuxAddress(mux, 0);
  enableMux(mux, false);
}

void configurePins() {
  configureMuxPins(MUX_I_SRC);
  configureMuxPins(MUX_I_RET);
  configureMuxPins(MUX_VP);
  configureMuxPins(MUX_VN);
}

void configureI2CDevices() {
  Wire.begin(PIN_SDA, PIN_SCL);
  if (!dac.begin(MCP4725_ADDRESS)) {
    Serial.println("[Fatal] MCP4725 not found at 0x60");
    while (true) delay(1000);
  }
  if (!ads.begin(ADS1115_ADDRESS, &Wire)) {
    Serial.println("[Fatal] ADS1115 not found at 0x48");
    while (true) delay(1000);
  }
  ads.setGain(GAIN_ONE);
  ads.setDataRate(RATE_ADS1115_860SPS);
  updateDac(DEFAULT_DAC_CODE);
}

void setup() {
  Serial.begin(115200);
  delay(1200);
  configurePins();
  configureI2CDevices();
  printHelp();
}

void loop() {
  if (Serial.available()) handleCommand(Serial.readStringUntil('\n'));
  if (continuousMode && millis() - lastFrameMs >= framePeriodMs) {
    emitFrame();
    lastFrameMs = millis();
  }
}
