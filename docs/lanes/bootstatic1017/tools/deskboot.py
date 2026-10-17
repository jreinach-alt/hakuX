#!/usr/bin/env python3
"""Desktop boot of one disc with the [boot1045] present probe on (#1045), through the xemu window, not -display none.

usage: deskboot.py NAME TOTAL_S PROBE_S [--iso PATH] [--video offscreen|wayland] [ENV=V ...]

Writes to build-linux/runs/NAME (git-ignored): xemu.toml, a fresh copy of the goldens disk, qemu.log, and probe/
(boot1045_log.txt, boot1045_f*.ppm, boot1045_r*.bin). The window is SDL's offscreen driver (EGL, llvmpipe) by
default, so nothing shows on the owner's screen; Vulkan is lavapipe.

C: guard (brief): refuses to start with under 40 GB free on /mnt/c. After the run it lists the WSL crash dumps that
appeared while it ran, and deletes only those whose name carries this run's emulator pid.
"""
import os
import shutil
import subprocess
import sys
import time

WT = "/home/justin/hakux-work/wt/bootstatic1017"
B = WT + "/build-linux"
NX = "/home/justin/.local/nxdk-tools"
CRASH = "/mnt/c/Users/Justin/AppData/Local/Temp/wsl-crashes"
ISO = "/mnt/d/hakux-staging/xiso/41560017-Tony_Hawk_s_Pro_Skater_4.xiso.iso"
HDD = "/mnt/d/hakux-staging/hdd-goldens-nova.qcow2"
EEPROM = "/home/justin/hakux-work/wt/bp1017desk/run/eeprom.bin"


def free_c_gb():
    st = os.statvfs("/mnt/c")
    return st.f_bavail * st.f_frsize / 1e9


def main():
    a = sys.argv[1:]
    name, total, probe_s = a[0], int(a[1]), int(a[2])
    iso, video, extra = ISO, "offscreen", {}
    i = 3
    while i < len(a):
        if a[i] == "--iso":
            iso = a[i + 1]
            i += 2
            continue
        if a[i] == "--video":
            video = a[i + 1]
            i += 2
            continue
        k, v = a[i].split("=", 1)
        extra[k] = v
        i += 1

    gb = free_c_gb()
    print("C: free %.1f GB" % gb, flush=True)
    if gb < 40:
        print("REFUSED: under 40 GB free on C:", flush=True)
        return 3

    out = os.path.join(B, "runs", name)
    if os.path.exists(out):
        os.replace(out, out + ".old.%d" % int(time.time()))
    probe = os.path.join(out, "probe")
    os.makedirs(probe)
    hdd = os.path.join(out, "hdd.qcow2")
    shutil.copy2(HDD, hdd)
    shutil.copy2(EEPROM, os.path.join(out, "eeprom.bin"))
    toml = os.path.join(out, "xemu.toml")
    with open(toml, "w") as f:
        f.write(f"""[general]
show_welcome = false
skip_boot_anim = true

[display]
renderer = 'VULKAN'

[display.vulkan]
preferred_physical_device = 'llvmpipe (LLVM 20.1.2, 256 bits)'

[sys.files]
bootrom_path = '/home/justin/hakux-work/desktop/mcpx.bin'
flashrom_path = '/home/justin/hakux-work/desktop/bios.bin'
eeprom_path = '{out}/eeprom.bin'
hdd_path = '{hdd}'
dvd_path = '{iso}'
""")

    env = dict(os.environ)
    env.update({
        "LD_LIBRARY_PATH": f"{NX}/root/usr/lib/x86_64-linux-gnu:{NX}/root/lib/x86_64-linux-gnu",
        "VK_ICD_FILENAMES": "/usr/share/vulkan/icd.d/lvp_icd.json",
        "SDL_AUDIODRIVER": "dummy",
        "SDL_VIDEODRIVER": video,
        "HAKUX_BOOTPROBE": probe,
        "HAKUX_BOOTPROBE_SECS": str(probe_s),
    })
    if video == "wayland":
        env.update({"XDG_RUNTIME_DIR": "/mnt/wslg/runtime-dir", "WAYLAND_DISPLAY": "wayland-0"})
    env.pop("XEMU_FRAME_DUMP", None)
    env.update(extra)

    before = set(os.listdir(CRASH)) if os.path.isdir(CRASH) else set()
    log = open(os.path.join(out, "qemu.log"), "w")
    t0 = time.time()
    p = subprocess.Popen([f"{B}/qemu-system-i386", "-config_path", toml], env=env, stdout=log,
                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    print("pid %d, iso %s, video %s, total %d s, probe %d s" % (p.pid, os.path.basename(iso), video, total, probe_s),
          flush=True)
    try:
        rc = p.wait(timeout=total)
    except subprocess.TimeoutExpired:
        p.terminate()
        try:
            rc = p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            p.kill()
            rc = p.wait()
        rc = "timeout (%s)" % rc
    el = time.time() - t0
    log.close()
    time.sleep(2)
    after = set(os.listdir(CRASH)) if os.path.isdir(CRASH) else set()
    new = sorted(after - before)
    for f in new:
        if str(p.pid) in f:
            os.remove(os.path.join(CRASH, f))
            print("crash dump of this run deleted: %s" % f, flush=True)
        else:
            print("new crash dump NOT this run's pid, left: %s" % f, flush=True)
    print("exit %s after %.0f s; C: free %.1f GB" % (rc, el, free_c_gb()), flush=True)
    n_f = sum(1 for f in os.listdir(probe) if f.startswith("boot1045_f"))
    n_r = sum(1 for f in os.listdir(probe) if f.startswith("boot1045_r"))
    print("probe: %d frames, %d ram dumps -> %s" % (n_f, n_r, probe), flush=True)
    with open(os.path.join(out, "qemu.log"), errors="replace") as f:
        for line in f:
            if "[boot1045]" in line and ("armed" in line or "done" in line or "off:" in line):
                print(line.rstrip(), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
