#!/usr/bin/env python3
"""lane.pmucounters (#433): read [pmu433] lines.

  pmuread.py --controls FILE...   control kernels against their expectations
  pmuread.py LOGCAT [--after RE] [--secs N] [--slow-ms 34.5]
                                  the slice table: whole window, good slices,
                                  slow slices, and slow minus good
  pmuread.py --samples LOGCAT [--apk APK] [--after RE]
                                  R2: the sampled event's top TBs and host
                                  functions, by category
  pmuread.py --selftest           the reader on synthetic lines, including a
                                  control that must FAIL

Line formats (hakux-pmu.c.inc):
  [pmu433] ctl=NAME units=N ms=M cpu=A-B p=PMU g0=RUN:v,... g1=... g2=...
  [pmu433] s=N dt=MS fr=N fmax=MS tclk=MS cs=N mig=N cpus=HEX p=PMU g0=... ...

Groups (raw PMUv3 events; every group carries cycles and instructions):
  g0 cyc ins sfe sbe brr brm bis
  g1 cyc ins l1i itl l1d dtl l2d
  g2 cyc ins iwk dwk l1ia l1da l3d

Only one group holds the cycle counter at a time, so per PMU the sum of the
three groups' cyc (ins) is the thread's user cycles (instructions) on that
core type, and a ratio of two events inside one group is exact over that
group's running time. No scaling is applied anywhere.
"""
import re
import sys

GROUPS = [
    ["cyc", "ins", "sfe", "sbe", "brr", "brm", "bis"],
    ["cyc", "ins", "l1i", "itl", "l1d", "dtl", "l2d"],
    ["cyc", "ins", "iwk", "dwk", "l1ia", "l1da", "l3d"],
]

# Expectations, written before any device run (NOTES.md "R0 controls").
# (name, metric, lo, hi, cores) -- cores: which PMUs the bound applies to,
# by a substring of the PMU name, or None for every core type.
BIG = ("x3", "a715", "a710", "a78", "x2", "x1")
EXPECT = [
    ("alu1", "ipc", 0.95, 1.12, None),            # 66 instr / 64 cycles
    ("mul1", "ipc", 0.45, 0.58, BIG),             # MUL latency 2
    ("ind1", "brm/unit", 0.0, 0.01, None),        # one target: predicted
    ("ind8", "brm/unit", 0.75, 0.95, None),       # 7/8 of random targets
    ("chase16k", "l1d/unit", 0.0, 0.02, None),    # fits L1D
    ("chase64m", "l1d/unit", 0.9, 1.1, None),     # every load misses L1D
    ("chase64m", "l2d/unit", 0.85, 1.1, BIG),     # and L2 (64 MB >> L2)
    ("chase64m", "sbe/cyc", 0.8, 1.0, BIG),       # back-end bound
    ("code16k", "l1i/unit", 0.0, 0.05, None),     # fits L1I
    ("code512k", "l1i/unit", 0.8, 1.2, BIG),      # one line per block
    ("code512k", "sfe/cyc", 0.4, 1.0, BIG),       # front-end bound
]

TOKEN = re.compile(r"(\w+)=(\S+)")
TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)")


def parse(line):
    """-> (head dict, {pmu: [[group values] x3, [run ms] x3]}) or None."""
    i = line.find("[pmu433] ")
    if i < 0:
        return None
    body = line[i + 9:]
    parts = re.split(r" p=", body)
    head = dict(TOKEN.findall(parts[0]))
    pmus = {}
    for part in parts[1:]:
        name, _, rest = part.partition(" ")
        vals, runs = [None] * 3, [0.0] * 3
        for g, val in TOKEN.findall(rest):
            if not g.startswith("g"):
                continue
            k = int(g[1:])
            run, _, nums = val.partition(":")
            runs[k] = float(run)
            # `x`: an event this core refused (its slot counted ins)
            vals[k] = [None if x == "x" else int(x)
                       for x in nums.split(",")]
        pmus[name] = (vals, runs)
    ts = TS.match(line)
    head["_ts"] = ts.group(1) if ts else ""
    return head, pmus


