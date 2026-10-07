#!/usr/bin/env python3
"""Apply each call-site patch to a scratch copy and exercise it. No device, no
host state: a temp DISPATCH_DIR and a temp work root.

    python3 docs/lanes/dispatchgate1006/tools/verify_patches.py [--pathfind-tree W/wt/pathfind]

1. every patch applies (`git apply --check` against its own tree);
2. patched request.sh / hold.sh pass `bash -n`;
3. patched hold.sh `take`: shadow mode takes an ungated hold (and logs it), enforce
   mode refuses it with exit 3, and a host update-window tag is exempt;
4. patched title_verdict.py compiles and writes `failing_all`;
5. patched pathfind_selftest.py passes on patched pathfind.py, including the new
   `dispatchgate` leg.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
P = os.path.join(HERE, "..", "patches")
fails = []


def ok(name, cond, detail=""):
    print("%-5s %s %s" % ("PASS" if cond else "FAIL", name, detail))
    if not cond:
        fails.append(name)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def apply_to(tree, patch):
    r = run(["git", "apply", "--check", "--directory", "", os.path.abspath(os.path.join(P, patch))], cwd=tree) \
        if False else run(["git", "apply", "--check", os.path.abspath(os.path.join(P, patch))], cwd=tree)
    return r.returncode == 0, (r.stderr or r.stdout).strip()[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pathfind-tree", default="/home/justin/hakux-work/wt/pathfind")
    a = ap.parse_args()
    for patch, tree in (("request.sh.patch", REPO), ("hold.sh.patch", REPO), ("title_verdict.py.patch", REPO),
                        ("pathfind.py.patch", a.pathfind_tree), ("pathfind_selftest.py.patch", a.pathfind_tree)):
        good, why = apply_to(tree, patch)
        ok("applies: " + patch, good, why)

    tmp = tempfile.mkdtemp(prefix="dg-verify-")
    try:
        # scratch copy of docs/testing with the repo patches applied
        t = os.path.join(tmp, "repo")
        os.makedirs(t)
        shutil.copytree(os.path.join(REPO, "docs", "testing"), os.path.join(t, "docs", "testing"),
                        ignore=shutil.ignore_patterns("*.tsv", "run-*", "predictions", "golden_overrides"))
        run(["git", "init", "-q"], cwd=t)
        for patch in ("request.sh.patch", "hold.sh.patch", "title_verdict.py.patch"):
            r = run(["git", "apply", os.path.abspath(os.path.join(P, patch))], cwd=t)
            ok("applied in scratch: " + patch, r.returncode == 0, r.stderr.strip()[:200])
        for sh in ("docs/testing/request.sh", "docs/testing/jobs/hold.sh"):
            r = run(["bash", "-n", os.path.join(t, sh)])
            ok("bash -n " + sh, r.returncode == 0, r.stderr.strip()[:200])
        r = run([sys.executable, "-m", "py_compile", os.path.join(t, "docs/testing/title_verdict.py")])
        ok("py_compile title_verdict.py (patched)", r.returncode == 0, r.stderr.strip()[:200])
        src = open(os.path.join(t, "docs/testing/title_verdict.py")).read()
        ok("title_verdict.py writes failing_all", 'v["failing_all"]' in src)

        # hold.sh take through the gate, against a temp work root
        root = os.path.join(tmp, "work")
        D = os.path.join(root, "dispatch")
        os.makedirs(os.path.join(D, "hold"))
        os.makedirs(os.path.join(root, "pm"))
        hold = os.path.join(t, "docs/testing/jobs/hold.sh")
        env = dict(os.environ, DISPATCH_DIR=D)
        r = run(["bash", hold, "take", "nova", "lane.pathfind", "pathfind 54430001 one run"], env=env)
        logged = open(os.path.join(root, "pm", "dispatch-log.tsv")).read() if os.path.exists(
            os.path.join(root, "pm", "dispatch-log.tsv")) else ""
        ok("hold.sh take, shadow: ungated hold is taken and logged", r.returncode == 0 and "SHADOW-HOLD-UNGATED" in logged,
           "rc %d; %s" % (r.returncode, (r.stdout + r.stderr).strip().replace("\n", " | ")[:160]))
        run(["bash", hold, "release", "nova", "lane.pathfind"], env=env)
        with open(os.path.join(root, "pm", "dispatch-gate.mode"), "w") as f:
            f.write("enforce\n")
        r = run(["bash", hold, "take", "nova", "lane.pathfind", "pathfind 54430001 one run"], env=env)
        ok("hold.sh take, enforce: ungated hold refused (exit 3, no hold file)",
           r.returncode == 3 and not os.path.exists(os.path.join(D, "hold", "nova")),
           "rc %d; %s" % (r.returncode, r.stderr.strip().replace("\n", " | ")[:160]))
        r = run(["bash", hold, "take", "nova", "hostupd-4242", "host update window"], env=env)
        ok("hold.sh take, enforce: host update-window tag is exempt", r.returncode == 0,
           "rc %d" % r.returncode)
        run(["bash", hold, "release", "nova", "hostupd-4242"], env=env)

        # pathfind: a scratch copy of the pathfind tree's docs/testing with both patches applied
        pt = os.path.join(tmp, "pathfind")
        os.makedirs(pt)
        shutil.copytree(os.path.join(a.pathfind_tree, "docs", "testing"), os.path.join(pt, "docs", "testing"),
                        ignore=shutil.ignore_patterns("*.tsv", "run-*", "predictions", "golden_overrides", "paths"))
        shutil.copy(os.path.join(REPO, "docs/testing/dispatch_gate.py"), os.path.join(pt, "docs/testing"))
        shutil.copy(os.path.join(REPO, "docs/testing/title_registry.py"), os.path.join(pt, "docs/testing"))
        run(["git", "init", "-q"], cwd=pt)
        for patch in ("pathfind.py.patch", "pathfind_selftest.py.patch"):
            r = run(["git", "apply", os.path.abspath(os.path.join(P, patch))], cwd=pt)
            ok("applied in scratch: " + patch, r.returncode == 0, r.stderr.strip()[:200])
        r = run([sys.executable, os.path.join(pt, "docs/testing/titles/pathfind_selftest.py")],
                cwd=os.path.join(pt, "docs/testing/titles"), timeout=900)
        last = [l for l in r.stdout.splitlines() if "dispatchgate" in l or l.startswith("pathfind_selftest:")]
        ok("pathfind_selftest (patched), dispatchgate leg included",
           r.returncode == 0 and any("dispatchgate" in l for l in last),
           " | ".join(last)[:300] or (r.stdout + r.stderr)[-300:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nverify_patches: %s" % ("all pass" if not fails else "FAIL: " + ", ".join(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
