#!/usr/bin/env python3
"""lane.pmucounters (#433): read [pmu433] lines.

  pmuread.py --controls FILE...   control kernels against their expectations
  pmuread.py LOGCAT [--after RE] [--secs N] [--slow-ms 34.5]
                                  the slice table per core type: whole window,
                                  good slices, slow slices, slow minus good,
                                  and the good slices' spread
  pmuread.py --samples LOGCAT [--apk APK] [--after RE]
                                  R2: per sampled event, the top TBs and host
                                  functions by category, then one table of
                                  every event's share per category
  pmuread.py --selftest           the reader on synthetic lines, including a
                                  control that must FAIL

Line formats (hakux-pmu.c.inc):
  [pmu433] layout mode=1 gsz=5 g0=11,08,23,24,22 g1=11,08,01,02,35 ...
  [pmu433] ctl=NAME units=N ms=M cpu=A-B p=UNIT g0=RUN:v,... g1=... ...
  [pmu433] s=N dt=MS fr=N fmax=MS tclk=MS cs=N mig=N cpus=HEX p=UNIT g0=...
  [pmu433] smp w=W ev=0xE per=P n=N lost= jit= stub= host= drop= cpu=C:N,...
  [pmu433] smpj w=W ev=0xE r=R n=N pc= phys= ic= sz= tier=
  [pmu433] smph w=W ev=0xE r=R n=N lib= off= hint=

A UNIT is `c<cpu>-<core>` (counted only while the thread ran on that CPU) or
a PMU name (any CPU). The event names of each group come from the last layout
line before it; with none, the 10-05 layout below (three 7-event groups).

Every group carries cycles and instructions, so a ratio of two events inside
one group is exact over that group's running time, and an event's rate is
taken from its own group's cycles or instructions. The PMU runs one group at
a time (R0: at most 5 events schedule, and two 5-event groups do not fit
together), so per unit the sum of the groups' cycles (instructions, running
time) is the thread's user cycles (instructions, time) on that CPU, less the
rotation gaps. `coverage` (the summed running time over task-clock) says how
much of the thread's time the counters saw. No scaling is applied anywhere.
"""
import math
import re
import sys

LAYOUT_1005 = [
    ["cyc", "ins", "sfe", "sbe", "brr", "brm", "bis"],
    ["cyc", "ins", "l1i", "itl", "l1d", "dtl", "l2d"],
    ["cyc", "ins", "iwk", "dwk", "l1ia", "l1da", "l3d"],
]
GROUPS = LAYOUT_1005

EVNAME = {0x11: "cyc", 0x08: "ins", 0x23: "sfe", 0x24: "sbe", 0x21: "brr",
          0x22: "brm", 0x7a: "bis", 0x01: "l1i", 0x02: "itl", 0x03: "l1d",
          0x05: "dtl", 0x17: "l2d", 0x35: "iwk", 0x34: "dwk", 0x14: "l1ia",
          0x04: "l1da", 0x2a: "l3d", 0x10: "brmp", 0x19: "bus"}


def evname(code):
    return EVNAME.get(code, "e%02x" % code)


# Expectations, written before any device run (NOTES.md "R0 controls").
# (name, metric, lo, hi, cores) -- cores: which units the bound applies to,
# by a substring of the unit name, or None for every core type.
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
LOGMAX = 1023   # __android_log_print's payload, less its NUL
TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)")


def parse_layout(line):
    """`[pmu433] layout ... g0=11,08,...` -> [[names] per group], or None."""
    i = line.find("[pmu433] layout ")
    if i < 0:
        return None
    groups = {}
    for k, v in TOKEN.findall(line[i + 16:]):
        if re.fullmatch(r"g\d+", k):
            groups[int(k[1:])] = [evname(int(x, 16)) for x in v.split(",")]
    return [groups[k] for k in sorted(groups)] or None


