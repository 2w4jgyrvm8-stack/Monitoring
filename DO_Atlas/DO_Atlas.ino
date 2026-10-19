#include <Wire.h>

const int sensorAddress = 9; // Updated to match your scanner result

void setup() {
  Wire.begin();
  Serial.begin(9600);
  while (!Serial);
  Serial.println("DO Sensor Initialized");
}

void loop() {
  // 1. Send read command to the sensor
  Wire.beginTransmission(sensorAddress);
  Wire.write("R");
  Wire.endTransmission();

  // 2. Wait for the sensor to process (EZO-DO takes about 600-900ms)
  delay(1000); 

  // 3. Request the response string from the sensor
  Wire.requestFrom(sensorAddress, 7); // Request up to 7 bytes
  
  String sensorData = "";
  while (Wire.available()) {
    char c = Wire.read();
    sensorData += c;
  }

  // 4. Print the result to the Serial Monitor
  Serial.print("DO Reading: ");
  Serial.println(sensorData);

  delay(2000); // Wait 2 seconds before next reading
}