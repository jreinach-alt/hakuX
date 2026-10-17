# lane.fistdefault1016 -- HAKUX_FIST_ROUND on by default (#939 (b))

Brief: `/home/justin/hakux-work/briefs/fistdefault1016.md`. Issue #939 (and #433 umbrella). Base
`master @ fb6ebcff40`. Grant and cause: `docs/lanes/x1port1012/PR.md`/NOTES.md (lane.x1port1012,
not touched by this lane except to read).

## The change

`tcg/aarch64/tcg-target.c.inc`, `tcg_target_init` (~line 4320) and the comment at the top of the
file (~line 25):

- `hakux_fist_round` now defaults to `true`. `HAKUX_FIST_ROUND=0` is the only value that turns it
  off; unset or any other value is ON.
- `hb_log` line reworded to say which way it was decided: `fist round=ON (default)`,
  `fist round=ON (env)`, `fist round=OFF (env HAKUX_FIST_ROUND=0)`. `hb_log` itself prefixes every
  line with `perfarch ` (`tools/bench/hostbench.c.inc:63,65`), so the device log carries
  `perfarch fist round=ON (default)` with no env set -- the string the prediction's V leg greps.
- The file-top comment no longer says "off by default".

Nothing else touched: no change to `tcg_out_fist` (tcg-target.c.inc:3161-3177, the FRINTI
emission itself), no change to the x86_64 backend, no new switch.

## Grep for other default-off statements

`grep -ri "FIST_ROUND\|fist round\|fist_round"` across the repo, outside this lane's own files,
turns up only `docs/lanes/x1port1012/{NOTES,OUTBOX,PR}.md` and
`docs/testing/predictions/x1port1012-fistround.json` -- all history, owned by lane.x1port1012,
left untouched per the brief. A broader grep for bare `FIST` turns up only unrelated title names
(`Beat Down - Fists of Vengeance`, `Evil Dead - A Fistful of Boomstick`) and
`nv2a-hardware-gap-list.md`'s generic "61 FIST/FISTP sites" line, which makes no default claim.
**No living doc (`docs/testing/*.md`) or Android settings string says the switch is default-off.**
Nothing to fix there.

`nv2a_index.json`: not regenerated. This lane touches no file the index covers (no
`hw/xbox/nv2a/**`); the index-regen rule in AGENTS.md/memory applies to indexed source files,
and `tcg/aarch64/tcg-target.c.inc` is not one of them.

## Evidence

### Cost per site: arithmetic, not measured

No existing benchmark in the repo measures `FRINTI` or this site's cost (`tools/bench/` has no
`FRINTI`/`FCVTZS` hits, `grep`ped). Reasoning instead:

- Before: one instruction per inline FIST/FISTP, `FCVTZS` (`tcg_out_fpcvt`).
- After (switch on): two instructions, `FRINTI Vtmp, Vn` then `FCVTZS Rd, Vtmp`
  (`tcg_out_fist`, tcg-target.c.inc:3161-3177). The second has a true data dependency on the
  first's output register, so the pair cannot issue in parallel on the same site; the site's
  latency is the sum of both instructions' latencies, not the max.
- Both are ARM FP/SIMD instructions in the same class as the existing FP conversions already used
  throughout this backend (`FCVTZS`, `FCVT*`, `FADD`, etc. -- see the `AArch64Insn` enum,
  tcg-target.c.inc:600-710); published core optimization guides (e.g. Arm Cortex-A76/Neoverse N1)
  list `FRINT*` and `FCVT*` at comparable single-digit-cycle latency and 1/cycle or better
  throughput, so the added cost is on the order of one extra single-digit-cycle, fully-pipelined
  FP instruction per occurrence of an inline FIST/FISTP, not a stall or a memory access.
- Scope: this only affects a title's **inline** x87 FIST/FISTP sites (the ones JIT-compiled
  directly, counted per title by lane.x1port1012 at 32-63 for Halo); `helper_fistt*` (the
  non-inlined C helper path) is untouched, per x1port1012 NOTES.md:870. A hot loop that executes
  such a site every iteration pays one extra FP instruction per iteration; a title with none in
  its hot path pays nothing. This is consistent with run 13's regression leg (R: PASS, no
  crash, menu animates smoothly) and the owner's broader direction that default-on is a
  correctness fix whose cost is bounded per-site, not a global slowdown.

### FRINTI and FPCR.RMode: all four RC values, including truncate

Traced the full path from the guest's x87 control word to the ARM FPCR bit that `FRINTI` reads:

