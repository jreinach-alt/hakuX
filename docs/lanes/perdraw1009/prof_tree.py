#!/usr/bin/env python3
"""Split one thread of a simpleperf fp profile by INLINED function and source line.

    prof_tree.py PERF_DATA LIBXEMU_SO --tid TID [--fps F] [--top N]
                 [--self-of SYM] [--under SYM ...] [--lines-in SYM ...] [--callers-of SYM ...]

simpleperf's own symbol is the outermost (non-inlined) function, so pfifo_thread's "self" time hides
the pusher, the method dispatch and the FIFO spin, all inlined into it. This re-symbolizes every
libxemu.so address in each sample (leaf and callchain) with llvm-symbolizer --inlining against the
SAME build's libxemu.so (it carries .debug_line), so each frame expands to its inline stack.

  --self-of SYM    leaf samples whose outer symbol is SYM: split by innermost inlined function and
                   by source line.
  --under SYM      inclusive samples per (inline-expanded) function among samples that have SYM on
                   the stack, i.e. what SYM's subtree spends, function by function.
  --lines-in SYM   samples with SYM on the stack, by the source line SYM's (innermost) frame sits
                   on: its own line or the call it is in, so callees and frameless leaves are
                   charged to SYM's call site.
  --callers-of SYM for leaf SYM (memcpy_opt, memcmp: frameless, so fp unwinding drops their direct
                   caller), the first libxemu frame above them, as inlined function + line.

ms/frame = samples (1 ms each at -f 1000) / seconds / fps * 1000; --fps is the frame rate the
window ran at (state where it came from). Counts are from report-sample records, not report rows.
"""
import collections, os, re, subprocess, sys

SP = "/home/justin/Android/Sdk/ndk/29.0.14206865/simpleperf/bin/linux/x86_64/simpleperf"
SYMB = "/home/justin/Android/Sdk/ndk/29.0.14206865/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-symbolizer"


def samples(path, tid):
    out = subprocess.run([SP, "report-sample", "-i", path, "--show-callchain"],
                         capture_output=True, text=True, errors="replace").stdout
    cur = None
    frame = None
    in_chain = False
    for line in out.splitlines():
        s = line.strip()
        if s == "sample:":
            if cur is not None and not in_chain and frame:
                cur["frames"].append(frame)
            if cur and cur.get("thread_id") == tid:
                yield cur
            cur = {"frames": []}
            frame = {}
            in_chain = False
            continue
        if cur is None:
            continue
        if s == "callchain:":
            in_chain = True
            cur["frames"].append(frame)
            frame = {}
            continue
        if ":" not in s:
            continue
        k, v = s.split(":", 1)
        v = v.strip()
        if not in_chain and k not in ("vaddr_in_file", "file", "symbol"):
            cur[k] = v
            continue
        frame[k] = v
        if k == "symbol":
            if in_chain:
                cur["frames"].append(frame)
            frame = {} if in_chain else frame
    if cur is not None and not in_chain and frame:
        cur["frames"].append(frame)
    if cur and cur.get("thread_id") == tid:
        yield cur


def symbolize(so, addrs):
    addrs = sorted(addrs)
    inp = "".join("0x%x\n" % a for a in addrs)
    out = subprocess.run([SYMB, "--obj=" + so, "--inlining", "--relativenames"], input=inp,
                         capture_output=True, text=True).stdout
    blocks = out.split("\n\n")
    res = {}
    for a, b in zip(addrs, blocks):
        ls = [l for l in b.strip().splitlines()]
        st = []
        for i in range(0, len(ls) - 1, 2):
            fn = ls[i]
            loc = ls[i + 1]
            m = re.match(r"(.*?):(\d+)(?::\d+)?$", loc)
            f, ln = (m.group(1), int(m.group(2))) if m else (loc, 0)
            st.append((fn, os.path.basename(f), ln))
        res[a] = st  # innermost first
    return res


