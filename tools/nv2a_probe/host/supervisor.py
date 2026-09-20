#!/usr/bin/env python3
"""Keep the probe running on the console without anybody standing over it.

The console has exactly three states worth distinguishing, and they are
distinguishable without guessing, because the dashboard and the probe cannot
both be running:

    AT_DASHBOARD   FTP answers  -> UnleashX has the console, the probe does not
    RUNNING        ICMP but no FTP -> an XBE has the console; that is the probe
    UNREACHABLE    no ICMP      -> booting, off, or wedged

UnleashX's FTP server implements a SITE verb family, so AT_DASHBOARD is
actionable: `SITE EXEC <path>` starts an XBE. That is what removes the human
from the loop -- every soft reset, watchdog reset and escape-hatch return lands
at the dashboard, and the dashboard can be told to start the probe again.

WHAT THIS DELIBERATELY WILL NOT DO. It never power-cycles, never writes to the
console's drive, and never issues a second launch while one is in flight. A
genuinely wedged console (no ICMP, CPU gone) cannot be recovered by any
software on this side, so the supervisor reports it and stops rather than
thrashing. Pretending otherwise would just hide the one case that still needs
hands.

BOUNCE PROTECTION. If a launched probe returns to the dashboard almost
immediately, launching it again produces a loop that looks like progress and
is not. After `--max-bounces` fast returns the supervisor stops and says so.
"""

from __future__ import annotations

import argparse
import enum
import subprocess
import sys
import time


class State(enum.Enum):
    AT_DASHBOARD = "at-dashboard"
    RUNNING = "running"
    UNREACHABLE = "unreachable"


class Console:
    """Talks to the real console. Swapped out wholesale by the tests."""

    def __init__(self, host: str, user: str = "xbox", password: str = "xbox"):
        self.host, self.user, self.password = host, user, password

    def ping(self, timeout: float = 2.0) -> bool:
        return subprocess.run(
            ["ping", "-c", "1", "-W", str(int(timeout)), self.host],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

    def ftp_up(self, timeout: float = 5.0) -> bool:
        import ftplib
        try:
            f = ftplib.FTP()
            f.connect(self.host, 21, timeout=timeout)
            f.login(self.user, self.password)
            try:
                f.quit()
            except Exception:
                f.close()
            return True
        except Exception:
            return False

    def site_exec(self, path: str, timeout: float = 10.0) -> str:
        """Ask the dashboard to launch an XBE. Returns the server's reply."""
        import ftplib
        f = ftplib.FTP()
        f.connect(self.host, 21, timeout=timeout)
        f.login(self.user, self.password)
        try:
            return f.sendcmd("SITE EXEC " + path)
        finally:
            try:
                f.quit()
            except Exception:
                f.close()


class Supervisor:
    def __init__(self, console, xbe_path: str, *, max_bounces: int = 3,
                 fast_return_s: float = 45.0, unreachable_alert_s: float = 180.0,
                 log=print):
        self.console = console
        self.xbe_path = xbe_path
        self.max_bounces = max_bounces
        self.fast_return_s = fast_return_s
        self.unreachable_alert_s = unreachable_alert_s
        self.log = log
        self.bounces = 0
        self.launches = 0
        self.last_launch: float | None = None
        self.unreachable_since: float | None = None
        self.stopped_reason: str | None = None

    # -- observation ----------------------------------------------------
    def observe(self, now: float | None = None) -> State:
        if self.console.ftp_up():
            return State.AT_DASHBOARD
        if self.console.ping():
            return State.RUNNING
        return State.UNREACHABLE

    # -- one decision ---------------------------------------------------
    def step(self, now: float) -> State:
        state = self.observe()

        if state is State.RUNNING:
            self.unreachable_since = None
            if self.last_launch is not None:
                # It launched and stayed up: that run counts as good.
                self.bounces = 0
            return state

        if state is State.UNREACHABLE:
            if self.unreachable_since is None:
                self.unreachable_since = now
                self.log("  unreachable -- could be a reboot; waiting")
            elif now - self.unreachable_since > self.unreachable_alert_s:
                self.stop("console unreachable for %ds. No ICMP means the "
                          "processor is gone, and nothing on this side can "
                          "recover that: it needs a power cycle."
                          % int(now - self.unreachable_since))
            return state

        # AT_DASHBOARD
        self.unreachable_since = None
        if (self.last_launch is not None
                and now - self.last_launch < self.fast_return_s):
            self.bounces += 1
            self.log("  probe returned to the dashboard after %.0fs (bounce %d/%d)"
                     % (now - self.last_launch, self.bounces, self.max_bounces))
            if self.bounces >= self.max_bounces:
                self.stop("the probe returned to the dashboard %d times in a "
                          "row without staying up. Relaunching again would "
                          "look like progress and would not be any."
                          % self.bounces)
                return state
        try:
            reply = self.console.site_exec(self.xbe_path)
            self.launches += 1
            self.last_launch = now
            self.log("  launched (%d): %s" % (self.launches, reply))
        except Exception as exc:
            self.log("  launch failed: %s" % exc)
        return state

    def stop(self, reason: str) -> None:
        self.stopped_reason = reason
        self.log("\n  STOPPING: %s" % reason)

    def run(self, interval: float = 10.0, sleep=time.sleep, clock=time.time,
            max_iterations: int | None = None) -> str | None:
        i = 0
        last = None
        while self.stopped_reason is None:
            if max_iterations is not None and i >= max_iterations:
                break
            now = clock()
            state = self.step(now)
            if state is not last:
                self.log("[%s] %s" % (time.strftime("%H:%M:%S"), state.value))
                last = state
            i += 1
            if self.stopped_reason is None:
                sleep(interval)
        return self.stopped_reason


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="192.168.50.1")
    ap.add_argument("--xbe", default="E:\\Apps\\NV2AProbe\\default.xbe")
    ap.add_argument("--interval", type=float, default=10.0)
    ap.add_argument("--max-bounces", type=int, default=3)
    ap.add_argument("--once", action="store_true",
                    help="observe and act once, then exit (for checking)")
    args = ap.parse_args()

    sup = Supervisor(Console(args.host), args.xbe, max_bounces=args.max_bounces)
    print("supervising %s, launching %s when the dashboard is up"
          % (args.host, args.xbe))
    print("a wedged console is REPORTED, never power-cycled -- that still needs hands")
    reason = sup.run(interval=args.interval,
                     max_iterations=1 if args.once else None)
    print("\nlaunches: %d, bounces: %d" % (sup.launches, sup.bounces))
    return 1 if reason else 0


if __name__ == "__main__":
    sys.exit(main())
