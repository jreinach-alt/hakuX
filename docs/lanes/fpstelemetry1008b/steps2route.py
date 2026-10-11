#!/usr/bin/env python3
"""Turn a pathfind run's steps.jsonl into a timed route (lane.fpstelemetry1008b,
forked from docs/lanes/fps20786/steps2route.py to fix two gaps that tool hit on
NFS Most Wanted/Midnight Club II/Fantastic 4/Dino Crisis 3, #433).

    steps2route.py <steps.jsonl> --name NAME --gameplay N --loop TOKENS
                   [--hold-s 600] [--offset 4] [--state first-run]
    steps2route.py <steps.jsonl> --name NAME --gameplay N --hold-log HOLD.JSONL
                   [--hold-cutoff 750] [--offset 4] [--state first-run]

Every step up to and including step N (the one pathfind read as gameplay)
plays its action at the step's own time + offset seconds after launch, with
pathfind's input mapping (pathfind.py send(): d-pad = the hat, a button is a
120-ms press, then 0.35 s, and 0.25 s after every token). Pathfind took each
step 8-15 s apart because it waited for a model, and every screen it passed
waits for input, so its pace is the safe one: a press can land late, not
early. After step N: `mark gameplay`, then either a genre loop (`--loop`,
pathfind's HOLD_GENRES grammar, repeated to cover --hold-s) or a literal
replay of a recorded hold (`--hold-log`, see below), with a frame roughly
every 30s.

Fix 1 (tok_lines): the upstream tool had no branch for a combo token
(`RT+left:N`, `RT+right:N`, `LT+left:N`, `LT+right:N` -- a trigger held
together with a stick direction, used by HOLD_GENRES["drive"] and recorded
directly in NFS Most Wanted's and Midnight Club II's own pathfind steps) --
only pathfind.py's own send() handled those. Added here, same semantics as
send(): hold the trigger, hold the stick, wait, release the stick, release
the trigger.

Fix 2 (--hold-log): the upstream tool could only generate a fixed genre loop
after `mark gameplay`. Two titles' pathfind holds are not well modelled by a
fixed loop -- Fantastic 4 cycles gameplay burst -> game_over -> cutscene
(needs START to skip, A to dismiss dialogue, before the next burst) and Dino
Crisis 3's model adapted its own action mix over the hold (dropping a
menu-opening button, changing the stick/button mix partway through) -- so
`--hold-log` replays that title's own recorded `hold.jsonl` verbatim (each
row's `action` at the row's own `hold_s` + offset, relative to the mark),
rather than inventing a loop. `--hold-cutoff` caps how much of a long hold to
replay (Fantastic 4's own hold ran 1674s to reach 600s of play; this lane
cuts it short of that for one measurement, not a full reproduction).
"""
import argparse, json

HAT = {"UP": ("HATY", "min"), "DOWN": ("HATY", "max"), "LEFT": ("HATX", "min"), "RIGHT": ("HATX", "max")}
STICK = {"up": [("LY", "min")], "down": [("LY", "max")], "left": [("LX", "min")], "right": [("LX", "max")],
         "upleft": [("LY", "min"), ("LX", "min")], "upright": [("LY", "min"), ("LX", "max")]}
RSTICK = {"up": [("RY", "min")], "down": [("RY", "max")], "left": [("RX", "min")], "right": [("RX", "max")]}


def tok_lines(tok):
    """(route lines, seconds) for one pathfind token."""
    if tok in HAT:
        ax, v = HAT[tok]
        return [f"axis {ax} {v}", f"axis {ax} mid", "wait 0.6"], 0.6
    if ":" not in tok:
        return [f"press {tok} 120", "wait 0.6"], 0.72
    parts = tok.split(":")
    s = float(parts[-1])
    if parts[0] in ("STICK", "RSTICK"):
        axes = (STICK if parts[0] == "STICK" else RSTICK)[parts[1]]
        return ([f"axis {a} {v}" for a, v in axes] + [f"wait {s}"] +
                [f"axis {a} mid" for a, _ in axes] + ["wait 0.25"]), s + 0.25
    if "+" in parts[0]:
        # a trigger and the left stick together (pathfind.py send()'s own branch):
        # steer on the gas, or reverse while turning off a wall.
        trig, d = parts[0].split("+")
        axes = STICK[d]
        return ([f"axis {trig} max"] + [f"axis {a} {v}" for a, v in axes] + [f"wait {s}"] +
                [f"axis {a} mid" for a, _ in axes] + [f"axis {trig} min", "wait 0.25"]), s + 0.25
    if parts[0] in ("RT", "LT"):
        return [f"axis {parts[0]} max", f"wait {s}", f"axis {parts[0]} min", "wait 0.25"], s + 0.25
    if parts[0] == "HOLD":
        return [f"hold {parts[1]}", f"wait {s}", f"release {parts[1]}", "wait 0.25"], s + 0.25
    raise SystemExit(f"token not handled: {tok}")


