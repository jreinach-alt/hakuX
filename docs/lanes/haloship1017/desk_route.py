#!/usr/bin/env python3
"""Desktop Halo run along a kept route (#1039). One run, one output dir.

usage: desk_route.py OUT --total S [--route FILE] [--gate NAME ...]
                     [--every S --cine S] [--at-mark SPEC] [--zrep] [ENV=V ...]

Runs build-linux/qemu-system-i386 with build-linux/run/xemu.toml (keyboard on
port 1, the Nova titles disk copy as the HDD) and follows the route file:
`wait N`, `press BTN`, `shot NAME`, `mark NAME`, `repeat forever { ... }`.
A press writes "<BTN>" to the HAKUX_PAD_FILE (ui/xemu-input.c), held 300 ms.
A shot arms a one-frame frame dump (marker "1,images") and moves its files to
OUT/shots/NAME.*; a `--gate NAME` shot then waits for OUT/go.NAME before the
route goes on, so a menu is seen before it is pressed through.

After `mark`: with --at-mark SPEC, a frame dump SPEC is armed at the mark and
its files go to OUT/dump.* when it closes; otherwise the repeat block runs, or
with --every S, a shot every S seconds for --cine S seconds. The run ends at
--total S (timeout -s TERM) or after the post-mark work.

The fast paths are set as the app sets them by default (MainActivity
FASTPATHS_VARS, SURFGPU=1; GPL is the C default); ENV=V arguments override.
Every step goes to OUT/route.log with seconds since start and since the mark.
"""
import glob
import os
import shutil
import subprocess
import sys
import time

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
B = os.path.join(WT, "build-linux")
NX = "/home/justin/.local/nxdk-tools"
ROUTE = os.path.join(WT, "docs/lanes/halo1016/routes/halo-cinematic.route")
FAST = ["HAKUX_REPORT_ASYNC", "HAKUX_TEXSCAN", "HAKUX_DRAWREC",
        "HAKUX_UNI_BULK", "HAKUX_UNI_UBERCACHE", "HAKUX_UNI_FOGCACHE",
        "HAKUX_POSTED_PUT", "HAKUX_LOCKFREE_WAKE"]


def parse_route(path):
    """A flat list of (op, arg); a repeat block becomes ('repeat', [steps])."""
    steps, stack = [], []
    for raw in open(path):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("repeat"):
            stack.append(steps)
            steps = []
            continue
        if line == "}":
            block, steps = steps, stack.pop()
            steps.append(("repeat", block))
            continue
        op, _, arg = line.partition(" ")
        steps.append((op, arg.strip()))
    return steps


