#!/usr/bin/env python3
"""Which draws does the guest issue on alternate frames only? (#804)

    alt_draws.py framedump_<id>.jsonl [--logcat logcat.txt] [--min-run 6]
    alt_draws.py --selftest

A frame dump record is written after the draw is recorded into the command
buffer (vk/draw.c, nv2a_diag_log_draw_call after vkCmdDraw*), so a draw the
async-compile skip drops is NOT in the dump; a draw that is in the dump was
recorded. Each draw is keyed two ways:

    full   kind, primitive, vertex/index count, shader-state hash, and every
           enabled texture stage's offset. Not the colour target: RalliSport
           triple-buffers, so the target changes every frame for every draw
    tex    shader hash and the enabled stages' texture offsets only, which
           survives a level-of-detail change in the count as an object nears

For every key the presence over the dump's frames is a string such as
`X.X.X.X`. A key ALTERNATES when it has a stretch of at least --min-run
consecutive frames that strictly toggle (present, absent, present, ...). A key
in ANTIPHASE with an alternating key is present exactly where it is absent,
which is what a visibility test drawn in place of the object would look like.

With --logcat, the perflog build's `hakuX-rpbrk` lines are read: `qry` is the
render-pass breaks the occlusion queries caused in the last 60 flips, so a
non-zero `qry` means the guest is running visibility tests.
"""

import json
import re
import sys
from collections import defaultdict


def load(path):
    session, end = None, None
    draws = defaultdict(list)
    frames = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            t = r.get("t")
            if t == "session":
                session = r
            elif t == "draw":
                draws[r["f"]].append(r)
            elif t == "frame":
                frames[r["f"]] = r
            elif t == "end":
                end = r
    return session, draws, frames, end


def tex_key(d):
    return tuple((s["s"], s["off"]) for s in d.get("tex", []) if s.get("en"))


def keys_of(d):
    full = (d.get("kind"), d.get("prim"), d.get("count"), d.get("shader"), tex_key(d))
    tex = (d.get("shader"), tex_key(d))
    return full, tex


def presence(draws, nframes, which):
    pres = defaultdict(lambda: [0] * nframes)
    for f in range(nframes):
        for d in draws.get(f, []):
            k = keys_of(d)[which]
            pres[k][f] += 1
    return pres


def longest_toggle(bits):
    """Longest stretch of strictly alternating presence, as (start, length)."""
    best = (0, 0)
    start = 0
    for i in range(1, len(bits) + 1):
        if i == len(bits) or bool(bits[i]) == bool(bits[i - 1]):
            if i - start > best[1]:
                best = (start, i - start)
            start = i
    return best


def analyse(draws, nframes, which, min_run):
    pres = presence(draws, nframes, which)
    alt = []
    for k, v in pres.items():
        s, n = longest_toggle(v)
        if n >= min_run and sum(1 for x in v[s:s + n] if x) >= min_run // 2:
            alt.append((k, s, n, v))
    alt.sort(key=lambda a: (-a[2], a[1]))
    anti = []
    for k, s, n, v in alt[:20]:
        for k2, v2 in pres.items():
            if k2 == k:
                continue
            seg = range(s, s + n)
            if all(bool(v2[i]) != bool(v[i]) for i in seg):
                anti.append((k, k2))
    every = [k for k, v in pres.items() if sum(1 for x in v if x) >= 0.95 * nframes]
    return pres, alt, anti, every


def bits_str(v):
    return "".join("X" if x else "." for x in v)


def read_rpbrk(logcat):
    rows = []
    pat = re.compile(r"^(\S+ \S+) .*hakuX-rpbrk.*RP:(\d+)\(fin(\d+) fb(\d+) qry(\d+)")
    marks = []
    with open(logcat, errors="replace") as fh:
        for line in fh:
            m = pat.search(line)
            if m:
                rows.append((m.group(1), int(m.group(2)), int(m.group(5))))
            elif "framedump:" in line or "hakuX-route" in line:
                marks.append(line.rstrip()[:160])
    return rows, marks