def parse(line):
    """-> (head dict, {unit: ([group values], [run ms])}) or None."""
    i = line.find("[pmu433] ")
    if i < 0:
        return None
    body = line[i + 9:]
    if not re.match(r"(ctl|s)=", body):
        return None   # open / layout / cores / read / smp* lines
    parts = body.split(" p=")
    head = dict(TOKEN.findall(parts[0]))
    if len(line[i:].rstrip("\n")) >= LOGMAX and len(parts) > 1:
        # Android cut this line (5e4110e016 and older): its last unit may
        # be partial or end mid-number, so it is dropped and counted
        parts = parts[:-1]
        head["_cut"] = 1
    units = {}
    for part in parts[1:]:
        name, _, rest = part.partition(" ")
        gs = {}
        for g, val in TOKEN.findall(rest):
            if not re.fullmatch(r"g\d+", g):
                continue
            run, _, nums = val.partition(":")
            # `x`: an event this core refused (its slot counted ins)
            gs[int(g[1:])] = (float(run), [None if x == "x" else int(x)
                                           for x in nums.split(",")])
        n = max(gs) + 1 if gs else 0
        units[name] = ([gs[k][1] if k in gs else None for k in range(n)],
                       [gs[k][0] if k in gs else 0.0 for k in range(n)])
    ts = TS.match(line)
    head["_ts"] = ts.group(1) if ts else ""
    return head, units


def records(path, after=None):
    """(layout, head, units) for every ctl / slice line after `after`."""
    started = after is None
    layout = LAYOUT_1005
    held = None   # a slice is complete when a line that is not its `s=N+`
    for line in open(path, errors="replace"):
        lay = parse_layout(line)   # the layout is printed once, at start
        if lay:
            layout = lay
            continue
        if not started:
            started = re.search(after, line) is not None
            continue
        p = parse(line)
        if not p:
            continue
        s = p[0].get("s", "")
        if s.endswith("+"):
            if held and held[1].get("s") == s[:-1]:
                held[2].update(p[1])
                if p[0].get("_cut"):
                    held[1]["_cut"] = held[1].get("_cut", 0) + 1
            continue
        if held:
            yield held
        held = (layout, p[0], p[1])
    if held:
        yield held


def keyed(layout, vals, runs=None):
    """A unit's groups as {group signature: [values..., run]}."""
    out = {}
    for g, v in enumerate(vals):
        if v is None or g >= len(layout) or len(layout[g]) != len(v):
            continue
        out[tuple(layout[g])] = list(v) + [runs[g] if runs else 0.0]
    return out


def add(acc, k):
    """acc += k, both from keyed(); a refused (None) value stays None."""
    for sig, v in k.items():
        if sig not in acc:
            acc[sig] = [0] * len(v)
        acc[sig] = [None if a is None or b is None else a + b
                    for a, b in zip(acc[sig], v)]
    return acc


def _idx(sig, name, last=False):
    hits = [i for i, n in enumerate(sig) if n == name]
    return (hits[-1] if last else hits[0]) if hits else None


def ev(acc, name):
    """Event `name` summed over the groups that hold it (not as their cycles
    or instructions follower), with those groups' cycles and instructions."""
    x = cyc = ins = 0
    found = False
    for sig, v in acc.items():
        i = _idx(sig, name)
        ci, ii = _idx(sig, "cyc", True), _idx(sig, "ins", True)
        if i is None or ci is None or ii is None:
            continue
        if name in ("cyc", "ins") and sig.count(name) < 2:
            continue
        if v[i] is None:
            return None, None, None
        found = True
        x, cyc, ins = x + v[i], cyc + v[ci], ins + v[ii]
    return (x, cyc, ins) if found else (None, None, None)


def totals(acc):
    """User cycles, instructions and counted ms over every group."""
    cyc = ins = run = 0
    for sig, v in acc.items():
        ci, ii = _idx(sig, "cyc", True), _idx(sig, "ins", True)
        if ci is None or ii is None:
            continue
        cyc, ins, run = cyc + (v[ci] or 0), ins + (v[ii] or 0), run + v[-1]
    return cyc, ins, run


