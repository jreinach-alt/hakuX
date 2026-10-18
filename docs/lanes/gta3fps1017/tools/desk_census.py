#!/usr/bin/env python3
"""Desktop GTA III census run (#1049): boot, an A-train to gameplay, a held window.

usage: desk_census.py OUT --total S [--first S] [--train N] [--gap S]
                      [--shot-every S] [ENV=V ...]

Runs build-linux/qemu-system-i386 (an NV2A_PERF_LOG build) with
build-linux/run/xemu.toml, headless on lavapipe. After --first seconds it
presses A --train times, --gap seconds apart (gta-3.route's A-train: A alone
skips the intros and starts a new game), then presses nothing until --total.
A shot (a one-frame dump, "1,images") is taken every --shot-every seconds
throughout and kept as OUT/shots/<t>.png, so each census window can be placed
against what was on screen.

Every line qemu prints goes to OUT/qemu.log prefixed with seconds since
start, which is what lines the 60-flip [s2c]/txw windows up with the shots.

The fast paths are set as the app sets them by default (MainActivity
FASTPATHS_VARS, SURFGPU=1), as haloship1017's desk_route.py does; ENV=V
arguments override. Refuses to start under 20 GB free on C: (a crash dump is
~7.8 GB) and lists any new crash dump at the end.
"""
import glob
import os
import shutil
import subprocess
import sys
import threading
import time

WT = os.path.abspath(os.path.join(os.path.dirname(__file__), *[".."] * 4))
B = os.path.join(WT, "build-linux")
NX = "/home/justin/.local/nxdk-tools"
CRASH = "/mnt/c/Users/Justin/AppData/Local/Temp/wsl-crashes"
# A qemu segfault writes a ~7.8 GB dump to C:; 20 GB leaves room for two.
GUARD_GB = 20
FAST = ["HAKUX_REPORT_ASYNC", "HAKUX_TEXSCAN", "HAKUX_DRAWREC",
        "HAKUX_UNI_BULK", "HAKUX_UNI_UBERCACHE", "HAKUX_UNI_FOGCACHE",
        "HAKUX_POSTED_PUT", "HAKUX_LOCKFREE_WAKE"]


def crash_files():
    try:
        return set(os.listdir(CRASH))
    except OSError:
        return set()


class Run:
    def __init__(self, out, total, extra):
        self.out = out
        self.dump = os.path.join(out, "dumpdir")
        self.pad = os.path.join(out, "pad")
        os.makedirs(self.dump, exist_ok=True)
        os.makedirs(os.path.join(out, "shots"), exist_ok=True)
        self.log = open(os.path.join(out, "census.log"), "a", buffering=1)
        self.t0 = time.time()
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
        self.qlog = open(os.path.join(out, "qemu.log"), "w", buffering=1)
        self.p = subprocess.Popen(
            ["timeout", "-s", "TERM", str(total),
             os.path.join(B, "qemu-system-i386"), "-config_path",
             os.path.join(B, "run", "xemu.toml"), "-display", "none"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, cwd=out)
        self.reader = threading.Thread(target=self.copy_log, daemon=True)
        self.reader.start()
        self.say(f"qemu pid {self.p.pid}")

    def copy_log(self):
        for raw in self.p.stdout:
            line = raw.decode("utf-8", "replace").rstrip("\n")
            self.qlog.write(f"{time.time() - self.t0:8.1f} {line}\n")

    def say(self, msg):
        self.log.write(f"{time.time() - self.t0:8.1f} {msg}\n")

    def alive(self):
        return self.p.poll() is None

    def press(self, btn, ms=300):
        tmp = self.pad + ".tmp"
        with open(tmp, "w") as f:
            f.write(f"{btn} {ms}\n")
        os.rename(tmp, self.pad)
        self.say(f"press {btn} {ms}")

    def shot(self):
        """Arm a one-frame dump; return (tag, ppm or None) once it closes."""
        t = time.time() - self.t0
        tag = f"{t:06.0f}"
        tmp = os.path.join(self.dump, "frame_dump.tmp")
        with open(tmp, "w") as f:
            f.write("1,images\n")
        os.rename(tmp, os.path.join(self.dump, "frame_dump.on"))
        end = time.time() + 20
        done = False
        while time.time() < end and self.alive() and not done:
            for j in glob.glob(os.path.join(self.dump, "framedump_*.jsonl")):
                try:
                    with open(j, "rb") as f:
                        f.seek(max(0, os.path.getsize(j) - 4096))
                        done = done or b'"t":"end"' in f.read()
                except OSError:
                    pass
            time.sleep(0.3)
        time.sleep(0.5)
        ppm = None
        for f in sorted(glob.glob(os.path.join(self.dump, "framedump_*"))):
            if f.endswith(".ppm") and ppm is None:
                ppm = f
            else:
                os.replace(f, os.path.join(self.out, "shots",
                                           f"{tag}.{os.path.basename(f)}"))
        png = None
        if ppm:
            from PIL import Image
            png = os.path.join(self.out, "shots", f"{tag}.png")
            Image.open(ppm).save(png)
            os.replace(ppm, os.path.join(self.out, "shots", f"{tag}.ppm"))
        self.say(f"shot {tag} {'ok' if done else 'TIMEOUT'} {png or 'no image'}")

    def finish(self):
        if self.alive():
            self.say("done: stopping qemu")
            self.p.terminate()
        try:
            self.p.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self.p.kill()
            self.p.wait()
        self.reader.join(timeout=10)
        self.say(f"DONE exit {self.p.returncode}")


def main():
    a = sys.argv[1:]
    out = a.pop(0)
    total, first, train, gap, every = 900, 60.0, 16, 6.0, 30.0
    extra = {}
    while a:
        k = a.pop(0)
        if k == "--total":
            total = int(a.pop(0))
        elif k == "--first":
            first = float(a.pop(0))
        elif k == "--train":
            train = int(a.pop(0))
        elif k == "--gap":
            gap = float(a.pop(0))
        elif k == "--shot-every":
            every = float(a.pop(0))
        elif "=" in k:
            key, val = k.split("=", 1)
            extra[key] = val
        else:
            sys.exit(f"unknown argument {k}")
    st = shutil.disk_usage("/mnt/c")
    if st.free < GUARD_GB * 2**30:
        sys.exit(f"C: has {st.free / 2**30:.1f} GB free, under {GUARD_GB}: "
                 "not starting")
    os.makedirs(out, exist_ok=True)
    before = crash_files()
    r = Run(out, total, extra)
    r.say(f"C: free {st.free / 2**30:.1f} GB; first {first} train {train} "
          f"gap {gap} shot-every {every} total {total}")
    presses = [first + i * gap for i in range(train)]
    next_shot = every
    try:
        while r.alive():
            t = time.time() - r.t0
            if presses and t >= presses[0]:
                presses.pop(0)
                r.press("A")
            elif t >= next_shot:
                r.shot()
                next_shot += every
            time.sleep(0.2)
    finally:
        r.finish()
        new = sorted(crash_files() - before)
        r.say(f"new crash dumps: {new if new else 'none'}")


if __name__ == "__main__":
    main()
