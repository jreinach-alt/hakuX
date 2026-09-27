# lane.retreason425 -- #425: why the vCPU's TBs return to cpu_exec_loop

Base: master @ 231d04df51. Issue #425, feeding #412 (Agent Under Fire, 4541000D).
Hand-off: #425 comments 01:45Z (lane.aufire412b) and 02:04Z (job.cloud's
correction: the fourth cause, gen_eob's plain exit).

## 1. The counter (6a598c5404)

`[rr425]` and `[rr425pc]`, one line each every 2 s at `[jc425]`'s gate, tag
`hakuX` at WARN (in every runner's LOGCAT_SPEC, so no allow-list edit). Counters
only; no control-flow change. XBOX builds only; always on (no switch).

The problem it solves: a TB that ends in gen_eob()'s plain `exit_tb(NULL, 0)`
and a `helper_lookup_tb_ptr` miss that returns the epilogue both reach
cpu_tb_exec with ret 0, so the loop sees tb_exit 0 and a NULL TB for both. A
loop-side counter cannot separate them. So each marks itself:

- **translator** (translate.c, two hunks): `gen_eob()` stores a 64-bit tag
  into the host global `hakux_rr425_eob` just before each plain
  `exit_tb(NULL, 0)` (the RECHECK_TF arm and the final `else`). The tag carries
  the mode (EOB_NEXT, EOB_INHIBIT_IRQ, EOB_ONLY, RECHECK_TF, DISAS_JUMP inside a
  shadow), whether the TB began in an interrupt shadow, and the pc of the TB's
  last instruction (recorded in `i386_tr_insn_start`, a new DisasContext field
  under XBOX). Codegen cost: a pointer materialisation and one store per such
  exit.
- **helper** (cpu-exec.c): `helper_lookup_tb_ptr` counts its calls (`hc`) and
  misses (`hm`) and sets `rr425_miss` before returning the epilogue.
- **loop** (cpu-exec.c, `cpu_loop_exec_tb`): after every return, reads and
  clears both marks and books the return once: `r` TB_EXIT_REQUESTED, `g` a
  goto_tb exit not yet patched (returned TB non-NULL), `e` tagged, `m`
  helper miss, `o` none of these. At the next dispatch `g` splits into `gs`
  (target spans two pages, never chained), `gi` (CF_INVALID), `ga`
  (tb_add_jump called).
- **context**: `it` dispatches, `x` longjmps into cpu_exec_setjmp, `ip`
  dispatches with `interrupt_request` non-zero, `iq` interrupts taken, `xr`
  loop exits on exit_request.
- **timing**: 1 in 64 dispatches, get_clock() from a TB's return to the next
  TB's entry (`gapus`: the loop, including the barrier in
  cpu_handle_interrupt) and across that TB's run (`tbus`), each scaled by
  `it / samples`. A sample a longjmp lands in is dropped; cpu_exec_loop entry
  resets it so a gap never spans time outside cpu_exec.
- **top PCs** (`[rr425pc]`): the 16 commonest (cause, pc) pairs in the window,
  each with the first three guest bytes at that pc (cpu_memory_rw_debug at
  print time). For `e` the pc is the returning TB's last instruction as
  translated; for the others it is the pc the loop resumes at (under CF_PCREL
  the returning TB's own pc is not known for them).

Self-checks the reader enforces before any number is read (`rr425.py`):
`d = it - (e+m+o+r+g)` must not exceed `x` (a return nothing booked is a
longjmp out of a TB); `m` must equal `hm` up to window-edge slop; `gs+gi+ga
<= g`; `pcdrop == 0`.

Known blind spots, stated so they are not read as zeros: a superblock's
rewritten exit (translate-all.c, `b_exit1->args[0] = 0`) and VMRUN end in `o`,
not `e`. `ga` counts tb_add_jump calls, including ones that find the slot
already claimed. Returns from `cpu_exec_step_atomic` are not booked (their
marks are dropped).

Compile-checked for arm64 Android against the shared tree's compile commands
(clang, NDK 29, the Release flags; no new warnings). `rr425.py --selftest`
passes.

## 2. Arms

| what | ref | request id |
|---|---|---|
| B: counters, AUF survey route, 400 s, Nova | 6a598c5404 | `1790477867-retreason425-2004056` |
| A: master control (fps without counters) | 231d04df51 | `1790477870-retreason425-2004282` |
| pixels must-not-move, 8 suites | 231d04df51 vs 6a598c5404 | `docs/testing/predictions/retreason425-pixels-inert.json` (arms job) |

Read with `python3 docs/lanes/retreason425/rr425.py --from 299 --to 400 <id>`
(mission play starts ~299 s on the survey route, per aufire412b).

## 3. Result

Pending the arms above. 2026-09-27 03:00Z (20:00 PDT): both soaks queued on the Nova
behind aufire412b (running), doa413b x2 and tbflip424 x2; the Thor is
owner-held. preflight passes on be819ae6bf+. Waiting on those two result ids;
nothing of this lane is running in a session.

## Files outside this lane

None edited. cputlb.c / tb-maint.c / tb-internal.h untouched; the `[rr425]`
line needs no dispatcher allow-list change (tag `hakuX` at W).
