#!/usr/bin/env python3
"""Raspberry Pi logger for the Arduino dual EZO-DO sketch (do_measure_2probes_6h.ino).

Reads lines "time_ms;<probe1>;<probe2>" from the Arduino serial port, adds a Pi timestamp
and appends each sample to a CSV (flushed per row, so data survive a crash / power loss).

Usage:   python3 do_logger.py [--port /dev/ttyACM0] [--hours 6] [--outdir .]
Requires: pip install pyserial

Note: opening the port resets the Arduino (DTR), which starts a fresh session on the board.
"""
import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import serial

HEADER = ["timestamp_iso", "epoch_s", "arduino_ms",
          "do1_mgL", "do1_sat_pct", "do2_mgL", "do2_sat_pct",
          "status1", "status2"]


def parse_reply(reply):
    """'9.12,98.5' -> ('9.12','98.5','OK'); '9.12' -> ('9.12','','OK'); 'ERR2' -> ('','','ERR2').
    Assumes order mg/L, %sat (EZO-DO order). With a single enabled output, check the column meaning."""
    reply = reply.strip()
    if reply.startswith("ERR") or not reply:
        return "", "", reply or "ERR_EMPTY"
    vals = [v.strip() for v in reply.split(",")]
    vals += [""] * (2 - len(vals))
    return vals[0], vals[1], "OK"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--hours", type=float, default=6.0)
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args()

    t_limit = args.hours * 3600 + 120          # safety margin beyond the Arduino's own 6 h stop
    t0 = time.monotonic()
    out = Path(args.outdir) / f"do_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    with serial.Serial(args.port, args.baud, timeout=5) as ser, \
            open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        f.flush()
        print(f"Logging to {out} (Ctrl+C to stop early)")
        n = 0
        try:
            while time.monotonic() - t0 < t_limit:
                raw = ser.readline().decode("ascii", errors="replace").strip()
                if not raw:
                    continue
                if raw.startswith("#"):
                    print(raw)
                    if "done" in raw:
                        break
                    continue
                parts = raw.split(";")
                if len(parts) != 3 or not parts[0].isdigit():
                    continue                    # header line or corrupted line
                now = datetime.now().astimezone()
                d1, s1, st1 = parse_reply(parts[1])
                d2, s2, st2 = parse_reply(parts[2])
                w.writerow([now.isoformat(timespec="milliseconds"), f"{now.timestamp():.3f}",
                            parts[0], d1, s1, d2, s2, st1, st2])
                f.flush()
                n += 1
                if n % 30 == 0:
                    print(f"{now:%H:%M:%S}  samples: {n}  last: {parts[1]} | {parts[2]}")
        except KeyboardInterrupt:
            print("Stopped by user.")
        print(f"Done: {n} samples written to {out}")


if __name__ == "__main__":
    sys.exit(main())
