# Audit pass 1 — PR #102, `lane.blitsafe`: #92's instrument, #89's narrowing, and the rebase

**Auditor** `job.cloud` (claims no files; audit record only).
**Subject** PR #102, branch `lane/blitsafe`, tip **`aec3641413`**, nine commits
over `origin/master` (**`55bc6c6c2b`**).
**Date** 2026-09-19. **Records** `2026-09-19-blitsafe-pass1.{md,json}`.

**0 HIGH. 2 MEDIUM. 5 LOW.**

**The compiled code in this diff is clean.** I verified #89's "the two
expressions agree by construction" chain end to end, at the tip rather than
from the commit message, and it holds: there is exactly one divergence route
and the lane names it. I found no HIGH and no MEDIUM in `hw/`.

**Both MEDIUMs are in the instruments, not in the emulator.** M1: this PR's
rebase left #88's and #91's registered arms bound to a commit pair that is
reachable from **no ref at all**, and `arms.sh` skips such a prediction
structurally and permanently — so neither arm can ever be re-queued or
re-verified, including by pass 2. M2: `clr89_probe()`'s print gate makes the
heartbeat mutually exclusive with divergence reporting, so in the one world the
probe exists to detect the log goes **silent**, which this project's own rule
reads as VOID.

The commits from the earlier round (`67dc7724ee`, #88's policy) were audited at
`2026-09-18-blitsafe-pass{1,2}` at their pre-rebase shas. I re-checked that the
rebase preserved them and did not re-litigate their findings; the carry-forward
is at the end.

---

## What is new in this PR, and what was audited before

| commit | new to this round? |
|---|---|
| `67dc7724ee` #88 policy | no — audited as `4726557b0f` |
| `b6017b1b93` re-bind #88's arm | no — pass 2's M2 CLOSED, M3 OPEN |
| `cde230bf1d`, `48f89a6260` #91 docs | yes |
| `3f2563d6e9` the two probes | **yes** |
| `77bd2977cc` #89's narrowing | **yes** |
| `ec14e56377`, `aec3641413` #89's prediction | **yes** |
| `2f26267904` #92's investigation record | **yes** |

The rebase itself is new and is where M1 comes from.

---

## M1 — MEDIUM. #88's and #91's arms are bound to commits reachable from no ref, and `arms.sh` skips them permanently

`docs/testing/predictions/issue88-vk-same-offset-colour-wins.json` (modified
here) and `docs/testing/predictions/issue91-swap-solo-classification.json`
(**added** here) both register:

```
"a_ref": "f343580647",
"b_ref": "4726557b0f",
```

Both objects still exist in this host's object database. Neither is reachable
from anything:

```
$ git branch -a --contains f343580647   # (empty)
$ git branch -a --contains 4726557b0f   # (empty)
$ git merge-base --is-ancestor f343580647 HEAD; echo $?   # 1
```

### The scenario, from the harness's own code

`docs/testing/jobs/arms.sh:130-135` defines `live_ancestor()` as "is `$1` an
ancestor of the trunk or of any lane tip", and `:213` applies it:

```
live_ancestor "$b" || { skip "$sha" "$src: b_ref $b is not an ancestor of
    $TIP or any lane branch (stale registration; re-register on live refs)"; continue; }
```

`already_ran()` at `:99-127` then says, in its own words, that this class of
skip is terminal: *"Structural skips (no `a_ref`, `a_ref == b_ref`, a ref that
does not resolve, **a stale `b_ref`**, a soak, no suite with goldens) never
carry that text and stand until the prediction itself changes, because no edit
to this script can turn one of them into a run."*

So:

- the arms job will **never** queue either prediction, on this tick or any
  later one, until the file's bytes change;
- **audit pass 2 cannot re-verify #88's or #91's arms**, which is the one thing
  pass 2 exists to do, and the #88 policy is the only code in this PR with a
  device-measured justification;
- `git gc` will eventually delete both objects, at which point even a manual
  `ab_run.sh` on this host stops working — and until then a manual run *would*
  succeed against a tree 109 commits behind master and report a clean,
  confident measurement of it.

### This is pass 2's M3, in the direction pass 2 said was dangerous

`2026-09-18-blitsafe-pass2.json` recorded M3 as OPEN with the note that
`f343580647`/`4726557b0f` were at that moment **ancestors of the lane branch**
("checked with merge-base, not assumed") and that the danger was the fold
rewriting them. The rebase in this PR did the rewriting a fold would have done,
and the registration was not moved with it. A second prediction file — #91's,
new in this PR — was then registered on the same already-dead pair, so it is
dead on arrival: it has never been runnable by the arms job and never will be
in its current form.

