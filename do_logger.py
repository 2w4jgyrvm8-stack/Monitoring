#!/usr/bin/env python3
"""Raspberry Pi logger for the Arduino EZO probe measurement sketch.

Reads lines "time_ms;<probe1>;..." from the Arduino serial port, adds a Pi timestamp
and appends each sample to a CSV (flushed per row, so data survive a crash / power loss).

Usage:   python3 do_logger.py [--probes orp,orp,orp,do,do] [--plot]
Requires: pip install pyserial
Plotting: pip install matplotlib

Probe types and order must match the Arduino's output fields. ORP values are treated as mV.
DO replies are interpreted as "mg/L,%sat" (or a single mg/L value).
Opening the port resets the Arduino (DTR), which starts a fresh session on the board.
"""
import argparse
import csv
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import serial

DEFAULT_PROBES = ("orp", "orp", "orp", "do", "do")
METADATA_HEADER = ["timestamp_iso", "epoch_s", "arduino_ms"]


def parse_probe_types(value):
    """Parse an ordered, comma-separated list of ORP and DO probe types."""
    probes = tuple(probe.strip().lower() for probe in value.split(","))
    if not probes or any(probe not in ("orp", "do") for probe in probes):
        raise argparse.ArgumentTypeError(
            "probes must be a comma-separated list containing only 'orp' and 'do'"
        )
    return probes


def probe_columns(probes):
    """Build CSV measurement and status columns in the configured probe order."""
    counts = {"orp": 0, "do": 0}
    columns = []
    measurements = []
    for probe in probes:
        counts[probe] += 1
        name = f"{probe}{counts[probe]}"
        fields = [f"{name}_mV"] if probe == "orp" else [f"{name}_mgL", f"{name}_sat_pct"]
        columns.extend(fields)
        measurements.extend(fields)
        columns.append(f"{name}_status")
    return columns, measurements


def parse_reply(reply, probe_type):
    """Return measurement strings and status for a single ORP or DO reply."""
    reply = reply.strip()
    fields = 1 if probe_type == "orp" else 2
    empty = [""] * fields
    if reply.startswith("ERR") or not reply:
        return empty, reply or "ERR_EMPTY"

    values = [value.strip() for value in reply.split(",")]
    if len(values) > fields:
        return empty, "ERR_INVALID_REPLY"
    values += [""] * (fields - len(values))
    for value in values:
        if value:
            try:
                number = float(value)
            except ValueError:
                return empty, "ERR_INVALID_REPLY"
            if not math.isfinite(number):
                return empty, "ERR_INVALID_REPLY"
    return values, "OK"


def create_plotter(measurements):
    """Create one live plot window for each measured quantity."""
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit("Plotting requires matplotlib; install it with: pip install matplotlib") from exc

    plots = []
    for measurement in measurements:
        figure, axis = plt.subplots()
        axis.set_title(measurement)
        axis.set_xlabel("Elapsed time (minutes)")
        axis.set_ylabel(measurement)
        axis.grid(True)
        (line,) = axis.plot([], [])
        plots.append((figure, axis, line, [], []))
    plt.ion()
    plt.show(block=False)
    return plt, plots


def update_plots(plt, plots, elapsed_ms, values):
    """Add one sample to each plot and refresh its separate window."""
    elapsed_minutes = int(elapsed_ms) / 60000
    for (_, axis, line, times, readings), value in zip(plots, values):
        times.append(elapsed_minutes)
        try:
            readings.append(float(value) if value else float("nan"))
        except ValueError:
            readings.append(float("nan"))
        line.set_data(times, readings)
        axis.relim()
        axis.autoscale_view()
    plt.pause(0.001)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--hours", type=float, default=6.0)
    ap.add_argument("--outdir", default=".")
    ap.add_argument(
        "--probes",
        type=parse_probe_types,
        default=DEFAULT_PROBES,
        metavar="TYPE[,TYPE...]",
        help=("ordered probe types matching the Arduino output fields; "
              "choices are orp and do (default: orp,orp,orp,do,do)"),
    )
    ap.add_argument("--plot", action="store_true", help="show live plots in separate windows")
    args = ap.parse_args()

    columns, measurements = probe_columns(args.probes)
    plotter = create_plotter(measurements) if args.plot else None
    t_limit = args.hours * 3600 + 120          # safety margin beyond the Arduino's own 6 h stop
    t0 = time.monotonic()
    out = Path(args.outdir) / f"do_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    with serial.Serial(args.port, args.baud, timeout=5) as ser, \
            open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(METADATA_HEADER + columns)
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
                if not parts[0].isdigit():
                    continue                    # header line or corrupted timestamp
                if len(parts) != len(args.probes) + 1:
                    print(f"Skipping row: expected {len(args.probes)} probe values, got {len(parts) - 1}")
                    continue

                now = datetime.now().astimezone()
                row_values = []
                probe_fields = []
                for reply, probe_type in zip(parts[1:], args.probes):
                    values, status = parse_reply(reply, probe_type)
                    row_values.extend(values)
                    probe_fields.extend(values)
                    probe_fields.append(status)
                w.writerow([
                    now.isoformat(timespec="milliseconds"),
                    f"{now.timestamp():.3f}",
                    parts[0],
                    *probe_fields,
                ])
                f.flush()
                n += 1
                if plotter:
                    update_plots(plotter[0], plotter[1], parts[0], row_values)
                if n % 30 == 0:
                    print(f"{now:%H:%M:%S}  samples: {n}  last: {' | '.join(parts[1:])}")
        except KeyboardInterrupt:
            print("Stopped by user.")
        print(f"Done: {n} samples written to {out}")
        if plotter:
            plotter[0].ioff()
            plotter[0].show()


if __name__ == "__main__":
    sys.exit(main())
