#!/usr/bin/env python3
"""Question: do the captures that moved between gta3drive1017's pixel arms
(Antialiasing_tests/CPUWriteIgnoresSurfaceConfig, FramebufferNotModifiedBySurfaceState,
and Texture_shadow_comparator's +-80/86 px shifts) also move between earlier
pairs of runs, where the change between the pair cannot have reached them?

For each pair it runs ab_compare.py --json, then prints both refs, and for the
watched captures the A -> B values plus the count of shadow_comparator movers.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RES = "/home/justin/hakux-work/dispatch/results"
OUT = os.path.join(REPO, ".aside", "pixel_noise")

PAIRS = [
    ("1-1792280164-lane.gta3drive1017-1362137", "1-1792280141-lane.gta3drive1017-1361822"),
    ("1-1791670443-drawrec1010-3709316", "1-1791670444-drawrec1010-3709731"),
    ("1-1791661636-drawrec1010-950252", "1-1791661643-drawrec1010-951834"),
    ("1-1791622671-pfifowait1009-332891", "1-1791622678-pfifowait1009-333205"),
    ("1-1791641570-perdrawon1010-3943774", "1-1791642456-perdrawon1010-4121401"),
    ("1-1791659693-reportasync1010-543406", "1-1791659700-reportasync1010-546194"),
    ("1-1791047884-lane.memfast-3559153", "1-1791047884-lane.memfast-3559222"),
    ("1-1790549936-arms-drain474-base-2297206", "1-1790549937-arms-drain474-fix-2297407"),
    # after f5a67ba52c, where Texture_shadow_comparator went 264/288 -> 0/288
    ("0-1792163875-fps1015-716177", "0-1792163881-fps1015-716411"),
    ("1792239595-defaulton1017-3309294", "1792239595-defaulton1017-3309495"),
    ("1-1791650753-texscan1010-2542806", "1-1791650757-texscan1010-2543971"),
]
WATCH = (
    "Antialiasing_tests/CPUWriteIgnoresSurfaceConfig",
    "Antialiasing_tests/FramebufferNotModifiedBySurfaceState",
)


def main():
    os.makedirs(OUT, exist_ok=True)
    pairs = PAIRS
    if sys.argv[1:] == ["--late"]:
        pairs = PAIRS[-3:]
    for a, b in pairs:
        jpath = os.path.join(OUT, "%s__%s.json" % (a, b))
        subprocess.run(
            [sys.executable, os.path.join(REPO, "docs", "testing", "ab_compare.py"),
             "--a", os.path.join(RES, a), "--b", os.path.join(RES, b),
             "--allow-same-binary", "--json", jpath],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=REPO)
        if not os.path.exists(jpath):
            print("%s vs %s: no json" % (a, b))
            continue
        d = json.load(open(jpath))
        print("%s (%s) vs %s (%s)" % (a, d["a"].get("ref"), b, d["b"].get("ref")))
        movers = d.get("movers") or []
        seen = {}
        sc = 0
        for m in movers:
            key = m.get("capture") or "%s/%s" % (m.get("suite"), m.get("test"))
            if key.startswith("Texture_shadow_comparator/"):
                sc += 1
            if key in WATCH:
                seen[key] = (m.get("a"), m.get("b"))
        for w in WATCH:
            print("    %-58s %s" % (w, seen.get(w, "same")))
        print("    shadow_comparator movers: %d   all movers: %d" % (sc, len(movers)))


if __name__ == "__main__":
    main()
