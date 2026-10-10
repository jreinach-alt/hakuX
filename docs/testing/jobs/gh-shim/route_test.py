#!/usr/bin/env python3
"""route_test.py -- offline checks of route.sh's phase 3 (no systemd, no live units).

Runs route.sh against a temporary units directory (FORGE_UNITS_DIR), so nothing
under ~/.config/systemd is touched. Checks:
  - `on phase3` writes one drop-in per phase 3 unit, and no phase 1 or 2 unit gets one;
  - each phase 3 drop-in puts the shim first on PATH and sets FORGE_USER, and
    sets no HAKUX_FORGE (that switch is phase 2's dry-run gate);
  - hakux-hostops runs as `hostops`; the others as the default `jobs`;
  - hakux-cloud and hakux-forge* never get one (cloud is disabled; the forge is not a client);
  - hakux-pm@ gets its drop-in on the template directory, so every instance inherits it;
  - `off phase3` removes every one of them.
Exit 0 when every check passes. Run: python3 docs/testing/jobs/gh-shim/route_test.py
"""
import os, pathlib, re, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROUTE = HERE / "route.sh"
PHASE3 = re.search(r'^PHASE3="([^"]+)"', ROUTE.read_text(), re.M).group(1).split()
PHASE12 = re.findall(r'^PHASE[12]="([^"]+)"', ROUTE.read_text(), re.M)
PHASE12 = " ".join(PHASE12).split()
fails = []
passes = 0


def check(name, ok, detail=""):
    global passes
    if ok:
        passes += 1
        print("ok   " + name)
    else:
        fails.append(name)
        print("FAIL " + name + (": " + str(detail) if detail else ""))


def route(units, *args):
    env = dict(os.environ, FORGE_UNITS_DIR=str(units))
    p = subprocess.run(["bash", str(ROUTE), *args], env=env, capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout, p.stderr


work = pathlib.Path(tempfile.mkdtemp(prefix="route-test-"))
units = work / "units"
units.mkdir()
try:
    rc, out, err = route(units, "on", "phase3")
    check("on phase3 exits 0", rc == 0, (rc, err))
    drops = {p.parent.name[: -len(".service.d")] if p.parent.name.endswith(".service.d") else p.parent.name
             for p in units.rglob("zz-forge-shim.conf")}
    expect = {u for u in PHASE3}
    check("one drop-in per phase 3 unit", drops == expect, sorted(expect ^ drops))
    check("phase 1 and 2 units get nothing from phase3", not (drops & set(PHASE12)), sorted(drops & set(PHASE12)))
    check("hakux-cloud is not routed", "hakux-cloud" not in drops)
    check("no hakux-forge* unit is routed", not any(d.startswith("hakux-forge") for d in drops))
    for u in sorted(expect):
        d = units / (u + ".service.d")   # hakux-pm@ -> hakux-pm@.service.d, the template's drop-in dir
        conf = (d / "zz-forge-shim.conf").read_text()
        env_lines = [l for l in conf.splitlines() if l.startswith("Environment=")]
        check(u + " PATH starts with the shim",
              any(l.startswith("Environment=PATH=") and "/forge/shim/bin:" in l for l in env_lines), env_lines[:1])
        check(u + " sets no HAKUX_FORGE", not any(l.startswith("Environment=HAKUX_FORGE") for l in env_lines), env_lines)
        who = "hostops" if u == "hakux-hostops" else "jobs"
        check(u + " FORGE_USER=" + who, f"Environment=FORGE_USER={who}" in env_lines, env_lines)
    rc, out, err = route(units, "on", "hakux-hostops")
    check("on <unit> accepts a phase 3 unit by name", rc == 0 and "routed hakux-hostops" in out, (rc, out, err))
    rc, out, err = route(units, "on", "hakux-cloud")
    check("on hakux-cloud is refused (unknown unit, exit 2)", rc == 2, (rc, err))
    rc, out, err = route(units, "off", "phase3")
    left = list(units.rglob("zz-forge-shim.conf"))
    check("off phase3 removes every phase 3 drop-in", rc == 0 and not left, [str(p) for p in left][:3])
finally:
    shutil.rmtree(work, ignore_errors=True)

print(f"\n{passes} passed, {len(fails)} failed" + (": " + ", ".join(fails) if fails else ""))
sys.exit(1 if fails else 0)
