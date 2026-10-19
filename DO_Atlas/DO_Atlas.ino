#include <Wire.h>

// Default I2C address for the Atlas Scientific EZO-DO circuit is 97
#define DO_ADDRESS 97 

void setup() {
  // Start serial communication with your computer screen (Serial Monitor)
  Serial.begin(9600); 
  
  // Join the I2C bus as the master controller
  Wire.begin(); 
  
  delay(2000); // Give the sensor a couple of seconds to boot up
  Serial.println("DO Sensor Initialized. Starting readings...");
}

void loop() {
  // Step 1: Send the "R" (Read) command to the DO circuit
  Wire.beginTransmission(DO_ADDRESS);
  Wire.write('R');          // 'R' tells the sensor to take a measurement
  Wire.endTransmission();

  // Step 2: Dissolved Oxygen calculations take about 600 milliseconds
  delay(600); 

  // Step 3: Request the response data from the sensor (we ask for up to 20 bytes)
  Wire.requestFrom(DO_ADDRESS, 20);
  
  // The first byte received is the response code (1 means success/command executed)
  char responseCode = Wire.read(); 
  
  String sensorData = "";
  while (Wire.available()) {
    char c = Wire.read();
    if (c == 0) { // Null character marks the end of the string
      break;
    }
    sensorData += c;
  }

  // Step 4: Print the results to the Serial Monitor
  if (responseCode == 1) {
    // The default output format is: "DO, Percent Saturation" (e.g., 8.25,100.2)
    Serial.print("DO Reading: ");
    Serial.println(sensorData); 
  } else {
    Serial.println("Error: Sensor is still processing or not responding.");
  }

  // Wait 2 seconds before taking the next reading
  delay(2000);
}
