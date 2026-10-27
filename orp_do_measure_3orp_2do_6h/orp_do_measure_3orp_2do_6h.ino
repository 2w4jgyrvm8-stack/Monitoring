// EZO multi-probe I2C logger.
// Output on serial (9600 baud), one line per sample:
//     time_ms;<probe 1>;<probe 2>;...
// On a failed read the reply field is "ERR<code>" (see ezoFetch() for codes).
// Probe fields follow EZO_ADDR order; use do_logger.py's --probes option to match that order.
// UNTESTED on hardware. Opening the serial port from the Pi resets the Arduino (DTR) and starts
// a new session; the Arduino also stops by itself after the configured operating hours.

#include <Wire.h>

// --- Configuration ---------------------------------------------------------------------------
// Add or remove addresses to match the probes; the count and serial header update automatically.
// Enter addresses in decimal. Wire accepts the numeric address directly (102 is the same as 0x66).
// Use a different address for each circuit; scan the bus or change it with the circuit's 'I2C,n' command.
// The sample values below are decimal addresses: ORP1=102, ORP2=101, ORP3=111, DO1=10, DO2=9.
const uint8_t       EZO_ADDR[]  = {102, 101, 111, 10, 9};
const uint8_t       N_PROBES    = sizeof(EZO_ADDR) / sizeof(EZO_ADDR[0]);

const unsigned long OPERATING_HOURS = 6UL;    // change the total run time here
const unsigned long SAMPLE_MS       = 10000UL; // change the sample interval here (milliseconds)
const unsigned long DURATION_MS = OPERATING_HOURS * 60UL * 60UL * 1000UL;
const uint16_t      READ_WAIT   = 1000;     // ms after 'R' (datasheet: 600 ms; Tentacle uses 1000 ms)
const uint8_t       BUF_LEN     = 32;       // Arduino Wire buffer size
// ---------------------------------------------------------------------------------------------

unsigned long tStart;
unsigned long nextSampleMs = 0;   // scheduled time of next sample, relative to tStart (no drift)
bool finished = false;

// Sends one ASCII command to the circuit at addr. Returns true if the device acknowledged.
bool ezoSend(uint8_t addr, const char *cmd) {
  Wire.beginTransmission(addr);
  Wire.print(cmd);
  return Wire.endTransmission() == 0;
}

// Fetches the reply of a previously sent command.
// Returns the EZO response code (1 = success, 2 = error, 255 = no data),
// or -2 = no bytes received, -3 = still pending after 10 polls.
int ezoFetch(uint8_t addr, char *out, uint8_t outLen) {
  out[0] = '\0';
  for (uint8_t tries = 0; tries < 10; tries++) {
    if (Wire.requestFrom(addr, (uint8_t)BUF_LEN) == 0) return -2;
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
  Serial.println(F("# EZO multi-probe measurement"));
  Serial.print(F("time_ms"));
  for (uint8_t i = 0; i < N_PROBES; i++) {
    Serial.print(F(";probe"));
    Serial.print(i + 1);
  }
  Serial.println();
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
  if (elapsed < nextSampleMs) return;       // not yet time for the next sample
  nextSampleMs += SAMPLE_MS;                // fixed schedule: no cumulative drift

  // Start conversions on all probes, wait once, then read all (converted in parallel).
  bool sent[N_PROBES];
  for (uint8_t i = 0; i < N_PROBES; i++) sent[i] = ezoSend(EZO_ADDR[i], "R");

  delay(READ_WAIT);

  Serial.print(elapsed);                    // ms since start, at the beginning of the cycle
  for (uint8_t i = 0; i < N_PROBES; i++) {
    char reply[BUF_LEN];
    int code = sent[i] ? ezoFetch(EZO_ADDR[i], reply, sizeof(reply)) : -1;  // -1 = no device at addr
    Serial.print(';');
    if (code == 1) {
      Serial.print(reply);
    } else {
      Serial.print(F("ERR"));
      Serial.print(code);
    }
  }
  Serial.println();
}
