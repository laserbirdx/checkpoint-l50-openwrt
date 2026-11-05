#!/usr/bin/env python3
"""Serial console daemon: keeps the port open, appends everything it receives
to a log file and sends whatever is written to a FIFO. Reconnects if the
USB-serial adapter disappears (e.g. while power-cycling the board).

usage: serd.py <port> <logfile> <fifo>
needs: pyserial
"""
import os
import select
import sys
import time

import serial

port, log, fifo = sys.argv[1], sys.argv[2], sys.argv[3]
if not os.path.exists(fifo):
    os.mkfifo(fifo)
fd = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
with open(log, 'ab', buffering=0) as lf:
    while True:
        try:
            s = serial.Serial(port, 115200, timeout=0)
        except (serial.SerialException, OSError):
            time.sleep(0.5)
            continue
        lf.write(b'\n[serd: port open]\n')
        try:
            while True:
                r, _, _ = select.select([s.fileno(), fd], [], [], 0.2)
                if s.fileno() in r:
                    d = s.read(4096)
                    if d:
                        lf.write(d)
                if fd in r:
                    d = os.read(fd, 4096)
                    s.write(d)
        except (serial.SerialException, OSError) as e:
            lf.write(f'\n[serd: port lost: {e}]\n'.encode())
            try:
                s.close()
            except Exception:
                pass
            time.sleep(0.5)