class Run:
    def __init__(self, out, total, gates, extra):
        self.out = out
        self.dump = os.path.join(out, "dumpdir")
        self.pad = os.path.join(out, "pad")
        os.makedirs(self.dump, exist_ok=True)
        os.makedirs(os.path.join(out, "shots"), exist_ok=True)
        self.gates = set(gates)
        self.log = open(os.path.join(out, "route.log"), "a", buffering=1)
        self.t0 = time.time()
        self.tmark = None
        self.nshot = 0
        env = dict(os.environ)
        env.update({
            "LD_LIBRARY_PATH": f"{NX}/root/usr/lib/x86_64-linux-gnu:"
                               f"{NX}/root/lib/x86_64-linux-gnu",
            "XEMU_FRAME_DUMP_DIR": self.dump,
            "HAKUX_PAD_FILE": self.pad,
            "VK_ICD_FILENAMES": "/usr/share/vulkan/icd.d/lvp_icd.json",
            "SDL_VIDEODRIVER": "wayland",
            "XDG_RUNTIME_DIR": "/mnt/wslg/runtime-dir",
            "WAYLAND_DISPLAY": "wayland-0",
            "SDL_AUDIODRIVER": "dummy",
            "HAKUX_SURFGPU": "1",
        })
        for v in FAST:
            env[v] = "1"
        env.update(extra)
        self.say("env " + " ".join(f"{k}={env[k]}" for k in sorted(env)
                                   if k.startswith(("HAKUX_", "XEMU_"))))
        self.qlog = open(os.path.join(out, "qemu.log"), "w")
        self.p = subprocess.Popen(
            ["timeout", "-s", "TERM", str(total),
             os.path.join(B, "qemu-system-i386"), "-config_path",
             os.path.join(B, "run", "xemu.toml"), "-display", "none"],
            env=env, stdout=self.qlog, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, cwd=out)
        self.say(f"qemu pid {self.p.pid}")

    def say(self, msg):
        now = time.time()
        since = f"{now - self.tmark:8.1f}" if self.tmark else "       -"
        self.log.write(f"{now - self.t0:8.1f} {since} {msg}\n")

    def alive(self):
        return self.p.poll() is None

    def wait(self, s):
        end = time.time() + s
        while time.time() < end and self.alive():
            time.sleep(min(0.2, max(0, end - time.time())))

    def press(self, btn, ms=300):
        tmp = self.pad + ".tmp"
        with open(tmp, "w") as f:
            f.write(f"{btn} {ms}\n")
        os.rename(tmp, self.pad)
        self.say(f"press {btn} {ms}")
        self.wait(ms / 1000.0 + 0.2)

    def arm(self, spec):
        tmp = os.path.join(self.dump, "frame_dump.tmp")
        with open(tmp, "w") as f:
            f.write(spec + "\n")
        os.rename(tmp, os.path.join(self.dump, "frame_dump.on"))

    def collect(self, prefix, timeout):
        """Wait for the armed dump's json to close; move its files out."""
        end = time.time() + timeout
        done = False
        while time.time() < end and self.alive():
            for j in glob.glob(os.path.join(self.dump, "framedump_*.json")):
                try:
                    with open(j, "rb") as f:
                        f.seek(max(0, os.path.getsize(j) - 4096))
                        if b'"t":"end"' in f.read():
                            done = True
                except OSError:
                    pass
            if done:
                break
            time.sleep(0.3)
        time.sleep(0.5)
        moved = []
        for f in sorted(glob.glob(os.path.join(self.dump, "framedump_*"))):
            dst = f"{prefix}.{os.path.basename(f)}"
            shutil.move(f, dst)
            moved.append(os.path.basename(dst))
        return done, moved

    def shot(self, name):
        self.nshot += 1
        tag = f"{self.nshot:03d}_{name}"
        self.arm("1,images")
        done, moved = self.collect(os.path.join(self.out, "shots", tag), 20)
        self.say(f"shot {tag} {'ok' if done else 'TIMEOUT'} {len(moved)} files")
        if name in self.gates:
            go = os.path.join(self.out, f"go.{name}")
            self.say(f"GATE {name}: waiting for {go}")
            while not os.path.exists(go) and self.alive():
                time.sleep(0.5)
            self.say(f"gate {name} open")

    def steps(self, steps, args):
        for op, arg in steps:
            if not self.alive():
                return
            if op == "wait":
                self.wait(float(arg))
            elif op == "press":
                self.press(arg.split()[0])
            elif op == "shot":
                self.shot(arg.split()[0])
            elif op == "mark":
                self.tmark = time.time()
                self.say(f"mark {arg}")
                self.after_mark(args)
                return
            elif op == "repeat":
                self.repeat = arg

    def after_mark(self, args):
        if args["at_mark"]:
            self.arm(args["at_mark"])
            self.say(f"armed {args['at_mark']}")
            done, moved = self.collect(os.path.join(self.out, "dump"),
                                       args["total"])
            self.say(f"dump {'closed' if done else 'NOT closed'} "
                     f"{len(moved)} files")
        elif args["every"]:
            end = time.time() + args["cine"]
            while time.time() < end and self.alive():
                t = time.time()
                self.shot("cine")
                self.wait(max(0, args["every"] - (time.time() - t)))
        else:
            while self.alive():
                self.steps(self.repeat, args)

    def finish(self):
        if self.alive():
            self.say("route done: stopping qemu")
            self.p.terminate()
        try:
            self.p.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self.p.kill()
            self.p.wait()
        left = sorted(glob.glob(os.path.join(self.dump, "framedump_*")))
        for f in left:
            shutil.move(f, os.path.join(self.out, "left." + os.path.basename(f)))
        self.say(f"DONE exit {self.p.returncode} left {len(left)} files")


def main():
    a = sys.argv[1:]
    out = a.pop(0)
    args = {"total": 900, "route": ROUTE, "gates": [], "every": 0, "cine": 0,
            "at_mark": None}
    extra = {}
    while a:
        k = a.pop(0)
        if k == "--total":
            args["total"] = int(a.pop(0))
        elif k == "--route":
            args["route"] = a.pop(0)
        elif k == "--gate":
            args["gates"].append(a.pop(0))
        elif k == "--every":
            args["every"] = float(a.pop(0))
        elif k == "--cine":
            args["cine"] = float(a.pop(0))
        elif k == "--at-mark":
            args["at_mark"] = a.pop(0)
        elif k == "--zrep":
            extra["HAKUX_ZREP"] = os.path.join(out, "zrep.txt")
        elif "=" in k:
            key, val = k.split("=", 1)
            extra[key] = val
        else:
            sys.exit(f"unknown argument {k}")
    os.makedirs(out, exist_ok=True)
    steps = parse_route(args["route"])
    r = Run(out, args["total"], args["gates"], extra)
    r.repeat = next((s for op, s in steps if op == "repeat"), [])
    try:
        r.steps(steps, args)
    finally:
        r.finish()


if __name__ == "__main__":
    main()
