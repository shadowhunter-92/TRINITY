#!/usr/bin/env python3
"""Launch a disposable loopback Modbus simulator and read it; exits immediately."""
from __future__ import annotations

import socketserver
import struct
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trinitylab.industrial.modbus import read_registers
from trinitylab.util import emit


class _Reader(socketserver.BaseRequestHandler):
    def handle(self):
        req = bytearray()
        while len(req) < 12:
            chunk = self.request.recv(12 - len(req))
            if not chunk:
                return
            req.extend(chunk)
        tx, protocol, length, unit, code, address, count = struct.unpack(">HHHBBHH", req)
        if protocol != 0 or length != 6 or code not in (3, 4) or count > 125 or address + count > 65536:
            return
        vals = [(100 + i) & 0xFFFF for i in range(address, address + count)]
        payload = struct.pack(">HHHBBB", tx, 0, 3 + 2 * count, unit, code, count * 2) + struct.pack(">" + "H" * count, *vals)
        self.request.sendall(payload)


class _LocalServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    server = _LocalServer(("127.0.0.1", 0), _Reader)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        vals = read_registers("127.0.0.1", server.server_address[1], 0, 3, enable_network=True)
        emit({"project": "trinity_industrial", "demo": "disposable_loopback_modbus", "function": "03_read_holding", "readings": vals, "expected": [100, 101, 102], "passed": vals == [100, 101, 102], "scope": "loopback_only_no_real_hardware"})
        return 0 if vals == [100, 101, 102] else 2
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


if __name__ == "__main__":
    sys.exit(main())
