"""Desktop (lavapipe) Halo run with a frame dump (#1038), after x1port1012's deskgd.py.

usage: deskrun.py TOTAL_S OUTDIR SPEC [ENV=V ...] [-- QEMU_ARG ...]
  SPEC is XEMU_FRAME_DUMP verbatim, e.g. "8,images,rttmax16384,gd,after120,cap2400".
  Arguments after "--" go to qemu; one of them may be a "-config_path" replacing run/xemu.toml.
  A save-state load (the Nova's slot2.stream, QEVM body at byte 377, two pads on ports 1-2):
    deskrun.py 300 OUT SPEC -- -config_path run/xemu-load.toml
      -device usb-hub,port=1.3,ports=3 -device usb-xbox-gamepad,index=0,port=1.3.1,id=gamepad_0
      -device usb-hub,port=1.4,ports=3 -device usb-xbox-gamepad,index=1,port=1.4.1,id=gamepad_1
      -incoming "exec:tail -c +378 slot2.stream"
Refuses to start unless /mnt/c has at least 40 GB free (a crashing xemu leaves a ~7.8 GB dump
there). Prints the crash directory's new entries after the run; deleting them is by hand, by name.
"""
import glob, os, shutil, subprocess, sys, time

WT = "/home/justin/hakux-work/wt/haloshadow1017"
B = f"{WT}/build-linux"
NX = "/home/justin/.local/nxdk-tools"
CRASH = "/mnt/c/Users/Justin/AppData/Local/Temp/wsl-crashes"

total, out, spec = int(sys.argv[1]), sys.argv[2], sys.argv[3]
rest = sys.argv[4:]
qargs = rest[rest.index("--") + 1:] if "--" in rest else []
rest = rest[:rest.index("--")] if "--" in rest else rest
extra = dict(a.split("=", 1) for a in rest)
if "-config_path" not in qargs:
    qargs = ["-config_path", f"{B}/run/xemu.toml"] + qargs

st = os.statvfs("/mnt/c")
free_gb = st.f_bavail * st.f_frsize / 2**30
print(f"C: free {free_gb:.1f} GB", flush=True)
if free_gb < 40:
    print("REFUSED: under 40 GB free on C:", flush=True)
    sys.exit(3)
before = set(os.listdir(CRASH)) if os.path.isdir(CRASH) else set()

dump = os.path.join(B, "run", "dump")
os.makedirs(dump, exist_ok=True)
for f in glob.glob(os.path.join(dump, "*")):
    os.unlink(f)
env = dict(os.environ)
env.update({
    "LD_LIBRARY_PATH": f"{NX}/root/usr/lib/x86_64-linux-gnu:{NX}/root/lib/x86_64-linux-gnu",
    "XEMU_FRAME_DUMP": spec,
    "XEMU_FRAME_DUMP_DIR": dump,
    "VK_ICD_FILENAMES": "/usr/share/vulkan/icd.d/lvp_icd.json",
    "SDL_VIDEODRIVER": "wayland", "XDG_RUNTIME_DIR": "/mnt/wslg/runtime-dir",
    "WAYLAND_DISPLAY": "wayland-0", "SDL_AUDIODRIVER": "dummy",
})
env.update(extra)
os.makedirs(out, exist_ok=True)
log = open(os.path.join(out, "qemu.log"), "w")
t0 = time.time()
p = subprocess.Popen(["timeout", "-s", "TERM", str(total), f"{B}/qemu-system-i386",
                      "-display", "none"] + qargs,
                     env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
p.wait()
got = sorted(glob.glob(os.path.join(dump, "*")))
for f in got:
    shutil.move(f, os.path.join(out, os.path.basename(f)))
after = set(os.listdir(CRASH)) if os.path.isdir(CRASH) else set()
new = sorted(after - before)
print(f"DONE exit {p.returncode} in {time.time() - t0:.0f} s, {len(got)} files -> {out}", flush=True)
print(f"crash dir: {len(after)} entries, new: {new if new else 'none'}", flush=True)