def metric(acc, m, units):
    num, _, den = m.partition("/")
    if m == "ipc":
        cyc, ins, _ = totals(acc)
        return ins / cyc if cyc else None
    x, cyc, ins = ev(acc, num)
    if x is None:
        return None
    if den == "unit":
        # the groups take turns, so a group saw only part of the kernel's
        # units: scale its count to the whole kernel by instructions (a
        # kernel's units are a fixed number of instructions each)
        if not ins:
            return None
        x = x * totals(acc)[1] / ins
    base = {"unit": units, "cyc": cyc, "ins": ins, "kins": ins / 1000.0}[den]
    return x / base if base else None


def core(unit):
    """`c7-x3` -> `x3`; a PMU-named unit is its own core type."""
    m = re.match(r"c\d+-(.+)$", unit)
    return m.group(1) if m else unit


def controls(paths):
    rows, bad, unread = [], 0, 0
    for path in paths:
        for line in open(path, errors="replace"):
            unread += "[pmu433] read " in line
        # the hook prints one ctl line per unit the kernel ran on
        ctl = {}
        for layout, head, units in records(path):
            if "ctl" not in head or not units:
                continue
            c = ctl.setdefault(head["ctl"], (head, {}, {}))
            for u, (v, r) in units.items():
                add(c[1].setdefault(u, {}), keyed(layout, v, r))
                c[2][u] = c[2].get(u, 0) + sum(r)
        for head, accs, runs in ctl.values():
            # judge the unit the kernel ran on; a migration leaves a sliver
            unit = max(runs, key=runs.get)
            share = runs[unit] / (sum(runs.values()) or 1)
            acc = accs[unit]
            for name, m, lo, hi, cores in EXPECT:
                if name != head["ctl"]:
                    continue
                if cores and not any(c in unit.lower() for c in cores):
                    continue
                v = metric(acc, m, int(head["units"]))
                ok = v is not None and lo <= v <= hi
                bad += not ok
                rows.append((path.split("/")[-1], unit, name, m, v, lo, hi,
                             "PASS" if ok else "FAIL", head.get("cpu"),
                             runs[unit], share))
    print("| file | unit | control | metric | read | expected | verdict | cpu "
          "| run ms | unit share |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for f, unit, name, m, v, lo, hi, verdict, cpu, run, share in rows:
        vs = "none" if v is None else "%.3f" % v
        print("| %s | %s | %s | %s | %s | %g-%g | %s | %s | %.1f | %.2f |"
              % (f, unit, name, m, vs, lo, hi, verdict, cpu, run, share))
    print("\n%d of %d expectations failed" % (bad, len(rows)))
    if unread:
        print("%d bad group reads logged by the hook (see [pmu433] read lines): "
              "a group that never ran or did not read cannot be judged" % unread)
    return 1 if bad or not rows else 0


ROWS = [("IPC", "ipc"), ("stall_fe %", "sfe/cyc"), ("stall_be %", "sbe/cyc"),
        ("br mispred /kins", "brm/kins"), ("br retired /kins", "brr/kins"),
        ("indirect spec /kins", "bis/kins"), ("L1I refill /kins", "l1i/kins"),
        ("L1I TLB refill /kins", "itl/kins"), ("L1D refill /kins", "l1d/kins"),
        ("L1D TLB refill /kins", "dtl/kins"), ("L2D refill /kins", "l2d/kins"),
        ("ITLB walk /kins", "iwk/kins"), ("DTLB walk /kins", "dwk/kins"),
        ("L3D refill /kins", "l3d/kins"), ("L1I access /kins", "l1ia/kins"),
        ("L1D access /kins", "l1da/kins")]


def _sd(xs):
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def slices(path, after=None, secs=None, slow_ms=34.5):
    rows = [(lay, h, u) for lay, h, u in records(path, after)
            if "s" in h and "dt" in h]
    if secs:
        acc, keep = 0.0, []
        for r in rows:
            if acc >= secs * 1000:
                break
            keep.append(r)
            acc += float(r[1]["dt"])
        rows = keep
    if not rows:
        print("no slice lines")
        return 1
    classes = {"all": [], "good": [], "slow": []}
    for r in rows:
        dt, fr = float(r[1]["dt"]), int(r[1]["fr"])
        classes["all"].append(r)
        classes["slow" if fr == 0 or dt / fr > slow_ms else "good"].append(r)
    # time on each unit / core type, and how much of task-clock it covers
    share, cshare = {}, {}
    run_all = tclk_all = dt_all = cs_all = mig_all = 0.0
    for lay, head, units in rows:
        tclk_all += float(head["tclk"])
        dt_all += float(head["dt"])
        cs_all += int(head["cs"])
        mig_all += int(head["mig"])
        for u, (vals, runs) in units.items():
            share[u] = share.get(u, 0) + sum(runs)
            cshare[core(u)] = cshare.get(core(u), 0) + sum(runs)
            run_all += sum(runs)
    tot = sum(share.values()) or 1
    print("slices %d (good %d, slow %d at > %g ms/frame); on-CPU %.1f%% of "
          "wall; coverage %.3f (counted / task-clock); cs %.0f/s, mig %.1f/s"
          % (len(rows), len(classes["good"]), len(classes["slow"]), slow_ms,
             100 * tclk_all / dt_all, run_all / tclk_all if tclk_all else 0,
             1000 * cs_all / dt_all, 1000 * mig_all / dt_all))
    cut = [h for _, h, _ in rows if h.get("_cut")]
    if cut:
        print("cut by the log limit: %d slices, %d units dropped (their "
              "counts are missing from the tables)"
              % (len(cut), sum(h["_cut"] for h in cut)))
    print("core-type share of counted time: " + ", ".join(
        "%s %.1f%%" % (k, 100 * v / tot) for k, v in
        sorted(cshare.items(), key=lambda kv: -kv[1])))
    print("per unit: " + ", ".join(
        "%s %.1f%%" % (k, 100 * v / tot) for k, v in
        sorted(share.items(), key=lambda kv: -kv[1])))
    for ct in sorted(cshare, key=lambda k: -cshare[k]):
        if cshare[ct] / tot < 0.05:
            continue
        print("\n### %s (%.1f%% of counted time)\n" % (ct, 100 * cshare[ct]
                                                        / tot))
        stats, per_slice = {}, []
        for cls, rs in classes.items():
            acc = {}
            dt = fr = tclk = mig = 0.0
            for lay, head, units in rs:
                dt += float(head["dt"])
                fr += int(head["fr"])
                tclk += float(head["tclk"])
                mig += int(head["mig"])
                one = {}
                for u, (vals, runs) in units.items():
                    if core(u) == ct:
                        add(one, keyed(lay, vals, runs))
                add(acc, one)
                if cls == "good" and one:
                    per_slice.append(one)
            cyc, ins, run = totals(acc)
            st = {"n": len(rs), "fps": 1000 * fr / dt if dt else 0,
                  "oncpu %": 100 * tclk / dt if dt else 0,
                  "here % of oncpu": 100 * run / tclk if tclk else 0,
                  "mig /s": 1000 * mig / dt if dt else 0,
                  "Mins /frame": ins / fr / 1e6 if fr else None,
                  "Mcyc /frame": cyc / fr / 1e6 if fr else None,
                  "GHz (cyc/run)": cyc / run / 1e6 if run else None}
            for label, m in ROWS:
                v = metric(acc, m, 1)
                if v is not None and "%" in label:
                    v *= 100
                st[label] = v
            stats[cls] = st
        # the good slices' own spread, per metric, one value per slice
        spread = {}
        for label, m in ROWS:
            xs = [metric(o, m, 1) for o in per_slice]
            xs = [x * (100 if "%" in label else 1) for x in xs if x is not None]
            spread[label] = _sd(xs)
        print("| | all | good | slow | slow - good | good sd | > 2 sd |")
        print("|---|---|---|---|---|---|---|")
        for k in stats["all"]:
            vals = [stats[c][k] for c in ("all", "good", "slow")]
            g, s = vals[1], vals[2]
            diff = (s - g) if (g is not None and s is not None) else None
            sd = spread.get(k)
            lead = ("*" if diff is not None and sd and len(per_slice) >= 3
                    and abs(diff) > 2 * sd else "")
            print("| %s | %s | %s |" % (k, " | ".join(
                "-" if v is None else ("%d" % v if k == "n" else "%.3g" % v)
                for v in vals + [diff, sd]), lead))
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


def _symbolize(host, apk):
    """{(lib, off): n} -> {function: n}."""
    funcs = {}
    cache = {}
    z = None
    if apk:
        import zipfile
        sys.path.insert(0, __file__.rsplit("/", 1)[0])
        import elfsyms
        z = zipfile.ZipFile(apk)
    for (lib, off), cnt in host.items():
        name = "%s+0x%x" % (lib, off)
        if z is not None:
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
        funcs[name] = funcs.get(name, 0) + cnt
    return funcs


def samples(path, apk=None, after=None):
    """Aggregate smp / smpj / smph lines over every window after `after`,
    per sampled event (a line with no ev= belongs to the last smp line's)."""
    started = after is None
    per = {}
    cur = None

    def new():
        return {"tot": {}, "tbs": {}, "host": {}, "cpu": {}, "per": None}

    for line in open(path, errors="replace"):
        if not started:
            started = re.search(after, line) is not None
            continue
        i = line.find("[pmu433] smp")
        if i < 0:
            continue
        kind, _, rest = line[i + 9:].partition(" ")
        kv = dict(TOKEN.findall(rest))
        e = kv.get("ev", cur)
        d = per.setdefault(e, new())
        if kind == "smp":
            cur = e
            for k in ("n", "lost", "jit", "stub", "host", "drop"):
                d["tot"][k] = d["tot"].get(k, 0) + int(kv[k])
            d["per"] = kv.get("per")
            for c in kv.get("cpu", "-").split(","):
                if ":" in c:
                    a, b = c.split(":")
                    d["cpu"][int(a)] = d["cpu"].get(int(a), 0) + int(b)
        elif kind == "smpj":
            key = (kv["pc"], kv["phys"])
            t = d["tbs"].setdefault(key, [0, kv["ic"], kv["sz"], kv["tier"]])
            t[0] += int(kv["n"])
        elif kind == "smph":
            key = (kv["lib"], int(kv["off"], 16))
            d["host"][key] = d["host"].get(key, 0) + int(kv["n"])
    per = {e: d for e, d in per.items() if d["tot"]}
    if not per:
        print("no smp lines")
        return 1
    catshare, funcshare, tbshare = {}, {}, {}
    for e in sorted(per, key=lambda x: int(x, 16) if x else 0):
        d = per[e]
        tot = d["tot"]
        n = tot["n"] or 1
        name = evname(int(e, 16)) if e else "?"
        print("\n## event %s (%s): %d samples, period %s, lost %d, dropped %d"
              % (e, name, tot["n"], d["per"], tot["lost"], tot["drop"]))
        if d["cpu"]:
            print("samples by cpu: " + ", ".join(
                "%d %.1f%%" % (c, 100.0 * k / n)
                for c, k in sorted(d["cpu"].items())))
        print("jit (in a TB) %.1f%%, dispatch stub %.1f%%, host code %.1f%%" % (
            100 * tot["jit"] / n, 100 * tot["stub"] / n, 100 * tot["host"] / n))
        print("(top-20 tables per window: a row's share is a lower bound)\n")
        print("| rank | guest pc | phys | icount | host bytes | tier | samples "
              "| % of all |")
        print("|---|---|---|---|---|---|---|---|")
        for r, ((pc, phys), (cnt, ic, sz, tier)) in enumerate(
                sorted(d["tbs"].items(), key=lambda kv: -kv[1][0])[:20]):
            print("| %d | %s | %s | %s | %s | %s | %d | %.2f |"
                  % (r, pc, phys, ic, sz, tier, cnt, 100.0 * cnt / n))
        funcs = _symbolize(d["host"], apk)
        cats = {}
        for fn, cnt in funcs.items():
            c = category(fn)
            cats[c] = cats.get(c, 0) + cnt
        cats["dispatch stub (code buffer)"] = tot["stub"]
        cats["jit (TB code)"] = tot["jit"]
        print("\n| host category | samples | % of all |\n|---|---|---|")
        for c, cnt in sorted(cats.items(), key=lambda kv: -kv[1]):
            print("| %s | %d | %.2f |" % (c, cnt, 100.0 * cnt / n))
        print("\n| rank | host function | category | samples | % of all |")
        print("|---|---|---|---|---|")
        for r, (fn, cnt) in enumerate(sorted(funcs.items(),
                                             key=lambda kv: -kv[1])[:20]):
            print("| %d | %s | %s | %d | %.2f |"
                  % (r, fn, category(fn), cnt, 100.0 * cnt / n))
        catshare[name] = {c: 100.0 * k / n for c, k in cats.items()}
        funcshare[name] = {f: 100.0 * k / n for f, k in funcs.items()}
        tbshare[name] = {"%s/%s" % k: 100.0 * v[0] / n
                         for k, v in d["tbs"].items()}
    if len(per) > 1:
        evs = list(catshare)
        lead = "cyc" if "cyc" in evs else evs[0]
        print("\n## where each event happens (%% of that event's samples; "
              "rows by %s)\n" % lead)
        for title, tab in (("category", catshare), ("host function", funcshare),
                           ("TB (pc/phys)", tbshare)):
            keys = sorted(set(k for t in tab.values() for k in t),
                          key=lambda k: -tab[lead].get(k, 0))[:15]
            print("| %s | %s |" % (title, " | ".join(evs)))
            print("|---|%s" % ("---|" * len(evs)))
            for k in keys:
                print("| %s | %s |" % (k, " | ".join(
                    "%.2f" % tab[e].get(k, 0) for e in evs)))
            print()
    return 0


def _run(fn, *args):
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*args)
    return rc, buf.getvalue()