def main():
    a = sys.argv[1:]
    path, so = a.pop(0), a.pop(0)
    tid, fps, top = None, None, 25
    self_of, unders, callers, lines_in = None, [], [], []
    while a:
        k = a.pop(0)
        if k == "--tid": tid = a.pop(0)
        elif k == "--fps": fps = float(a.pop(0))
        elif k == "--top": top = int(a.pop(0))
        elif k == "--self-of": self_of = a.pop(0)
        elif k == "--under": unders.append(a.pop(0))
        elif k == "--callers-of": callers.append(a.pop(0))
        elif k == "--lines-in": lines_in.append(a.pop(0))
    S = list(samples(path, tid))
    t = [int(s.get("time", 0)) for s in S]
    span = (max(t) - min(t)) / 1e9
    n = len(S)
    def ms(c):
        return c / span / fps if fps else float("nan")
    print(f"tid {tid}: {n} samples over {span:.1f} s; fps {fps} -> 1 sample/s = {1/fps if fps else 0:.3f} ms/frame")
    addrs = set()
    for s in S:
        for f in s["frames"]:
            if f.get("file", "").endswith("libxemu.so") and "vaddr_in_file" in f:
                addrs.add(int(f["vaddr_in_file"], 16))
    sym = symbolize(so, addrs)

    def expand(s):
        """the sample's stack, leaf first, each frame expanded to its inline stack (innermost first)."""
        st = []
        for i, f in enumerate(s["frames"]):
            if f.get("file", "").endswith("libxemu.so") and "vaddr_in_file" in f:
                a = int(f["vaddr_in_file"], 16)
                for e in sym.get(a, []) or [(f.get("symbol", "?"), "?", 0)]:
                    st.append((e[0], e[1], e[2], i))
            else:
                st.append((f.get("symbol", "?"), os.path.basename(f.get("file", "?")), 0, i))
        return st

    if self_of:
        fn_c, line_c = collections.Counter(), collections.Counter()
        tot = 0
        for s in S:
            if s["frames"] and s["frames"][0].get("symbol") == self_of:
                st = [e for e in expand(s) if e[3] == 0]
                tot += 1
                fn_c[st[0][0]] += 1
                line_c[(st[0][0], st[0][1], st[0][2])] += 1
                # the outer inline frames name which inlined callee the line sits in
        print(f"\n== self of {self_of}: {tot} samples = {ms(tot):.2f} ms/frame, {100*tot/n:.1f}% of thread")
        print("  by innermost inlined function:")
        for k, v in fn_c.most_common(top):
            print(f"   {v:6d} {ms(v):6.2f} ms/f  {k}")
        print("  by source line:")
        for k, v in line_c.most_common(top):
            print(f"   {v:6d} {ms(v):6.2f} ms/f  {k[0]}  {k[1]}:{k[2]}")
        # inline paths (outer -> inner) for the self samples
        path_c = collections.Counter()
        for s in S:
            if s["frames"] and s["frames"][0].get("symbol") == self_of:
                st = [e for e in expand(s) if e[3] == 0]
                path_c[" > ".join("%s:%d" % (e[0], e[2]) for e in reversed(st))] += 1
        print("  by inline path (outer > inner):")
        for k, v in path_c.most_common(top):
            print(f"   {v:6d} {ms(v):6.2f} ms/f  {k[:160]}")

    for under in unders:
        inc = collections.Counter()
        tot = 0
        for s in S:
            st = expand(s)
            names = [e[0] for e in st]
            if under not in names:
                continue
            tot += 1
            # only frames BELOW (callee side of) the first occurrence of `under`
            idx = names.index(under)
            for nm in set(names[:idx]):
                inc[nm] += 1
        print(f"\n== under {under}: {tot} samples = {ms(tot):.2f} ms/frame, {100*tot/n:.1f}% of thread")
        for k, v in inc.most_common(top * 2):
            print(f"   {v:6d} {ms(v):6.2f} ms/f  {100*v/tot:5.1f}%  {k[:110]}")

    for fn in lines_in:
        lc = collections.Counter()
        tot = 0
        for s in S:
            st = expand(s)
            hit = [e for e in st if e[0] == fn]
            if not hit:
                continue
            tot += 1
            lc[(hit[0][1], hit[0][2])] += 1
        print(f"\n== lines in {fn} (where its first frame on the stack sits): {tot} samples = {ms(tot):.2f} ms/frame")
        for k, v in lc.most_common(top):
            print(f"   {v:6d} {ms(v):6.2f} ms/f  {k[0]}:{k[1]}")

    for c in callers:
        cc = collections.Counter()
        cl = collections.Counter()
        tot = 0
        for s in S:
            if not s["frames"] or s["frames"][0].get("symbol") != c:
                continue
            tot += 1
            st = expand(s)
            above = [e for e in st if e[3] > 0 and e[1] != "?"]
            if above:
                e = above[0]
                cc[e[0]] += 1
                cl[(e[0], e[1], e[2])] += 1
            else:
                cc["(no libxemu frame)"] += 1
        print(f"\n== callers of {c}: {tot} samples = {ms(tot):.2f} ms/frame (first libxemu frame above; fp drops the direct caller)")
        for k, v in cc.most_common(top):
            print(f"   {v:6d} {ms(v):6.2f} ms/f  {k}")
        print("  by call line:")
        for k, v in cl.most_common(top):
            print(f"   {v:6d} {ms(v):6.2f} ms/f  {k[0]}  {k[1]}:{k[2]}")


main()
