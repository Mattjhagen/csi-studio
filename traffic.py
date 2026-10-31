#!/usr/bin/env python3
"""Send small unicast UDP packets to the Cardputer to produce AP downlink CSI."""
import argparse
import ipaddress
import json
import socket
import time
import urllib.request


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target', help='Cardputer private IPv4 address; otherwise read local receiver status')
    p.add_argument('--rate', type=float, default=10)
    args = p.parse_args()
    if not 0 < args.rate <= 50:
        p.error('rate must be between 0 and 50 packets per second')
    target = args.target
    if not target:
        with urllib.request.urlopen('http://127.0.0.1:8765/api/frames', timeout=3) as response:
            device = json.load(response)['status'].get('device')
        if not device or time.time()-device['time'] > 5:
            p.error('No recent device status; connect firmware v0.3 or specify --target')
        target = device.get('ip')
    try:
        addr = ipaddress.IPv4Address(target)
    except ipaddress.AddressValueError:
        p.error('target must be a private IPv4 address')
    if not addr.is_private or addr.is_loopback or addr.is_multicast or addr.is_unspecified or addr.is_link_local:
        p.error('target must be a private LAN IPv4 address')
    print('Sending %.1f packets/s to Cardputer %s:5501; Ctrl+C stops' % (args.rate, addr), flush=True)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            while True:
                sock.sendto(b'CSI-Studio-probe', (str(addr), 5501))
                time.sleep(1/args.rate)
        except KeyboardInterrupt:
            pass
        except OSError as exc:
            raise SystemExit("Cannot reach the Cardputer: %s. Check its IP and network isolation." % exc)


if __name__ == '__main__':
    main()