def add(acc, vals):
    for g in range(3):
        if vals[g] is None:
            continue
        if acc[g] is None:
            acc[g] = [0] * len(vals[g])
        acc[g] = [None if a is None or b is None else a + b
                  for a, b in zip(acc[g], vals[g])]
    return acc


def ev(vals, name):
    """Event `name` and the cycles/instructions of its own group."""
    for g, names in enumerate(GROUPS):
        if name in names[2:] and vals[g] is not None:
            v = dict(zip(names, vals[g]))
            if v[name] is None:
                return None, None, None
            return v[name], v["cyc"], v["ins"]
    return None, None, None


def totals(vals):
    cyc = sum(v[0] for v in vals if v)
    ins = sum(v[1] for v in vals if v)
    return cyc, ins


def metric(vals, m, units):
    num, _, den = m.partition("/")
    if m == "ipc":
        cyc, ins = totals(vals)
        return ins / cyc if cyc else None
    x, cyc, ins = ev(vals, num)
    if x is None:
        return None
    base = {"unit": units, "cyc": cyc, "ins": ins, "kins": ins / 1000.0}[den]
    return x / base if base else None


def controls(paths):
    rows, bad = [], 0
    for path in paths:
        for line in open(path, errors="replace"):
            p = parse(line)
            if not p or "ctl" not in p[0]:
                continue
            head, pmus = p
            for pmu, (vals, runs) in pmus.items():
                for name, m, lo, hi, cores in EXPECT:
                    if name != head["ctl"]:
                        continue
                    if cores and not any(c in pmu.lower() for c in cores):
                        continue
                    v = metric(vals, m, int(head["units"]))
                    ok = v is not None and lo <= v <= hi
                    bad += not ok
                    rows.append((path.split("/")[-1], pmu, name, m, v, lo, hi,
                                 "PASS" if ok else "FAIL", head.get("cpu")))
    print("| file | pmu | control | metric | read | expected | verdict | cpu |")
    print("|---|---|---|---|---|---|---|---|")
    for f, pmu, name, m, v, lo, hi, verdict, cpu in rows:
        vs = "none" if v is None else "%.3f" % v
        print("| %s | %s | %s | %s | %s | %g-%g | %s | %s |"
              % (f, pmu, name, m, vs, lo, hi, verdict, cpu))
    print("\n%d of %d expectations failed" % (bad, len(rows)))
    return 1 if bad or not rows else 0


ROWS = [("IPC", "ipc"), ("stall_fe %", "sfe/cyc"), ("stall_be %", "sbe/cyc"),
        ("br mispred /kins", "brm/kins"), ("br retired /kins", "brr/kins"),
        ("indirect spec /kins", "bis/kins"), ("L1I refill /kins", "l1i/kins"),
        ("L1I TLB refill /kins", "itl/kins"), ("L1D refill /kins", "l1d/kins"),
        ("L1D TLB refill /kins", "dtl/kins"), ("L2D refill /kins", "l2d/kins"),
        ("ITLB walk /kins", "iwk/kins"), ("DTLB walk /kins", "dwk/kins"),
        ("L3D refill /kins", "l3d/kins")]


