#!/usr/bin/env python3
import csv, os, sys, threading
from collections import deque
from datetime import datetime
import serial
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.animation import FuncAnimation

PORT = "/dev/ttyACM0"        # oppure il percorso in /dev/serial/by-id/
BAUD = 9600                  # deve coincidere con Serial.begin()
OUTFILE = os.path.expanduser("~/turbidimetro/dati.csv")
TS_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_PUNTI = 50000            # punti in memoria per il grafico (~70 h a 5 s)
REFRESH_MS = 2000

buffer = deque(maxlen=MAX_PUNTI)   # (datetime, [valori], [volt])
lock = threading.Lock()
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

def reader():
    os.makedirs(os.path.dirname(OUTFILE), exist_ok=True)
    nuovo = not os.path.exists(OUTFILE) or os.path.getsize(OUTFILE) == 0
    with open(OUTFILE, "a", newline="", buffering=1) as f:
        w = csv.writer(f)
        ser = open_port()
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
                    continue
                campi, valori, volt = parsed
                if nuovo:
                    w.writerow(header(len(valori)))
                    nuovo = False
                now = datetime.now()
                ts = now.strftime(TS_FORMAT)
                w.writerow([ts] + campi)
                f.flush()
                with lock:
                    buffer.append((now, valori, volt))
                print(ts, *campi, sep="  ")
            elif line.startswith("#"):
                print(line)
        # chiusura pulita: forza la scrittura su disco
        f.flush()
        os.fsync(f.fileno())
        if ser:
            ser.close()

fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(10, 7))

def on_key(event):
    """Esc (con la finestra del grafico in focus) -> arresto acquisizione e chiusura."""
    if event.key == "escape":
        print("\nEsc: arresto acquisizione.")
        stop.set()
        plt.close(fig)

fig.canvas.mpl_connect("key_press_event", on_key)

def update(_):
    with lock:
        dati = list(buffer)
    if not dati:
        return
    t = [d[0] for d in dati]
    n = len(dati[0][1])
    ax1.cla(); ax2.cla()
    for i in range(n):
        ax1.plot(t, [d[1][i] for d in dati], label=f"Sensore {i+1}")
        ax2.plot(t, [d[2][i] for d in dati], label=f"Sensore {i+1}")
    ax1.set_ylabel("Valore (NTU se non calibrato)")
    ax2.set_ylabel("Tensione (V)")
    ax2.set_xlabel("Ora (Esc per fermare e chiudere)")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
    for ax in (ax1, ax2):
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left")
    fig.autofmt_xdate()

th = threading.Thread(target=reader, daemon=True)
th.start()
ani = FuncAnimation(fig, update, interval=REFRESH_MS, cache_frame_data=False)
try:
    plt.show()
except KeyboardInterrupt:
    pass
finally:
    stop.set()
    th.join(timeout=3)   # attende la chiusura pulita del file (max ~2 s di timeout seriale)
    print("Interrotto. Dati salvati in", OUTFILE)