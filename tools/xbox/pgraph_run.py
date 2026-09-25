#!/usr/bin/env python3
"""Run an nxdk_pgraph_tests XBE on the project console and fetch what it wrote.

    tools/xbox/pgraph_run.py --xbe-dir DIR --config CFG.json --app NAME --out RUNDIR
                             [--host 192.168.50.1] [--timeout-min 20] [--check]

DIR holds `default.xbe` and the resource directories built beside it
(`build-xbe/src/xbe/xbe_file/`). CFG is the run's config; it is installed as
`nxdk_pgraph_tests_config.json` beside the XBE, which the console reads as
`d:\\nxdk_pgraph_tests_config.json`. NAME is the directory under `E:\\Apps\\`.
RUNDIR is local and receives the captures, the progress log, a copy of the
config and PROVENANCE.txt.

WHAT IT REFUSES, because the console cannot be power-cycled from here and a
wedged or powered-off console stays that way until someone presses the button:

  - to launch on anything but the DASHBOARD. FTP answering means UnleashX has
    the console; ICMP without FTP means an XBE already has it; neither means it
    is off, asleep or wedged. Only the first is a place to start from;
  - a config with `enable_shutdown_on_completion: true` (the console would
    power off with the log on its disk), `enable_progress_log: false` (the log
    is the only proof of completion) or networking on;
  - an `output_directory_path` that already exists on the console, so nothing
    stale can be fetched and read as this run's;
  - an app directory that already holds a different `default.xbe`; another
    run's install is never overwritten;
  - to run while `E:\\nxdk_pgraph_tests\\nxdk_pgraph_tests_config.json` exists:
    the XBE reads that path FIRST and it silently wins over the config beside
    it (docs/testing/handoff-on-hardware.md, section 3).

HOW IT KNOWS THE RUN FINISHED. Exactly one way: the console is back at the
dashboard and `pgraph_progress_log.txt` in the output directory contains
"Testing completed normally". A run's duration proves nothing (AGENTS.md: a
run cut off by a wait loop is not a completed run), and neither does a file's
presence. A launch that comes back to the dashboard without that line is a
failure and is NOT relaunched: bounce protection, as in
tools/nv2a_probe/host/supervisor.py, whose state model this reuses.

FTP: passive, and the server ignores LIST's path argument, so it always CWDs
first and lists bare (a recursive walk written the other way re-lists the root
and finds nothing).

--kind vsh runs nxdk_vsh_tests instead (branch hakux/completion-marker in
~/nxdk_vsh_tests). Its shutdown and autorun are COMPILE-TIME, so there is no
config to inspect: the runner reads the XBE's own bytes and refuses one that
lacks the reboot message (a shutdown build compiles it out), the autorun
entry, the completion line or the suite-list path. CFG is then a plain suite
list, installed as `vsh_tests.cnf` beside the XBE -- and it MUST be there
before launch, because a build that reads it ASSERTs inside the XBE when it
is missing; the upload's size check is what guarantees it. Output lands in
`E:\\Apps\\NAME\\nxdk_vsh_tests`, so NAME must be a fresh directory.

--check does every refusal test above and stops before touching anything.

Exit: 0 finished and fetched; 2 refused before launch; 3 launched but did not
finish (timeout, or back at the dashboard without the completion line);
4 the console stopped answering ping -- it needs hands.
"""
import argparse
import datetime
import ftplib
import hashlib
import io
import json
import os
import subprocess
import sys
import time

COMPLETED = "Testing completed normally"
LOG_NAME = "pgraph_progress_log.txt"
VSH_LOG = "log.txt"
VSH_CONFIG = "vsh_tests.cnf"
# What a safe nxdk_vsh_tests build contains, by its own strings.
VSH_MUST_HAVE = (b"Rebooting in 4 seconds", b"Run all and exit (automatic in",
                 COMPLETED.encode(), b"d:\\" + VSH_CONFIG.encode())
ROOT_CONFIG = ("/E/nxdk_pgraph_tests", "nxdk_pgraph_tests_config.json")


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def say(msg):
    print("%s %s" % (datetime.datetime.now().strftime("%H:%M:%S"), msg), flush=True)


