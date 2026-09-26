#!/usr/bin/env python3
"""Run SEVERAL pgraph tests of one suite, in suite order, on this worktree's
desktop build (dc_build.sh), with HAKUX_RING_LOG set so pgraph.c prints the
ring phase of every draw.

    dc_run.py <tag> 'Specular' ControlFlags_FF ControlFlags_VS [--iso ISO]

desktop_channel.sh run builds a ONE-test disc. The #53 ring's phase at a
program draw depends on everything since the last fixed-function lit vertex,
which is in the previous test, so the pricing needs the FF test and the VS
test on one disc, adjacent, as they ran in the golden session.

Writes build-linux/ring53runs/<tag>/{run.log,out/}. Prints RUN_EXIT, the
renderer line, the progress log and the RING53 lines.
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TESTING = os.path.join(TREE, "docs", "testing")
BIN = os.path.join(TREE, "build-linux", "qemu-system-i386")
X1 = "/home/justin/hakuX/hakux-backup/x1box"
PREFIX = "/home/justin/hakux-work/desktop/deps/prefix"


def main():
    args = sys.argv[1:]
    iso_base = "/home/justin/nxdk_pgraph_tests_xiso.iso"
    if "--iso" in args:
        i = args.index("--iso")
        iso_base = args[i + 1]
        del args[i:i + 2]
    if "--methods" in args:  # also trace every weighed method (RING53M)
        args.remove("--methods")
        os.environ["HAKUX_RING_LOG"] = "2"
    tag, suite, tests = args[0], args[1], args[2:]
    rundir = os.path.join(TREE, "build-linux", "ring53runs", tag)
    shutil.rmtree(rundir, ignore_errors=True)
    os.makedirs(os.path.join(rundir, "disc"))
    shutil.copy(os.path.join(X1, "hdd.img"), os.path.join(rundir, "hdd.img"))
    shutil.copy(os.path.join(X1, "eeprom.bin"), os.path.join(rundir, "eeprom.bin"))

    guest = "r53" + tag[:5]
    cfg = {
        "settings": {
            "enable_progress_log": True, "disable_autorun": False,
            "enable_autorun_immediately": True, "enable_shutdown_on_completion": True,
            "enable_pgraph_region_diff": False, "skip_tests_by_default": True,
            "delay_milliseconds_between_tests": 0, "delay_milliseconds_before_exit": 4000,
            "network": {"enable": False, "config_automatic": False, "config_dhcp": False,
                        "static_ip": "", "static_netmask": "", "static_gateway": "",
                        "static_dns_1": "", "static_dns_2": "",
                        "ftp": {"ftp_ip": "", "ftp_port": 21, "ftp_user": "xbox",
                                "ftp_password": "xbox", "ftp_timeout_milliseconds": 10000}},
            "sharding": {"index": 0, "count": 0},
            "output_directory_path": "e:/" + guest,
        },
        "test_suites": {suite: dict({"skipped": False},
                                    **{t: {"skipped": False} for t in tests})},
    }
    cfg_path = os.path.join(rundir, "disc", "cfg.json")
    iso = os.path.join(rundir, "disc", "iso.iso")
    json.dump(cfg, open(cfg_path, "w"), indent=2)
    r = subprocess.run([sys.executable, os.path.join(TESTING, "make_test_iso.py"),
                        iso_base, "-o", iso, "--config", cfg_path],
                       capture_output=True, text=True)
    if r.returncode:
        print("ISO FAILED", r.stderr[-400:] or r.stdout[-400:])
        return 1

    xdg = os.path.join(rundir, "xdg")
    os.makedirs(os.path.join(xdg, "xemu", "xemu"))
    open(os.path.join(xdg, "xemu", "xemu", "xemu.toml"), "w").write(f"""[general]
show_welcome = false
skip_boot_anim = true

[display]
renderer = 'OPENGL'

[display.quality]
surface_scale = 1

[net]
enable = false

[sys.files]
bootrom_path = '{X1}/mcpx.bin'
flashrom_path = '{X1}/flash.bin'
eeprom_path = '{rundir}/eeprom.bin'
hdd_path = '{rundir}/hdd.img'
dvd_path = '{iso}'
""")
    env = dict(os.environ, XDG_DATA_HOME=xdg, SDL_VIDEODRIVER="offscreen",
               SDL_AUDIODRIVER="dummy",
               HAKUX_RING_LOG=os.environ.get("HAKUX_RING_LOG", "1"))
    ma = subprocess.run(["gcc", "-print-multiarch"], capture_output=True, text=True).stdout.strip() \
        or "x86_64-linux-gnu"
    env["LD_LIBRARY_PATH"] = f"{PREFIX}/usr/lib/{ma}:{PREFIX}/usr/lib"
    with open(os.path.join(rundir, "run.log"), "w") as log:
        rc = subprocess.run(["timeout", "-k", "5", "420", BIN, "-machine", "xbox",
                             "-display", "none"], env=env, stdout=log,
                            stderr=subprocess.STDOUT).returncode
    print("RUN_EXIT=%d" % rc)
    text = open(os.path.join(rundir, "run.log"), errors="replace").read()
    for line in text.splitlines():
        if line.startswith("nv2a: renderer:"):
            print(line)
            break
    subprocess.run([sys.executable, os.path.join(TESTING, "extract_results.py"),
                    os.path.join(rundir, "hdd.img"), "-o", os.path.join(rundir, "out"),
                    "-d", guest], capture_output=True)
    plog = os.path.join(rundir, "out", "pgraph_progress_log.txt")
    print(open(plog).read() if os.path.exists(plog) else "NO PROGRESS LOG")
    ring = [l for l in text.splitlines() if l.startswith("RING53")]
    open(os.path.join(rundir, "ring.log"), "w").write("\n".join(ring) + "\n")
    print("RING53 lines: %d (ring.log)" % len(ring))
    for f in sorted(os.listdir(os.path.join(rundir, "out"))) if os.path.isdir(
            os.path.join(rundir, "out")) else []:
        print("  ", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
