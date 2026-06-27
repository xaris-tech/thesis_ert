#include <Wire.h>
#include <Adafruit_ADS1X15.h>
#include <Adafruit_MCP4725.h>

constexpr uint8_t PIN_SDA = 8;
constexpr uint8_t PIN_SCL = 9;

constexpr uint8_t PIN_MUX_S0 = 4;
constexpr uint8_t PIN_MUX_S1 = 5;
constexpr uint8_t PIN_MUX_S2 = 6;
constexpr uint8_t PIN_MUX_S3 = 7;
constexpr uint8_t PIN_MUX_EN = 15;

constexpr uint8_t MCP4725_ADDRESS = 0x60;
constexpr uint8_t ADS1115_ADDRESS = 0x48;

constexpr uint8_t ELECTRODE_COUNT = 8;
constexpr uint8_t SAMPLE_COUNT = 8;
constexpr uint16_t DEFAULT_DAC_CODE = 512;
constexpr uint16_t DEFAULT_SETTLE_MS = 8;
constexpr uint16_t DEFAULT_CONTINUOUS_PERIOD_MS = 150;

const char *ELECTRODE_LABELS[ELECTRODE_COUNT] = {
  "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8"
};

Adafruit_ADS1115 ads;
Adafruit_MCP4725 dac;

bool continuousMode = false;
uint16_t muxSettleMs = DEFAULT_SETTLE_MS;
uint16_t continuousPeriodMs = DEFAULT_CONTINUOUS_PERIOD_MS;
uint16_t dacCode = DEFAULT_DAC_CODE;
unsigned long lastContinuousScanMs = 0;

void setMuxChannel(uint8_t channel) {
  digitalWrite(PIN_MUX_S0, (channel & 0x01) ? HIGH : LOW);
  digitalWrite(PIN_MUX_S1, (channel & 0x02) ? HIGH : LOW);
  digitalWrite(PIN_MUX_S2, (channel & 0x04) ? HIGH : LOW);
  digitalWrite(PIN_MUX_S3, (channel & 0x08) ? HIGH : LOW);
}

float readChannelMillivolts(uint8_t channel) {
  setMuxChannel(channel);
  delay(muxSettleMs);

  long totalCounts = 0;
  for (uint8_t sampleIndex = 0; sampleIndex < SAMPLE_COUNT; ++sampleIndex) {
    totalCounts += ads.readADC_Differential_0_1();
    delay(1);
  }

  const float averageCounts = static_cast<float>(totalCounts) / SAMPLE_COUNT;
  return ads.computeVolts(static_cast<int16_t>(averageCounts)) * 1000.0f;
}

void printScanFrame() {
  Serial.println("SCAN:");
  for (uint8_t channel = 0; channel < ELECTRODE_COUNT; ++channel) {
    const float millivolts = readChannelMillivolts(channel);
    Serial.print(channel);
    Serial.print(",");
    Serial.print(ELECTRODE_LABELS[channel]);
    Serial.print(",");
    Serial.println(millivolts, 3);
  }
  Serial.println("END");
}

void printHelp() {
  Serial.println();
  Serial.println("ESP32-S3 Phase 2 ERT Scanner");
  Serial.println("Commands:");
  Serial.println("  s          - single scan");
  Serial.println("  g          - continuous scanning on");
  Serial.println("  x          - continuous scanning off");
  Serial.println("  p<number>  - set MCP4725 raw DAC code (0-4095)");
  Serial.println("  t<number>  - set mux settle time in ms");
  Serial.println("  r<number>  - set continuous scan period in ms");
  Serial.println("  h          - print help");
  Serial.println();
  Serial.print("DAC code: ");
  Serial.println(dacCode);
  Serial.print("Settle ms: ");
  Serial.println(muxSettleMs);
  Serial.print("Period ms: ");
  Serial.println(continuousPeriodMs);
  Serial.print("Continuous mode: ");
  Serial.println(continuousMode ? "on" : "off");
  Serial.println("Injection pair is fixed in hardware: E1 drive, E5 return/reference.");
  Serial.println();
}

void updateDac(uint16_t newCode) {
  dacCode = min<uint16_t>(newCode, 4095);
  dac.setVoltage(dacCode, false);
  Serial.print("[DAC] raw code set to ");
  Serial.println(dacCode);
}

void handleCommand(String line) {
  line.trim();
  if (line.length() == 0) {
    return;
  }

  const char command = static_cast<char>(tolower(line.charAt(0)));
  const uint16_t value = line.length() > 1 ? static_cast<uint16_t>(line.substring(1).toInt()) : 0;

  switch (command) {
    case 's':
      printScanFrame();
      break;
    case 'g':
      continuousMode = true;
      Serial.println("[Mode] continuous scanning enabled");
      break;
    case 'x':
      continuousMode = false;
      Serial.println("[Mode] continuous scanning disabled");
      break;
    case 'p':
      updateDac(value);
      break;
    case 't':
      muxSettleMs = max<uint16_t>(value, 1);
      Serial.print("[Timing] settle ms set to ");
      Serial.println(muxSettleMs);
      break;
    case 'r':
      continuousPeriodMs = max<uint16_t>(value, 20);
      Serial.print("[Timing] period ms set to ");
      Serial.println(continuousPeriodMs);
      break;
    case 'h':
      printHelp();
      break;
    default:
      Serial.println("[Error] unknown command, use 'h' for help");
      break;
  }
}

void configurePins() {
  pinMode(PIN_MUX_S0, OUTPUT);
  pinMode(PIN_MUX_S1, OUTPUT);
  pinMode(PIN_MUX_S2, OUTPUT);
  pinMode(PIN_MUX_S3, OUTPUT);
  pinMode(PIN_MUX_EN, OUTPUT);

  digitalWrite(PIN_MUX_EN, LOW);
  setMuxChannel(0);
}

void configureI2CDevices() {
  Wire.begin(PIN_SDA, PIN_SCL);

  if (!dac.begin(MCP4725_ADDRESS)) {
    Serial.println("[Fatal] MCP4725 not found at 0x60");
    while (true) {
      delay(1000);
    }
  }

  if (!ads.begin(ADS1115_ADDRESS, &Wire)) {
    Serial.println("[Fatal] ADS1115 not found at 0x48");
    while (true) {
      delay(1000);
    }
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
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    handleCommand(command);
  }

  if (continuousMode && millis() - lastContinuousScanMs >= continuousPeriodMs) {
    printScanFrame();
    lastContinuousScanMs = millis();
  }
}