1. **`gen_flcr`** (`target/i386/tcg/translate.c:1732-1746`), called before every FP register
   access (`get_ft0`/`alloc_ft0`/`get_stn`/`alloc_stn`, `target/i386/ops_fpu.h:57,76,90,110` --
   this covers FIST/FISTP too, since they read an FPU register). It loads `fpuc` (the guest's x87
   control word), masks bits 10-11 (the x87 RC field, `& 0xc00`), shifts left 3 to land at bits
   13-14 (the MXCSR RC position), ORs in `0x1f80` (MXCSR's "mask all exceptions" bits, cosmetic),
   and emits one `INDEX_op_flcr` per TB (`s->flcr_set` latches it; reset by `gen_flush_fp`,
   translate.c:1807-1812, and by `dc->flcr_set = false` at TB start, translate.c:4627 -- the
   brief's "FLDCW ends the TB" is really "every new TB re-arms it", which covers an FLDCW that
   starts a new TB after it).
2. **aarch64 `INDEX_op_flcr`** (tcg-target.c.inc:3680-3711), gated by `BISECT_FP_FLCR`
   (tcg-target.c.inc:3125), which is `#define`d to `1` -- so this is the live path, not the
   `NOP: leave FPCR at... round-to-nearest` fallback at line 3709. The live path extracts the
   2-bit RC from the MXCSR-position bits, swaps bit0/bit1 (the comment at tcg-target.c.inc:3681-
   3685 states the two formats differ only by swapping RD/RU; RN=00 and RZ=11 are identical in
   both), shifts to FPCR's RMode field (bits 23:22) and writes it with `MSR FPCR`.
3. **The swap is a correct, complete map of all four values**, not just the common ones:
   RN (00) -> 00, RD (01) -> 10, RU (10) -> 01, RZ (11) -> 11. Checked against the ARM ARM's
   FPCR.RMode encoding (00=RN, 01=RP, 10=RM, 11=RZ) and the documented MXCSR RC encoding
   (00=RN, 01=RD/-inf, 10=RU/+inf, 11=RZ): the bit-swap is exactly the RD<->RU relabeling, so
   every one of the four x87 RC values reaches FPCR.RMode as the equivalent ARM rounding mode,
   including RZ.
4. **`FRINTI` honours FPCR.RMode by definition** (`I_FP1_FRINTI_S`/`_D`, tcg-target.c.inc:686-687,
   comment: "round to integral per FPCR.RMode" -- this is the instruction's architectural
   behaviour, not something this backend configures separately).
5. **Round-toward-zero still truncates with the switch on.** A guest that sets x87 RC to 11 (the
   `(int)` cast idiom, FISTTP, or an explicit `FLDCW` to e.g. `0xC00 | ...`) drives FPCR.RMode to
   `11` (RZ) by the chain above. `FRINTI` under RZ rounds-to-integral toward zero -- i.e.
   truncates -- so its output is already the truncated integer; the following `FCVTZS` (which
   always truncates fp-to-int, independent of FPCR) then converts that already-integral value
   exactly, losing nothing. So the RZ case is a no-op pair that reproduces the old single-`FCVTZS`
   result bit-for-bit. **A game that sets RC to truncate before FIST still truncates with the
   switch on.**

This directly answers the brief's break risk: the switch cannot regress a title that relies on
x87 truncate-before-FIST, because that path reduces to the old behaviour exactly.

## Prediction

`docs/testing/predictions/fistdefault1016-fistround.json`, registered below. Legs:

- **V**: the device log (Nova, Forza boot gate at fold) carries `perfarch fist round=ON (default)`
  with no `HAKUX_FIST_ROUND` in the run's env.
- **R**: the fold's device-run gate (Forza, 120 s, Nova) passes -- no crash/hang.
- **T**: by code reading only (no device leg needed to decide it): round-toward-zero RC still
  truncates with the switch on, per the FRINTI/FPCR.RMode trace above. Recorded here as a reading,
  not a device-measured leg.

This is an "on by default" flip of an already-verified fix (lane.x1port1012 run 13 already
proved B1-B3 and R for `HAKUX_FIST_ROUND=1` against the baseline bursts); this lane's own
prediction does not re-run that pixel-level A/B, it only confirms the default decided correctly
and that the regression gate still passes.

## Build check

NDK/Android compile check: see PR.md for the result (background build, `GRADLE_EXIT=`, JDK 21).

## Done

PR.md `State: ready` once the build check's exit code is in and the prediction is committed.
`Needs device: yes (Nova)`, `Needs NDK: yes`. The brief's four steps (default on, log rewording,
comment update, grep for other default-off claims) are all done; no other living doc needed a fix.

### preflight.sh territory gate: stale claim on a folded lane, not this lane's to fix

`bash docs/testing/preflight.sh` FAILs the `territory` gate: `docs/testing/nv2a_index.json is
claimed by both x1port1012 and fistdefault1016`. Checked `origin/board`'s `territory.toml`
directly (`git show origin/board:territory.toml`, not the stale, unrelated
`docs/testing/territory.toml` sitting in-tree from wave 94/2026-09-18): `[lane.x1port1012]` still
lists `docs/testing/nv2a_index.json` in its `files`, even though that lane folded
(`56fdef2c85 fold: lane/x1port1012-halo (offline)`, on `master`'s ancestry). A prior board update
(`6583bb5751`, 2026-10-16 ~19:00 PDT) moved `tcg/aarch64/tcg-target.c.inc` off x1port1012 onto
this lane's row but did not also release `nv2a_index.json` from the folded lane -- that half of
the move was missed, and it now collides with this lane's own (brief-granted, conditional) claim
on the same file.

Per AGENTS.md ("A lane cannot satisfy a gate it is barred from fixing", ~line 357): `territory.toml`
is barred to lanes, so the fix is a board request, not an edit. Filed
`$DISPATCH_DIR/board-requests/fistdefault1016.md` asking the board to release
`docs/testing/nv2a_index.json` from the folded `[lane.x1port1012]` (or, failing that, to drop it
from this lane's own row instead, since this lane never touches the file -- either side clears the
gate). This is the only preflight gate failing; `psh_differ`, `aci_vmstate`, the `nv2a_index`
freshness check (not needed here, see above), `coverage`, and the board-files check all pass.

This does not block marking the PR ready: every criterion this lane controls (the code change,
the evidence above, the committed+registered prediction, the passing NDK build) is met, and
AGENTS.md is explicit that a lane "must never be blamed for a gate it cannot reach." Ending this
session `waiting:` on the board resolving the stale x1port1012 claim.
