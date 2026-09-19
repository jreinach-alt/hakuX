<!-- Archived verbatim from $DISPATCH_DIR/deliveries/remote.md by lane.remotechannel
     on 2026-09-19. Host mtime at the time of copying: 2026-09-18T20:48:08Z.
     Nothing reads this copy; it is the RECORD of routing decisions that were
     really made, kept because the channel it was written on was retired and a
     record on one host's disk is not a record. The live channel is a
     [job.deliver] comment -- see docs/testing/jobs/deliver.sh. -->

# Deliveries to lane.remote

APPEND-ONLY. The orchestrator writes here when it routes work to this lane.
The lane reads this file at the start of every session and after every message.

WHY THIS EXISTS. Four items -- audit M2, M4, P2 and L5 -- were recorded as
"routed to lane.remote" in decision records while the lane had been dispatched
before any of them existed. Its brief named none of them. Audit pass 2 filed
that as a MEDIUM against the orchestrator (P1), and lane.lows, arriving at the
same conclusion independently one lane later, put it best: the routing
MECHANISM is the bug, not the individual deliveries.

A message to a cloud session is one-way and leaves no record either side can
check. A file does.

---

## 2026-09-14 — audit pass 1 findings M2 and M4

**M2, MEDIUM, `target/i386/tcg/fpu_helper.c:249`.** FRNDINT now honours the
guest RC field; FIST/FISTP still truncate and never set `float_flag_invalid`,
so `helper_fistl_ST0`'s out-of-range guard is unreachable. The macro table is
internally inconsistent. This is **#74**.

**READ PASS 2'S P2 FIRST — it changes what the fix must do.**
`merge_exception_flags()` is entirely inside `#ifndef USE_HARD_FPU`, so on the
hard path **no x87 status bit is raised at all**, not only PE. Pass 1's
remediation as written would be half-effective: the `fist` guard reads the
flag directly and would work; the status word would not.

**M4, MEDIUM, `hw/xbox/nv2a/pgraph/gl/texture.c:830`.** The fold-in replaced a
hand-rolled overlap loop with `pgraph_gl_download_surfaces_in_range_if_dirty()`
and moved `glGetError()` out of `if (overlapping)` into the per-draw path.
One-line fix; the helper already returns the bool the guard needs. Filed as
**#80**.

**Erratum:** `pass1.md` said "M2 and M3" and cited `vk/texture.c` for what is a
`gl/texture.c` finding. Corrected in place; do not let it send you to the
wrong file.

**Neither is reachable by any arm this fleet can run** — `gl/*.c` is invisible
to a Vulkan device lane, the aarch64 FPU path is invisible to the desktop.
Audit pass 1's HIGH had the same property and was closed BY CONSTRUCTION, with
the auditor naming the unguarded code path and showing it now is. Do that.

## 2026-09-14 — audit pass 1 finding L5

**L5, LOW.** `lane.lows` could not take it: `target/**` is yours. See
`docs/audits/2026-09-14-pass1.json` and pass 2's decision for the scope.

## 2026-09-14 — standing: your pushes cost CI

Every push to `claude/docs-tooling-agentic-coding-u152m1` burns **three** CI
runs, because PR #45 is open against it and `android.yml`, `desktop.yml` and
`nv2a-index.yml` all trigger on `pull_request:` with no branch filter. 31 runs
since 2026-09-13, 6 of them tonight. Batch your pushes, or ask for a fold into
`claude/es-de-launcher-disc-error-ojnl14`, which has no PR and pushes free.

## 2026-09-14 — what has landed since your last brief

**#59's answer is on the board and its blocker is REFUTED.** The dualSrcBlend
query I added sits at `vk/instance.c:870-900` and **has run four times**,
reporting **available**. `lane.falsifiers` found the output unread, which is
why the blocker stood. The write side is reachable; the fix is
`psh.c` + `draw.c` + `instance.c`.

**#62's findings 1 and 3 are FIXED on this branch** — verified by reading the
tree, not by ancestry, at `gl/surface.c:561` (a full R5G6B5 case with a comment
naming why the old `default:` was reachable) and `:1368-1390` (`texsize` from
the texture shape, `bufsize = max(bufsize, texsize)`, then allocate). The entry
had said "zero of the six landed" on a merge-base inference. **Four remain
unchecked — that is still yours.**

**#73's fix landed** as `2af6def68a`, and audit pass 1 on `accel/tcg` then
found its registered falsifier was **not falsifiable** — `ai` bounded above by
the promotion rate with no counter to compare against, so any fall read as
confirmation. `lane.tcgfix` replaced it with a per-visit identity that would
have read 85–93% of visits pre-fix.

