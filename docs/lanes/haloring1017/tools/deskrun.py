"""A desktop (lavapipe) Halo menu run with a gd frame dump and the guest RAM it was drawn from (#939).

usage: deskrun.py QEMU RUNDIR OUTDIR AFTER_S FRAMES TOTAL_S RAM_AT_S [images|noimages] [ENV=V ...]

RUNDIR holds this lane's own xemu.toml, hdd.qcow2 and eeprom.bin (copies; never
another lane's). The frame dump (XEMU_FRAME_DUMP=FRAMES,gd,...,afterAFTER_S) goes
to OUTDIR/dump. At RAM_AT_S seconds, inside the dump window, the HMP monitor's
pmemsave writes all 64 MB of guest RAM to OUTDIR/ram.bin: the ring's vertex
records and strips are static, so one image serves every frame of the dump.

The environment is the release app's defaults (HAKUX_SURFGPU and the fast paths),
so a desktop result is about the build players run; ENV=V arguments override.
"""
import glob
import os
import socket
import subprocess
import sys
import time

NX = "/home/justin/.local/nxdk-tools"
RELEASE_ENV = {k: "1" for k in (
    "HAKUX_SURFGPU", "HAKUX_REPORT_ASYNC", "HAKUX_TEXSCAN", "HAKUX_DRAWREC", "HAKUX_UNI_BULK",
    "HAKUX_UNI_UBERCACHE", "HAKUX_UNI_FOGCACHE", "HAKUX_POSTED_PUT", "HAKUX_LOCKFREE_WAKE")}

qemu, rundir, out = sys.argv[1], sys.argv[2], sys.argv[3]
after, frames, total, ram_at = int(sys.argv[4]), int(sys.argv[5]), float(sys.argv[6]), float(sys.argv[7])
rest = sys.argv[8:]
images = "images"
if rest and rest[0] in ("images", "noimages"):
    images = rest.pop(0)
extra = dict(a.split("=", 1) for a in rest)

dump = os.path.join(out, "dump")
os.makedirs(dump, exist_ok=True)
sock = os.path.join(out, "mon.sock")
if os.path.exists(sock):
    os.unlink(sock)
env = dict(os.environ)
env.update(RELEASE_ENV)
env.update({
    "LD_LIBRARY_PATH": f"{NX}/root/usr/lib/x86_64-linux-gnu:{NX}/root/lib/x86_64-linux-gnu",
    "XEMU_FRAME_DUMP": f"{frames},gd,{images},after{after},cap2000",
    "XEMU_FRAME_DUMP_DIR": dump,
    "VK_ICD_FILENAMES": "/usr/share/vulkan/icd.d/lvp_icd.json",
    "SDL_VIDEODRIVER": "wayland", "XDG_RUNTIME_DIR": "/mnt/wslg/runtime-dir",
    "WAYLAND_DISPLAY": "wayland-0", "SDL_AUDIODRIVER": "dummy",
})
env.update(extra)
with open(os.path.join(out, "env.txt"), "w") as f:
    for k in sorted(set(RELEASE_ENV) | set(extra) | {"XEMU_FRAME_DUMP"}):
        f.write(f"{k}={env[k]}\n")
    f.write(f"qemu={qemu}\n")

log = open(os.path.join(out, "qemu.log"), "w")
t0 = time.time()
p = subprocess.Popen([qemu, "-config_path", os.path.join(rundir, "xemu.toml"), "-display", "none",
                      "-monitor", f"unix:{sock},server,nowait"],
                     env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
try:
    while time.time() - t0 < ram_at and p.poll() is None:
        time.sleep(0.5)
    if p.poll() is None:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(sock)
        s.settimeout(10)
        s.sendall(f'pmemsave 0 0x4000000 "{out}/ram.bin"\n'.encode())
        time.sleep(3)
        print(f"pmemsave at +{time.time() - t0:.1f} s", flush=True)
    while time.time() - t0 < total and p.poll() is None:
        time.sleep(1)
finally:
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(30)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
n = len(glob.glob(os.path.join(dump, "*")))
print(f"DONE exit {p.returncode} in {time.time() - t0:.0f} s, {n} dump files", flush=True)
