#!/usr/bin/env python3
"""What the vCPU's JIT samples execute, by host-instruction class (#507, lane.vcpuplan).

    jitmix.py <capture_gta.sh session dir> [--data rec-on.data] [--cover 0.95]

Reads a session that docs/lanes/gta482/capture_gta.sh wrote (maps.txt,
codebuf-<start>.bin.gz, rec-on.data) and reuses gta482/tbmap.py to map the
vCPU thread's JIT samples to TranslationBlocks. It then disassembles the TBs
that hold --cover of the mapped samples (NDK llvm-objdump) and classifies every
host instruction:

  env_ld / env_st   load/store off x19 (env) at a non-negative offset: guest
                    register globals, cc_op/cc_src/cc_dst, the x87 stack
                    (fpregs[fpstt]), fpstt, xmm registers
  irq_chk           load off x19 at a negative offset that is not an LDP:
                    the TB-entry exit-request check (neg.icount_decr)
  tlb               LDP off x19 at a negative offset (CPUTLBDescFast mask/table,
                    one per softmmu compare) and immediate-offset loads off
                    x16/x17 (the CPUTLBEntry comparator and addend)
  xbox_fp           anything using x26/x27 as a base or CBZ/CBNZ on x26: the
                    per-TB preamble and the XBOX load fast path
  guest_mem         register-offset load/store ([xA, xB...]): the guest access
                    itself, after the TLB or the fast path
  fp                scalar FP (f* on s/d registers, scvtf/ucvtf/fcvtz*): x87
                    under fp_jit and nothing else in guest code
  simd              instructions on v registers (gvec integer SSE/MMX)
  call              bl/blr: a helper call (the helper's own time is outside
                    the JIT bucket)
  branch            b, b.cond, cbz/cbnz, tbz/tbnz, br, ret
  alu               everything else

Two weightings, both printed:
  static   each TB's class counts x that TB's samples / its host instructions
           (what the hot code is made of, free of skid)
  at-ip    the class of the instruction at each sample address (skid moves a
           sample onto the instruction after a stall, so read it as a check)

Offline; reads files only. The session is gta482's s1 (GTA SA alley, Thor,
build a593d8eb85, fp_jit on).
"""
import argparse
import bisect
import collections
import gzip
import glob
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gta482"))
import tbmap  # noqa: E402

NDKBIN = os.path.join(os.path.dirname(tbmap.NDK + "/"),
                      "toolchains/llvm/prebuilt/linux-x86_64/bin")
OBJCOPY = os.path.join(NDKBIN, "llvm-objcopy")
OBJDUMP = os.path.join(NDKBIN, "llvm-objdump")

CLASSES = ["env_ld", "env_st", "irq_chk", "tlb", "xbox_fp", "guest_mem",
           "fp", "simd", "call", "branch", "alu"]
BRANCH = {"b", "br", "ret", "cbz", "cbnz", "tbz", "tbnz"}
LOADS = ("ldr", "ldur", "ldp", "ldrb", "ldrh", "ldrsb", "ldrsh", "ldrsw",
         "ldurb", "ldurh", "ldursb", "ldursh", "ldursw", "ldar", "ldapr", "ldxr")
STORES = ("str", "stur", "stp", "strb", "strh", "sturb", "sturh", "stlr", "stxr")


