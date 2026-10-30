"""Exercise the Mac serial path through a pseudo-terminal, without hardware."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
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
                os.write(master, b'{"data":[3,4,0,5],"rssi":-42}\n')
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
        finally:
            process.terminate()
            process.communicate(timeout=3)
            os.close(master)
            os.close(slave)


if __name__ == '__main__':
    unittest.main()