class Console:
    def __init__(self, host, user="xbox", password="xbox", timeout=8.0):
        self.host, self.user, self.password, self.timeout = host, user, password, timeout

    def ping(self):
        return subprocess.run(["ping", "-c", "1", "-W", "2", self.host],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0

    def ftp(self):
        f = ftplib.FTP()
        f.connect(self.host, 21, timeout=self.timeout)
        f.login(self.user, self.password)
        f.set_pasv(True)
        return f

    def state(self):
        try:
            self.ftp().quit()
            return "dashboard"
        except Exception:
            return "running" if self.ping() else "unreachable"


def close(f):
    try:
        f.quit()
    except Exception:
        f.close()


def listing(f, path):
    """[(name, is_dir, size)] of one directory, or None if it does not exist."""
    try:
        f.cwd(path)
    except ftplib.error_perm:
        return None
    rows = []
    f.retrlines("LIST", rows.append)
    out = []
    for r in rows:
        parts = r.split(None, 8)
        if len(parts) < 9 or parts[8] in (".", ".."):
            continue
        out.append((parts[8], parts[0].startswith("d"), int(parts[4])))
    return out


def retr(f, path, name):
    buf = io.BytesIO()
    f.cwd(path)
    f.retrbinary("RETR " + name, buf.write)
    return buf.getvalue()


def ftp_path(win):
    """e:/x/y or e:\\x\\y -> /E/x/y, the FTP server's view of a drive path."""
    p = win.replace("\\", "/")
    if len(p) > 1 and p[1] == ":":
        p = "/" + p[0].upper() + p[2:]
    return p.rstrip("/")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_config(cfg):
    s = cfg.get("settings", {})
    why = []
    if s.get("enable_shutdown_on_completion") is not False:
        why.append("settings.enable_shutdown_on_completion must be false: true powers the console off with the log on its disk")
    if s.get("enable_progress_log") is not True:
        why.append("settings.enable_progress_log must be true: the log is the only proof the run completed")
    if (s.get("network") or {}).get("enable"):
        why.append("settings.network.enable must be false for this runner")
    if not s.get("output_directory_path"):
        why.append("settings.output_directory_path is required")
    for suite, tests in (cfg.get("test_suites") or {}).items():
        if isinstance(tests, dict) and "skipped" in tests:
            why.append("test_suites[%r] has a suite-level 'skipped', which overrides skip_tests_by_default for every test in it; list the tests instead" % suite)
    return why


def check_vsh(xbe_bytes, cfg_text):
    why = []
    for must in VSH_MUST_HAVE:
        if must not in xbe_bytes:
            why.append("the XBE does not contain %r -- not a safe nxdk_vsh_tests build"
                       % must.decode("latin-1"))
    if not [l for l in cfg_text.splitlines() if l.strip() and not l.startswith("#")]:
        why.append("the suite list is empty; an empty list runs every suite")
    return why


def upload_tree(f, local, remote):
    """STOR every file under `local` into `remote`, verifying sizes by LIST."""
    try:
        f.mkd(remote)
    except ftplib.error_perm:
        pass
    for name in sorted(os.listdir(local)):
        lp = os.path.join(local, name)
        if os.path.isdir(lp):
            upload_tree(f, lp, remote + "/" + name)
            continue
        f.cwd(remote)
        with open(lp, "rb") as fh:
            f.storbinary("STOR " + name, fh)
    got = {n: sz for n, d, sz in (listing(f, remote) or []) if not d}
    for name in os.listdir(local):
        lp = os.path.join(local, name)
        if os.path.isfile(lp) and got.get(name) != os.path.getsize(lp):
            raise RuntimeError("upload of %s: console holds %s bytes, local %d"
                               % (lp, got.get(name), os.path.getsize(lp)))


def fetch_tree(f, remote, local):
    os.makedirs(local, exist_ok=True)
    n = 0
    for name, is_dir, _ in listing(f, remote) or []:
        if is_dir:
            n += fetch_tree(f, remote + "/" + name, os.path.join(local, name))
        else:
            with open(os.path.join(local, name), "wb") as fh:
                fh.write(retr(f, remote, name))
            n += 1
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--xbe-dir", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--app", required=True, help="directory name under E:\\Apps\\")
    ap.add_argument("--out", required=True, help="local run directory")
    ap.add_argument("--host", default="192.168.50.1")
    ap.add_argument("--timeout-min", type=float, default=20.0)
    ap.add_argument("--unreachable-min", type=float, default=3.0,
                    help="how long without ping before the run is abandoned to a human")
    ap.add_argument("--check", action="store_true", help="refusal tests only; touch nothing")
    ap.add_argument("--kind", choices=("pgraph", "vsh"), default="pgraph")
    a = ap.parse_args(argv)

    xbe = os.path.join(a.xbe_dir, "default.xbe")
    if not os.path.isfile(xbe):
        print("REFUSED: no default.xbe in %s" % a.xbe_dir); return 2
    app = "/E/Apps/" + a.app
    if a.kind == "vsh":
        cfg = {"settings": {"network": {"enable": False}}}
        why = check_vsh(open(xbe, "rb").read(), open(a.config).read())
        outdir = "e:/Apps/%s/nxdk_vsh_tests" % a.app
        log_name, config_name = VSH_LOG, VSH_CONFIG
    else:
        cfg = json.load(open(a.config))
        why = check_config(cfg)
        outdir = cfg["settings"].get("output_directory_path")
        log_name, config_name = LOG_NAME, "nxdk_pgraph_tests_config.json"
    if why:
        for w in why:
            print("REFUSED: " + w)
        return 2
    con = Console(a.host)

    st = con.state()
    if st != "dashboard":
        print("REFUSED: the console is %s, not at the dashboard -- launch only from the dashboard" % st)
        return 2
    f = con.ftp()
    try:
        if a.kind == "pgraph" and any(n == ROOT_CONFIG[1] for n, d, _ in (listing(f, ROOT_CONFIG[0]) or [])):
            print("REFUSED: %s/%s exists and would silently win over this run's config"
                  % ROOT_CONFIG); return 2
        if listing(f, ftp_path(outdir)) is not None:
            print("REFUSED: output directory %s already exists on the console; use a fresh one"
                  % outdir); return 2
        existing = {n: sz for n, d, sz in (listing(f, app) or []) if not d}
        if "default.xbe" in existing:
            there = retr(f, app, "default.xbe")
            if hashlib.sha256(there).hexdigest() != sha256(xbe):
                print("REFUSED: %s already holds a different default.xbe" % app); return 2
    finally:
        close(f)
    say("preflight ok: dashboard, config safe, %s fresh, %s free or identical" % (outdir, app))
    if a.check:
        return 0

    os.makedirs(a.out, exist_ok=True)
    prov = {"started_utc": now_utc(), "host": a.host, "app": app,
            "xbe_sha256": sha256(xbe), "config_sha256": sha256(a.config),
            "output_directory_path": outdir}
    subprocess.run(["cp", a.config, os.path.join(a.out, "config" + os.path.splitext(a.config)[1])], check=True)

    f = con.ftp()
    try:
        staging = os.path.join(a.out, ".install")
        if os.path.exists(staging):
            subprocess.run(["rm", "-rf", staging], check=True)
        subprocess.run(["cp", "-r", a.xbe_dir, staging], check=True)
        for stale in ("nxdk_pgraph_tests_config.json", "sample-config.json", VSH_CONFIG):
            p = os.path.join(staging, stale)
            if os.path.exists(p):
                os.unlink(p)
        subprocess.run(["cp", a.config, os.path.join(staging, config_name)], check=True)
        say("uploading %s -> %s" % (a.xbe_dir, app))
        upload_tree(f, staging, app)
        path = "E:\\Apps\\%s\\default.xbe" % a.app
        say("SITE EXEC %s -> %s" % (path, f.sendcmd("SITE EXEC " + path)))
    finally:
        close(f)
    t0 = time.time()
    unreachable_since = None
    seen_running = False
    dark = not (cfg["settings"].get("network") or {}).get("enable")
    while True:
        time.sleep(10)
        el = time.time() - t0
        st = con.state()
        if el > a.timeout_min * 60:
            prov["result"] = "TIMEOUT-" + st.upper()
            json.dump(prov, open(os.path.join(a.out, "PROVENANCE.json"), "w"), indent=2)
            if st != "dashboard":
                # An XBE that never hands back cannot be stopped from here.
                print("OWNER: %s has been %s for %.0f min without finishing. It needs a "
                      "power cycle: press the power button; it boots to the dashboard."
                      % (path, st, el / 60))
                return 4
            return 3
        if st == "unreachable":
            # With networking off in the config -- which check_config insists
            # on -- the XBE never answers ping, so a run in progress LOOKS
            # unreachable from the first second to the last (measured on the
            # first #31 run, 2026-09-25). Only a network-enabled XBE can be
            # told apart from a dead console here; a dark one waits for the
            # overall timeout above.
            unreachable_since = unreachable_since or time.time()
            seen_running = seen_running or dark   # the XBE has the console
            if not dark and time.time() - unreachable_since > a.unreachable_min * 60:
                prov["result"] = "UNREACHABLE"
                json.dump(prov, open(os.path.join(a.out, "PROVENANCE.json"), "w"), indent=2)
                print("OWNER: the console at %s stopped answering ping %.0f s into a run of %s. "
                      "It needs a power cycle: press the power button; it boots to the dashboard."
                      % (a.host, el, path))
                return 4
            continue
        unreachable_since = None
        if st == "running":
            seen_running = True
            continue
        # At the dashboard: done, bounced, or not started yet.
        f = con.ftp()
        try:
            try:
                log = retr(f, ftp_path(outdir), log_name).decode("utf-8", "replace")
            except ftplib.all_errors:
                log = None
        finally:
            close(f)
        if log is not None and COMPLETED in log:
            break
        if el > 90 and (seen_running or log is not None):
            say("back at the dashboard WITHOUT '%s' -- not relaunching" % COMPLETED)
            prov["result"] = "RETURNED-INCOMPLETE"
            break
        if el > 90:
            say("never left the dashboard -- the launch did not take; not relaunching")
            prov["result"] = "DID-NOT-START"
            json.dump(prov, open(os.path.join(a.out, "PROVENANCE.json"), "w"), indent=2)
            return 3
    say("run returned after %.0f s; fetching %s" % (time.time() - t0, outdir))
    f = con.ftp()
    try:
        n = fetch_tree(f, ftp_path(outdir), os.path.join(a.out, "console"))
    finally:
        close(f)
    prov.setdefault("result", "COMPLETED")
    prov.update({"finished_utc": now_utc(), "files_fetched": n,
                 "seconds": round(time.time() - t0)})
    json.dump(prov, open(os.path.join(a.out, "PROVENANCE.json"), "w"), indent=2)
    say("%s: %d file(s) in %s" % (prov["result"], n, os.path.join(a.out, "console")))
    return 0 if prov["result"] == "COMPLETED" else 3


if __name__ == "__main__":
    sys.exit(main())
