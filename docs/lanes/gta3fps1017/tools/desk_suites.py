#!/usr/bin/env python3
"""Desktop pgraph suite run, one arm (#1049): R1 on or off by env.

usage: desk_suites.py OUT --disc ISO [--total S] [ENV=V ...]

Runs build-linux/qemu-system-i386 headless on lavapipe with a fresh copy of
the blank desktop HDD (/home/justin/hakux-work/desktop/hdd.qcow2) and the
given pgraph disc (make_test_iso.py, --shutdown-on-completion
--progress-log), then extracts e:\\nxdk_pgraph_tests to OUT/results. qemu's
output goes to OUT/qemu.log with seconds since start: R1's lines
("[s2tdrain] first skip" with R1 on, "[s2tdrain] on" with HAKUX_S2T_DRAIN=1)
are read there. The fast paths are set as the app sets them by default.
Refuses to start under 20 GB free on C:.
"""
import os
import shutil
import subprocess
import sys
import time

WT = os.path.abspath(os.path.join(os.path.dirname(__file__), *[".."] * 4))
B = os.path.join(WT, "build-linux")
NX = "/home/justin/.local/nxdk-tools"
DESK = "/home/justin/hakux-work/desktop"
CRASH = "/mnt/c/Users/Justin/AppData/Local/Temp/wsl-crashes"
# A qemu segfault writes a ~7.8 GB dump to C:; 20 GB leaves room for two.
GUARD_GB = 20
FAST = ["HAKUX_REPORT_ASYNC", "HAKUX_TEXSCAN", "HAKUX_DRAWREC",
        "HAKUX_UNI_BULK", "HAKUX_UNI_UBERCACHE", "HAKUX_UNI_FOGCACHE",
        "HAKUX_POSTED_PUT", "HAKUX_LOCKFREE_WAKE"]
TOML = """[general]
show_welcome = false
skip_boot_anim = true

[display]
renderer = 'VULKAN'

[display.vulkan]
preferred_physical_device = 'llvmpipe (LLVM 20.1.2, 256 bits)'

[sys.files]
bootrom_path = '{desk}/mcpx.bin'
flashrom_path = '{desk}/bios.bin'
eeprom_path = '{out}/eeprom.bin'
hdd_path = '{out}/hdd.qcow2'
dvd_path = '{disc}'
"""


def crash_files():
    try:
        return set(os.listdir(CRASH))
    except OSError:
        return set()


def main():
    a = sys.argv[1:]
    out = os.path.abspath(a.pop(0))
    disc, total, extra = None, 1200, {}
    while a:
        k = a.pop(0)
        if k == "--disc":
            disc = os.path.abspath(a.pop(0))
        elif k == "--total":
            total = int(a.pop(0))
        elif "=" in k:
            key, val = k.split("=", 1)
            extra[key] = val
        else:
            sys.exit(f"unknown argument {k}")
    if not disc:
        sys.exit("--disc is required")
    st = shutil.disk_usage("/mnt/c")
    if st.free < GUARD_GB * 2**30:
        sys.exit(f"C: has {st.free / 2**30:.1f} GB free, under {GUARD_GB}: "
                 "not starting")
    os.makedirs(out)
    shutil.copy2(os.path.join(DESK, "hdd.qcow2"), os.path.join(out, "hdd.qcow2"))
    shutil.copy2(os.path.join(B, "run", "eeprom.bin"),
                 os.path.join(out, "eeprom.bin"))
    with open(os.path.join(out, "xemu.toml"), "w") as f:
        f.write(TOML.format(desk=DESK, out=out, disc=disc))
    env = dict(os.environ)
    env.update({
        "LD_LIBRARY_PATH": f"{NX}/root/usr/lib/x86_64-linux-gnu:"
                           f"{NX}/root/lib/x86_64-linux-gnu",
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
    before = crash_files()
    t0 = time.time()
    with open(os.path.join(out, "qemu.log"), "w", buffering=1) as log:
        log.write("    0.0 env " + " ".join(
            f"{k}={env[k]}" for k in sorted(env) if k.startswith("HAKUX_")) + "\n")
        p = subprocess.Popen(
            ["timeout", "-s", "TERM", str(total),
             os.path.join(B, "qemu-system-i386"), "-config_path",
             os.path.join(out, "xemu.toml"), "-display", "none"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, cwd=out)
        for raw in p.stdout:
            log.write(f"{time.time() - t0:8.1f} "
                      f"{raw.decode('utf-8', 'replace').rstrip()}\n")
        rc = p.wait()
        log.write(f"{time.time() - t0:8.1f} EXIT {rc}\n")
    new = sorted(crash_files() - before)
    x = subprocess.call([sys.executable,
                         os.path.join(WT, "docs/testing/extract_results.py"),
                         os.path.join(out, "hdd.qcow2"), "-o",
                         os.path.join(out, "results")])
    print(f"SUITES_EXIT={rc} extract={x} wall={time.time() - t0:.0f}s "
          f"new crash dumps: {new if new else 'none'}", flush=True)


if __name__ == "__main__":
    main()
