// EZO-DO: dual-probe dissolved oxygen logger, 6 h session, I2C.
// Output on serial (9600 baud), one line per sample:
//     time_ms;<reply probe 1>;<reply probe 2>
// Each reply is "mg/L,%sat" if both outputs are enabled (check with 'O,?'), or a single value.
// On a failed read the reply field is "ERR<code>" (see ezoFetch() for codes).
// Lines starting with '#' are comments/status. The Raspberry Pi script (do_logger.py) adds the
// timestamp and writes the CSV.
// UNTESTED on hardware. Opening the serial port from the Pi resets the Arduino (DTR) and starts
// a new 6 h session; the Arduino also stops by itself after DURATION_MS.

#include <Wire.h>

// --- Configuration ---------------------------------------------------------------------------
// Both circuits must have DIFFERENT I2C addresses. Probe 1 = address from your previous scan (0x09).
// Probe 2 address is a PLACEHOLDER (0x0A): set it to your real address (scan, or change it with
// the 'I2C,n' command on the circuit).
const uint8_t       EZO_ADDR[]  = {0x09, 0x0A};
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
  Serial.println(F("# EZO-DO 2-probe 6 h measurement"));
  Serial.println(F("time_ms;probe1;probe2"));
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

  // Start the conversion on all probes, wait once, then read all (both are converted in parallel).
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
