![OpenWrt on Check Point L-50](assets/banner.webp)

# OpenWrt on Check Point L-50

Installation guide for OpenWrt 25.12.5 on the Check Point L-50 (600 Appliance, Marvell
Kirkwood 88F6281). The board is supported by official OpenWrt, but there is almost no
documentation on how to actually get OpenWrt onto it. This is the procedure that was used
on a real unit, start to finish.

The stock U-Boot only offers Check Point's boot menu, not a U-Boot prompt. The install
therefore goes through the Kirkwood BootROM's UART boot (`kwboot`), replaces U-Boot with
OpenWrt's, and then installs the official images.

Images are on the [Releases](../../releases/latest) page: the official OpenWrt 25.12.5
images and a 256 MiB build of the official U-Boot (see below).

> **Unofficial guide.** This replaces the bootloader and overwrites the stock firmware.
> Take a full flash backup first. You do this at your own risk.

## Hardware

| Component | Details |
|---|---|
| SoC | Marvell Kirkwood 88F6281 A1, ARMv5 @ 1.2 GHz |
| RAM | 256 MiB DDR2 (single chip-select) |
| Flash | 512 MiB NAND |
| Ethernet | 1x WAN (`eth0`), 8x LAN + 1x DMZ on Marvell switch chips behind `eth1` (`mv88e6085` driver) |
| USB | USB 2.0 host |
| Console | RJ45 console port on the case, 115200 8N1 |
| Stock bootloader | U-Boot 1.1.4, "Check Point version 3.4.27" |
| Stock firmware | SecurePlatform Embedded, Linux 2.6.22, A/B layout |

### 256 MiB units need a patched U-Boot

The official OpenWrt `u-boot.kwb` for this board enables a second DDR chip-select window
(CS1, register `0xFFD0150C`), i.e. it assumes 512 MiB. On the 256 MiB unit it hung silently
right after kwboot. Disabling the CS1 window fixes it.

[`tools/uboot_256m.py`](tools/uboot_256m.py) makes that change to the official file and
fixes the header checksum. The result is the `u-boot-256m.kwb` in the release, and you can
regenerate it yourself:

```sh
python3 tools/uboot_256m.py u-boot.kwb u-boot-256m.kwb
sha256sum u-boot-256m.kwb   # b34165b99322b7053f815735b6375646aa70e2ccdbcb9e4fbd82779d80e26308
```

The stock boot log shows the RAM size: `DRAM Total size 256MB`.

## Console

The console is the **RJ45 console port** on the case. Use a standard Cisco-style
RJ45-to-USB console cable at **115200 8N1**. Everything uses that speed: the stock U-Boot,
stock Linux, OpenWrt's U-Boot and OpenWrt.

- Stock U-Boot: press **Ctrl+C** at `Hit 'Ctrl + C' for boot menu` to get the
  *SecurePlatform Embedded Boot Menu*.
- OpenWrt's U-Boot: press any key at `Hit any key to stop autoboot` (1 s). The prompt is `=>`.

## What you need

- A Cisco-style RJ45-to-USB console cable and `kwboot` (part of the U-Boot tools).
- A FAT-formatted USB stick with:
  - `u-boot-256m.kwb`
  - `openwrt-25.12.5-kirkwood-generic-checkpoint_l-50-initramfs-uImage`
  - `openwrt-25.12.5-kirkwood-generic-checkpoint_l-50-squashfs-sysupgrade.bin`
  - free space for the flash backup (about 520 MB)
- An Ethernet cable on the WAN port with internet access (for step 7).

## Installation

### 1. Get a root shell on the stock firmware

1. Power on and press **Ctrl+C** when the stock U-Boot shows
   `Hit 'Ctrl + C' for boot menu`.
2. In the *SecurePlatform Embedded Boot Menu*, choose **4. Restore to Factory Defaults
   (local)** and confirm with `y`.
3. Let it boot. On the console log in as **`admin` / `admin`**. You land directly in the
   Expert (root) shell, `[Expert@...]#`.

The factory reset wipes the stock configuration and logs, and rewrites the primary image
from the `default_sw` partition.

### 2. Back up the flash

Plug the USB stick into the router. In the Expert shell it is mounted under `/mnt/usb2`.

```sh
mkdir -p /mnt/usb2/backup && cd /mnt/usb2/backup
for i in 0 1 2 3 4 5 6 7 8 9 10; do
  n=$(grep "^mtd$i:" /proc/mtd | cut -d\" -f2)
  nanddump -q -o -f mtd$i-$n.bin /dev/mtd$i
  echo "mtd$i $n rc=$?"
done
sync; md5sum mtd*.bin > md5sums.txt; cat /proc/mtd > proc_mtd.txt
fw_printenv > fw_printenv.txt
```

### 3. Write down the MAC addresses

The OpenWrt U-Boot keeps its environment in a different place, so the stock MAC addresses
are gone once it is installed. Take these from `fw_printenv.txt`:

`ethaddr`, `eth0addr`, `eth1addr`, `lan1_mac_addr` ... `lan8_mac_addr`, `dmz_mac_addr`

### 4. Boot OpenWrt's U-Boot from RAM with kwboot

Nothing is written to flash in this step. With the router **powered off**, start `kwboot`
(options before the serial device), then power the router on:

