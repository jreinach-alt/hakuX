# Audit pass 1: lane.perfarch, PR #308

Head audited: `48e41cf698`. I read the diff (`gh pr diff 308`): 15 files, all
new except `tcg/aarch64/tcg-target.c.inc` (+161) and `tcg/tcg-op.c` (+17).

**Result: 1 MEDIUM, 3 LOW. The PR goes to `needs-remediation`.**

The default path is inert. With no `HAKUX_*` variable set, the backend runs
three `getenv` calls at init and one `hb_place_state` test per translated
block, and emits the same code as master. The `tcg_gen_mb` edit is in the
`XBOX` branch. That branch already elides every barrier, so under `rcpc` it
can only add barriers (the ones requesting ST_LD); it removes none. The
LDAPR/STLR encodings, the UXTW index fold and TMP2 = X30 are correct, as
section 8.2 says.

## MEDIUM 1: the rcpc emitter faults on a misaligned guest access, and section 8.2's diagnosis of the boot hang rests on an unverified "no crash"

`tcg/aarch64/tcg-target.c.inc`, `hakux_tso_ld_direct` / `hakux_tso_st_direct`;
`docs/investigations/perf-architecture.md` section 8.2; NOTES "Resume 3".

**Defect.** x86 guest memops carry no alignment requirement. In
`prepare_host_addr`, `a_mask` is 0, so the fast path (the TLB hit, and the
XBOX RAM/VRAM paths) accepts any address that does not cross a page. Plain
LDR/STR accept an unaligned address on Normal memory. LDAPR and STLR do not.

- Without FEAT_LSE2, a misaligned LDAPR or STLR raises an Alignment fault.
- With FEAT_LSE2, an access that crosses a 16-byte boundary still faults.
- An access inside 16 bytes faults unless `SCTLR_EL1.nAA` is set.

The emitter sends every fast-path access to LDAPR/STLR, with no alignment
test and no fallback. FEX-Emu, whose mapping section 1 cites, relies on a
SIGBUS handler that backpatches unaligned atomics. This prototype has
nothing in that role.

**Failure scenario.** Set `HAKUX_TCG_TSO=rcpc` on the Nova (LRCPC present,
so the mode reports `-> ON`). The first guest load or store whose address
crosses 16 bytes (or, if `nAA` is clear, any misaligned one) runs as
LDAPR/STLR on the fast path. The CPU raises an Alignment fault, and the
kernel delivers SIGBUS with `BUS_ADRALN`. QEMU's `sigbus_handler`
(`system/cpus.c:387`) is installed over bionic's debuggerd handler. For any
`si_code` other than an MCE, it calls `sigbus_reraise()`, which sets
`SIG_DFL` and raises again. The process dies with no tombstone, no
`Fatal signal` line and no `F DEBUG` line. The app's log just stops. That
matches B1 and B2 exactly: "nothing after `qemu_main`", "no crash line", and
no `tso rcpc emitted` line.

**Why this is MEDIUM, and what it breaks.** The mode is off by default and
only an arm sets it, so the blast radius is bounded. But the lane's written
conclusion is wrong where it will be read:

- Section 8.2 says "The process neither crashed nor raised SIGILL". This
  death mode leaves no line for `tso_judge.py`'s `CRASH` regex, or anything
  else in the app's logcat, to match. The claim is an absence the instrument
  cannot see.
- The candidates listed (register 31 as SP, an unexpected `HostAddress`
  shape) do not include the alignment fault.
- The next step recorded in section 8.2 and NOTES ("dump `out_asm` ... read
  the first LDAPR/STLR") would show correctly encoded instructions and
  settle nothing.
- The ranked table (row 8) and the guarantees table in section 1 present
  the mode as a working TSO whose cost is simply unmeasured.

**Remediation.**
1. Correct section 8.2, the row 8 cell and NOTES where they are read.
   Replace "neither crashed" with what the logs actually show. Name the
   alignment fault as the leading candidate. State the check that settles
   it: in the B runs' logs, did the process die or stay alive for the full
   240 s? Look for ActivityManager `has died` / `Process ... exited` for the
   app pid, or process liveness at the end of the soak.
2. Stop claiming the emitter is correct for arbitrary guest accesses. Either:
   - guard it: emit `tst addr, #(size-1)`, use LDAPR/STLR when aligned, and
     fall back to LDR + `DMB ISHLD` or `DMB ISH` + STR when not. For
     16-byte-crossing accesses under LSE2, test on `addr & 15`. The guard
     costs something, and that cost belongs in the model and the prediction
     band before any re-arm.
   - or record in section 1 and in the `hakux_tso_rcpc` comment that the
     mode faults on misaligned accesses and is not runnable as built.

   Either is acceptable for this PR. Leaving the code and the doc claiming
   otherwise is not.

## LOW 1: `tso_judge.py` T2 cannot see the likeliest failure of the thing it guards

`tools/bench/tso_judge.py`, `CRASH` and leg T2. The regex matches only
debuggerd/libc and `hakuX-crash` lines. A `SIG_DFL` death, as in MEDIUM 1,
prints none of them. T2 ("B logs no more crash lines than A") would pass on
a B arm that died silently, if it lived long enough to clear the window gate.
The window-count half of T2 partly covers this. Consider also treating "log
ends before `seconds`" as a death.

## LOW 2: `hostbench.c.inc` breaks the macOS arm64 build

`tools/bench/hostbench.c.inc` is included under `#ifdef XBOX` into every
aarch64 TCG backend. It uses `__NR_sched_setaffinity`, `__NR_getcpu` and
`__NR_gettid` outside any `__linux__` guard. The first two are only reached
through `hb_setaffinity`/`hb_getcpu`, which are compiled for every host. On
an Apple-silicon build, `<sys/syscall.h>` defines none of them, so the build
stops with an error. `ci.yml` says the macOS build is unmaintained and runs
only on dispatch, so no scored or shipped build is affected. Guard the file
body with `__linux__`, as the `qemu_getauxval` call already is.

## LOW 3: a bench harness inside the production backend

872 lines of micro-benchmark and sampler code ship in every Android binary,
included from `tcg-target.c.inc`. The header comment explains why: it is the
first code that runs after the env pref is applied. It is inert when unset,
so this is a layering note, not a defect. If the levers graduate into a fix
PR, move the harness behind a build option.

## Not findings (checked)

- `tcg_gen_mb` under rcpc: `parallel` becomes "requests ST_LD". The x86
  `guest_mo` masks ST_LD out of every `tcg_gen_req_mo`, so only MFENCE-class
  requests emit. Under the shipped elision nothing emits, so this is strictly
  stronger than the default. LOCK-prefixed RMW without ST_LD is listed as
  dropped in section 1.
- The slow-path DMBs: ISHLD after the load helper and ISH before the store
  helper. Their placement relative to `tcg_out_goto(raddr)` is correct.
- The i128 path: a DMB ISH before a store pair and an ISHLD after a load
  pair. This matches the table.
- `hakux_place_vcpu_once` from `tcg_out_tb_start`: translation happens on
  the single vCPU thread, so the unsynchronised `hb_place_state` is safe.
  The Galleon B runs show it pinned the right thread (100% on the X3).
- The prediction files are well formed. Both arms use one ref with an env
  A/B, and the judges read thresholds only from `expect`. Section 8 reports
  both arms as refused, or a no-boot, rather than as verdicts.