def slices(path, after=None, secs=None, slow_ms=34.5):
    started = after is None
    rows = []
    for line in open(path, errors="replace"):
        if not started:
            started = re.search(after, line) is not None
            continue
        p = parse(line)
        if p and "s" in p[0] and "dt" in p[0]:
            rows.append(p)
    if secs:
        acc, keep = 0.0, []
        for r in rows:
            if acc >= secs * 1000:
                break
            keep.append(r)
            acc += float(r[0]["dt"])
        rows = keep
    if not rows:
        print("no slice lines")
        return 1
    classes = {"all": [], "good": [], "slow": []}
    for head, pmus in rows:
        dt, fr = float(head["dt"]), int(head["fr"])
        classes["all"].append((head, pmus))
        slow = fr == 0 or dt / fr > slow_ms
        classes["slow" if slow else "good"].append((head, pmus))
    # PMUs by share of running time
    share = {}
    for head, pmus in rows:
        for pmu, (vals, runs) in pmus.items():
            share[pmu] = share.get(pmu, 0) + sum(runs)
    tot = sum(share.values()) or 1
    print("core-type share of counted time: " + ", ".join(
        "%s %.1f%%" % (k, 100 * v / tot) for k, v in
        sorted(share.items(), key=lambda kv: -kv[1])))
    for pmu in sorted(share, key=lambda k: -share[k]):
        if share[pmu] / tot < 0.05:
            continue
        print("\n### %s\n" % pmu)
        stats = {}
        for cls, rs in classes.items():
            acc = [None] * 3
            dt = fr = tclk = mig = 0.0
            for head, pmus in rs:
                dt += float(head["dt"])
                fr += int(head["fr"])
                tclk += float(head["tclk"])
                mig += int(head["mig"])
                if pmu in pmus:
                    add(acc, pmus[pmu][0])
            cyc, ins = totals(acc)
            st = {"n": len(rs), "fps": 1000 * fr / dt if dt else 0,
                  "oncpu %": 100 * tclk / dt if dt else 0,
                  "mig /s": 1000 * mig / dt if dt else 0,
                  "Mins /frame": ins / fr / 1e6 if fr else None,
                  "Mcyc /frame": cyc / fr / 1e6 if fr else None}
            for label, m in ROWS:
                v = metric(acc, m, 1)
                if v is not None and "%" in label:
                    v *= 100
                st[label] = v
            stats[cls] = st
        keys = list(stats["all"].keys())
        print("| | all | good | slow | slow - good |")
        print("|---|---|---|---|---|")
        for k in keys:
            vals = [stats[c][k] for c in ("all", "good", "slow")]
            g, s = vals[1], vals[2]
            diff = (s - g) if (g is not None and s is not None) else None
            print("| %s | %s |" % (k, " | ".join(
                "-" if v is None else ("%d" % v if k == "n" else "%.3g" % v)
                for v in vals + [diff])))
    return 0



# Host functions by category (R2). First match wins; names from libxemu.so.
CATEGORIES = [
    ("dispatch", r"^(helper_lookup_tb_ptr|cpu_exec_loop|cpu_exec\b|cpu_exec_setjmp"
                 r"|cpu_tb_exec|tb_lookup|tb_htable_lookup|tb_add_jump"
                 r"|cpu_handle_|jc425|rr425|hakux_tlb68|tier1_|qht_lookup)"),
    ("softmmu", r"(^tlb_|_mmu$|^do_ld|^do_st|^probe_access|^io_|^mmu_lookup"
                r"|^victim_tlb|^cpu_ld|^cpu_st|^helper_ld|^helper_st"
                r"|^address_space_|^memory_region_|^flatview_)"),
    ("translation", r"^(tcg_|gen_|disas_|translator_|tb_gen_code|i386_tr_"
                    r"|x86_|liveness_|reachable_|la_)"),
    ("helper", r"^helper_"),
]


def category(name):
    for cat, pat in CATEGORIES:
        if re.search(pat, name):
            return cat
    return "other"


