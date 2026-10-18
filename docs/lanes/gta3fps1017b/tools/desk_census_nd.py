#!/usr/bin/env python3
"""gta3fps1017's desk_census.py with qemu non-dumpable (#1049).

usage: desk_census_nd.py OUT [desk_census.py arguments]

desk_census.py refuses to start under 20 GB free on C: because a qemu
segfault pipes a ~7.8 GB dump to WSL's handler on C: (core_pattern
|/wsl-capture-crash; ulimit -c 0 does not stop it). With
/proc/sys/fs/suid_dumpable 0, exec of a binary the user cannot read makes the
process non-dumpable, and the kernel's do_coredump returns before the pipe:
no dump at all. So this wrapper requires build-linux/qemu-system-i386 to be
execute-only for the user (chmod 0311), drops the free-space guard, and after
the launch checks that qemu really is non-dumpable (its /proc/PID/environ is
owned by root); if not, it stops qemu and exits 3.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "gta3fps1017", "tools"))
import desk_census as dc  # noqa: E402

QEMU = os.path.join(dc.B, "qemu-system-i386")


def qemu_pid(timeout_pid):
    for _ in range(50):
        try:
            with open(f"/proc/{timeout_pid}/task/{timeout_pid}/children") as f:
                kids = f.read().split()
            if kids:
                return int(kids[0])
        except OSError:
            pass
        time.sleep(0.1)
    return None


def main():
    if os.access(QEMU, os.R_OK):
        sys.exit(f"{QEMU} is readable: chmod 0311 it first (non-dumpable)")
    with open("/proc/sys/fs/suid_dumpable") as f:
        if f.read().strip() != "0":
            sys.exit("fs.suid_dumpable is not 0: non-dumpable not assured")
    dc.GUARD_GB = 0
    start = dc.Run.__init__

    def init(self, *a, **k):
        start(self, *a, **k)
        pid = qemu_pid(self.p.pid)
        owner = None
        if pid:
            try:
                owner = os.stat(f"/proc/{pid}/environ").st_uid
            except OSError:
                pass
        self.say(f"nondump: qemu pid {pid} /proc owner uid {owner}")
        if owner != 0:
            self.say("nondump: qemu is dumpable, stopping")
            self.p.terminate()
            self.p.wait()
            sys.exit(3)

    dc.Run.__init__ = init
    dc.main()


if __name__ == "__main__":
    main()