def classify(mn, ops):
    base = re.search(r"\[(\w+)(?:,\s*([^\]]+))?\]", ops)
    if mn in BRANCH or mn.startswith("b."):
        if mn in ("cbz", "cbnz") and ops.startswith("x26"):
            return "xbox_fp"
        return "branch"
    if mn in ("bl", "blr"):
        return "call"
    if base and (mn in LOADS or mn in STORES):
        b, rest = base.group(1), (base.group(2) or "")
        neg = rest.strip().startswith("#-")
        if b in ("x26", "x27"):
            return "xbox_fp"
        if b == "x19":
            if neg:
                return "tlb" if mn == "ldp" else "irq_chk"
            return "env_ld" if mn in LOADS else "env_st"
        if b in ("x16", "x17") and rest.strip().startswith("#"):
            return "tlb"
        if rest and re.match(r"[xw]\d+", rest.strip()):
            return "guest_mem"
        if re.search(r"\b[qdsbh]\d+\b", ops.split("[")[0]):
            return "env_ld" if mn in LOADS else "env_st"  # FP spill/fill
        return "guest_mem"
    if " v" in " " + ops or re.search(r"\bv\d+\.", ops):
        return "simd"
    if (mn.startswith("f") or mn in ("scvtf", "ucvtf")) and re.search(r"\b[sd]\d+\b", ops):
        return "fp"
    if "x26" in ops.split(",")[1:2] or ops.startswith("x26"):
        return "xbox_fp"
    return "alu"


