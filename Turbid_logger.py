#!/usr/bin/env python3
import csv, os, sys, time
from datetime import datetime
import serial

PORT = "/dev/ttyACM0"        # oppure il percorso in /dev/serial/by-id/
BAUD = 9600                  # deve coincidere con Serial.begin()
OUTFILE = os.path.expanduser("~/turbidimetro/dati.csv")
TS_FORMAT = "%Y-%m-%d %H:%M:%S"

def open_port():
    while True:
        try:
            return serial.Serial(PORT, BAUD, timeout=2)
        except serial.SerialException:
            print("Porta non disponibile, riprovo tra 5 s...", file=sys.stderr)
            time.sleep(5)

def parse_data_line(line):
    """'DATA,millis,v1..vN,volt1..voltN' -> (campi_str, valori, volt) oppure None."""
    campi = line.split(",")[1:]
    if len(campi) < 3:
        return None
    try:
        num = [float(x) for x in campi[1:]]
    except ValueError:
        return None
    if len(num) % 2:
        return None
    n = len(num) // 2
    return campi, num[:n], num[n:]

def header(n):
    return (["timestamp", "millis"]
            + [f"valore{i+1}" for i in range(n)]
            + [f"volt{i+1}" for i in range(n)])

os.makedirs(os.path.dirname(OUTFILE), exist_ok=True)
nuovo = not os.path.exists(OUTFILE) or os.path.getsize(OUTFILE) == 0

with open(OUTFILE, "a", newline="", buffering=1) as f:
    w = csv.writer(f)
    ser = open_port()
    print(f"Acquisizione su {PORT} -> {OUTFILE} (Ctrl+C per fermare)")
    try:
        while True:
            try:
                line = ser.readline().decode("ascii", errors="ignore").strip()
            except serial.SerialException:
                ser.close()
                ser = open_port()
                continue
            if line.startswith("DATA,"):
                parsed = parse_data_line(line)
                if parsed is None:
                    continue                      # riga corrotta: scarta
                campi, valori, volt = parsed
                if nuovo:
                    w.writerow(header(len(valori)))
                    nuovo = False
                ts = datetime.now().strftime(TS_FORMAT)
                w.writerow([ts] + campi)
                f.flush()
                print(ts, *campi, sep="  ")
            elif line.startswith("#"):
                print(line)
    except KeyboardInterrupt:
        print("\nInterrotto.")