```sh
kwboot -b u-boot-256m.kwb -t /dev/<console-cable>
```

The BootROM picks up the image over the console port, runs it, and `kwboot` switches to a
terminal. You see `U-Boot 2020.04 ... Model: Check Point L-50`. It finds no UBI volume and
stops at the `=>` prompt, which is expected.

On macOS with the USB console cable, `kwboot` (U-Boot v2026.07) needed small changes to get
through: ignore the NAK noise the cable produces at power-on, send the boot pattern in
bursts of four, and drain the input for 300 ms after a NAK.

### 5. Test-boot OpenWrt from the USB stick

```
usb start
fatload usb 0 0x800000 openwrt-25.12.5-kirkwood-generic-checkpoint_l-50-initramfs-uImage
bootm 0x800000
```

OpenWrt runs from RAM. Flash is still untouched; a power cycle brings the stock firmware back.

### 6. Replace U-Boot on NAND

kwboot again (step 4) so you are at the `=>` prompt of the RAM-loaded U-Boot, then write
the same image to NAND and verify it:

```
usb start
mw.b 0x800000 0xff 0xc0000
fatload usb 0 0x800000 u-boot-256m.kwb
nand erase 0x0 0x100000
nand write 0x800000 0x0 0xc0000
mw.b 0x2000000 0x00 0xc0000
nand read 0x2000000 0x0 0xc0000
cmp.b 0x800000 0x2000000 0xc0000
```

`cmp.b` must report `Total of 786432 byte(s) were the same`. Do not power off between
`nand erase` and a successful `cmp.b`.

Reset the environment and put the MAC addresses from step 3 back:

```
env default -a
setenv ethaddr <ethaddr>
setenv eth0addr <eth0addr>
setenv eth1addr <eth1addr>
setenv lan1_mac_addr <lan1_mac_addr>
...
setenv lan8_mac_addr <lan8_mac_addr>
setenv dmz_mac_addr <dmz_mac_addr>
saveenv
```

The default environment boots with
`bootcmd=ubi part ubi; ubi read 0x800000 kernel; bootm 0x800000`.

### 7. Install OpenWrt

Boot the initramfs again:

```
fatload usb 0 0x800000 openwrt-25.12.5-kirkwood-generic-checkpoint_l-50-initramfs-uImage
bootm 0x800000
```

The initramfs has no USB storage support. With the WAN port connected, add it and copy the
sysupgrade image from the stick:

```sh
apk update
apk add kmod-usb-storage kmod-fs-vfat kmod-nls-cp437 kmod-nls-iso8859-1 block-mount
mkdir -p /mnt/usb && mount /dev/sda1 /mnt/usb
cp /mnt/usb/openwrt-25.12.5-kirkwood-generic-checkpoint_l-50-squashfs-sysupgrade.bin /tmp/sysupgrade.bin
umount /mnt/usb
sysupgrade -T /tmp/sysupgrade.bin
sysupgrade -n /tmp/sysupgrade.bin
```

`sysupgrade` formats the `ubi` partition and writes the kernel and rootfs volumes. The router
reboots into OpenWrt from NAND (`mount_root: switching to ubifs overlay`).

## After installation

| Setting | Value |
|---|---|
| LAN | `lan1` ... `lan8` and `dmz` bridged, `192.168.1.1` |
| WAN | `eth0`, DHCP client |
| Login | `root`, no password. Set one with `passwd` |
| Package manager | `apk` |

## Flash layout

| Region | Stock firmware | OpenWrt |
|---|---|---|
| `0x0000000` - `0x00a0000` | `u-boot` (U-Boot 1.1.4) | `u-boot` (U-Boot 2020.04, `0xc0000`) |
| `0x00a0000` - `0x0100000` | `bootldr-env` | U-Boot env at `0xc0000` |
| `0x0100000` - `0x7a00000` | `kernel-1`, `rootfs-1`, start of `kernel-2`/`rootfs-2` | `ubi` (kernel, rootfs, rootfs_data) |
| rest | `rootfs-2`, `default_sw`, `images_back`, `config-back`, `logs`, `storage` | not written by the install |

## Tools

| File | Purpose |
|---|---|
| [`tools/uboot_256m.py`](tools/uboot_256m.py) | makes the 256 MiB U-Boot from the official `u-boot.kwb` |
| [`tools/serd.py`](tools/serd.py) | console daemon: logs the console to a file, reconnects after power cycles |
| [`tools/sc.py`](tools/sc.py) | sends a command through `serd.py` and prints the reply; `-c` spams Ctrl+C to stop autoboot |

## License

This guide is licensed under [CC BY 4.0](LICENSE). The scripts in `tools/` are
[MIT](LICENSE-tools).

The OpenWrt images in the release are unmodified official OpenWrt 25.12.5 builds, licensed
under GPL-2.0. `u-boot-256m.kwb` is the official OpenWrt 25.12.5 `u-boot.kwb` with only the
DDR header change described above.
Source code: [openwrt/openwrt @ v25.12.5](https://github.com/openwrt/openwrt/tree/v25.12.5),
official downloads:
[downloads.openwrt.org](https://downloads.openwrt.org/releases/25.12.5/targets/kirkwood/generic/).