def disasm(blob):
    with tempfile.TemporaryDirectory() as t:
        raw, elf = os.path.join(t, "code.bin"), os.path.join(t, "code.o")
        open(raw, "wb").write(blob)
        subprocess.run([OBJCOPY, "-I", "binary", "-O", "elf64-littleaarch64",
                        "--rename-section=.data=.text,code", raw, elf], check=True)
        out = subprocess.run([OBJDUMP, "-d", "--no-show-raw-insn", "--triple=aarch64",
                              "--mattr=+v8.2a,+fp-armv8,+neon,+lse,+rcpc", elf],
                             check=True, capture_output=True, text=True).stdout
    ins = {}
    for line in out.splitlines():
        m = re.match(r"\s*([0-9a-f]+):\s+(\S+)\s*(.*)$", line)
        if m:
            ins[int(m.group(1), 16)] = (m.group(2), m.group(3).split("//")[0].strip())
    return ins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--data", default="rec-on.data")
    ap.add_argument("--cover", type=float, default=0.95)
    ap.add_argument("--dump", type=int, default=0, help="annotate the N hottest TBs")
    a = ap.parse_args()

    tbs, _ = tbmap.load_headers(a.dir)
    starts = [t[0] for t in tbs]
    tid, ips, nsamp = tbmap.jit_samples(os.path.join(a.dir, a.data), None)
    by_tb = collections.Counter()
    ip_by_tb = collections.defaultdict(list)
    for ip in ips:
        i = bisect.bisect_right(starts, ip) - 1
        if i >= 0 and ip < tbs[i][0] + tbs[i][1]:
            by_tb[i] += 1
            ip_by_tb[i].append(ip)
    mapped = sum(by_tb.values())
    print(f"tid {tid}: {nsamp} samples, {len(ips)} JIT, {mapped} mapped to a TB")

    bufs = []
    for f in sorted(glob.glob(os.path.join(a.dir, "codebuf-*.bin.gz"))):
        base = int(re.search(r"codebuf-([0-9a-f]+)", f).group(1), 16)
        bufs.append((base, gzip.open(f).read()))

    def code(start, size):
        for base, buf in bufs:
            if base <= start and start + size <= base + len(buf):
                return buf[start - base:start - base + size]
        return None

    chosen, acc = [], 0
    for i, n in by_tb.most_common():
        if acc >= a.cover * mapped:
            break
        chosen.append(i)
        acc += n
    blob, offs = bytearray(), {}
    for i in chosen:
        c = code(tbs[i][0], tbs[i][1])
        if c is None:
            continue
        offs[i] = len(blob)
        blob += c
        blob += b"\0" * ((-len(blob)) % 4)
    ins = disasm(bytes(blob))

    static = collections.Counter()
    atip = collections.Counter()
    host_n = guest_n = 0.0
    tb_cls = {}
    for i in chosen:
        if i not in offs:
            continue
        o, size = offs[i], tbs[i][1]
        cls = collections.Counter()
        for addr in range(o, o + size, 4):
            if addr in ins:
                cls[classify(*ins[addr])] += 1
        tot = sum(cls.values()) or 1
        tb_cls[i] = cls
        w = by_tb[i]
        for k, v in cls.items():
            static[k] += w * v / tot
        host_n += w * tot
        guest_n += w * max(1, tbs[i][6])
        for ip in ip_by_tb[i]:
            addr = o + (ip - tbs[i][0]) // 4 * 4
            if addr in ins:
                atip[classify(*ins[addr])] += 1
    cov = sum(by_tb[i] for i in offs)
    print(f"disassembled {len(offs)} TBs holding {cov} samples "
          f"({100 * cov / max(1, mapped):.1f}% of mapped JIT samples)")
    print(f"sample-weighted host insns per TB {host_n / max(1, cov):.1f}, guest insns per TB "
          f"{guest_n / max(1, cov):.1f}, host/guest {host_n / max(1, guest_n):.2f}")
    st, at = sum(static.values()) or 1, sum(atip.values()) or 1
    print(f"\n{'class':10s} {'static %':>9s} {'at-ip %':>8s}")
    for k in CLASSES:
        print(f"{k:10s} {100 * static[k] / st:9.1f} {100 * atip[k] / at:8.1f}")

    # per-TB counts of guest memory accesses and how they are served
    n_tlb = n_fp = n_call = n_x87 = 0.0
    for i in offs:
        o, size = offs[i], tbs[i][1]
        w = by_tb[i] / cov
        for addr in range(o, o + size, 4):
            if addr not in ins:
                continue
            mn, ops = ins[addr]
            if mn == "ldp" and ops.find("[x19, #-") >= 0:
                n_tlb += w
            if mn in ("cbz", "cbnz") and ops.startswith("x26"):
                n_fp += w
            if mn in ("bl", "blr"):
                n_call += w
            if classify(mn, ops) == "fp":
                n_x87 += w
    print(f"\nper executed TB (sample-weighted): softmmu TLB compares {n_tlb:.2f}, "
          f"XBOX load fast paths {n_fp:.2f}, helper calls {n_call:.2f}, scalar FP ops {n_x87:.2f}")

    # Which way did the XBOX preamble go at run time? In the per-TB preamble
    # (ldr w16,[x27,#8]; cbz; ldr w16,[x27,#0xc]; cbnz; ldr x26,[x27]; b; mov
    # w26,#0) samples on `ldr x26` / its `b` mean the fast path was armed;
    # samples on `mov w26, #0` mean it was off (active == 0 or cb_count > 0).
    # The same split inside each load: after `cbz x26`, samples on the
    # fast-path block (tst ... #0xfc000000 onwards) vs on the TLB LDP.
    armed = off = 0
    fp_hits = tlb_after_cbz = 0
    for i in offs:
        o, size = offs[i], tbs[i][1]
        hits = collections.Counter((ip - tbs[i][0]) // 4 * 4 for ip in ip_by_tb[i])
        seq = [(addr - o, ins[addr]) for addr in range(o, o + size, 4) if addr in ins]
        for k, (rel, (mn, ops)) in enumerate(seq[:12]):
            if mn == "ldr" and ops.startswith("x26, [x27]"):
                armed += hits.get(rel, 0) + hits.get(rel + 4, 0)
            if mn == "mov" and ops.startswith("w26, #0x0"):
                off += hits.get(rel, 0)
        for k, (rel, (mn, ops)) in enumerate(seq):
            if mn == "cbz" and ops.startswith("x26"):
                # fast-path block: the next 4 instructions (tst, b.ne, mov, b)
                fp_hits += sum(hits.get(seq[j][0], 0) for j in range(k + 1, min(k + 5, len(seq))))
    print(f"\nXBOX preamble outcome (samples): armed {armed}, off {off}; "
          f"samples inside load fast-path blocks {fp_hits}")

    # Window attribution (at-ip): every instruction belongs to one role,
    # found from the code's shape rather than one instruction's operands.
    #   preamble   the TB's first instructions up to and including `mov w26,#0`
    #              (bti hint, the XBOX active/cb_count checks)
    #   exitchk    ldur [x19,#-0x10] / tbnz / sturb [x19,#-0xc] (exit request,
    #              can_do_io)
    #   xboxchk    `cbz x26` through the instruction before the TLB LDP (the
    #              per-load fast-path test and its VRAM leg)
    #   tlb        the TLB LDP through its b.ne (mask/table, index, entry
    #              address, comparator load, addend load, page/align compare)
    #   tbexit     the EIP store ([x19,#0x20]) and the branch after it
    #   body       everything else (the guest's own work, flags, env traffic)
    roles = collections.Counter()
    for i in offs:
        o, size = offs[i], tbs[i][1]
        hits = collections.Counter((ip - tbs[i][0]) // 4 * 4 for ip in ip_by_tb[i])
        seq = [(addr - o, ins[addr]) for addr in range(o, o + size, 4) if addr in ins]
        role = {}
        for k, (rel, (mn, ops)) in enumerate(seq[:10]):
            role[rel] = "preamble"
            if mn == "mov" and ops.startswith("w26, #0x0"):
                break
        k = 0
        while k < len(seq):
            rel, (mn, ops) = seq[k]
            if mn == "ldur" and "[x19, #-0x10]" in ops:
                role[rel] = "exitchk"
                if k + 1 < len(seq):
                    role[seq[k + 1][0]] = "exitchk"
                if k + 2 < len(seq) and "[x19, #-0xc]" in seq[k + 2][1][1]:
                    role[seq[k + 2][0]] = "exitchk"
            elif mn == "sturb" and "[x19, #-0xc]" in ops:
                role.setdefault(rel, "exitchk")
            elif mn == "cbz" and ops.startswith("x26"):
                j = k
                while j < len(seq) and not (seq[j][1][0] == "ldp" and "[x19, #-" in seq[j][1][1]):
                    role[seq[j][0]] = "xboxchk"
                    j += 1
                k = j
                continue
            elif mn == "ldp" and "[x19, #-" in ops:
                j = k
                while j < len(seq):
                    role[seq[j][0]] = "tlb"
                    if seq[j][1][0] == "b.ne":
                        break
                    j += 1
                k = j + 1
                continue
            elif mn in ("str", "stur") and ops.endswith("[x19, #0x20]"):
                role[rel] = "tbexit"
                if k + 1 < len(seq) and seq[k + 1][1][0] in ("b", "br"):
                    role[seq[k + 1][0]] = "tbexit"
            k += 1
        for rel, n in hits.items():
            roles[role.get(rel, "body")] += n
    tot = sum(roles.values()) or 1
    print("\nat-ip by role (share of disassembled JIT samples):")
    for r in ("preamble", "exitchk", "xboxchk", "tlb", "tbexit", "body"):
        print(f"  {r:9s} {100 * roles[r] / tot:5.1f}%")

    fp_tbs = sum(by_tb[i] for i, c in tb_cls.items() if c["fp"])
    print(f"samples in TBs with any scalar FP op: {100 * fp_tbs / max(1, cov):.1f}%")

    # annotated listings of the hottest TBs: samples per host instruction
    for i in [j for j, _ in by_tb.most_common(a.dump) if j in offs]:
        o, size = offs[i], tbs[i][1]
        hits = collections.Counter((ip - tbs[i][0]) // 4 * 4 for ip in ip_by_tb[i])
        print(f"\n--- TB pc {tbs[i][2]:#x}: {by_tb[i]} samples, {tbs[i][6]} guest insns, "
              f"{size // 4} host insns")
        last = max(hits) if hits else 0
        for addr in range(o, min(o + size, o + last + 4 * 24), 4):
            if addr in ins:
                mn, ops = ins[addr]
                print(f"  {addr - o:5x} {hits.get(addr - o, 0):5d}  {classify(mn, ops):9s} {mn} {ops}")


if __name__ == "__main__":
    main()
