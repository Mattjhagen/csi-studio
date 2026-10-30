#!/bin/zsh
cd -- "${0:A:h}"
/usr/bin/open 'http://127.0.0.1:8765'
exec /usr/bin/python3 receiver.py --simulate
