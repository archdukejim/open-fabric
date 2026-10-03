#!/usr/bin/env python3
"""Send one MAB Access-Request (User-Name = the MAC, with a
Message-Authenticator) and print the answer: "Access-Accept vlan=30",
"Access-Reject" or "no reply". Stands in for a switch in the sandbox test.

    radius_mab.py <server> <mac>          (the shared secret on stdin)
"""
import hashlib
import hmac
import os
import socket
import sys

server, mac = sys.argv[1], sys.argv[2].encode()
secret = sys.stdin.readline().strip().encode()
auth = os.urandom(16)


def attr(t, v):
    return bytes([t, len(v) + 2]) + v


pw, prev, enc = mac.ljust(32, b"\0"), auth, b""
for i in range(0, 32, 16):
    block = bytes(a ^ b for a, b in zip(pw[i:i + 16], hashlib.md5(secret + prev).digest()))
    enc, prev = enc + block, block
body = attr(1, mac) + attr(2, enc) + attr(31, mac) + attr(32, b"sandbox-switch") + attr(80, b"\0" * 16)
head = bytes([1, 42]) + (20 + len(body)).to_bytes(2, "big") + auth
signature = hmac.new(secret, head + body, hashlib.md5).digest()
packet = head + body[:-16] + signature
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(5)
s.sendto(packet, (server, 1812))
try:
    reply = s.recv(4096)
except socket.timeout:
    print("no reply")
    sys.exit(0)
code = {2: "Access-Accept", 3: "Access-Reject"}.get(reply[0], "?")
vlan, i = None, 20
while i < len(reply):
    t, n = reply[i], reply[i + 1]
    if t == 81:                                   # Tunnel-Private-Group-Id (tag byte first if < 0x20)
        v = reply[i + 2:i + n]
        vlan = (v[1:] if v and v[0] < 0x20 else v).decode()
    i += n
print(code + (f" vlan={vlan}" if vlan else ""))
