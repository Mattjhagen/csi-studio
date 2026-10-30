#!/usr/bin/env python3
"""Local-only CSI viewer. Python standard library; no installation required."""
import argparse, collections, csv, io, json, math, random, socket, threading, time, os, subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

lock = threading.Lock()
frames = collections.deque(maxlen=300)
status = {'accepted': 0, 'rejected': 0, 'source': 'waiting', 'error': None}

def parse(line):
    line = line.strip()
    if line.startswith('{'):
        obj = json.loads(line)
        values = obj['data']
        rssi = float(obj.get('rssi', -50))
        invalid = bool(obj.get('first_word_invalid', False))
    elif line.startswith('CSI_DATA,'):
        row = next(csv.reader(io.StringIO(line)))
        # Espressif get-started CSV: data is the final quoted array;
        # len and first_word_invalid immediately precede it.
        values = json.loads(row[-1])
        if int(row[-3]) != len(values):
            raise ValueError('CSV CSI length mismatch')
        invalid = bool(int(row[-2]))
        rssi = float(row[3])
    else:
        raise ValueError('not a CSI record')
    if not isinstance(values, list) or not 4 <= len(values) <= 4096 or len(values) % 2:
        raise ValueError('CSI data must contain an even number of signed bytes')
    if any(type(v) is not int or not -128 <= v <= 127 for v in values) or not math.isfinite(rssi):
        raise ValueError('invalid sample')
    if invalid:
        values = values[4:]  # ESP32 first four bytes may be invalid
    amp = [round(math.hypot(values[i], values[i+1]), 3) for i in range(0, len(values), 2)]
    if not amp:
        raise ValueError('empty CSI data')
    return {'time': time.time(), 'rssi': rssi, 'amplitudes': amp, 'mean': sum(amp)/len(amp)}

def ingest(line, source):
    try:
        frame = parse(line)
        frame['source'] = source
        with lock:
            frames.append(frame)
            status.update(accepted=status['accepted']+1, source=source)
    except (ValueError, KeyError, TypeError, IndexError, csv.Error):
        with lock:
            status['rejected'] += 1

def udp(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', port))
    while True:
        data, _ = sock.recvfrom(65535)
        for line in data.decode('utf-8', errors='replace').splitlines():
            ingest(line, 'UDP')

def serial(port, baud):
    try:
        subprocess.run(['stty', '-f', port, str(baud), 'raw', '-echo'], check=True, capture_output=True)
        with open(port, 'rb', buffering=0) as stream:
            while True:
                line = stream.readline(65536)
                if not line:
                    raise OSError('Serial device disconnected')
                ingest(line.decode('utf-8', errors='replace'), 'ESP32 serial')
    except (OSError, subprocess.CalledProcessError) as exc:
        with lock:
            status['error'] = str(exc)

def simulate():
    start = time.monotonic()
    rng = random.Random(32)
    while True:
        t = time.monotonic()-start
        data = []
        for k in range(64):
            a = 35 + 12*math.sin(k/9+t*2) + rng.gauss(0, 1.5)
            data.extend([round(a*math.sin(k/8)), round(a*math.cos(k/8))])
        ingest(json.dumps({'data': data, 'rssi': -48+3*math.sin(t)}), 'SIMULATED')
        time.sleep(.05)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/frames':
            with lock:
                payload = json.dumps({'status': dict(status), 'frames': list(frames)}).encode()
            content_type = 'application/json'
        elif self.path in ('/', '/index.html'):
            payload = Path(__file__).with_name('index.html').read_bytes()
            content_type = 'text/html; charset=utf-8'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(payload)
    def log_message(self, *args):
        pass

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--simulate', action='store_true')
    p.add_argument('--serial', help='Mac serial device, e.g. /dev/cu.usbmodem...')
    p.add_argument('--baud', type=int, default=115200)
    p.add_argument('--port', type=int, default=8765)
    p.add_argument('--udp-port', type=int, default=5500)
    args = p.parse_args()
    if args.simulate and args.serial:
        p.error('Choose simulation or serial input')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    # Bind UDP before announcing readiness, so conflicts fail visibly.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', args.udp_port))
    def receive():
        while True:
            data, _ = sock.recvfrom(65535)
            for line in data.decode('utf-8', errors='replace').splitlines():
                ingest(line, 'UDP')
    threading.Thread(target=receive, daemon=True).start()
    if args.simulate:
        threading.Thread(target=simulate, daemon=True).start()
    if args.serial:
        threading.Thread(target=serial, args=(args.serial,args.baud), daemon=True).start()
    print('Dashboard: http://127.0.0.1:%d | local UDP: %d | Ctrl+C to stop' % (args.port,args.udp_port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        sock.close()

if __name__ == '__main__':
    main()
