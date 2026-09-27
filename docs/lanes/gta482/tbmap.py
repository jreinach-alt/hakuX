#!/usr/bin/env python3
"""Guest PCs behind a thread's JIT samples, from a TCG code-buffer dump (#482).

    tbmap.py <session dir> [--tid T] [--top N] [--data rec-on.data]

<session dir> is capture_gta.sh's output: maps.txt, codebuf-<start>.bin.gz
(one per executable anonymous mapping of the emulator) and rec-on.data.

How it works. tcg_tb_alloc() places each TranslationBlock header in the code
buffer immediately before the host code it describes, aligned to the icache
line, and the header's tc.ptr points at that code. So a 64-byte-aligned
offset whose u64 at +40 (tc.ptr) equals its own address plus a small constant
is a header. The constant is found, not assumed: every aligned offset votes
its (tc.ptr - own address) and the mode wins; it must be the header size
rounded up to 64 (192 for the layout below). A sample's host address is then
mapped to the header whose [tc.ptr, tc.ptr + tc.size) holds it.

TranslationBlock layout (include/exec/translation-block.h, aarch64, XBOX;
unchanged from a593d8eb85 to c91697f116):
    0 pc   8 cs_base   16 flags u32   20 cflags u32   24 size u16 (guest
    bytes)   26 icount u16   32 ihash   40 tc.ptr   48 tc.size   56 page_next[2]
    72 page_addr[2]   ...   160 exec_count u32   164 tier u8
tb->pc is stored even under CF_PCREL (translate-all.c: "Always set PC for hint
recording").

Self-checks (printed; a FAIL voids the table):
  - the delta mode is 192 and holds >= 95% of the headers found;
  - the headers' pcs include the tier-1 promote pcs logged in the session's
    logcat, when there are any (a known-answer check on the pc field);
  - mapped share: JIT samples that land inside some TB. Samples outside every
    TB are the prologue/epilogue or code the dump no longer holds (a tb_flush
    between sample and dump; the logcat's "buffer full" line says whether one
    happened). Reported, not hidden.

The dump is taken after the records, so a TB invalidated and retranslated in
between is still in the buffer at its old address with CF_INVALID set (the
buffer is only reused after a flush): the sample still maps to the code that
ran. Retranslations are counted as extra headers with the same (pc, flags).
"""
import argparse
import bisect
import collections
import glob
import gzip
import os
import re
import subprocess
import sys

import numpy as np

NDK = sorted(glob.glob(os.path.expanduser("~/Android/Sdk/ndk/*")))[-1]
SP = NDK + "/simpleperf/bin/linux/x86_64/simpleperf"
CF_INVALID = 0x4000
CF_TIER1 = 0x80000
CF_SUPERBLOCK = 0x100000
HDR = 192


def load_headers(d):
    tbs = []  # (code_start, code_size, pc, flags, cflags, gsize, icount, page0, exec_count, tier)
    deltas = collections.Counter()
    for f in sorted(glob.glob(os.path.join(d, "codebuf-*.bin.gz"))):
        base = int(re.search(r"codebuf-([0-9a-f]+)", f).group(1), 16)
        buf = gzip.open(f).read()
        n = len(buf) // 64 * 64
        a = np.frombuffer(buf[:n], dtype=np.uint64).reshape(-1, 8)  # one 64-byte line per row
        own = base + np.arange(a.shape[0], dtype=np.uint64) * np.uint64(64)
        # tc.ptr is word 5 of the line the header starts on
        rel = a[:, 5].astype(np.int64) - own.astype(np.int64)
        small = (rel > 0) & (rel <= 1024)
        deltas.update(rel[small].tolist())
        idx = np.nonzero(rel == HDR)[0]
        idx = idx[idx + 3 < a.shape[0]]
        for i in idx.tolist():
            off = i * 64
            w = buf[off:off + HDR]
            pc = int.from_bytes(w[0:8], "little")
            flags = int.from_bytes(w[16:20], "little")
            cflags = int.from_bytes(w[20:24], "little")
            gsize = int.from_bytes(w[24:26], "little")
            icount = int.from_bytes(w[26:28], "little")
            tcptr = int.from_bytes(w[40:48], "little")
            tcsize = int.from_bytes(w[48:56], "little")
            page0 = int.from_bytes(w[72:80], "little")
            execc = int.from_bytes(w[160:164], "little")
            tier = w[164]
            if not (0 < tcsize < 1 << 20) or gsize > 1 << 16:
                continue
            tbs.append((tcptr, tcsize, pc, flags, cflags, gsize, icount, page0, execc, tier))
    tbs.sort()
    return tbs, deltas


