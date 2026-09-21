#!/usr/bin/env python3
"""Supervisor tests against a scripted console. No hardware.

Everything worth testing here is a path a healthy run never takes: the reboot
gap, the bounce loop, and the wedge that no software can fix. If they are not
driven deliberately they are not driven at all.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from supervisor import Supervisor, State   # noqa: E402

fails = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


class FakeConsole:
    """Replays a scripted sequence of states; records launches."""

    def __init__(self, script):
        self.script = list(script)
        self.launches = []
        self.i = 0
        self.power_cycles = 0            # must stay zero, forever

    def _now(self):
        s = self.script[min(self.i, len(self.script) - 1)]
        return s

    def ftp_up(self, timeout=5.0):
        return self._now() == "dash"

    def ping(self, timeout=2.0):
        return self._now() in ("dash", "running")

    def site_exec(self, path, timeout=10.0):
        self.launches.append(path)
        return "200 EXEC command succeeded."

    def advance(self):
        self.i += 1


def drive(script, *, max_bounces=3, interval=10.0, clock_step=10.0, **kw):
    con = FakeConsole(script)
    t = [1000.0]
    sup = Supervisor(con, "E:\\x.xbe", max_bounces=max_bounces, log=lambda *a: None, **kw)

    def sleep(_):
        con.advance()
        t[0] += clock_step

    sup.run(interval=interval, sleep=sleep, clock=lambda: t[0],
            max_iterations=len(script))
    return sup, con


def main() -> int:
    print("== at the dashboard, it launches the probe ==")
    sup, con = drive(["dash"])
    check(con.launches == ["E:\\x.xbe"], "one launch issued")

    print("== while the probe is running, it does nothing ==")
    sup, con = drive(["running", "running", "running"])
    check(con.launches == [], "no launch while an XBE has the console")

    print("== a normal reboot cycle relaunches once the dashboard returns ==")
    # launch, runs for a good while, comes back to the dashboard, relaunch
    sup, con = drive(["dash"] + ["running"] * 8 + ["dash"], clock_step=20.0)
    check(len(con.launches) == 2, "launched at the start and again after the reboot "
                                  f"(got {len(con.launches)})")
    check(sup.bounces == 0, "a run that stayed up is not counted as a bounce")

    print("== a probe that keeps falling straight back stops the loop ==")
    sup, con = drive(["dash"] * 8, clock_step=5.0, max_bounces=3)
    check(sup.stopped_reason is not None, "supervisor stopped itself")
    check("without staying up" in (sup.stopped_reason or ""),
          "and says why: it was bouncing, not progressing")
    check(len(con.launches) <= 3, f"it did not keep launching ({len(con.launches)})")

    print("== a short unreachable gap is treated as a reboot, not a wedge ==")
    sup, con = drive(["running", "unreachable", "unreachable", "dash"],
                     clock_step=10.0)
    check(sup.stopped_reason is None, "did not cry wedge during a reboot")
    check(len(con.launches) == 1, "relaunched once the dashboard came back")

    print("== a console that stays dark is reported, never power-cycled ==")
    sup, con = drive(["unreachable"] * 40, clock_step=10.0,
                     unreachable_alert_s=120.0)
    check(sup.stopped_reason is not None, "supervisor stopped")
    check("power button" in (sup.stopped_reason or ""),
          "and says plainly that it needs hands")
    check("AutoTurnOff" in (sup.stopped_reason or ""),
          "and does not assert a wedge -- an idle console powers itself off")
    # The RETRACTION, checked as an absence. The two checks above pass just as
    # happily with the old claim still in the message: an edit that restores
    # "No ICMP means the processor is gone" alongside the AutoTurnOff sentence
    # keeps this suite green, and the false diagnosis is back. run_tests.sh
    # mutates the message to put that wording back, so this row is itself
    # proven to fire.
    check("processor is gone" not in (sup.stopped_reason or ""),
          "and never claims the processor is gone -- ICMP cannot show that")
    check(con.power_cycles == 0, "it never attempted a power cycle itself")
    check(con.launches == [], "and never tried to launch into a dark console")

    print()
    if fails:
        print("%d check(s) failed" % len(fails))
        return 1
    print("supervisor suite OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
