#include <Wire.h>

const int sensorAddress = 9; // Your confirmed I2C address

void setup() {
  Wire.begin();
  Serial.begin(9600);
  while (!Serial); // Wait for Serial Monitor to open
  
  // Configure EZO-DO to output BOTH mg/L and % Saturation
  delay(200);
  
  // Enable mg/L output
  Wire.beginTransmission(sensorAddress);
  Wire.write("O,mg,1");
  Wire.endTransmission();
  delay(300);

  // Enable % saturation output
  Wire.beginTransmission(sensorAddress);
  Wire.write("O,%s,1");
  Wire.endTransmission();
  delay(300);

  Serial.println("EZO-DO Sensor Initialized with Dual Output (% and mg/L)");
}

void loop() {
  // 1. Send read command to the sensor
  Wire.beginTransmission(sensorAddress);
  Wire.write("R");
  Wire.endTransmission();

  // 2. Wait for the sensor conversion time (~600ms to 900ms)
  delay(1000); 

  // 3. Request data response (Dual output string is slightly longer, request up to 20 bytes)
  Wire.requestFrom(sensorAddress, 20); 
  
  String sensorData = "";
  while (Wire.available()) {
    char c = Wire.read();
    if (c != 0) { // Ignore null characters
      sensorData += c;
    }
  }

  // 4. Print results
  if (sensorData.length() > 0) {
    Serial.print("Raw Sensor Output: ");
    Serial.println(sensorData);
    
    // Note: When both are active, the EZO circuit typically returns a comma-separated 
    // string (e.g., "mg/L, %sat"). You can parse them here or read them directly.
  } else {
    Serial.println("Error: No data received from sensor.");
  }

  delay(2000); // Wait 2 seconds before the next reading
}