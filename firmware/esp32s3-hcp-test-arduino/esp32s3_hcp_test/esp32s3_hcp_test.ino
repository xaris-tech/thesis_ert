#include <Wire.h>
#include <Adafruit_MCP4725.h>

constexpr uint8_t PIN_SDA = 8;
constexpr uint8_t PIN_SCL = 9;
constexpr uint8_t MCP4725_ADDRESS = 0x60;

// Test range: R1=R3=5k, R2=R4=100R, Rs=10R.
// With a 3.3 V DAC supply, code 620 commands approximately 1 mA.
constexpr float RS_OHMS = 10.0f;
constexpr uint16_t MAX_SAFE_DAC_CODE = 620;

Adafruit_MCP4725 dac;
uint16_t dacCode = 0;

void setDac(uint16_t requestedCode) {
  dacCode = min<uint16_t>(requestedCode, MAX_SAFE_DAC_CODE);
  dac.setVoltage(dacCode, false);

  const float estimatedVolts = 3.3f * dacCode / 4095.0f;
  const float estimatedMicroamps = estimatedVolts * 0.02f / RS_OHMS * 1000000.0f;

  Serial.print("[DAC] code=");
  Serial.print(dacCode);
  Serial.print(" estimated_vout=");
  Serial.print(estimatedVolts, 4);
  Serial.print("V estimated_current=");
  Serial.print(estimatedMicroamps, 1);
  Serial.println("uA");

  if (requestedCode > MAX_SAFE_DAC_CODE) {
    Serial.println("[LIMIT] Request clipped to Rs=10 ohm maximum code 620");
  }
}

void printHelp() {
  Serial.println();
  Serial.println("ESP32-S3 HCP Test - Rs=10 ohm range");
  Serial.println("p<number>  Set DAC code from 0 to 620 (example: p300)");
  Serial.println("o          Output off: set DAC code to 0");
  Serial.println("h          Show this help");
  Serial.println("Use newline line ending and 115200 baud.");
}

void handleCommand(String command) {
  command.trim();
  if (command.isEmpty()) return;

  if (command == "o" || command == "O") {
    setDac(0);
    return;
  }
  if (command == "h" || command == "H") {
    printHelp();
    return;
  }
  if (command[0] == 'p' || command[0] == 'P') {
    const long requestedCode = command.substring(1).toInt();
    if (requestedCode < 0) {
      Serial.println("[ERROR] DAC code cannot be negative");
      return;
    }
    setDac(static_cast<uint16_t>(requestedCode));
    return;
  }

  Serial.println("[ERROR] Unknown command; send h for help");
}

void setup() {
  Serial.begin(115200);
  delay(500);

  Wire.begin(PIN_SDA, PIN_SCL);
  if (!dac.begin(MCP4725_ADDRESS)) {
    Serial.println("[FATAL] MCP4725 not found at address 0x60");
    while (true) delay(1000);
  }

  // Always start with zero command. EEPROM is intentionally not written.
  setDac(0);
  printHelp();
}

void loop() {
  if (Serial.available()) {
    handleCommand(Serial.readStringUntil('\n'));
  }
}
