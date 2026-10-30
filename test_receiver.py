import json
from pathlib import Path
import socket
import signal
import subprocess
import sys
import time
import unittest
import urllib.request
from receiver import parse
from test_serial import free_port


class ReceiverTests(unittest.TestCase):
    def test_json(self):
        self.assertEqual(parse('{"data":[3,4,0,5]}')['amplitudes'], [5, 5])

    def test_csv_and_invalid_word(self):
        self.assertEqual(parse('CSI_DATA,0,aa,-50,8,1,"[1,2,3,4,3,4,0,5]"')['amplitudes'], [5, 5])

    def test_bad_records(self):
        for line in ['boot log', '{"data":[1,2,3]}', '{"data":[128,0,1,0]}',
                     'CSI_DATA,0,aa,-50,6,0,"[3,4,0,5]"']:
            with self.assertRaises((ValueError, KeyError)):
                parse(line)

    def test_live_udp_and_dashboard(self):
        port, udp = free_port(socket.SOCK_STREAM), free_port(socket.SOCK_DGRAM)
        base = 'http://127.0.0.1:%d' % port
        process = subprocess.Popen([
            sys.executable, str(Path(__file__).with_name('receiver.py')), '--simulate',
            '--port', str(port), '--udp-port', str(udp)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        def get():
            with urllib.request.urlopen(base+'/api/frames', timeout=.5) as response:
                return json.load(response)
        try:
            deadline = time.monotonic()+5
            while True:
                try:
                    if get()['frames']:
                        break
                except OSError:
                    pass
                if time.monotonic() > deadline:
                    self.fail('Simulation receiver did not become ready')
                time.sleep(.05)
            before = get()['status']['rejected']
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(b'{"data":[3,4,0,5],"rssi":-42}', ('127.0.0.1', udp))
                sock.sendto(b'bad record', ('127.0.0.1', udp))
            deadline = time.monotonic()+3
            while True:
                result = get()
                if result['status']['rejected'] > before:
                    break
                if time.monotonic() > deadline:
                    self.fail('UDP data did not arrive')
                time.sleep(.05)
            self.assertTrue(any(f['source']=='UDP' and f['amplitudes']==[5,5] for f in result['frames']))
            self.assertTrue(any(f['source']=='SIMULATED' for f in result['frames']))
            with urllib.request.urlopen(base+'/', timeout=.5) as response:
                self.assertIn(b'Wi-Fi CSI Studio', response.read())
        finally:
            process.send_signal(signal.SIGINT)
            _, errors = process.communicate(timeout=3)
            self.assertEqual(process.returncode, 0, errors.decode())
            self.assertNotIn(b'Traceback', errors)


if __name__ == '__main__':
    unittest.main()
