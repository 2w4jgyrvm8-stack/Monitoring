// EZO: 3 ORP + 2 dissolved oxygen probes, 6 h session, I2C.
// Output on serial (9600 baud), one line per sample:
//     time_ms;<ORP 1>;<ORP 2>;<ORP 3>;<DO 1>;<DO 2>
// On a failed read the reply field is "ERR<code>" (see ezoFetch() for codes).
// Lines starting with '#' are comments/status. do_logger.py defaults to this ORP/DO order;
// use its --probes option to match a different sensor order and number of Arduino output fields.
// UNTESTED on hardware. Opening the serial port from the Pi resets the Arduino (DTR) and starts
// a new 6 h session; the Arduino also stops by itself after DURATION_MS.

#include <Wire.h>

// --- Configuration ---------------------------------------------------------------------------
// All five circuits must have DIFFERENT I2C addresses. 0x09 is from the previous sketch;
// 0x0A-0x0D are examples/placeholders. Set every entry to the address of its circuit
// (scan the bus or change an address with the circuit's 'I2C,n' command).
// Order: 3 ORP circuits, then 2 DO circuits.
const uint8_t       EZO_ADDR[]  = {0x09, 0x0A, 0x0B, 0x0C, 0x0D};
const uint8_t       N_PROBES    = sizeof(EZO_ADDR) / sizeof(EZO_ADDR[0]);

const unsigned long DURATION_MS = 6UL * 60UL * 60UL * 1000UL;  // 6 h = 21 600 000 ms
const unsigned long SAMPLE_MS   = 2000UL;   // sampling period (must be > READ_WAIT + I2C time)
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
  Serial.println(F("# EZO 3-ORP + 2-DO 6 h measurement"));
  Serial.println(F("time_ms;orp1;orp2;orp3;do1;do2"));
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
