#!/usr/bin/env python3
"""Send a command through serd.py and print the output that follows.

Waits until the output goes quiet, or until a regex matches.
  sc.py [-t timeout] [-w regex] [-i idle] [-c ctrlc_seconds] [-n] [command]

-c N  keep sending Ctrl+C for N seconds first (stops U-Boot autoboot)
-n    do not append a newline to the command

Expects console.log and console.fifo (from serd.py) next to this script.
"""
import argparse
import os
import re
import sys
import time

D = os.path.dirname(os.path.abspath(__file__))
LOG, FIFO = os.path.join(D, 'console.log'), os.path.join(D, 'console.fifo')

ap = argparse.ArgumentParser()
ap.add_argument('-t', type=float, default=10)
ap.add_argument('-w', default=None)
ap.add_argument('-i', type=float, default=1.5)
ap.add_argument('-c', type=float, default=0)
ap.add_argument('-n', action='store_true')
ap.add_argument('cmd', nargs='?')
a = ap.parse_args()

start = os.path.getsize(LOG)
fd = os.open(FIFO, os.O_WRONLY)
if a.c:
    end = time.time() + a.c
    while time.time() < end:
        os.write(fd, b'\x03')
        time.sleep(0.05)
        if a.w and re.search(a.w, open(LOG, 'rb').read()[start:].decode('latin1')):
            break
if a.cmd is not None:
    os.write(fd, a.cmd.encode() + (b'' if a.n else b'\n'))

t0 = last = time.time()
size = os.path.getsize(LOG)
while time.time() - t0 < a.t:
    time.sleep(0.1)
    ns = os.path.getsize(LOG)
    if ns != size:
        size, last = ns, time.time()
    out = open(LOG, 'rb').read()[start:].decode('latin1')
    if a.w and re.search(a.w, out):
        break
    if not a.w and time.time() - last > a.i:
        break
sys.stdout.write(open(LOG, 'rb').read()[start:].decode('latin1').replace('\r', ''))
