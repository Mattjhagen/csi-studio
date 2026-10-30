import json, socket, time, unittest, urllib.request
from receiver import parse
class ReceiverTests(unittest.TestCase):
    def test_json(self):
        self.assertEqual(parse('{"data":[3,4,0,5]}')['amplitudes'], [5,5])
    def test_csv_and_invalid_word(self):
        self.assertEqual(parse('CSI_DATA,0,aa,-50,8,1,"[1,2,3,4,3,4,0,5]"')['amplitudes'],[5,5])
    def test_bad_records(self):
        for line in ['boot log', '{"data":[1,2,3]}', '{"data":[128,0,1,0]}','CSI_DATA,0,aa,-50,6,0,"[3,4,0,5]"']:
            with self.assertRaises((ValueError,KeyError)):
                parse(line)
    def test_live_udp_and_dashboard(self):
        def get():
            return json.load(urllib.request.urlopen('http://127.0.0.1:8765/api/frames'))
        before=get()['status']['rejected']
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        sock.sendto(b'{"data":[3,4,0,5],"rssi":-42}',('127.0.0.1',5500))
        sock.sendto(b'bad record',('127.0.0.1',5500))
        time.sleep(.15)
        result=get()
        self.assertTrue(any(f['source']=='UDP' and f['amplitudes']==[5,5] for f in result['frames']))
        self.assertGreater(result['status']['rejected'],before)
        self.assertTrue(any(f['source']=='SIMULATED' for f in result['frames']))
        self.assertIn(b'Wi-Fi CSI Studio',urllib.request.urlopen('http://127.0.0.1:8765/').read())
        sock.close()
if __name__=='__main__': unittest.main()