def jit_samples(data, tid):
    p = subprocess.Popen([SP, "report-sample", "-i", data], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, text=True)
    per_tid = collections.Counter()
    ips = collections.defaultdict(list)
    total = collections.Counter()
    cur = va = None
    for line in p.stdout:
        s = line.strip()
        if s.startswith("thread_id:"):
            cur = s.split()[1]
            total[cur] += 1
        elif s.startswith("vaddr_in_file:"):
            va = s.split()[1]
        elif s.startswith("file:"):
            f = s.split(None, 1)[1] if len(s.split()) > 1 else ""
            if f == "unknown" or f.startswith("[anon") or f.startswith("//anon") or "memfd" in f:
                per_tid[cur] += 1
                ips[cur].append(int(va, 16))
    p.wait()
    if tid is None:
        tid = per_tid.most_common(1)[0][0]
    return tid, ips[tid], total[tid]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--tid")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--data", default="rec-on.data")
    a = ap.parse_args()

    tbs, deltas = load_headers(a.dir)
    nh = len(tbs)
    mode, mode_n = deltas.most_common(1)[0] if deltas else (None, 0)
    hdr_share = mode_n / max(1, sum(n for d, n in deltas.items() if n > 100))
    print(f"headers: {nh}; delta mode {mode} ({mode_n}); share of frequent deltas {100 * hdr_share:.1f}%  "
          f"[{'ok' if mode == HDR and hdr_share >= 0.95 else 'FAIL'}]")
    if not tbs:
        sys.exit("no TB headers found")

    # known-answer check: tier-1 promote pcs from the session logcat
    lc = os.path.join(a.dir, "logcat.txt")
    promo = set()
    if os.path.exists(lc):
        for line in open(lc, errors="replace"):
            m = re.search(r"hakuX-tier1.*(?:promote|consume) #\d+: pc=0x([0-9a-f]+)", line)
            if m:
                promo.add(int(m.group(1), 16))
        flush = sum(1 for line in open(lc, errors="replace") if "buffer full" in line)
        print(f"logcat: {flush} 'buffer full' lines (a code-buffer flush voids old headers)")
    pcs = {t[2] & 0xffffffff for t in tbs}
    if promo:
        hit = len(promo & pcs)
        print(f"known-answer: {hit} of {len(promo)} tier-1 promote pcs are header pcs  "
              f"[{'ok' if hit >= 0.8 * len(promo) else 'FAIL'}]")

    starts = [t[0] for t in tbs]
    tid, ips, nsamp = jit_samples(os.path.join(a.dir, a.data), a.tid)
    by_tb = collections.Counter()
    unmapped = 0
    for ip in ips:
        i = bisect.bisect_right(starts, ip) - 1
        if i >= 0 and ip < tbs[i][0] + tbs[i][1]:
            by_tb[i] += 1
        else:
            unmapped += 1
    nj = len(ips)
    print(f"tid {tid}: {nsamp} samples, {nj} JIT ({100 * nj / max(1, nsamp):.1f}%), "
          f"mapped {nj - unmapped} ({100 * (nj - unmapped) / max(1, nj):.1f}% of JIT)")

    # aggregate by guest pc (all translations of one pc), by 4 KB page, by 64 KB
    by_pc = collections.Counter()
    ntrans = collections.Counter()
    for t in tbs:
        ntrans[(t[2], t[3])] += 1
    for i, n in by_tb.items():
        by_pc[tbs[i][2]] += n
    by_pg = collections.Counter()
    by_64k = collections.Counter()
    for pc, n in by_pc.items():
        by_pg[pc >> 12] += n
        by_64k[pc >> 16] += n
    mapped = max(1, nj - unmapped)
    kern = sum(n for pc, n in by_pc.items() if pc >= 0x80000000)
    print(f"guest kernel (pc >= 0x80000000): {100 * kern / mapped:.1f}% of mapped JIT samples; title {100 - 100 * kern / mapped:.1f}%")

    def cum(counter):
        acc, out = 0, {}
        for i, (_, n) in enumerate(counter.most_common(), 1):
            acc += n
            for q in (0.5, 0.8, 0.9):
                if q not in out and acc >= q * mapped:
                    out[q] = i
        return ", ".join(f"{int(q * 100)}% in {out[q]}" for q in sorted(out))
    print(f"spread: {len(by_pc)} guest pcs ({cum(by_pc)}); {len(by_pg)} 4 KB pages ({cum(by_pg)}); "
          f"{len(by_64k)} 64 KB ranges ({cum(by_64k)})")

    print(f"\ntop 64 KB guest ranges")
    for r, n in by_64k.most_common(15):
        print(f"  {r << 16:08x}-{(r << 16) + 0xffff:08x}  {n:6d}  {100 * n / mapped:5.1f}%")
    print(f"\ntop 4 KB guest pages")
    for r, n in by_pg.most_common(20):
        print(f"  {r << 12:08x}  {n:6d}  {100 * n / mapped:5.1f}%")
    print(f"\ntop guest pcs (tb pc: samples, share, guest bytes, insns, translations in buffer, invalid, tier1)")
    info = {}
    for t in tbs:
        k = t[2]
        s = info.setdefault(k, [0, 0, 0, t[5], t[6]])
        s[0] += 1
        s[1] += bool(t[4] & CF_INVALID)
        s[2] += bool(t[4] & CF_TIER1) or t[9] > 0
    for pc, n in by_pc.most_common(a.top):
        s = info[pc]
        print(f"  {pc:08x}  {n:6d}  {100 * n / mapped:5.2f}%  {s[3]:4d} B  {s[4]:3d} insn  x{s[0]}  inv {s[1]}  t1 {s[2]}")

    # retranslation in the buffer: headers per (pc, flags)
    multi = [(k, n) for k, n in ntrans.items() if n > 1]
    extra = sum(n - 1 for _, n in multi)
    inv = sum(1 for t in tbs if t[4] & CF_INVALID)
    print(f"\nbuffer: {nh} headers, {len(ntrans)} distinct (pc, flags); {extra} extra translations over "
          f"{len(multi)} keys; {inv} carry CF_INVALID")
    bypage = collections.Counter()
    for (pc, _), n in multi:
        bypage[pc >> 12] += n - 1
    print("most-retranslated guest pages (extra translations)")
    for pg, n in bypage.most_common(12):
        print(f"  {pg << 12:08x}  {n}")


if __name__ == "__main__":
    main()
