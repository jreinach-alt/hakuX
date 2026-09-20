#!/usr/bin/env python3
"""Host-side tests against a simulated probe. No console required.

The parts worth testing here are the ones that only matter when something has
already gone wrong: attributing a dead socket to the write that was in flight,
and never issuing that write again. Those paths are unreachable in a healthy
run, so if they are not exercised deliberately they are not exercised at all.

The fake probe implements the same wire protocol, including the journal
handshake, and hangs on one nominated register the way real silicon would.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_driver import ProbeServer, ProbeError   # noqa: E402

PORT = 24299
HANG_AT = 0x000208          # the register our fake silicon dies on


class FakeProbe(threading.Thread):
    """Speaks the probe protocol. Dies on HANG_AT to simulate a wedge."""

    daemon = True

    def __init__(self, port, hang_once=True):
        super().__init__()
        self.port = port
        self.hang_once = hang_once
        self.hung = False
        self.regs = {}
        self.seq = 0
        self.sessions = 0
        self.stop = False

    def run(self):
        while not self.stop:
            try:
                s = socket.create_connection(("127.0.0.1", self.port), timeout=5)
            except OSError:
                time.sleep(0.05)
                continue
            self.sessions += 1
            try:
                self._serve(s)
            except Exception:
                pass
            finally:
                try:
                    s.close()
                except Exception:
                    pass

    def _serve(self, s):
        f = s.makefile("rwb")
        f.write(b"HELLO 1 nv2a-probe base=FD000000 size=01000000\n")
        f.flush()
        while True:
            line = f.readline()
            if not line:
                return
            cmd = line.decode().strip().split()
            if not cmd:
                continue
            if cmd[0] == "R":
                off = int(cmd[1], 16)
                f.write(b"OK R %08X %08X PMC\n" % (off, self.regs.get(off, 0)))
                f.flush()
            elif cmd[0] == "W":
                off, val = int(cmd[1], 16), int(cmd[2], 16)
                self.seq += 1
                f.write(b"JOURNAL %d W %08X %08X\n" % (self.seq, off, val))
                f.flush()
                ack = f.readline()
                if not ack.startswith(b"ACK"):
                    return
                if off == HANG_AT and not (self.hang_once and self.hung):
                    # Journalled, acked, and now the console wedges mid-write.
                    self.hung = True
                    return
                self.regs[off] = val
                f.write(b"OK W %08X %08X\n" % (off, val))
                f.flush()
            elif cmd[0] == "S":
                f.write(b"STATUS proto=1 uptime_ms=1 reads=0 writes=0\n")
                f.flush()
            else:
                f.write(b"ERR EPARSE\n")
                f.flush()


def main() -> int:
    wd = tempfile.mkdtemp(prefix="probe-test-")
    fails = []

    def check(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    srv = ProbeServer(wd, host="127.0.0.1", port=PORT)
    fake = FakeProbe(PORT)
    fake.start()
    try:
        print("== a healthy write round-trips and is journalled ==")
        sess = srv.accept(timeout=10)
        sess.write32(0x000100, 0xDEADBEEF)
        check(sess.read32(0x000100) == 0xDEADBEEF, "value read back")
        entries = [json.loads(l) for l in
                   open(os.path.join(wd, "journal.jsonl"), encoding="utf-8")]
        check(any(e.get("state") == "journalled" and e.get("offset") == 0x100
                  for e in entries), "intent journalled before execution")
        check(any(e.get("state") == "completed" for e in entries),
              "outcome recorded")

        print("== a write that wedges the console is attributed and poisoned ==")
        try:
            sess.write32(HANG_AT, 0xFFFFFFFF)
            check(False, "expected the link to die")
        except (ProbeError, OSError):
            check(True, "link death surfaced to the caller")
        orphan = srv.note_link_death(RuntimeError("socket died"))
        check(orphan is not None and orphan["offset"] == HANG_AT,
              "the in-flight write is identified as the suspect")
        check(srv.poison.is_poison(HANG_AT, 0xFFFFFFFF),
              "suspect added to the poison list")
        entries = [json.loads(l) for l in
                   open(os.path.join(wd, "journal.jsonl"), encoding="utf-8")]
        check(any(e.get("state") == "suspected_hang" for e in entries),
              "journal records it as a suspected hang")
        sess.close()

        print("== the driver reconnects and refuses to reissue the poison ==")
        sess = srv.accept(timeout=10)
        check(fake.sessions >= 2, "probe redialled after the wedge")
        try:
            sess.write32(HANG_AT, 0xFFFFFFFF)
            check(False, "poisoned write must not be issued a second time")
        except ProbeError as e:
            check("poison" in str(e), "poisoned write refused before the wire")
        sess.write32(0x000104, 0x12345678)
        check(sess.read32(0x000104) == 0x12345678, "sweep resumes past the suspect")

        print("== the SWEEP's offset-level filter sees the ban ==")
        # The sweep asks "is this register banned" with val=None. An exact-key
        # lookup answered no for a ban recorded against a specific value, and
        # the register that had just wedged the console went back on the todo
        # list. This is the check that would have caught it.
        check(srv.poison.is_poison(HANG_AT, None),
              "is_poison(off, None) matches a ban recorded for one value")
        check(not srv.poison.is_poison(0x000999, None),
              "an unrelated register is not banned")

        print("== poison survives a restart (it is persisted) ==")
        srv2 = ProbeServer(wd, host="127.0.0.1", port=PORT + 1)
        check(srv2.poison.is_poison(HANG_AT, 0xFFFFFFFF),
              "poison list reloaded from disk")
        srv2.close()
        sess.close()
    finally:
        fake.stop = True
        srv.close()
        shutil.rmtree(wd, ignore_errors=True)

    print()
    if fails:
        print("%d check(s) failed" % len(fails))
        return 1
    print("host driver loopback suite OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