def samples(path, apk=None, after=None):
    """Aggregate smp / smpj / smph lines over every window after `after`."""
    started = after is None
    tot = {}
    tbs, host = {}, {}
    for line in open(path, errors="replace"):
        if not started:
            started = re.search(after, line) is not None
            continue
        i = line.find("[pmu433] smp")
        if i < 0:
            continue
        kind, _, rest = line[i + 9:].partition(" ")
        kv = dict(TOKEN.findall(rest))
        if kind == "smp":
            for k in ("n", "lost", "jit", "stub", "host", "drop"):
                tot[k] = tot.get(k, 0) + int(kv[k])
            tot["ev"] = kv["ev"]
        elif kind == "smpj":
            key = (kv["pc"], kv["phys"])
            t = tbs.setdefault(key, [0, kv["ic"], kv["sz"], kv["tier"]])
            t[0] += int(kv["n"])
        elif kind == "smph":
            key = (kv["lib"], int(kv["off"], 16))
            host[key] = host.get(key, 0) + int(kv["n"])
    if not tot:
        print("no smp lines")
        return 1
    n = tot["n"] or 1
    print("event %s: %d samples, lost %d, dropped %d" % (
        tot["ev"], tot["n"], tot["lost"], tot["drop"]))
    print("jit (in a TB) %.1f%%, dispatch stub %.1f%%, host code %.1f%%" % (
        100 * tot["jit"] / n, 100 * tot["stub"] / n, 100 * tot["host"] / n))
    print("(top-20 tables per window: a row's share is a lower bound)\n")
    print("| rank | guest pc | phys | icount | host bytes | tier | samples "
          "| % of all |")
    print("|---|---|---|---|---|---|---|---|")
    for r, ((pc, phys), (cnt, ic, sz, tier)) in enumerate(
            sorted(tbs.items(), key=lambda kv: -kv[1][0])[:20]):
        print("| %d | %s | %s | %s | %s | %s | %d | %.2f |"
              % (r, pc, phys, ic, sz, tier, cnt, 100.0 * cnt / n))
    funcs = {}
    if apk:
        import zipfile
        sys.path.insert(0, __file__.rsplit("/", 1)[0])
        import elfsyms
        z = zipfile.ZipFile(apk)
        cache = {}
        for (lib, off), cnt in host.items():
            if lib not in cache:
                mem = [m for m in z.namelist()
                       if m.endswith("/" + lib) and "arm64" in m]
                if mem:
                    fs = elfsyms.functions(z.read(mem[0]))
                    cache[lib] = (fs, [f[0] for f in fs])
                else:
                    cache[lib] = None
            if cache[lib]:
                fs, starts = cache[lib]
                name = elfsyms.name_at(fs, starts, off).split("+")[0]
            else:
                name = "%s+0x%x" % (lib, off)
            funcs[name] = funcs.get(name, 0) + cnt
    else:
        for (lib, off), cnt in host.items():
            key = "%s+0x%x" % (lib, off)
            funcs[key] = funcs.get(key, 0) + cnt
    cats = {}
    for name, cnt in funcs.items():
        c = category(name)
        cats[c] = cats.get(c, 0) + cnt
    cats["dispatch stub (code buffer)"] = tot["stub"]
    cats["jit (TB code)"] = tot["jit"]
    print("\n| host category | samples | % of all |\n|---|---|---|")
    for c, cnt in sorted(cats.items(), key=lambda kv: -kv[1]):
        print("| %s | %d | %.2f |" % (c, cnt, 100.0 * cnt / n))
    print("\n| rank | host function | category | samples | % of all |")
    print("|---|---|---|---|---|")
    for r, (name, cnt) in enumerate(sorted(funcs.items(),
                                           key=lambda kv: -kv[1])[:20]):
        print("| %d | %s | %s | %d | %.2f |"
              % (r, name, category(name), cnt, 100.0 * cnt / n))
    return 0