### Remediation, and it is cheap — but it is a claim, not an instruction

The live equivalent of the dead pair is `a_ref 55bc6c6c2b` (`origin/master`,
which is `67dc7724ee^`) and `b_ref 67dc7724ee`. **Verified rather than
assumed** — the two pairs are the same one-file change:

| pair | `git diff --stat` | patch-id of the `vk/surface.c` diff |
|---|---|---|
| `f343580647` → `4726557b0f` | `vk/surface.c` only, +61 −2 | `4e14c872b0957eb185a4f7075393ad3581e7087e` |
| `55bc6c6c2b` → `67dc7724ee` | `vk/surface.c` only, +61 −2 | `4e14c872b0957eb185a4f7075393ad3581e7087e` |

Identical. So re-binding preserves the property both predictions rest on — that
the arms differ in `vk/surface.c` alone — and preserves it by patch-id rather
than by assertion.

**Two costs the lane should weigh before taking this, and the second is the
reason I am not treating re-binding as obviously correct:**

1. Re-binding changes the file's bytes, hence its sha256, hence `arms.sh`'s
   candidate identity — so both arms get **queued again** (5 runs × 2 arms ×
   2 predictions). That is real device time for results already obtained.
2. The new pair sits on a different base: 109 commits of `master` that the old
   pair did not carry. The *absolute* values need not reproduce. #88's own
   prediction already conditions on this ("ARM A IS THE CHECK … If arm A comes
   back at other values, then the claim is the DELTAS"), so a re-run is
   readable — but it is not the same measurement, and a miss on an absolute
   must not be read as the mechanism failing.

If the lane judges the re-run not worth it, the alternative that also closes
the finding is to say so **in the file**: record the verdict as historical and
the refs as unrepeatable, so the registration stops reading as a live claim
that a reader would expect to be able to check. What must not remain is a
prediction that looks live, is silently skipped forever, and names a binary
nobody can rebuild.

---

## M2 — MEDIUM. `clr89_probe()`'s heartbeat is mutually exclusive with divergence reporting, so the interesting world reads as VOID

`hw/xbox/nv2a/pgraph/vk/draw.c:846`:

```c
/* Every divergence for the first twenty, then a heartbeat. */
if (!(diverged ? g_clr89.diverged <= 20 : g_clr89.clears % 512 == 0)) {
    return;
}
```

The two arms of the ternary are alternatives, not alternatives-plus-a-floor.
The heartbeat `g_clr89.clears % 512 == 0` is evaluated **only on a clear that
did not diverge**.

### The failure scenario

Divergence becomes persistent — every clear from some point on takes
`drawn_format != shape_format`. That is not a corner: it is the world the probe
was written to detect, and `docs/investigations/surface-shape-has-no-address.md`
describes the route (`framebuffer_dirty()` returning false on a changed shape
when `!color_format && !zeta_format`, `vk/surface.c:121-123`) as a state a
surface stays in rather than passes through.

In that world the probe prints exactly twenty lines — `diverged=1` through
`diverged=20` — and then **nothing at all**, because every subsequent clear
takes the `diverged` arm and fails `diverged <= 20`. The reader sees a log that
stopped. Under `dispatcher.sh:934` ("SILENCE IS VOID, never pass. An absent
line means the capture failed, not that the condition did not occur") that run
is unreadable, and the prediction file's own instruction — "`[clr89] diverged=N`
is what a log run reports, and SILENCE IS VOID rather than pass" — cannot be
followed, because the final `N` is never printed. Twenty divergences and twenty
thousand are indistinguishable from each other and from a filtered tag.

This is not hypothetical asymmetry: `surf92_probe()` at `vk/surface.c:208-209`
gets it right, and the contrast is the evidence.

```c
if (!(missed_now || (addr_change && g_surf92.addr_change <= 64) ||
      g_surf92.updates % 2048 == 0)) {
```

Three ORed conditions: the event is never suppressed, and the heartbeat fires
on its own schedule regardless of what the event did. `[surf92]` always tells
you it is alive; `[clr89]` stops talking exactly when it has the most to say.

**Remediation.** Make the heartbeat independent, the way `surf92_probe()` does:

```c
if (!((diverged && g_clr89.diverged <= 20) || g_clr89.clears % 512 == 0)) {
    return;
}
```

That keeps the flood cap on divergence lines and restores the periodic
`diverged=` total in every world.

---

## The LOWs

### L1 — `g_clr89.no_binding` is structurally always zero, and prints as if measured

`draw.c:836-838` counts clears reached with `r->color_binding == NULL`, and
`:831-833` falls back to `shape_format` in that case. Neither can happen. Every
call site of `pgraph_vk_get_clear_color()` is guarded on the binding:
`draw.c:6864` (`if (write_color && r->color_binding)`, inline path),
`draw.c:6946` (fall-through path, both the all-channels branch at `:6958` and
the blend-constants branch at `:6963` sit inside it). The function's own new
comment says as much — "Every caller already guards on `r->color_binding`".

Not a defect: the fallback is a correct backstop and costs nothing. Filed
because `nobind=0` appears in the log line beside three counters that *are*
measurements, and this project has a name for a row that cannot be anything but
its registered value. A reader totting up "the no-binding case never occurred"
would be reading a constant. Either drop the field or mark it in the format
string as structural.

### L2 — both probes are unconditional in the shipping build's hot path, and nothing on the branch removes them

`surf92_probe()` is called from `update_surface_part()` (`vk/surface.c:3311-3313`)
on every upload-side call, and `clr89_probe()` from `pgraph_vk_get_clear_color()`
(`draw.c:866`) on every clear. Neither is behind `#if NV2A_PERF_LOG`, a config
flag, or a runtime toggle — unlike `vaf_stats_log_and_reset()` and
`opt_stats_log_and_reset()` alongside them in the same file. Android is the
build that ships.

The per-call cost is a call and three increments, which is small, and the
project has precedent for permanent `hakuX` probes. The finding is not the cost;
it is that **nothing schedules their removal**. The PR body, `NOTES.md` and the
investigation record all describe them as instruments for one arm, and the fold
has no step that takes them out. A logged decision is required either way:
"they stay, because X" is acceptable, silence is not.

### L3 — the `[surf92]` line prints `updates` and `shapedirty` on different denominators

`vk/surface.c:213-219`. `g_surf92.updates` is incremented once per
`update_surface_part()` (`:190`), of which there are up to **two** per
`pgraph_vk_surface_update()`. `g_surf92.shape_dirty` is incremented once per
`pgraph_vk_surface_update()` (`:3677`). The two numbers sit adjacent in one log
line and invite being read as a ratio; `shapedirty/updates` is not one, and is
wrong by up to 2×. `addrchg` and `missed` share `updates`' denominator and are
fine. A word in the format string, or counting `shape_dirty` per part, fixes it.

### L4 — three artifacts cite `draw.c:6751` for a call that is at `:6757`

The claim "`pgraph_vk_clear_surface()` calls that `surface_update` before every
clear" carries the citation `draw.c:6751` in all three places it is made: the
code comment at `draw.c:806`, `issue89-clear-pad-alpha-shape.json`, and
`docs/investigations/surface-shape-has-no-address.md`. `:6751` is
`write_zeta = (parameter & (…_Z | …_STENCIL));`. The call is at `:6757`.
Separately, `issue91-swap-solo-classification.json` and the #92 record cite
`pgraph.c:2386` for `surface_color.buffer_dirty = true`; `:2386` is
`pg->dma_color = parameter;` and the flag is set at `:2387` (the #92 record's
prose gets this right — "one line below the `dma_color` write itself" — while
its table's number does not).

Cosmetic, and the claims themselves are true. Filed because this lane's
citations are otherwise exact — I spot-checked ten and eight were on the nose —
and the whole point of citing a line is that the next reader can refute it in a
minute rather than re-derive it.

### L5 — the branch is uncompiled, and I could not build it either

The PR body says so plainly, which is the right thing to have done. I read for
the two failure modes the body itself names as most likely and found neither:

- `<android/log.h>` is reached by both edited files transitively —
  `renderer.h:41` includes `debug.h`, which includes it at `:26` under
  `#ifdef __ANDROID__`. `vk/surface.c` had no `__android_log_print` before this
  commit, so this was worth checking; it is fine.
- The desktop `fprintf` fallbacks (`surface.c:174-176`, `draw.c:817-819`) use
  only `HWADDR_PRIx` and `%lu`/`%d`/`%s`/`%02x`, all of which match their
  arguments (`vram_addr` is `hwaddr`, `renderer.h:290`), and `stdio.h` arrives
  via `qemu/osdep.h`.

Reading is not a build. This stands as the open item the PR body already
identifies as the most important next step.

---

## What I checked and found clean, stated so pass 2 does not re-derive it

**#89's narrowing is sound, and the "agree by construction" chain holds.** I
walked it at the tip rather than accepting the commit message:

| step | verified at |
|---|---|
| `framebuffer_dirty()` memcmps the whole `SurfaceShape`, `color_format` included | `vk/surface.c:118-125` |
| a dirty shape sets **both** `buffer_dirty` flags | `:3681-3682` |
| a set `buffer_dirty` NULLs the binding before `update_surface_part()` | `:3685-3687`, `:3689-3691` |
| a NULL binding opens the gate | `:3308-3309` |
| the compatible-reuse path refreshes `drawn_format` from the live target | `:3500` |
| `target.drawn_format` **is** `pg->surface_shape.color_format` | `:3215` |
| the clear calls `surface_update` first, and every call site guards on the binding | `draw.c:6757`, `:6864`, `:6946` |

Every path through an open gate leaves the bound surface's `drawn_format` equal
to `pg->surface_shape.color_format` — the compatible hit refreshes it, the
incompatible path evicts and `*surface = target`, the create path likewise. So
the old expression and the new one can only differ when the gate does **not**
open on a changed shape, which is the `!color_format && !zeta_format` early-out
at `:121-123` and nothing else. That is the hole the lane names, registers as
the world in which its leg fails, and declines to close for the right reason
(the function is duplicated verbatim at `gl/surface.c:997`). I could not find a
second route.

**And that hole is not an unsafety.** In it the new code passes
`color_format == 0` to `pgraph_glsl_surface_pad_alpha_mode()`, which is a plain
`switch` with a `default: return PSH_PAD_ALPHA_NONE` (`glsl/psh.c:236-248`) —
no table index, no out-of-range read.

**`surf92_probe()`'s `missed` is a genuine discriminator, not a restatement.**
I traced what it can actually count. `pgraph_vk_surface_update()` unbinds
*before* calling `update_surface_part()` whenever `buffer_dirty` is set
(`:3685`, `:3689`), so at probe time a non-NULL `current_binding` implies
`buffer_dirty == false`. `gate_open` therefore reduces to `mem_dirty`, and
`missed` reduces to "a binding is held, the target address differs from it, and
the CPU did not write the memory" — which is world (a) and cannot be world (b).
The probe's stated contract survives contact with the code.

**The tag will actually be captured.** Both probes log under `hakuX` at
`ANDROID_LOG_INFO`, and `hakuX:I` is in `dispatcher.sh:973`'s default
`LOGCAT_SPEC`. The comment's reasoning for not using `hakuX-lane` is correct.

**The zeta decline's download-path reachability is unchanged from the previous
round and is not re-raised.** `2026-09-18-blitsafe-pass1` filed it as L3 and
pass 2 DECIDED it, accepting both declines and establishing the sharper fact
that the early return is *required* on that path because
`download_surface_deferred()` dereferences its argument (`vk/surface.c:1461`).
I re-read that path against the rebased tree and reached the same conclusion
independently: `pg->surface_zeta.draw_dirty` is left set by the decline, and
the harm is bounded to repeated no-op work because
`download_surface_deferred()` guards on the *binding's* `draw_dirty`, not the
pg-level flag, so no spurious VRAM write can follow. Carried forward as decided,
not refiled.

---

## Carried forward from `2026-09-18-blitsafe-pass2`, unchanged by this diff

- **N1** (LOW, OPEN) — `nv2a_index.json` stale at the arm-A ref. This PR
  restates it with a new and stronger reason: regenerating on this host would
  write 102 suites where 103 are committed, because the local
  `nxdk_pgraph_tests` checkout (`33e7c6b0`) predates the `Surface as vertex
  array` suite. That is the right call and it matches the standing rule that a
  regeneration against an older tests tree silently deletes a suite.
- **N2** (LOW, OPEN) — the three-suite disc requirement for #88 is carried in
  prose only. Unchanged.
- **N5** (LOW, OPEN) — the Khronos validation layer is owed and not covered, on
  two independent blockers. This PR adds a third Vulkan-backend change on top
  of the two that already owed it. I could not run it either; the PR body's
  account of why is consistent with what pass 2 measured.
- **M3** (MEDIUM, OPEN) — now superseded by **M1** above, which is the same
  defect after the event pass 2 predicted.

I could not verify the #89 prediction's leg arithmetic ("42 legs, of which 32
can fail") because `/home/justin/goldens/` is outside this session's reach. The
lane states it checked every key against a golden on disk. Pass 2 should count
them; if the count is right, the commit that states which ten legs are inert is
the most useful thing in this PR after the narrowing itself.

---

## Verdict

**HIGH: 0. MEDIUM: 2 (M1, M2). LOW: 5 (L1–L5).**

Per AGENTS.md, every HIGH and MEDIUM is remediated before the fold, and every
LOW gets a logged decision. **PR #102 goes to `needs-remediation`.**
