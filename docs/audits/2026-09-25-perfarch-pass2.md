# Audit pass 2: lane.perfarch, PR #308

Head verified: `1ea65ec877` (remediation of pass 1, `2026-09-25-perfarch-pass1.md`).

**Result: clean. The pass-1 MEDIUM's scenario can no longer mislead where it
is read; one new LOW (the PR body). The PR goes to `fold-ready`.**

## MEDIUM 1: rcpc emitter faults on misaligned access; section 8.2 rests on "no crash"

The remediation took pass 1's second option: record, not guard. The code
path is unchanged, so an rcpc run still faults on a misaligned access. Pass 1
accepted that option, because the mode is off by default and only an arm
sets it. What pass 2 must verify is that no reading surface in the diff
still claims the mode works, or still reads "no crash line" as "alive".

| scenario from pass 1 | where it was read | now |
|---|---|---|
| "The process neither crashed nor raised SIGILL" | section 8.2 | gone. 8.2 now says the logs do not show whether the process hung or died, names the Alignment fault as the leading candidate, and says "no crash line" is not evidence of life. `grep -i "neither crashed"` over the doc, NOTES and predictions returns nothing. |
| fault missing from the candidates | section 8.2 | it is now the leading candidate. The two old candidates remain, marked less likely. |
| next step "dump `out_asm`", which cannot settle it | 8.2, NOTES "Resume 3", NOTES next-three item 1 | replaced in all three places with the check that does settle it: the app pid's `has died` / `Process ... exited` line in the B runs' full logcat, or liveness at the end of the soak. Both files say explicitly that `out_asm` would not settle it. No `out_asm`/`in_asm` instruction remains outside those disclaimers. |
| row 8 and the section-1 guarantees table present a working TSO | ranked table, section 1 | row 8 now reads "not runnable as built: LDAPR/STLR fault on misaligned guest accesses, and there is no guard". Section 1 has a `misaligned guest accesses -> fault` row, then "The prototype is not runnable as built", with both fixes (a `tst` guard with a DMB fallback, or FEX-style SIGBUS backpatching). It also says the guard's cost belongs in the band before any re-arm. |
| code claims correctness for arbitrary accesses | `hakux_tso_rcpc` (`tcg/tcg-op.c`), the emitter (`tcg-target.c.inc`) | both now carry "NOT RUNNABLE AS BUILT" / "No alignment test" comments naming the fault and the SIG_DFL re-raise. |

I checked the mechanism the correction relies on in `system/cpus.c`.
`sigbus_handler` calls `sigbus_reraise()` for every `si_code` except
`BUS_MCEERR_AO`/`AR`, and `sigbus_reraise()` sets `SIG_DFL` and raises again.
So a `BUS_ADRALN` death leaves no debuggerd line. The text is right.

"Hang" wording: the only remaining "hung" is in 8.2 ("do not say whether the
process hung or died"), and it is correct. NOTES now says "stopped", not
"hung".

**Verdict: resolved.** The mode still faults, as recorded, but no reader of
the doc, NOTES or code is told otherwise. The registered prediction's
thresholds are unchanged, and none is needed: the arm ran and was refused on
validity, and section 8.2 says a re-arm first needs the guard and a re-banded
prediction.

## Pass-1 LOWs

LOW 1 (`tso_judge.py` T2 blind to a SIG_DFL death), LOW 2 (`hostbench.c.inc`
lacks a `__linux__` guard for macOS arm64) and LOW 3 (bench harness in the
backend) are unchanged. LOWs do not block, and none has a scored or shipped
failure scenario. LOW 1's blindness is now stated in section 8.2.

## New LOW: the PR body still carries the pass-1 claim

The PR description's arm-results table still reads "fails: the guest hangs
at boot under rcpc, 2 of 2 runs (log ends at `qemu_main`, no crash)". Its
summary still presents `HAKUX_TCG_TSO=rcpc` as "x86-TSO by construction",
without the misalignment fault. A fold is a `--no-ff` merge, so the body does
not enter history. But it is the first thing a reader of #308 or #68 sees.
Change "hangs" to "stops at boot (hung or died; alignment fault leading,
section 8.2)" and add "not runnable as built" to the rcpc bullet. The
auditor may not edit the lane's PR, so this is left to the lane or the board.
