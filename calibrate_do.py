// EZO-DO I2C <-> USB-serial bridge (Arduino = I2C master, Raspberry Pi = serial host)
// UNTESTED on hardware. Verify address / timings / response codes against the EZO-DO datasheet.
//
// Protocol on serial (115200 8N1, newline-terminated):
//   Pi -> Arduino : an EZO command, e.g.  R   Cal   Cal,0   Cal,?   T,25.0
//   Arduino -> Pi : "<code>,<payload>"   e.g.  1,9.09   (code = EZO I2C response code)
//
// EZO I2C response codes (Atlas I2C documentation, from memory - verify in datasheet):
//   1 = success, 2 = syntax error, 254 = still processing, 255 = no data

#include <Wire.h>
#include <ctype.h>

const uint8_t EZO_ADDR = 0x09;        // YOUR circuit's address (scan found channel 9); factory default would be 0x61
const uint8_t BUF_LEN  = 32;          // Arduino Wire buffer limit

char cmd[40];
uint8_t cmdLen = 0;

uint16_t processingDelayMs(const char *c) {
  if (c[0] == 'r') return 600;                          // read: 600 ms per datasheet
  if (c[0] == 'c' && c[1] == 'a' && c[2] == 'l') return 1300;  // calibration (from memory; polling covers errors)
  return 300;
}

void ezoTransact(const char *c) {
  Wire.beginTransmission(EZO_ADDR);
  Wire.print(c);
  uint8_t err = Wire.endTransmission();
  if (err != 0) {                         // 2 = NACK on address: nothing at EZO_ADDR
    Serial.print("255,i2c_error_");
    Serial.println(err);
    return;
  }
  delay(processingDelayMs(c));

  for (uint8_t tries = 0; tries < 10; tries++) {
    if (Wire.requestFrom(EZO_ADDR, BUF_LEN) == 0) {
      Serial.println("255,no_bytes");
      return;
    }
    uint8_t code = Wire.read();
    char buf[BUF_LEN];
    uint8_t n = 0;
    while (Wire.available()) {
      char ch = Wire.read();
      if (ch == 0) break;                 // payload is null-terminated
      if (n < BUF_LEN - 1) buf[n++] = ch;
    }
    while (Wire.available()) Wire.read(); // drain
    buf[n] = '\0';

    if (code == 254) { delay(100); continue; }  // not ready yet, poll again
    Serial.print(code);
    Serial.print(',');
    Serial.println(buf);
    return;
  }
  Serial.println("254,timeout");
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  Wire.setClock(100000);                  // standard-mode I2C
  Serial.println("READY");
}

void loop() {
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\r') continue;
    if (ch == '\n') {
      cmd[cmdLen] = '\0';
      if (cmdLen > 0) ezoTransact(cmd);
      cmdLen = 0;
    } else if (cmdLen < sizeof(cmd) - 1) {
      cmd[cmdLen++] = tolower(ch);        // EZO commands are case-insensitive
    }
  }
}