ap = argparse.ArgumentParser()
ap.add_argument("steps")
ap.add_argument("--name", required=True)
ap.add_argument("--gameplay", type=int, required=True)
ap.add_argument("--loop", help="comma-separated pathfind tokens (mutually exclusive with --hold-log)")
ap.add_argument("--hold-log", help="a recorded hold.jsonl to replay verbatim instead of --loop")
ap.add_argument("--hold-cutoff", type=float, default=1e9, help="max hold_s to replay from --hold-log")
ap.add_argument("--hold-s", type=float, default=600)
ap.add_argument("--offset", type=float, default=4)
ap.add_argument("--state", default="first-run")
ap.add_argument("--source", default="")
a = ap.parse_args()
if bool(a.loop) == bool(a.hold_log):
    raise SystemExit("pass exactly one of --loop or --hold-log")

steps = [json.loads(l) for l in open(a.steps)]
out = [f"# state: {a.state}",
       f"# {a.name}: generated by docs/lanes/fpstelemetry1008b/steps2route.py from pathfind's",
       f"# recorded run {a.source or a.steps} (steps 1-{a.gameplay}, then "
       + (f"a genre loop)." if a.loop else f"a literal hold-log replay)."),
       "# Each step's input plays at the step's own time + %.0f s; a frame per step." % a.offset]
clock = 0.0
for s in steps:
    if s["n"] > a.gameplay:
        break
    at = float(s["t"]) + a.offset
    if at > clock:
        out.append("wait %.1f" % (at - clock))
        clock = at
    out.append(f"shot s{s['n']:02d}-{s['state']}")
    out.append(f"# step {s['n']} [{s['state']}] {s.get('why', '')[:100]}")
    for tok in s.get("action", []):
        lines, secs = tok_lines(tok)
        out += lines
        clock += secs
out.append("wait 3")
out.append("mark gameplay")
clock += 3

if a.loop:
    body, per = [], 0.0
    for tok in a.loop.split(","):
        lines, secs = tok_lines(tok)
        body += lines
        per += secs
    inner = max(1, int(30 // per))
    outer = int(a.hold_s // (inner * per)) + 1
    out.append(f"# genre loop: {per:.1f} s, {inner} per frame, {outer} frames")
    out.append(f"repeat {outer} {{")
    out.append("shot hold")
    out.append(f"repeat {inner} {{")
    out += body
    out.append("}")
    out.append("}")
    clock += outer * inner * per
else:
    hold_rows = [json.loads(l) for l in open(a.hold_log)]
    out.append(f"# hold-log replay from {a.hold_log}, cutoff hold_s<={a.hold_cutoff:.0f}")
    hclock, last_shot = 0.0, -30.0
    for r in hold_rows:
        hs = r.get("hold_s")
        if hs is None or hs > a.hold_cutoff:
            break
        acts = r.get("action") or []
        if not acts:
            continue
        at = hs + a.offset
        if at > hclock:
            out.append("wait %.1f" % (at - hclock))
            hclock = at
        if hclock - last_shot >= 30.0:
            out.append(f"shot hold-{int(hclock):04d}")
            last_shot = hclock
        out.append(f"# hold n={r.get('n')} state={r.get('state')} src={r.get('src')}")
        for tok in acts:
            lines, secs = tok_lines(tok)
            out += lines
            hclock += secs
    clock += hclock

out.append(f"# route ends ~{clock:.0f} s after launch")
print("\n".join(out))
