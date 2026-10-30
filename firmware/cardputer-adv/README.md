# Cardputer-Adv CSI receiver

Target: M5Stack Cardputer-Adv, ESP32-S3FN8, 8 MB flash, USB CDC. Uses the Adv-aware M5Cardputer 1.1.1 library. This is a dedicated firmware image, not an M5Launcher plugin.

## Build

Install PlatformIO Core 6.2.0 in an isolated Python environment, then:

```sh
pio run -d firmware/cardputer-adv
```

Dependencies and compiler downloads are handled by PlatformIO. Platform espressif32 8.0.0 uses the newer Arduino ESP32 framework already available on this Mac; USB flags and board settings follow M5Stack's Cardputer-Adv configuration. Build artifacts live in the ignored `.pio` directory.

## Install with M5Launcher

To keep M5Launcher, copy the compiled `.pio/build/cardputer-adv/firmware.bin` to the microSD card and install it through Launcher's SD browser. This is an app-only image. It needs a slot at least as large as the binary; allow for Launcher's partition alignment. Inspect any proposed removal or repartition before proceeding. This route does not use the direct PlatformIO upload command below.

## Preserve existing firmware first

Do not flash over M5Launcher or another app until you have chosen how to preserve it. A full 8 MB flash backup captures the existing flash layout and settings; it does not back up the microSD card. Backups may contain Wi-Fi credentials and other private settings: keep them local and out of Git. This repo ignores `backups/` and `*.flash-backup.bin`.

Example using esptool 4.8.1 and an actual detected device path:

```sh
python -m esptool --chip esp32s3 --port /dev/cu.usbmodemYOUR_DEVICE --baud 460800 read_flash 0 0x800000 backups/cardputer.flash-backup.bin
```

Use download mode if required: power switch OFF, hold G0 while connecting USB, release G0. Check the detected chip/flash size before reading or writing. Firmware upload replaces the bootloader/partition layout/app at the configured addresses; it can replace M5Launcher. A backup is for restoring to the same device, with flash encryption/security settings taken into account.

After choosing a direct flash installation:

```sh
pio run -d firmware/cardputer-adv -t upload --upload-port /dev/cu.usbmodemYOUR_DEVICE
```

## USB streaming (v0.2)

The v0.2 build uses an 8 KB USB TX buffer and a bounded write timeout, and continues attempting writes when the native USB connection indicator temporarily reports disconnected. This addresses short streams that stop after a few records.

## Use

1. Reset the Cardputer after flashing if it remains in download mode.
2. On the Cardputer keyboard, enter your **2.4 GHz** Wi-Fi SSID and press Enter.
3. Enter the password and press Enter. Backspace edits; password characters are masked. Printable ASCII SSIDs (up to 32 bytes) and passwords (up to 63 bytes) are supported; non-ASCII names and 64-digit raw PSKs need a future input extension. Empty passwords work for open networks.
4. Credentials are passed to the Wi-Fi driver in RAM, with persistence disabled. They are not compiled into firmware, printed to USB, or saved by this app to flash. Reset requires re-entry. Previous firmware's flash contents are not erased wholesale by this app.
5. The display reports connection, channel, RSSI, records sent, and queue drops. USB JSON goes directly into the existing Mac receiver:

```sh
python3 receiver.py --serial /dev/cu.usbmodemYOUR_DEVICE --baud 115200
```

Stop the simulator and close other serial monitors first. The firmware does not wait for a Mac connection to show its UI. A reset changes the network; a connection timeout asks for reset and re-entry.

The firmware captures LLTF CSI from the associated access point and generates gateway ping traffic at a nominal 20 Hz. Actual record rate depends on router replies, radio traffic, and USB availability; callbacks are throttled to at most 20 Hz. A bounded FreeRTOS queue keeps USB work outside the Wi-Fi callback. Queue drops are shown on the device. Router isolation or ICMP filtering may reduce useful traffic. Wi-Fi reconnection may require a reset, especially when the AP BSSID or gateway changes.

This is raw CSI acquisition, without a calibrated motion/presence classifier. Sample indices are not calibrated frequency labels. Firmware must be built and then tested on the physical Adv; a successful compile alone is not hardware validation.

Official references:
- https://docs.m5stack.com/en/core/Cardputer-Adv
- https://github.com/m5stack/M5Cardputer
- https://github.com/espressif/esp-csi/tree/master/examples/get-started/csi_recv_router
