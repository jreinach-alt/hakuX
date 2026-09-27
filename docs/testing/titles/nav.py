#!/usr/bin/env python3
"""The navigating agent's hands and notebook: look, send one input, write it
down; then turn what was written into the title's route.

The agent is a person or a Claude session in a HELD device session. It loops:

    nav.py shot                 take a frame; print its path, to be looked at
    nav.py press A              send ONE input (press/hold/release/axis)
    nav.py mark profile-saved   note a milestone (also written to logcat)

and when it sees player control, `nav.py mark gameplay`, then plays for a
moment with `nav.py play ...` to confirm the input moves the player. Every
step goes into $NAV_DIR/<session>/nav.tsv with the host time it was sent, so

    nav.py route > routes/<name>.<variant>.route

replays the same inputs with the same gaps: the path the agent took IS the
route. The emitted route has NO `shot` after `mark gameplay`: a screencap
costs GPU and CPU and perturbs the frame rate the window measures, so the
measured window runs blind, and a reviewer judges it from the frames taken
before the mark and from the verdict.

    nav.py start <name> [--variant first-run|returning]   begin a session
    nav.py shot [label]            frame -> <session>/<n>-<label>.png
    nav.py press <BTN> [ms] | hold <BTN> | release <BTN> | axis <AX> <val>
    nav.py wait <s>                a deliberate pause, recorded as one
    nav.py mark <label>            logcat `hakuX-route: mark <label>` + frame
    nav.py play <step>...          the play pattern, recorded once, replayed
                                   forever after `mark gameplay` in the route
    nav.py route                   print the route
    nav.py end                     close the session

SERIAL is required, as for pad.sh; NAV_DRY=1 touches no device (selftest).
Inputs go through perf/pad.sh only: never `input keyevent`, which the app
takes as an exit (AGENTS.md).
"""

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PAD = os.path.join(HERE, "..", "perf", "pad.sh")
ROOT = os.environ.get("NAV_DIR", os.path.join(
    os.environ.get("HAKUX_WORK", "/home/justin/hakux-work"), "nav"))
CURRENT = os.path.join(ROOT, "current")
INPUTS = ("press", "hold", "release", "axis")
MIN_WAIT = 0.1


def die(msg):
    print(f"nav.py: {msg}", file=sys.stderr)
    sys.exit(2)


def session():
    try:
        with open(CURRENT) as fh:
            return fh.read().strip()
    except FileNotFoundError:
        die("no session; run `nav.py start <name>` first")


def log(sdir, verb, args, t=None):
    """One step, stamped when it was SENT: a frame is stamped before the
    screencap, so replaying `shot` (which costs the same again) keeps pace."""
    with open(os.path.join(sdir, "nav.tsv"), "a") as fh:
        fh.write(f"{t or time.time():.3f}\t{verb}\t{' '.join(args)}\n")


def read_log(sdir):
    rows = []
    with open(os.path.join(sdir, "nav.tsv")) as fh:
        for line in fh:
            t, verb, args = line.rstrip("\n").split("\t")
            rows.append((float(t), verb, args.split() if args else []))
    return rows


def dry():
    return bool(os.environ.get("NAV_DRY"))


def serial():
    s = os.environ.get("SERIAL")
    if not s and not dry():
        die("SERIAL is required")
    return s or "DRY"


def pad(*args):
    if dry():
        return 0
    env = dict(os.environ, SERIAL=serial())
    return subprocess.call(["bash", PAD, *args], env=env)


def screencap(path):
    if dry():
        open(path, "wb").close()
        return True
    with open(path, "wb") as fh:
        rc = subprocess.call(["timeout", "30", "adb", "-s", serial(), "exec-out",
                              "screencap", "-p"], stdout=fh, stderr=subprocess.DEVNULL)
    return rc == 0 and os.path.getsize(path) > 0


def logcat_mark(label):
    if dry():
        return True
    out = subprocess.run(["timeout", "20", "adb", "-s", serial(), "shell", "log", "-t",
                          "hakuX-route", f"'mark {label}'"], capture_output=True, text=True)
    return out.returncode == 0 and not out.stdout.strip()


