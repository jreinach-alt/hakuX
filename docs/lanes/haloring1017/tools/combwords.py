"""Print the hull combiner's register words for the ring's draws (#939, (a)).

usage: combwords.py DUMP.jsonl FRAME [FRAME...]

For n4 (864 indices) and n5 (4362): COMBINECOLORI/O 0-7, COMBINEALPHAI/O 0-7,
COMBINECTL, COMBINESPECFOG0/1, SPECFOGFACTOR0/1, COMBINEFACTOR0/1 0-7, so
hullsw.py's transcription can be checked against the guest's own words.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "x1port1012", "tools"))
import gdread as g  # noqa: E402

dump, frames = sys.argv[1], [int(x) for x in sys.argv[2:]]
session, draws, fr, skips, shaders = g.load(dump)
for d in draws:
    for k in ("f", "n", "count"):
        d[k] = int(d[k])
st = g.replay(draws, set(frames))
for f in frames:
    for d in draws:
        if d["f"] != f or d["count"] not in (864, 4362):
            continue
        r = st[(f, d["n"])]["r"]
        h = lambda base: "[" + ", ".join(f"{r[base + 4 * i]:#010x}" for i in range(8)) + "]"  # noqa: E731
        print(f"f{f} n{d['n']} count {d['count']} shader {d['shader']}")
        print(f"  COLORI {h(0x1900)}\n  COLORO {h(0x1920)}\n  ALPHAI {h(0x18C0)}\n  ALPHAO {h(0x18E0)}")
        print(f"  FACTOR0 {h(0x1880)}\n  FACTOR1 {h(0x18A0)}")
        print(f"  CTL {r[0x1940]:#010x} SPECFOG {r[0x1944]:#010x} {r[0x1948]:#010x} "
              f"SPECFOGFACTOR {r[0x19AC]:#010x} {r[0x19B0]:#010x}")
