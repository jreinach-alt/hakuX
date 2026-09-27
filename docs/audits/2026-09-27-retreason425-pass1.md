# Audit pass 1: PR #460, lane.retreason425 (#425 return-split counters, idle halt)

Head audited: `3700b87707`. Auditor: job.cloud, 2026-09-27.

**Result: no HIGH, one MEDIUM, three LOW.** Next state: `needs-remediation`.

## What the diff does

- `target/i386/tcg/translate.c`: under `XBOX`, `gen_eob()` stores a constant
  64-bit tag (mode, interrupt-shadow bit, pc of the TB's last instruction) to
  the host global `hakux_rr425_eob` immediately before each plain
  `exit_tb(NULL, 0)`. This covers the RECHECK_TF branch and the final `else`.
  `i386_tr_insn_start` records `hakux_insn_pc`.
- `accel/tcg/cpu-exec.c`: the `[rr425]` counters. Every return from
  `cpu_tb_exec` in `cpu_loop_exec_tb` is booked once as `e`/`m`/`o`/`r`/`g`,
  and a 2048-slot (cause, pc) table produces a top 16. One dispatch in 64 is
  timed. A `[rr425]` and a `[rr425pc]` line are logged every 2 s at the
  `tlb68` gate. `helper_lookup_tb_ptr` marks a miss.
  `cpu_exec_longjmp_cleanup` and `cpu_exec_step_atomic` clear the marks.
- `HAKUX_IDLE_HLT` (default off): when the guest idle window
  `fb 90 90 fa` returns in the order "STI return at P, then an EOB_NEXT
  return from a shadow at P+1", and `!cpu_has_work`, the vCPU halts with
  `EXCP_HLT` through `cpu_loop_exit`.
- Two must-not-move predictions, the reader `rr425.py`, `typecheck_rr.py`,
  and NOTES.

## What I checked

1. **Every return is booked once and the marks cannot go stale.** The tag
   store is the last op before `exit_tb`. The only thing before it in the
   RECHECK_TF branch is `gen_helper_rechecking_single_step`, and a longjmp
   out of that is cleared by `cpu_exec_longjmp_cleanup`.
   `rr425_miss` is set just before `helper_lookup_tb_ptr` returns the
   epilogue. `cpu_tb_exec` has exactly two callers (`cpu-exec.c:1743`,
   `:2077`), and both clear or book the marks. `TB_EXIT_REQUESTED` fires at
   TB entry, before any tag store, so `r` and `e` cannot collide. A tagged
   exit always returns a NULL TB, so `g` and `e` cannot collide either.
2. **The tag's fields match the translator.** `inhibit_reset` is computed
   before both store sites (`translate.c:2916-2924`). A DISAS_JUMP with
   `inhibit_reset` goes to the final `else`, so it is tagged 5 as the
   comment says. `pc_next` at `insn_start` is the start of the instruction,
   so an STI-ending TB tags P.
3. **Non-XBOX builds.** `RR425_COUNT` is a no-op with unused arguments.
   `rr425_miss`, `idle_hlt_armed` and `rr425_phase` are referenced only
   under `#ifdef XBOX`. The enum is referenced only inside the macro.
4. **The timing sample cannot span time outside cpu_exec.** `rr425_phase`
   is reset at `cpu_exec_loop` entry and in the longjmp cleanup.
5. **Top-16 selection.** It keeps a sorted array and replaces `top[15]`
   only when a larger count arrives. This is correct. `snprintf` is bounded
   by `off < sizeof(buf) - 48`, and one entry is at most 25 characters.
6. **Arithmetic.** `gapus` is mean ns × `it` / 1000. At the measured
   ~56 M returns per 2 s and ~100 ns means, that is about 5.6e9, far from
   overflow.
7. **Idle halt, as a transformation.** One byte is `STI`, so the
   instruction after it is always at P+1. A TB that starts in a shadow ends
   after one instruction with EOB_NEXT, so the second return is the NOP, and
   eip is at P+2 with IF set and the shadow cleared. This matches
   `helper_hlt`'s state, except that `HF_INHIBIT_IRQ` has already been
   cleared by the NOP's `gen_eob`. A wake is an interrupt taken at P+2,
   where the spin would also have taken it. As a local rewrite of
   `sti; nop; nop; cli` it is sound. The pilot says the whole-system claim is
   not (M1).
8. **Cost when off.** The counters run on every dispatch in every XBOX
   build: a hash probe per return, two `get_clock()` calls per 64
   dispatches, and one host store per plain-exit TB. The lane measured
   17.82 fps with the counters against 17.76 without them on AUF, and the
   pixel arm PASSED with 593 checks. The cost is measured, not assumed (L1).

## Findings

### M1 (MEDIUM): refuted idle-halt code folds with a comment that says it is safe

`accel/tcg/cpu-exec.c:1149-1210` (`idle_hlt_check` and its block comment).

The lane's own pilot (`1-1790515918-retreason425-1213231`, NOTES line 180)
ran `d259abab29` with `HAKUX_IDLE_HLT=1`, and it **wedged at boot**: no
`[rr425]` line, no frame, and `no nv2a fb` for 400 s. The A arm on the same
ref booted and ran. The PR body says "refuted as built". The code still
folds unchanged, and its block comment still asserts that "spinning until an
interrupt arrives and waiting for one are the same to the guest". That is the
claim the pilot falsified.

*Failure scenario:* a later lane chasing the same exec-loop share reads the
comment, sets `HAKUX_IDLE_HLT=1` (in a prefs file, an arm env, or a pilot),
and the title never reaches its first frame. The comment gives it no reason
to suspect the flag, and nothing in the tree records that the flag has
already been tried and wedges. The idiom match is also broader than the
comment says. It halts at **any** `sti; nop; nop; cli` whose NOP returns with
no work pending, not only `KiIdleLoop`, and there is no evidence that
interrupts are the only thing that ends every such loop at boot. That is one
candidate for the wedge. The cause is undiagnosed. The blast radius is
bounded (default off, env-gated), so this is MEDIUM, not HIGH.

*Remediation (a suggestion; decline with a reason if it is wrong):* remove the
idle-halt path from this PR (`idle_hlt_*`, the `getenv`, and the `RR_IH`
count), and keep the counters, which are what the PR claims and what the
pixel arm covers. `d259abab29` stays in history for whoever diagnoses the
wedge. If the lane wants to keep the code in tree instead, it must make the
flag unreachable (compile it out) and replace the equivalence sentence with
the pilot result and run id. A default-off env flag is not enough, because an
env flag is exactly how a pilot turns it on.

### L1 (LOW): always-on diagnostic in the hottest path of every XBOX build

`cpu-exec.c:2067-2090`, `rr425_book`. At the measured ~28 M returns/s, every
return pays a hash multiply and probe, and two WARN log lines (the second up
to ~1 KB) go to logcat every 2 s for the life of the process. The fps A/B shows
no measurable cost on AUF, and `[jc425]` on master set the precedent, so no
defect is shown. *Decision needed:* either gate the counters with the same
switch `[jc425]` will get when it is retired, or record that the counters stay
always-on until #425/#412 close.

### L2 (LOW): the verified idle pc is never invalidated

`idle_hlt_pc` is set once, after a byte check, and is trusted for the life of
the process. If code at P changes (an XBE that maps other code there after a
reboot into a title), an STI at P arms without the bytes being checked again.
It is unreachable while the flag is off and moot if M1 removes the code.

### L3 (LOW): `idle_hlt_not` records read failures as "not the idiom"

If `cpu_memory_rw_debug` fails once (for example, the page is not mapped yet
at the moment of the check), the pc is cached as not-idiom until another STI
pc hashes into its slot. This costs a missed halt only, and it is moot if M1
removes the code.

## Not findings

- `rr425.py` / `typecheck_rr.py` are lane tooling under
  `docs/lanes/retreason425/`, and nothing else imports them.
- Both prediction files name refs that have already been judged (PASS, 593
  checks, for the pixels arm). They are records, not live queue entries that
  would re-arm.
