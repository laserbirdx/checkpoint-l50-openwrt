#!/usr/bin/env python3
"""Make a 256 MiB variant of the OpenWrt Check Point L-50 u-boot.kwb.

The official image programs a second DDR chip-select window (CS1, register
0xFFD0150C), i.e. 512 MiB. Units with a single 256 MiB bank need that window
disabled. This rewrites the register value to 0 and fixes the header checksum.

usage: uboot_256m.py u-boot.kwb u-boot-256m.kwb
"""
import struct
import sys

CS1_SIZE_REG = 0xFFD0150C
EXT_START, EXT_CSUM = 0x20, 0x1FF

src, dst = sys.argv[1], sys.argv[2]
img = bytearray(open(src, "rb").read())

if img[0] != 0x8B:
    sys.exit("not a NAND kwbimage (block id != 0x8b)")
if sum(img[EXT_START:EXT_CSUM]) & 0xFF != img[EXT_CSUM]:
    sys.exit("extension header checksum mismatch, refusing to patch")

for off in range(EXT_START, EXT_CSUM - 7, 4):
    if struct.unpack_from("<I", img, off)[0] == CS1_SIZE_REG:
        old = struct.unpack_from("<I", img, off + 4)[0]
        struct.pack_into("<I", img, off + 4, 0)
        break
else:
    sys.exit("CS1 window register not found in header")

img[EXT_CSUM] = sum(img[EXT_START:EXT_CSUM]) & 0xFF
open(dst, "wb").write(img)
print(f"CS1 window 0x{old:08x} -> 0x00000000, header checksum 0x{img[EXT_CSUM]:02x}")