def _tmp(lines):
    import os
    import tempfile
    fd, path = tempfile.mkstemp()
    os.write(fd, ("\n".join(lines) + "\n").encode())
    os.close(fd)
    return path


def selftest():
    import os
    results = []
    # 10-05 format: alu1 at IPC 1.03 (PASS), ind8 at 1.20 mispredicts/unit
    # (40M in g0, which saw a third of the instructions; must FAIL)
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
    path = _tmp(lines)
    rc, out = _run(controls, [path])
    os.unlink(path)
    results.append(("controls 10-05", rc == 1
                    and "alu1 | ipc | 1.030 | 0.95-1.12 | PASS" in out
                    and "ind8 | brm/unit | 1.200 | 0.75-0.95 | FAIL" in out))
    # 10-05 slices: one good (30 frames) and one slow (20 frames) slice
    sl = [
        "10-05 12:00:01.000 1 2 W hakuX: [pmu433] s=0 dt=1000 fr=30 fmax=34"
        " tclk=900.0 cs=10 mig=0 cpus=80 p=x3 g0=300:1000,1500,100,300,150,3,10"
        " g1=300:1000,1500,10,1,20,2,5 g2=300:1000,1500,1,1,400,500,1",
        "10-05 12:00:02.000 1 2 W hakuX: [pmu433] s=1 dt=1000 fr=20 fmax=60"
        " tclk=950.0 cs=10 mig=0 cpus=80 p=x3 g0=310:1000,1000,100,500,100,6,10"
        " g1=310:1000,1000,10,1,40,2,15 g2=310:1000,1000,1,1,300,400,1",
    ]
    path = _tmp(sl)
    rc, out2 = _run(slices, path)
    os.unlink(path)
    results.append(("slices 10-05", rc == 0
                    and "| IPC | 1.25 | 1.5 | 1 | -0.5 |" in out2
                    and "| stall_be % | 40 | 30 | 50 | 20 |" in out2))
    # 10-09 format: layout line, per-CPU units, 5-event groups. alu1 on c7-x3
    # with a 2 ms sliver on c3-a715 (not judged); chase64m l2d (g3) at 0.95
    # per load (PASS: 760k in g3, which saw a fifth of the instructions);
    # ind8 bis absent from g0 must not matter.
    lay = ("[pmu433] layout mode=1 gsz=5 g0=11,08,23,24,22 g1=11,08,01,02,35"
           " g2=11,08,03,05,34 g3=11,08,17,2a,21 g4=11,08,7a,14,04")
    g = " g%d=100.0:330000000,340000000,1,1,1"
    lines = [
        lay,
        "[pmu433] ctl=alu1 units=1600000000 ms=520 cpu=7-7 p=c3-a715"
        " g0=2.0:9,1,1,1,1 g1=0:0,0,0,0,0 g2=0:0,0,0,0,0 g3=0:0,0,0,0,0"
        " g4=0:0,0,0,0,0",
        "[pmu433] ctl=alu1 units=1600000000 ms=520 cpu=7-7 p=c7-x3"
        + "".join(g % k for k in range(4)),
        "[pmu433] ctl=alu1 units=1600000000 ms=520 cpu=7-7 p=c7-x3"
        + g % 4,
        "[pmu433] ctl=chase64m units=4000000 ms=400 cpu=7-7 p=c7-x3"
        " g0=80:300000000,800000,1,270000000,1 g1=80:300000000,800000,1,1,1"
        " g2=80:300000000,800000,1,1,1 g3=80:300000000,800000,760000,1,1"
        " g4=80:300000000,800000,1,1,1",
    ]
    path = _tmp(lines)
    rc, out4 = _run(controls, [path])
    os.unlink(path)
    results.append(("controls 10-09", "c7-x3 | alu1 | ipc | 1.030 | 0.95-1.12"
                    " | PASS | 7-7 | 500.0 | 1.00" in out4
                    and "c3-a715 | alu1" not in out4
                    and "c7-x3 | chase64m | l2d/unit | 0.950" in out4
                    and "c7-x3 | chase64m | sbe/cyc | 0.900" in out4))
    # 10-09 slices: two units, three good slices (IPC 1.0, 1.1, 1.2 on the
    # X3) and one slow (IPC 0.5): slow - good is far outside the spread.
    def sline(s, fr, ins, sbe):
        grp = "".join(" g%d=190:1000,%d,1,%d,1" % (k, ins, sbe)
                      for k in range(5))
        return ("10-09 12:00:%02d.000 1 2 W hakuX: [pmu433] s=%d dt=1000"
                " fr=%d fmax=40 tclk=1000.0 cs=10 mig=1 cpus=88 p=c7-x3%s"
                " p=c3-a715 g0=50:100,100,1,1,1" % (s, s, fr, grp))
    sl = [lay, sline(1, 30, 1000, 300), sline(2, 30, 1100, 300),
          sline(3, 30, 1200, 300), sline(4, 20, 500, 600)]
    path = _tmp(sl)
    rc, out5 = _run(slices, path)
    os.unlink(path)
    results.append(("slices 10-09", rc == 0
                    and "coverage 1.000" in out5
                    and "### x3 (95.0% of counted time)" in out5
                    and "| IPC | 0.95 | 1.1 | 0.5 | -0.6 | 0.1 | * |" in out5
                    and "| stall_be % | 37.5 | 30 | 60 | 30 | 0 |  |" in out5))
    # samples, 10-05 format: two windows; one TB in both must sum
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
    path = _tmp(sm)
    rc, out3 = _run(samples, path)
    os.unlink(path)
    results.append(("samples 10-05", rc == 0
                    and "jit (in a TB) 65.0%, dispatch stub 5.0%" in out3
                    and "| 0 | 00011000 | 00011000 | 12 | 300 | 0 | 90 | 45.00 |"
                    in out3
                    and category("helper_lookup_tb_ptr") == "dispatch"
                    and category("do_ld4_mmu") == "softmmu"
                    and category("helper_fadd_ST0_FT0") == "helper"
                    and category("tcg_optimize") == "translation"))
    # samples, 10-09 format: two events in one window, kept apart
    sm = [
        "[pmu433] smp w=0 ev=0x11 per=100000 n=200 lost=0 jit=100 stub=20"
        " host=80 drop=0 cpu=7:190,3:10",
        "[pmu433] smpj w=0 ev=0x11 r=0 n=60 pc=00011000 phys=00011000 ic=12"
        " sz=300 tier=0",
        "[pmu433] smph w=0 ev=0x11 r=0 n=80 lib=libxemu.so off=451f40 hint=?",
        "[pmu433] smp w=0 ev=0x24 per=10000 n=100 lost=0 jit=90 stub=0"
        " host=10 drop=0 cpu=7:100",
        "[pmu433] smpj w=0 ev=0x24 r=0 n=80 pc=00011000 phys=00011000 ic=12"
        " sz=300 tier=0",
        "[pmu433] smph w=0 ev=0x24 r=0 n=10 lib=libxemu.so off=451f40 hint=?",
    ]
    path = _tmp(sm)
    rc, out6 = _run(samples, path)
    os.unlink(path)
    results.append(("samples 10-09", rc == 0
                    and "## event 0x11 (cyc): 200 samples" in out6
                    and "samples by cpu: 3 5.0%, 7 95.0%" in out6
                    and "## event 0x24 (sbe): 100 samples" in out6
                    and "| jit (TB code) | 50.00 | 90.00 |" in out6
                    and "| 00011000/00011000 | 30.00 | 80.00 |" in out6))
    # the layout reader itself
    results.append(("layout", parse_layout(lay)[3] == ["cyc", "ins", "l2d",
                                                        "l3d", "brr"]
                    and parse_layout("[pmu433] layout mode=2 gsz=5 g0=24,11,08"
                                     )[0] == ["sbe", "cyc", "ins"]))
    # a slice split over a `s=N+` line is one slice with both units; a line
    # Android cut (payload 1023 bytes) loses its last, partial unit
    u = " p=c%d-a715" + "".join(" g%d=10.0:1000,2000,1,1,1" % k
                                 for k in range(5))
    head = "[pmu433] s=%s dt=1000 fr=30 fmax=34 tclk=900.0 cs=1 mig=0 cpus=88"
    full = head % "2" + "".join(u % c for c in range(7))
    full += " p=c7-x3 g0=10.0:1000,2000,1,1,1 g1=10.0:1000,2000,1,1,1"
    full = full[:LOGMAX - 4] + "1,22"
    lines = [lay, head % "1" + u % 3, "[pmu433] s=1+" + u % 4, full,
             "[pmu433] ctl=alu1 units=1 ms=1 cpu=7-7" + u % 7]
    path = _tmp(lines)
    got = [(h.get("s", h.get("ctl")), sorted(un), h.get("_cut"))
           for _, h, un in records(path)]
    os.unlink(path)
    results.append(("split/cut", len(full) == LOGMAX and got == [
        ("1", ["c3-a715", "c4-a715"], None),
        ("2", ["c%d-a715" % c for c in range(7)], 1),
        ("alu1", ["c7-a715"], None)]))
    for o in (out, out2, out4, out5, out3, out6):
        print(o)
    for name, ok in results:
        print("%-16s %s" % (name, "PASS" if ok else "FAIL"))
    allok = all(ok for _, ok in results)
    print("selftest:", "PASS" if allok else "FAIL")
    return 0 if allok else 1


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