def report(path, logcat, min_run):
    session, draws, frames, end = load(path)
    nframes = (max(frames) + 1) if frames else (max(draws) + 1 if draws else 0)
    print(f"dump {path}: schema {session and session.get('schema')}, spec {session and session.get('spec')!r}, "
          f"{nframes} frames, end={end and end.get('why')}")
    if nframes == 0:
        print("no frames")
        return 3
    per = [len(draws.get(f, [])) for f in range(nframes)]
    print("draws per frame:", per[:60], "..." if nframes > 60 else "")
    even = [per[f] for f in range(0, nframes, 2)]
    odd = [per[f] for f in range(1, nframes, 2)]
    print(f"mean draws: even frames {sum(even)/max(1,len(even)):.1f}, odd frames {sum(odd)/max(1,len(odd)):.1f}")
    for which, name in ((0, "full"), (1, "tex")):
        pres, alt, anti, every = analyse(draws, nframes, which, min_run)
        print(f"\n== key {name}: {len(pres)} distinct, {len(every)} in >=95% of frames, "
              f"{len(alt)} alternate for >= {min_run} frames")
        for k, s, n, v in alt[:25]:
            print(f"  ALT f{s}-f{s+n-1} ({n}) {k}\n      {bits_str(v)}")
        for k, k2 in anti[:25]:
            print(f"  ANTIPHASE {k2}\n      against {k}\n      {bits_str(pres[k2])}")
        varying = [(k, v) for k, v in pres.items() if len(set(v)) > 1]
        print(f"  keys whose per-frame count varies: {len(varying)}")
        for k, v in varying[:25]:
            print(f"    {k} counts {sorted(set(v))}\n      {''.join(str(min(x, 9)) for x in v)}")
    if logcat:
        rows, marks = read_rpbrk(logcat)
        print(f"\nhakuX-rpbrk lines: {len(rows)} (each covers 60 flips)")
        for ts, rp, qry in rows:
            print(f"  {ts} RP {rp} qry {qry}")
        for m in marks:
            print("  ", m)
    return 0


def selftest():
    import tempfile, os
    lines = [json.dumps({"t": "session", "schema": 3, "spec": "selftest"})]
    car = {"kind": "inline_elements", "prim": 5, "count": 900, "shader": "c0",
           "color": {"addr": "0x200"}, "tex": [{"s": 0, "en": 1, "off": "0xCAR"}]}
    shadow = {"kind": "draw_arrays", "prim": 5, "count": 4, "shader": "s0",
              "color": {"addr": "0x100"}, "tex": [{"s": 0, "en": 1, "off": "0xSHD"}]}
    box = {"kind": "draw_arrays", "prim": 7, "count": 24, "shader": "b0",
           "color": {"addr": "0x100"}, "tex": []}
    for f in range(20):
        lines.append(json.dumps(dict(shadow, t="draw", f=f)))
        if 4 <= f < 16:
            lines.append(json.dumps(dict(car if f % 2 == 0 else box, t="draw", f=f)))
        else:
            lines.append(json.dumps(dict(car, t="draw", f=f)))
        lines.append(json.dumps({"t": "frame", "f": f, "draws": 2}))
    fd, p = tempfile.mkstemp(suffix=".jsonl")
    os.write(fd, ("\n".join(lines) + "\n").encode())
    os.close(fd)
    _, draws, frames, _ = load(p)
    os.unlink(p)
    pres, alt, anti, every = analyse(draws, 20, 0, 6)
    ok = (len(alt) == 2 and alt[0][1] in (3, 4) and alt[0][2] >= 12
          and any(k2[0] == "draw_arrays" and k2[1] == 7 for _, k2 in anti)
          and any(k[2] == 4 for k in every))
    print("selftest", "PASS" if ok else "FAIL", [(a[0][1], a[1], a[2]) for a in alt])
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    if len(argv) < 2:
        print(__doc__)
        return 2
    logcat = None
    min_run = 6
    if "--logcat" in argv:
        logcat = argv[argv.index("--logcat") + 1]
    if "--min-run" in argv:
        min_run = int(argv[argv.index("--min-run") + 1])
    return report(argv[1], logcat, min_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
