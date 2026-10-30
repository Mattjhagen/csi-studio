# CSI Studio

Cardputer-Adv firmware is now included in [`firmware/cardputer-adv`](firmware/cardputer-adv/README.md). It provides keyboard Wi-Fi setup, on-device status, and USB CSI streaming. See that guide for build, backup, and flashing steps.

## Mac dashboard

A dependency-free Python receiver and browser dashboard. Built and verified on an Apple M4 MacBook Air, macOS 27.0.1, with /usr/bin/python3 (3.9.6). No packages, drivers, system settings, or firmware were installed. The existing Homebrew Node installation fails due to a missing simdjson library; this project does not use Node.

## Start the simulation

Double-click `Start Simulation.command` in Finder, or run:

```sh
cd '/Users/matt/Documents/Codex/2026-10-30/referenced-chatgpt-conversation-this-is-an/outputs/esp32-csi'
/usr/bin/python3 receiver.py --simulate
```

Open http://127.0.0.1:8765 in a browser. The simulation runs at approximately 20 records/second. Stop with Control-C in the launcher's Terminal window. If a copy is already running, stop it before starting another; a port-in-use error means another process owns a required port. `--port` and `--udp-port` can select alternatives.

The page shows sample magnitudes, mean magnitude history, RSSI, record counts, and sample age. SIMULATED is synthetic data, not sensing. The last 300 records are retained in memory, not saved to disk. There is no motion, breathing, or presence classifier.

## Connect the ESP32 later

1. Connect the board with a data-capable USB cable. No obvious ESP32 port was present during setup. The board model, current firmware, USB driver needs, and baud rate are not yet known.
2. List devices with `ls /dev/cu.*`. Look for a newly appearing usbmodem, usbserial, SLAB_USBtoUART, or wchusbserial device. Do not use Bluetooth or unrelated devices. Some boards need a vendor USB driver; determine the board's USB bridge before installing one.
3. The board must run CSI-capable firmware, not just a Wi-Fi scanner. Espressif's `esp-csi/examples/get-started/csi_recv_router` is a possible future firmware route: the receiver joins an AP and generates ping traffic to obtain CSI. Choose the exact firmware and ESP-IDF version after identifying the board. No firmware toolchain or flashing has been performed.
4. Stop the simulation with Control-C. Start the receiver, replacing the example device path with the actual new port and matching the firmware's baud rate:

```sh
/usr/bin/python3 receiver.py --serial /dev/cu.usbmodemYOUR_DEVICE --baud 115200
```

5. Open the same dashboard. It should show ESP32 serial and fresh sample ages. Close other serial monitors first. Boot messages increment the rejected counter; continuous rejections suggest mismatched baud or CSV format. Device errors appear on the dashboard; reconnect and restart after a disconnect.

## Accepted records

One UTF-8 record per line, either JSON or Espressif get-started CSV.

JSON example:

```json
{"data":[3,4,0,5,-3,4,5,0],"rssi":-48,"first_word_invalid":false}
```

`data` contains interleaved signed integer CSI bytes (-128 through 127). Magnitude is calculated per adjacent pair. Espressif encodes imaginary then real; magnitude is unaffected by their order. Even lengths from 4 to 4096 are accepted. If `first_word_invalid` is true, the first four bytes are discarded.

CSV supports the get-started layout beginning `CSI_DATA,`, with RSSI at column index 3 and the final three columns `len,first_word_invalid,"[...signed bytes...]"`. The declared length must match the array. Firmware variants with different layouts need a parser adjustment. No phase calibration, LTF separation, null/pilot subcarrier removal, or cross-device calibration is performed; the chart uses complex sample index, not a calibrated subcarrier frequency axis.

## Local UDP bridge

The receiver always listens on 127.0.0.1:5500 for the same records, one or more newline-separated records per datagram. This is for a process on this Mac. The ESP32 cannot send directly to this loopback address over Wi-Fi; USB serial is the prepared hardware route. LAN listening would require a deliberate configuration change. Both HTTP and UDP are bound to loopback only; the dashboard loads no external scripts.

## Verification

The tests start temporary receivers on free local ports; no board or running simulator is required:

```sh
/usr/bin/python3 -m unittest discover -s . -v
```

Five tests cover JSON amplitudes, CSV invalid-byte handling, invalid records, live simulation/UDP/HTTP delivery, and the Mac serial path through a pseudo-terminal. The UDP test deliberately sends one malformed record to its temporary receiver. The browser was checked with live simulated values. Real USB serial acquisition remains unverified until the ESP32 is connected.

## CSI versus monitor mode

Monitor mode delivers captured Wi-Fi frames and metadata. A monitor-mode-capable dongle does not by itself guarantee access to per-subcarrier CSI; that requires compatible chipset, driver, and firmware support. This setup receives CSI exported by ESP32 firmware and does not use the Mac Wi-Fi adapter for CSI extraction. Kismet was not installed or configured; packet capture is an optional separate project once adapter and macOS driver compatibility are established.

Official references:
- https://github.com/espressif/esp-csi/tree/master/examples/get-started
- https://github.com/espressif/esp-csi/tree/master/examples/get-started/csi_recv_router
- https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-guides/wifi.html#wi-fi-channel-state-information