def emit_route(sdir):
    """nav.tsv -> route text. Gaps between steps become `wait`s; a frame
    before `mark gameplay` becomes a `shot` (the reviewer's evidence of the
    way in); after it, no frames at all, and the recorded `play` pattern
    repeats forever."""
    meta = json.load(open(os.path.join(sdir, "session.json")))
    rows = read_log(sdir)
    out = [f"# {meta['name']} ({meta['variant']}): recorded by nav.py on {meta['device'] or '?'}",
           f"# session {os.path.basename(sdir)}, started {meta['started']}.",
           "# Every wait is the gap the navigator actually left before the next step.",
           "# No frames after `mark gameplay`: the measured window runs blind."]
    prev = meta["t0"]
    in_play = False
    play = []
    for t, verb, args in rows:
        if verb == "play":
            play.append(" ".join(args))
            continue
        # A `wait` row is only time passing; the next step's gap carries it.
        if verb not in INPUTS + ("shot", "mark") or in_play:
            continue
        gap = t - prev
        if gap >= MIN_WAIT:
            out.append(f"wait {gap:.1f}")
        prev = t
        if verb == "shot":
            if not in_play:
                out.append(f"shot {args[0] if args else 'nav'}")
            continue
        if verb == "mark":
            out.append(f"mark {args[0]}")
            if args[0] == "gameplay":
                in_play = True
            continue
        if not in_play:
            out.append(f"{verb} {' '.join(args)}")
    if in_play:
        out.append("repeat forever {")
        out += [f"    {p}" for p in (play or ["wait 5"])]
        out.append("}")
    else:
        out.append("# never reached `mark gameplay`: this route is not a gameplay route")
    return "\n".join(out) + "\n"


def main(argv):
    if not argv:
        die(__doc__)
    verb, args = argv[0], argv[1:]
    if verb == "start":
        if not args:
            die("start <name> [--variant V]")
        variant = "first-run"
        if "--variant" in args:
            i = args.index("--variant")
            variant = args[i + 1]
            args = args[:i] + args[i + 2:]
        name = args[0]
        sid = f"{name}.{variant}-{time.strftime('%Y%m%dT%H%M%S')}"
        sdir = os.path.join(ROOT, sid)
        os.makedirs(sdir)
        json.dump({"name": name, "variant": variant, "device": os.environ.get("SERIAL"),
                   "started": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "t0": time.time()},
                  open(os.path.join(sdir, "session.json"), "w"), indent=1)
        open(os.path.join(sdir, "nav.tsv"), "w").close()
        with open(CURRENT, "w") as fh:
            fh.write(sdir)
        print(sdir)
        return 0
    sdir = session()
    if verb == "shot":
        n = sum(1 for f in os.listdir(sdir) if f.endswith(".png"))
        label = args[0] if args else "nav"
        path = os.path.join(sdir, f"{n:03d}-{label}.png")
        t = time.time()
        ok = screencap(path)
        log(sdir, "shot", [label], t)
        print(path if ok else f"SHOT FAILED {path}")
        return 0 if ok else 1
    if verb in INPUTS:
        rc = pad(verb, *args)
        log(sdir, verb, args)
        print(f"{verb} {' '.join(args)}" + ("" if rc == 0 else f"  (pad.sh rc {rc})"))
        return rc
    if verb == "wait":
        time.sleep(float(args[0]))
        log(sdir, "wait", args[:1])
        return 0
    if verb == "mark":
        t = time.time()
        ok = logcat_mark(args[0])
        log(sdir, "mark", args[:1], t)
        n = sum(1 for f in os.listdir(sdir) if f.endswith(".png"))
        screencap(os.path.join(sdir, f"{n:03d}-mark-{args[0]}.png"))
        print(f"mark {args[0]}" + ("" if ok else "  (logcat write FAILED)"))
        return 0 if ok else 1
    if verb == "play":
        step = " ".join(args)
        w = args[0] if args else ""
        if w in INPUTS:
            pad(*args)
        elif w == "wait":
            time.sleep(float(args[1]))
        else:
            die(f"play takes an input or `wait <s>`, not {step!r}")
        log(sdir, "play", args)
        print(f"play {step}")
        return 0
    if verb == "route":
        sys.stdout.write(emit_route(sdir))
        return 0
    if verb == "end":
        os.remove(CURRENT)
        print(sdir)
        return 0
    die(f"unknown verb {verb!r}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
