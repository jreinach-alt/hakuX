#!/usr/bin/env python3
"""The desktop before/after table for #1045: every present from the first to the title's first picture, per run.

usage: desk_ab.py RUN:ARM:TITLE [...]      (RUN is a dir under build-linux/runs with probe/boot1045_log.txt)

Classes are judge_boot.py's (its classify() and nb_bar). Coverage is judge_boot's C1 and C3 with one change to C2,
made after run d3 and stated in NOTES.md: judge_boot's download rule takes the kernel's start address from the first
lit picture, and on d3 the kernel's logo was never lit while the screen was on (the fix blanks the one present that
used to show it late), so the title's own first picture became "the first" and C2 found nothing after it. Here the
kernel's start address is the first non-zero start in a real mode (bpp > 0), read from the registers, not the
pixels; the title's first picture is the first lit present (lit >= LIT_PICTURE, nb < NB_FLOOR) at any other non-zero
start.

Per run: flash presents (window noise or green) from the first present to the title's first picture and over the
whole log; the static in the console surface (the texture's numbers, what a path that ignored screen-off would show)
and how many of those presents had the screen off.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import judge_boot as jb  # noqa: E402

RUNS = "/home/justin/hakux-work/wt/bootstatic1017/build-linux/runs"


def one(run):
    d = os.path.join(RUNS, run, "probe")
    rows = jb.parse_log(os.path.join(d, "boot1045_log.txt"))
    j = jb.judge(d)
    nb_bar = j["clean"]["nb_bar"]
    ns = [r["n"] for r in rows]
    c1 = ns[0] == 0 and all(b == a + 1 for a, b in zip(ns, ns[1:]))
    kstart = next((r["start"] for r in rows if r["bpp"] > 0 and r["start"] != 0), None)
    fp = next((i for i, r in enumerate(rows) if r["start"] not in (0, kstart) and r["lit"] >= jb.LIT_PICTURE
               and r["nb"] < jb.NB_FLOOR), None)
    tail = len(rows) - 1 - fp if fp is not None else 0
    covered = c1 and fp is not None and tail >= jb.TAIL_PRESENTS
    cls = [jb.classify(r, nb_bar) for r in rows]
    upto = cls[: fp + 1] if fp is not None else cls
    flash_upto = [rows[i]["n"] for i, c in enumerate(upto) if c in ("noise", "green")]
    flash_all = [rows[i]["n"] for i, c in enumerate(cls) if c in ("noise", "green")]
    tex = [r for r in rows if r["tlit"] >= 0 and jb.classify(
        {"lit": r["tlit"], "grn": r["tgrn"], "nb": r["tnb"]}, nb_bar) in ("noise", "green")]
    tex_off = sum(1 for r in tex if r["sr01"] & 0x20)
    edge = []
    for i in flash_all:
        r = rows[ns.index(i)]
        p = rows[ns.index(i) - 1] if ns.index(i) > 0 else None
        edge.append("n%d sr01=%02x start=%08x prev sr01=%s start=%s" % (
            i, r["sr01"], r["start"], "%02x" % p["sr01"] if p else "-", "%08x" % p["start"] if p else "-"))
    return {
        "presents": len(rows), "C1": c1, "kernel_start": "%08x" % kstart if kstart is not None else None,
        "title_first_picture_n": rows[fp]["n"] if fp is not None else None,
        "title_first_picture_ms": rows[fp]["t_ms"] if fp is not None else None,
        "tail": tail, "covered": covered,
        "presents_judged_to_first_picture": len(upto),
        "classes_to_first_picture": {c: upto.count(c) for c in sorted(set(upto))},
        "flash_to_first_picture": flash_upto, "flash_all": flash_all, "flash_detail": edge,
        "surface_static_presents": len(tex), "surface_static_screen_off": tex_off,
        "nb_bar": nb_bar,
    }


def main():
    print("| run | arm | title | covered | title's first picture (n, s) | presents judged to it | flash presents to it "
          "| flash presents, whole log | static in the console surface (screen off) |")
    print("|---|---|---|---|---|---|---|---|---|")
    detail = []
    for spec in sys.argv[1:]:
        run, arm, title = spec.split(":", 2)
        r = one(run)
        fpn = r["title_first_picture_n"]
        print("| %s | %s | %s | %s | %s | %d | %d %s | %d | %d (%d) |" % (
            run, arm, title, "yes" if r["covered"] else "NO (C1=%s tail=%d)" % (r["C1"], r["tail"]),
            "n%d, %.1f s" % (fpn, r["title_first_picture_ms"] / 1000) if fpn is not None else "none",
            r["presents_judged_to_first_picture"], len(r["flash_to_first_picture"]),
            r["flash_to_first_picture"] if r["flash_to_first_picture"] else "", len(r["flash_all"]),
            r["surface_static_presents"], r["surface_static_screen_off"]))
        detail.append((run, r))
    for run, r in detail:
        print("%s: kernel start %s, classes to first picture %s, nb_bar %.1f" % (
            run, r["kernel_start"], r["classes_to_first_picture"], r["nb_bar"]))
        for e in r["flash_detail"]:
            print("   flash %s" % e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
