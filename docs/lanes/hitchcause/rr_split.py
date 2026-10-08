"""Print the [rr425] time split (inside TBs: tbus; between TBs: gapus) for the
2 s spans that hold each hitch, next to a few baseline spans.

Usage: python3 rr_split.py <logcat.txt> <HH:MM> [<HH:MM> ...]
"""
import re
import sys

LINE = re.compile(r"^10-04 (\d\d):(\d\d):(\d\d\.\d+) .*\[rr425\] w=(\d+) dt=(\d+) (.*)$")
KV = re.compile(r"\b(gapus|tbus|it|e|g|ga|x|hc|hm|ip|pcdrop|sn)=(-?[0-9.]+)")


def main(path, stamps):
    with open(path, errors="replace") as fh:
        for raw in fh:
            m = LINE.match(raw.rstrip("\n"))
            if not m:
                continue
            h, mi, s, w, dt, rest = m.groups()
            stamp = "%s:%s" % (h, mi)
            if stamp not in stamps:
                continue
            f = {k: float(v) for k, v in KV.findall(rest)}
            tb = f.get("tbus", 0.0) / 1000.0
            gp = f.get("gapus", 0.0) / 1000.0
            d = float(dt)
            print("%s:%05.2f w=%-4s dt=%-5s inside_TB=%7.1fms between_TB=%7.1fms (%.0f%% in TB) "
                  "dispatches=%-7.0f" % (
                      stamp, float(s), w, dt, tb, gp,
                      100.0 * tb / (tb + gp) if tb + gp else 0.0, f.get("it", 0.0)))


if __name__ == "__main__":
    main(sys.argv[1], set(sys.argv[2:]))
