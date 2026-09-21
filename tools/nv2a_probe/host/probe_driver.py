#!/usr/bin/env python3
"""Host side of the NV2A probe.

The console dials out; this listens, so a console that wedges shows up as a
dead socket instead of as silence somebody has to time out on.

THE HOST OWNS THE JOURNAL. The probe refuses to execute a write it has not
journalled: it sends the intent, blocks, and only stores to the BAR after this
side has durably recorded the intent and acknowledged it. The console's own
drive is never touched during a run, which is what makes a probe run safe to
power-cycle out of.

Two consequences worth stating, because they are the reason the journal is
worth its complexity:

  * When a socket dies, the last journalled-but-uncompleted write is exactly
    the operation that was in flight. It is marked `suspected_hang` and added
    to the poison list.
  * A poisoned (offset, value) is never issued again, so a resumed sweep walks
    past the thing that killed it instead of into it a second time.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time


class ProbeError(RuntimeError):
    pass


class Journal:
    """Append-only record of write intents and their outcomes."""

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._fh = open(path, "a", encoding="utf-8")
        self._lock = threading.Lock()
        self.pending: dict | None = None

    def record_intent(self, seq: int, off: int, val: int) -> dict:
        entry = {
            "t": time.time(),
            "seq": seq,
            "op": "W",
            "offset": off,
            "value": val,
            "state": "journalled",
        }
        with self._lock:
            self._fh.write(json.dumps(entry) + "\n")
            self._fh.flush()
            os.fsync(self._fh.fileno())   # durable BEFORE the ack goes out
            self.pending = entry
        return entry

    def record_outcome(self, seq: int, state: str, detail: str = "") -> None:
        with self._lock:
            self._fh.write(json.dumps(
                {"t": time.time(), "seq": seq, "state": state,
                 "detail": detail}) + "\n")
            self._fh.flush()
            if self.pending and self.pending["seq"] == seq:
                self.pending = None

    def orphan(self) -> dict | None:
        """The intent that was in flight when the link died, if any."""
        with self._lock:
            return self.pending

    def close(self):
        try:
            self._fh.close()
        except Exception:
            pass


class PoisonList:
    """(offset, value) pairs that have already killed a session once."""

    def __init__(self, path: str):
        self.path = path
        self.items: dict[str, dict] = {}
        if os.path.exists(path):
            try:
                self.items = json.load(open(path, encoding="utf-8"))
            except Exception:
                self.items = {}

    @staticmethod
    def key(off: int, val: int | None) -> str:
        return "%08X/%s" % (off, "*" if val is None else "%08X" % val)

    def is_poison(self, off: int, val: int | None = None) -> bool:
        """Is this write banned?

        `val=None` asks the broader question "is this REGISTER banned", which
        is what a sweep needs: you cannot sweep a register without writing to
        it, so one value hanging the console bans the offset. The first version
        only compared exact keys, so a ban recorded as `00000200/00000000` did
        not match the sweep's `is_poison(0x200, None)` lookup and the register
        that had just wedged the machine went straight back onto the todo list.
        """
        if self.key(off, None) in self.items:
            return True
        if val is not None:
            return self.key(off, val) in self.items
        prefix = "%08X/" % off
        return any(k.startswith(prefix) for k in self.items)

    def add(self, off: int, val: int | None, why: str) -> None:
        self.items[self.key(off, val)] = {"why": why, "t": time.time()}
        tmp = self.path + ".tmp"
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.items, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)


class Session:
    """One accepted connection from the probe."""

    #: The probe's HELLO carries this when it was built with
    #: PROBE_ALLOW_HAZARDS -- the emulator-only variant whose hazard refusal is
    #: compiled out.
    HAZARD_MARK = "-HAZARDS-ALLOWED-EMULATOR-ONLY"

    def __init__(self, conn: socket.socket, peer, journal: Journal,
                 poison: PoisonList, timeout: float = 15.0,
                 allow_hazards: bool = False):
        self.conn = conn
        self.peer = peer
        self.journal = journal
        self.poison = poison
        self.conn.settimeout(timeout)
        self._buf = b""
        self.hello = self._recv_line()
        if not self.hello.startswith("HELLO"):
            raise ProbeError("expected HELLO, got %r" % self.hello)

        # THE HAZARD-ALLOWED BUILD IS REFUSED UNLESS IT WAS ASKED FOR.
        #
        # The variant exists so the emulator can be driven into registers the
        # console must never be driven into; the hazard refusal is compiled
        # out of it. It lands in bin-hazards/, under its own XBE title, so it
        # cannot occupy the path the console deploy reads -- but a file can be
        # copied, and "which CFLAGS were in that shell" is not a property this
        # side can see. The HELLO is, so this is where it gets checked. The
        # announcement existed before this check and nothing read it, which
        # made it a log line rather than a safety property.
        self.hazards_allowed = self.HAZARD_MARK in self.hello
        if self.hazards_allowed and not allow_hazards:
            raise ProbeError(
                "the probe that dialled in is the HAZARDS-ALLOWED build: its "
                "refusal to write NV_PMC_ENABLE, the PLL coefficients and the "
                "rest of the hazard list is compiled out. That build is for "
                "the emulator. If this really is the emulator, pass "
                "allow_hazards=True (probe_driver) or --allow-hazards; if it "
                "is the console, the wrong XBE is deployed. HELLO was: %s"
                % self.hello)

    # -- wire ------------------------------------------------------------
    def _recv_line(self) -> str:
        while b"\n" not in self._buf:
            chunk = self.conn.recv(4096)
            if not chunk:
                raise ProbeError("probe closed the connection")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return line.decode("utf-8", "replace").strip()

    def _send(self, s: str) -> None:
        self.conn.sendall((s + "\n").encode("utf-8"))

    # -- operations ------------------------------------------------------
    def read32(self, off: int) -> int:
        self._send("R %08X" % off)
        reply = self._recv_line()
        if reply.startswith("OK R"):
            return int(reply.split()[3], 16)
        raise ProbeError(reply)

    def write32(self, off: int, val: int) -> None:
        """Issue a write. The probe journals with us before it executes."""
        if self.poison.is_poison(off, val):
            raise ProbeError("poisoned: %08X=%08X has hung a session before"
                             % (off, val))
        self._send("W %08X %08X" % (off, val))
        seq = None
        while True:
            line = self._recv_line()
            if line.startswith("JOURNAL"):
                parts = line.split()
                seq = int(parts[1])
                joff, jval = int(parts[3], 16), int(parts[4], 16)
                if (joff, jval) != (off, val):
                    self._send("NAK %d" % seq)
                    raise ProbeError("probe journalled %08X=%08X, we asked for "
                                     "%08X=%08X" % (joff, jval, off, val))
                self.journal.record_intent(seq, joff, jval)
                self._send("ACK %d" % seq)
                continue
            if line.startswith("OK W"):
                if seq is not None:
                    self.journal.record_outcome(seq, "completed")
                return
            if line.startswith("ERR"):
                if seq is not None:
                    self.journal.record_outcome(seq, "refused", line)
                raise ProbeError(line)
            raise ProbeError("unexpected: %r" % line)

    def status(self) -> str:
        self._send("S")
        return self._recv_line()

    def ping(self) -> bool:
        self._send("P")
        return self._recv_line().startswith("OK")

    def soft_reset(self) -> None:
        self._send("X")
        try:
            self._recv_line()
        except Exception:
            pass

    def end_run(self) -> None:
        """Tell the probe this run ended on purpose, then close.

        Without it the probe reports every close as "disconnected; redialling",
        which looks identical to a failure on the console's screen.
        """
        try:
            self._send("Q")
            self._recv_line()
        except Exception:
            pass
        self.close()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


class ProbeServer:
    """Accepts the console's dial-out, forever, handing each to a callback."""

    def __init__(self, workdir: str, host: str = "0.0.0.0", port: int = 24242,
                 allow_hazards: bool = False):
        self.addr = (host, port)
        # Off by default and passed down to every session: the caller has to
        # say, once, that it knows it is talking to the emulator-only build.
        self.allow_hazards = allow_hazards
        self.journal = Journal(os.path.join(workdir, "journal.jsonl"))
        self.poison = PoisonList(os.path.join(workdir, "poison.json"))
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(self.addr)
        self.sock.listen(4)

    def accept(self, timeout: float | None = None) -> Session:
        self.sock.settimeout(timeout)
        conn, peer = self.sock.accept()
        return Session(conn, peer, self.journal, self.poison,
                       allow_hazards=self.allow_hazards)

    def note_link_death(self, exc: Exception) -> dict | None:
        """Attribute a dead socket to whatever was in flight.

        A write that was journalled and never completed is the operation the
        console died on. That is the whole reason the intent goes out before
        the store happens -- without it, a hang tells you only that something
        went wrong, not what.
        """
        orphan = self.journal.orphan()
        if orphan is None:
            return None
        self.journal.record_outcome(orphan["seq"], "suspected_hang", str(exc))
        self.poison.add(orphan["offset"], orphan["value"],
                        "link died with this write in flight")
        # Ban the whole register too, not just this value. A sweep has to write
        # to a register to measure it, so "this value hangs it" and "leave this
        # register alone" are the same instruction here.
        self.poison.add(orphan["offset"], None,
                        "link died with a write to this register in flight")
        return orphan

    def close(self):
        self.journal.close()
        try:
            self.sock.close()
        except Exception:
            pass
