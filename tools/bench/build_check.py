#!/usr/bin/env python3
"""Compile-check the host bench: aarch64 Android (NDK clang, -Werror) and the
build host (gcc), then run the host build's topology sampler for a few
seconds as a smoke test. The aarch64 binary is only built, not run -- lanes
cannot reach a handheld; the app runs the same code under HAKUX_HOSTBENCH."""
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "hostbench_main.c")


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    sys.stdout.write(r.stdout)
    sys.stdout.write(r.stderr)
    return r.returncode


def main():
    ccs = sorted(glob.glob(os.path.expanduser(
        "~/Android/Sdk/ndk/*/toolchains/llvm/prebuilt/linux-x86_64/bin/"
        "aarch64-linux-android26-clang")))
    rc = 0
    if ccs:
        rc |= run([ccs[-1], "-O2", "-Wall", "-Wextra", "-Werror",
                   "-Wno-unused-parameter", "-o", "/tmp/hostbench_a64", SRC,
                   "-llog"])
        print("aarch64:", "ok" if rc == 0 else "FAILED")
    else:
        print("aarch64: no NDK found, skipped")
    r2 = run(["gcc", "-O2", "-Wall", "-Werror", "-o", "/tmp/hostbench_host",
              SRC, "-lpthread"])
    print("host:", "ok" if r2 == 0 else "FAILED")
    rc |= r2
    if r2 == 0:
        env = dict(os.environ, HAKUX_TOPO="50,1", HAKUX_HOSTBENCH="1")
        try:
            subprocess.run(["/tmp/hostbench_host"], env=env, timeout=2.5)
        except subprocess.TimeoutExpired:
            pass
    return rc


if __name__ == "__main__":
    sys.exit(main())
