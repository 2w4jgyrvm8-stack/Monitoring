// EZO-DO: read dissolved oxygen in a loop for 2 minutes, then stop.
// Output on the serial monitor (9600 baud), CSV-style:  time_s,<reply from the circuit>
// The reply is "mg/L,%sat" if both outputs are enabled (check with the 'O,?' command in the
// Tentacle sketch); a single value if only one is enabled.
// UNTESTED on hardware. Press the Arduino reset button to run another 2-minute session.

#include <Wire.h>

const uint8_t       EZO_ADDR    = 0x09;        // your circuit (scan found channel 9); factory default 0x61
const unsigned long DURATION_MS = 120000UL;    // 2 minutes
const uint16_t      READ_WAIT   = 1000;        // ms to wait after 'R' (datasheet: 600 ms; Tentacle uses 1000 ms)
const uint8_t       BUF_LEN     = 32;          // Arduino Wire buffer size

unsigned long tStart;
bool finished = false;

// Sends one ASCII command and fetches the reply.
// Returns the EZO response code (1 = success, 2 = error, 255 = no data),
// or -1 = no device at EZO_ADDR, -2 = no bytes received, -3 = still pending after 10 polls.
int ezoCommand(const char *cmd, uint16_t waitMs, char *out, uint8_t outLen) {
  out[0] = '\0';

  Wire.beginTransmission(EZO_ADDR);
  Wire.print(cmd);
  if (Wire.endTransmission() != 0) return -1;

  delay(waitMs);

  for (uint8_t tries = 0; tries < 10; tries++) {
    if (Wire.requestFrom(EZO_ADDR, (uint8_t)BUF_LEN) == 0) return -2;
    int code = Wire.read();                 // first byte = response code

    uint8_t n = 0;
    while (Wire.available()) {
      char ch = Wire.read();
      if (ch == 0) break;                   // payload is null-terminated
      if (n < outLen - 1) out[n++] = ch;
    }
    while (Wire.available()) Wire.read();   // drain padding
    out[n] = '\0';

    if (code == 254) { delay(100); continue; }  // still processing, poll again
    return code;
  }
  return -3;
}

void setup() {
  Serial.begin(9600);
  Wire.begin();
  Serial.println(F("# EZO-DO 2-minute measurement"));
  Serial.println(F("time_s,reading"));
  tStart = millis();
}

void loop() {
  if (finished) return;

  unsigned long elapsed = millis() - tStart;
  if (elapsed >= DURATION_MS) {
    Serial.println(F("# done"));
    finished = true;
    return;
  }

  char reply[BUF_LEN];
  int code = ezoCommand("R", READ_WAIT, reply, sizeof(reply));

  Serial.print(elapsed / 1000.0, 1);
  Serial.print(',');
  if (code == 1) {
    Serial.println(reply);
  } else {
    Serial.print(F("error_code_"));
    Serial.println(code);
  }
}