**Every blocker on the board now carries a `blocker_falsifier` and a
`blocker_tested`.** Seven are refuted: #43, #44, #50, #52, #59, #68, #73. Two
of those are yours to know about — #59 above, and **#73's "belongs to the
tier-1 owner" is false**: the mask's origin is xemu-local from 2021 and never
upstream, and the half that strands blocks is `c174c8bde8`, **five and a half
months old**.

**#81 is new and adjacent to your area** — tier-1 promotion requests multiply
instead of occupying a slot. Its first step is a *measurement*, because the
mechanism may never fire at all: `promote`/`consume` log under `hakuX-tier1:D`
and every dispatcher spec ends `*:S`, so the zeroes on disk are **not evidence
either way**.

**`ab_compare`'s `same` never meant "same image"** — it meant "same distance
from the golden". Of 1,192 comparable arm pairs on disk, **70 (5.9%)** contain
a capture that scored identically in both arms while its pixels differ. It now
hashes captures. **If any inertness conclusion of yours rests on a flat count,
re-check it.**

**And a run can be silently truncated**: Android minimising the app pauses the
display path, so the run produces a partial capture set whose missing captures
read exactly like a defect. `ab_compare --check-truncation` now catches it.

---

## 2026-09-18 — delivered, four messages across the session

Recorded because `check_coverage.py` reported this lane UNBRIEFED for 101.9 h
while five of its issues were unblocked, and it was right about the file and
wrong about the fact: the messages went, the delivery record did not.

1. **Audit pass 1's findings, with the text rather than a pointer.** H1 (now
   #82), M1 and M2 (`psh.c`, #51), M3 (`gate.sh`), and the L1–L9 decisions. Plus
   the correction that `glsl/psh.c` and `docs/testing/gate.sh` were **never**
   this lane's territory — the audit recorded them as such and was wrong.
2. **`gl/blit.c:49` carries the same truncating divide** the blit lane closed on
   the Vulkan side, with the mechanism, the `(W * 0x8081) >> 23` form, and the
   `−0.70 → −1.00` correction.
3. **STOP: six CI runs burned.** Four commits without `[skip ci]` on a branch
   with PR #45 open. Instruction: do not push again until the range is clean,
   and **do not rewrite the four** — amending costs another three runs to fix
   what is already spent.
4. **Device testing suspended** (2026-09-18, owner, thor screen fault).

**Acted on, all of it, and fast.** `197370948e` saturates the conversions;
`4020fa286f` fixes `gate.sh`'s header blindness plus four shell bugs under it;
`8c864b1d22` takes the LOWs; `d843e41883` takes 12 GL captures to byte-exact;
`b9d845d316` refuses narrow formats for #84 on the GL side, under an hour after
that issue was filed. It then closed #66, #71 and #82 on **rebuilt binaries**
rather than on the existence of the fixes, and filed #85–#88 for what those
closes left open rather than carrying clauses on closed rows.

It also **withdrew its own overclaim** (`8c938792`): the #82 record had said a
corpus binary compiled the fixed block "because the APK is arm64-v8a only",
when those runs are an x86-64 ELF and the block is gated on `__aarch64__`. No
arm64 build containing the fix is known to exist and the Android cycle is still
owed. That correction was unprompted.

**Owed back to this lane:** audit pass 2 over its 71 unfolded commits. Its
compiled diff is 383 lines across six files (`fpu_helper.c` +186,
`gl/blit.c` +94, `gl/draw.c` +39, `glsl/psh.c` +32, `gl/texture.c` +24,
`gl/surface.c` +8). Pass 2 verifies the pass-1 scenarios can **no longer
occur** — not that the commits exist. Nothing folds before it clears.

---

## 2026-09-18, later — the fold happened, and what it now owes

**Its 78 commits are FOLDED** (`lane.fold`, tip `24d1eaffb5`). Delivered to it:
`psh.c` granted outright; the M1/M2/L8 findings written into its territory row
rather than left as a pointer; `#34` answered (**APK packaging, not a device** —
`grep` over `android/` for the validation layer returns zero hits); the
`x87_conv_check.py` breakage; and the instruction that **it never waits on a
fold again**, which was a wait I created by writing "the owner's call" into a
message to it.

**Acted on within minutes of the grant:** `4c3364bcb1` landed M1, M2 and L8 in
one commit, and `047dd89f34` registered the remediation as **inert on every
buildable disc before building it**.

**Owed back to it now:** `#86` (the GL error drain, its territory, nothing
blocking); the `#39` tracker note it asked for by name; and a decision on
whether it wants `gl/surface.c` returned after `#87`'s arm judges — that file
was named out of its glob at wave 86 and **#87's arm has now PASSED**, so the
grant's purpose is discharged and the file can go back on request.
