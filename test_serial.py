"""Exercise the Mac serial path through a pseudo-terminal, without hardware."""
import json
import os
from pathlib import Path
import socket
import signal
import subprocess
import sys
import time
import termios
import unittest
import urllib.request


def free_port(kind):
    with socket.socket(socket.AF_INET, kind) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@unittest.skipUnless(sys.platform == 'darwin', 'Mac stty serial integration')
class SerialIntegration(unittest.TestCase):
    def test_serial_to_http(self):
        master, slave = os.openpty()
        port = free_port(socket.SOCK_STREAM)
        udp = free_port(socket.SOCK_DGRAM)
        process = subprocess.Popen([
            sys.executable, str(Path(__file__).with_name('receiver.py')),
            '--serial', os.ttyname(slave), '--port', str(port), '--udp-port', str(udp)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            result = None
            while time.monotonic() < deadline:
                os.write(master, b'{"type":"status","version":"0.3","ip":"192.168.0.50","ping_sent":10,"ping_replies":10,"csi_callbacks":10}\n{"data":[3,4,0,5],"rssi":-42}\n')
                try:
                    with urllib.request.urlopen('http://127.0.0.1:%d/api/frames' % port, timeout=.3) as response:
                        result = json.load(response)
                    if result['frames']:
                        break
                except OSError:
                    pass
                time.sleep(.1)
            self.assertIsNotNone(result)
            self.assertIsNone(result['status']['error'])
            self.assertTrue(result['frames'], 'No frames arrived through the serial reader')
            self.assertEqual(result['frames'][-1]['amplitudes'], [5, 5])
            self.assertEqual(result['frames'][-1]['source'], 'ESP32 serial')
            self.assertEqual(result['status']['device']['ip'], '192.168.0.50')
            self.assertEqual(result['status']['rejected'], 0)
            self.assertEqual(termios.tcgetattr(slave)[4], termios.B115200)
            self.assertEqual(termios.tcgetattr(slave)[5], termios.B115200)
        finally:
            process.send_signal(signal.SIGINT)
            _, errors = process.communicate(timeout=3)
            self.assertEqual(process.returncode, 0, errors.decode())
            self.assertNotIn(b'Traceback', errors)
            os.close(master)
            os.close(slave)


if __name__ == '__main__':
    unittest.main()
