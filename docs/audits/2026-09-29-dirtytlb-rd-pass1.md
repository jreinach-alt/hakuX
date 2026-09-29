# Audit pass 1: PR #575, lane/dirtytlb-rd

`HAKUX_TCG68_RD` on by default: `tlb_reset_dirty()` / `tlb_set_dirty()` walk
only the MMU modes in `tlb.c.dirty` (#548). Head audited: `b30855c55a`.
Auditor: job.cloud, 2026-09-29.

**Verdict: no HIGH, no MEDIUM, two LOW.** The PR goes to `needs-audit-2`.

## What was checked

- **The diff:** 11 files, one of them code. `accel/tcg/cputlb.c` changes one
  line of behaviour: `hakux_tlb68_rd_on()` returns 1 when the variable is
  unset, instead of 0. The rest of the code diff is the header comment. The
  other ten files are lane NOTES, queue and register scripts, and four
  prediction files.
- **The switch reads the same way as `HAKUX_TCG68_JC`, which is already on
  by default.** `getenv(name) ? hakux_tlb68_env(name) : 1` is character for
  character the JC form at `cputlb.c:194`. The value is cached in a static
  after the first read, and `qatomic_read`/`qatomic_set` guard the benign race
  on the first read. Both threads compute the same value.
- **The exactness argument, re-derived from the tree at this head rather than
  taken from the comment or from `2026-09-25-tcgchurn-pass1.md`:**
  - `c.dirty` is written in three places only (grepped across the tree):
    - `tlb_init()` (`:575`) sets it to 0, with every mode initialised flushed.
    - `tlb_set_page_full()` (`:1468`) ORs in the mode's bit under
      `c.lock`, before any entry is installed in that mode.
    - `tlb_flush_by_mmuidx_async_work()` (`:627-634`) clears bits and, in the
      same critical section, runs `tlb_flush_one_mmuidx_locked()` on exactly
      the modes it cleared.
  - No file outside `cputlb.c` touches `c.dirty`.
  - The only writers of TLB entries are the following, all inside
    `cputlb.c`:
    - `tlb_set_page_full` (`:1492`, `:1538`).
    - The victim swap in `victim_tlb_hit` (`:1681-1683`), which stays
      within one mode.
    - `tlb_set_dirty1_locked` (`:1276`), which writes only to an entry that
      already matches.
    - The flush memsets.
  - Page flushes and large-page full-mode flushes leave the bit set, so the
    mode is still walked. They are conservative, not a hole.
  - Both walks read `c.dirty` under `c.lock`, the same lock every writer
    holds. This includes the cross-thread `tlb_reset_dirty` calls from
    `physmem.c` (the `rdo` path).
  - So a mode outside `c.dirty` holds only -1 entries. For those entries,
    `tlb_reset_dirty_range_locked()` returns on `TLB_INVALID_MASK`, and
    `tlb_set_dirty1_locked()` never matches because `addr | TLB_NOTDIRTY`
    is never -1. **Skipping those modes changes no entry.** I found no
    scenario in which B leaves an entry writable that A would have re-armed.
- **Other readers of the switch.** Outside this lane, it is named only in
  the old tcgchurn NOTES and audits. There, `=0` restores the full walk and
  `=1` still turns it on. No script on master relies on "unset means off"
  to build an A arm.
- **The header comment's figures** ("5,880 to 7,990 entries", "610 to 2,620"
  live) are sourced. They come from the Crimson and Blinx counter pairs in
  `docs/lanes/dirtytlb/NOTES.md:262-263` and from the Crimson pre-soaks in
  `dirtytlb-rd.json`.
- **CI:** both `build` checks are SUCCESS on the head, and the PR is
  MERGEABLE.
- **The registered evidence**, read from the PR body (I did not re-run it):
  - Crimson: every leg passes.
  - Pixels: 318 of 318 captures identical.
  - Signed suite: 19 of 19, three runs per arm.
  - Black: X FAIL, C/F/J void, K2 FAIL.

## Findings

### LOW 1: a registered falsifier fired and the PR lands anyway

`dirtytlb-rd-black.json`'s `falsifier` reads "Not exact: X fails", and X
failed. The failing clause is `sd` per flip: 125.3 in A against 162.0 in B,
+29%.

- **Scenario:** a reader who trusts the registered verdict alone concludes
  that the switch is inexact on Black.
- **Why this is LOW and not HIGH:**
  - The failure points the wrong way for inexactness. `sd` counts
    `tlb_set_dirty` calls, which come from notdirty-write traps. A walk that
    left entries writable would take fewer traps, so it would show fewer
    `sd`. B shows more.
  - `sd` per walk is 1.209 in both arms.
  - Within arm A, `sd` tracks the number of walks with r = 0.997.
  - So the clause measured scene load (B drew 118.8 walks per flip against
    85.7, and K2 is ×1.19), not exactness. This is the "a failing leg of
    this shape is evidence about the model" case in AGENTS.md.
  - Independently of the arms, the code read above finds no path by which
    the switch can be inexact.
- **The PR is candid about all of this.** It keeps the registered verdict
  as FAIL and names the replicate that would register a per-walk X.
- **What remains is a decision, not a defect.** Landing over a fired
  falsifier is the board's call, and this audit records that the code gives
  no reason to refuse it.

### LOW 2: any set value other than a leading "1" turns the fix off

`hakux_tlb68_env()` returns `v[0] == '1'`. So `HAKUX_TCG68_RD=on`, `=true`,
`=yes` or `=` (empty) all turn the fix **off**. Only unset or `1…` keep it
on. The comment says '"0" turns one off', which suggests that other values
keep it on.

- **Scenario:** someone sets `HAKUX_TCG68_RD=true` to force the fix on and
  gets the 22-mode walk.
- **Blast radius:** performance only, since both walks are exact. The
  behaviour is shared with `HAKUX_TCG68_JC` and predates this PR.
- **Optional fix:** treat only a leading `0` as off, or reword the comment
  to say "anything but 1 turns it off".

## Not findings

- The NOTES, scripts and prediction files are lane records. The two
  soak predictions (`dirtytlb-rd.json`, `-black.json`) have `expect: {}`
  on purpose and are hand-queued. Nothing in them runs in CI or on master
  at runtime.
- The ns-per-entry gap between Black and Crimson is unexplained (7.7 to 9.2
  against 1.3 to 2.8). The prediction says so, and it does not bear on
  correctness.

## For pass 2

Neither LOW needs a code change to fold. Pass 2 should confirm three things:

- The code line on the head is still the JC form.
- The `c.dirty` writer set is still the three sites above, in case a merge
  from master brought in a new fill or clear path.
- LOW 1's decision is visible in the PR, which it already is.
