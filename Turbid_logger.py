#!/usr/bin/env python3
import csv, os, sys, time, select, termios, tty, threading
from datetime import datetime
import serial

PORT = "/dev/ttyACM0"        # oppure il percorso in /dev/serial/by-id/
BAUD = 9600                  # deve coincidere con Serial.begin()
OUTFILE = os.path.expanduser("~/turbidimetro/dati.csv")
TS_FORMAT = "%Y-%m-%d %H:%M:%S"

stop = threading.Event()

def open_port():
    while not stop.is_set():
        try:
            return serial.Serial(PORT, BAUD, timeout=2)
        except serial.SerialException:
            print("Porta non disponibile, riprovo tra 5 s...", file=sys.stderr)
            stop.wait(5)
    return None

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

def esc_listener():
    """Thread: imposta 'stop' alla pressione di Esc (ignora sequenze come le frecce)."""
    fd = sys.stdin.fileno()
    while not stop.is_set():
        r, _, _ = select.select([fd], [], [], 0.2)
        if not r:
            continue
        ch = os.read(fd, 1)
        if ch == b"\x1b":
            # Esc "nudo" = nessun byte successivo entro 50 ms;
            # altrimenti è una sequenza (frecce, F-keys...) -> scarta
            r, _, _ = select.select([fd], [], [], 0.05)
            if not r:
                stop.set()
                return
            os.read(fd, 16)

os.makedirs(os.path.dirname(OUTFILE), exist_ok=True)
nuovo = not os.path.exists(OUTFILE) or os.path.getsize(OUTFILE) == 0

# cbreak: tasti letti senza Invio e senza echo, Ctrl+C resta attivo
tty_ok = sys.stdin.isatty()
if tty_ok:
    old_attr = termios.tcgetattr(sys.stdin.fileno())
    tty.setcbreak(sys.stdin.fileno())
    threading.Thread(target=esc_listener, daemon=True).start()

try:
    with open(OUTFILE, "a", newline="", buffering=1) as f:
        w = csv.writer(f)
        ser = open_port()
        msg = "Esc o Ctrl+C" if tty_ok else "Ctrl+C"
        print(f"Acquisizione su {PORT} -> {OUTFILE} ({msg} per fermare)")
        try:
            while ser and not stop.is_set():
                try:
                    line = ser.readline().decode("ascii", errors="ignore").strip()
                except serial.SerialException:
                    ser.close()
                    ser = open_port()
                    continue
                if line.startswith("DATA,"):
                    parsed = parse_data_line(line)
                    if parsed is None:
                        continue                  # riga corrotta: scarta
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
            pass
        finally:
            stop.set()
            f.flush()
            os.fsync(f.fileno())
            if ser:
                ser.close()
            print("\nInterrotto. Dati salvati in", OUTFILE)
finally:
    if tty_ok:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_attr)