def selftest():
    import os
    import tempfile
    # alu1 at IPC 1.03 (PASS), ind8 at 0.40 mispredicts/unit (must FAIL)
    lines = [
        "[pmu433] ctl=alu1 units=1600000000 ms=520 cpu=7-7 p=armv9_cortex_x3"
        " g0=170.0:1650000000,1700000000,1000,2000,26000000,10,5"
        " g1=170.0:1650000000,1700000000,1,1,1,1,1"
        " g2=170.0:1650000000,1700000000,1,1,1,1,1",
        "[pmu433] ctl=ind8 units=100000000 ms=400 cpu=7-7 p=armv9_cortex_x3"
        " g0=130.0:500000000,350000000,1,1,100000000,40000000,100000000"
        " g1=130.0:500000000,350000000,1,1,1,1,1"
        " g2=130.0:500000000,350000000,1,1,1,1,1",
    ]
    fd, path = tempfile.mkstemp()
    os.write(fd, ("\n".join(lines) + "\n").encode())
    os.close(fd)
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = controls([path])
    out = buf.getvalue()
    os.unlink(path)
    ok = rc == 1 and "alu1 | ipc | 1.030 | 0.95-1.12 | PASS" in out \
        and "ind8 | brm/unit | 0.400 | 0.75-0.95 | FAIL" in out
    # slices: one good (30 frames) and one slow (20 frames) slice
    sl = [
        "10-05 12:00:01.000 1 2 W hakuX: [pmu433] s=0 dt=1000 fr=30 fmax=34"
        " tclk=900.0 cs=10 mig=0 cpus=80 p=x3 g0=300:1000,1500,100,300,150,3,10"
        " g1=300:1000,1500,10,1,20,2,5 g2=300:1000,1500,1,1,400,500,1",
        "10-05 12:00:02.000 1 2 W hakuX: [pmu433] s=1 dt=1000 fr=20 fmax=60"
        " tclk=950.0 cs=10 mig=0 cpus=80 p=x3 g0=310:1000,1000,100,500,100,6,10"
        " g1=310:1000,1000,10,1,40,2,15 g2=310:1000,1000,1,1,300,400,1",
    ]
    fd, path = tempfile.mkstemp()
    os.write(fd, ("\n".join(sl) + "\n").encode())
    os.close(fd)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc2 = slices(path)
    out2 = buf.getvalue()
    os.unlink(path)
    ok2 = rc2 == 0 and "| IPC | 1.25 | 1.5 | 1 | -0.5 |" in out2 \
        and "| stall_be % | 40 | 30 | 50 | 20 |" in out2
    # samples: two windows; one TB in both must sum, categories must sort
    sm = [
        "[pmu433] smp w=0 ev=0x24 per=1000 n=100 lost=0 jit=60 stub=10"
        " host=30 drop=0",
        "[pmu433] smpj w=0 r=0 n=40 pc=00011000 phys=00011000 ic=12 sz=300"
        " tier=0",
        "[pmu433] smph w=0 r=0 n=30 lib=libxemu.so off=451f40 hint=?",
        "[pmu433] smp w=1 ev=0x24 per=1000 n=100 lost=0 jit=70 stub=0"
        " host=30 drop=0",
        "[pmu433] smpj w=1 r=0 n=50 pc=00011000 phys=00011000 ic=12 sz=300"
        " tier=0",
    ]
    fd, path = tempfile.mkstemp()
    os.write(fd, ("\n".join(sm) + "\n").encode())
    os.close(fd)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc3 = samples(path)
    out3 = buf.getvalue()
    os.unlink(path)
    ok3 = rc3 == 0 and "jit (in a TB) 65.0%, dispatch stub 5.0%" in out3 \
        and "| 0 | 00011000 | 00011000 | 12 | 300 | 0 | 90 | 45.00 |" in out3 \
        and category("helper_lookup_tb_ptr") == "dispatch" \
        and category("do_ld4_mmu") == "softmmu" \
        and category("helper_fadd_ST0_FT0") == "helper" \
        and category("tcg_optimize") == "translation"
    print(out)
    print(out2)
    print(out3)
    print("selftest:", "PASS" if ok and ok2 and ok3 else "FAIL")
    return 0 if ok and ok2 and ok3 else 1


def main(argv):
    if argv[1:2] == ["--selftest"]:
        return selftest()
    if argv[1:2] == ["--samples"]:
        apk = after = None
        rest = argv[3:]
        while rest:
            flag, val, rest = rest[0], rest[1], rest[2:]
            if flag == "--apk":
                apk = val
            elif flag == "--after":
                after = val
        return samples(argv[2], apk, after)
    if argv[1:2] == ["--controls"]:
        return controls(argv[2:])
    path, after, secs, slow = argv[1], None, None, 34.5
    rest = argv[2:]
    while rest:
        flag, val, rest = rest[0], rest[1], rest[2:]
        if flag == "--after":
            after = val
        elif flag == "--secs":
            secs = float(val)
        elif flag == "--slow-ms":
            slow = float(val)
    return slices(path, after, secs, slow)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
