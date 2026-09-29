#!/usr/bin/env python3
"""Add two frames after `mark gameplay` to each parked request's route.

    addshots.py            write routes/<name>.shots.route and check them
    addshots.py --apply    and replace the parked requests

Why: the Otogi re-pilot (0-0-s-1-1790615781-lane.slowtier2-otogi2870269)
showed play at the mark and left play 105 s later. Only the counters showed
it. A frame about 60 s and about 140 s after the mark shows whether the
scored window is still play. `shot` takes one screencap and writes nothing
to logcat, so the verdict's window does not move.

The route up to and including `mark gameplay` is unchanged. The play loop
`repeat forever { BODY }` becomes

    repeat N1 { BODY }  shot play1  repeat N2 { BODY }  shot play2
    repeat forever { BODY }

with N1 and N2 from the body's summed waits (60 s and 80 s nominal; the pad
steps add about 15%, so the frames land near +70 s and +160 s). A request is
replaced with os.replace, so coldslot.sh's copy never reads a torn file.
"""
import json
import os
import subprocess
import sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
PARK = f"{D}/parked/slowtier2-cold-20260928"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CHECK = os.path.join(ROOT, "docs/testing/titles/route.sh")
NOTE = ("# lane.slowtier2 2026-09-28: two frames added after the mark (play1, play2);"
        " the route to the mark is unchanged (docs/lanes/slowtier2/addshots.py).")


def reshape(route):
    ls = route.split("\n")
    marks = [i for i, l in enumerate(ls) if l.split("#")[0].split() == ["mark", "gameplay"]]
    if len(marks) != 1:
        raise SystemExit(f"want one `mark gameplay`, found {len(marks)}")
    m = marks[0]
    if ls[m + 1].split("#")[0].split() != ["repeat", "forever", "{"]:
        raise SystemExit(f"line after the mark is not the play loop: {ls[m + 1]!r}")
    end = None
    for i in range(m + 2, len(ls)):
        w = ls[i].split("#")[0].strip()
        if w.endswith("{"):
            raise SystemExit("nested block in the play loop")
        if w == "}":
            end = i
            break
    if end is None:
        raise SystemExit("play loop is not closed")
    if any(l.split("#")[0].strip() for l in ls[end + 1:]):
        raise SystemExit("steps after the play loop")
    if any("shot play1" in l for l in ls):
        return None, None
    body = ls[m + 2:end]
    dur = 0.0
    for l in body:
        w = l.split("#")[0].split()
        if w[:1] == ["wait"]:
            dur += float(w[1])
        elif w[:1] == ["press"]:
            dur += (float(w[2]) if len(w) > 2 else 60.0) / 1000.0
        elif w[:1] == ["mash"]:
            dur += int(w[2]) * float(w[3])
    n1, n2 = max(1, round(60 / dur)), max(1, round(80 / dur))
    out = [NOTE] + ls[:m + 1]
    out += [f"repeat {n1} {{"] + body + ["}", "shot play1"]
    out += [f"repeat {n2} {{"] + body + ["}", "shot play2"]
    out += ["repeat forever {"] + body + ["}", ""]
    return "\n".join(out), (dur, n1, n2)


def main():
    apply = "--apply" in sys.argv[1:]
    os.makedirs(f"{HERE}/routes", exist_ok=True)
    for f in sorted(os.listdir(PARK)):
        if not f.endswith(".req"):
            continue
        path = f"{PARK}/{f}"
        req = json.load(open(path))
        new, how = reshape(req["route"])
        if new is None:
            print(f"{f}: already has play1; left alone")
            continue
        name = req["route_name"]
        rfile = f"{HERE}/routes/{name}.shots.route"
        with open(rfile, "w") as fh:
            fh.write(new)
        chk = subprocess.run(["bash", CHECK, "--check", rfile], capture_output=True, text=True)
        ok = chk.returncode == 0
        print(f"{f}: route {name}, body {how[0]:.1f} s, repeat {how[1]} / shot play1 / "
              f"repeat {how[2]} / shot play2; route.sh --check exit {chk.returncode} "
              f"{(chk.stdout + chk.stderr).strip()[:120]}")
        if not ok:
            raise SystemExit(f"{rfile} does not parse; nothing replaced for {f}")
        if not apply:
            continue
        old_route = req["route"]
        req["route"] = new
        text = json.dumps(req, indent=2) + "\n"
        back = json.loads(text)
        if back["route"] != new or {k: v for k, v in back.items() if k != "route"} != \
                {k: v for k, v in req.items() if k != "route"}:
            raise SystemExit(f"{f}: round trip differs")
        if not os.path.exists(path):
            print(f"{f}: gone from the parked dir before the replace (slotted); not written")
            continue
        tmp = f"{path}.tmp-addshots"
        with open(tmp, "w") as fh:
            fh.write(text)
        if not os.path.exists(path):
            os.remove(tmp)
            print(f"{f}: gone from the parked dir before the replace (slotted); not written")
            continue
        os.replace(tmp, path)
        print(f"{f}: replaced ({len(old_route)} -> {len(new)} route bytes)")


main()
