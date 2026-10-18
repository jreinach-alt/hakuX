#!/usr/bin/env python3
"""Per draw, the host identity of every stage that samples one of the given
guest addresses (#1038): image handle, texture hash, guest-VRAM hash, s2t,
and the surface record. Plus every draw that renders INTO those addresses.

  texids.py DUMP F N0 N1 ADDR [ADDR ...]     (ADDR hex, e.g. 0x0212f000)
"""
import json, sys


def main():
    path, f, n0, n1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    addrs = {int(a, 16) for a in sys.argv[5:]}
    with open(path) as fh:
        for line in fh:
            if not line.startswith('{"t":"draw"'):
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d["f"] != f or not (n0 <= d["n"] <= n1):
                continue
            col = d.get("color") or {}
            ca = int(col.get("addr", "0x0"), 16) if col else 0
            mark = " RT" if ca in addrs else ""
            parts = []
            for s in d.get("tex", []):
                if not s.get("en"):
                    continue
                if int(s.get("off", "0x0"), 16) in addrs:
                    srf = s.get("srf") or {}
                    parts.append(f"s{s['s']}@{s['off'][-6:]} img {s.get('img', '')[-6:]} "
                                 f"gh {s.get('gh', '')[:8]} th {s.get('th', '')[:4]} "
                                 f"s2t {s.get('s2t')} dirty {srf.get('dirty')} "
                                 f"upl {srf.get('upl')} dlp {srf.get('dlp')}")
            if mark or parts:
                print(f"n{d['n']:4d} col {col.get('addr', '-'):>9} dirty {col.get('dirty', '-')}"
                      f" cb {d.get('cb')} cbd {d.get('cb_draws')} sub {d.get('submits')}{mark}"
                      + ("\n      " + "\n      ".join(parts) if parts else ""))


if __name__ == "__main__":
    main()
