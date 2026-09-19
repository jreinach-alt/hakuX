# Audit pass 2 — PR #143, `lane/diagdump77` (#77), over the remediation of pass 1

**Auditor** `job.cloud` audit-2 (claims no files; audit record only).
**Subject** PR #143, branch `lane/diagdump77`, tip **`a8515c65f7`**, one
remediation commit over pass 1's record `7fa7d27047`:

| commit | what |
|---|---|
| `23445c158d` | merge of `origin/master` (pass 1's out-of-scope note: the PR was `CONFLICTING` on `nv2a_index.json` and therefore had no workflow run on its merge commit) |
| `a8515c65f7` | **H1, M1, M2, M3 and all five LOWs**, plus the regenerated index over the merged tree |

**Pass 1's record** `docs/audits/2026-09-19-diagdump77-pass1.{md,json}` — 1
HIGH, 3 MEDIUM, 5 LOW.
**Date** 2026-09-19. **Records** `2026-09-19-diagdump77-pass2.{md,json}`.
**CI at this head** Android `build` SUCCESS, Desktop `build` SUCCESS, NV2A
index `check` SUCCESS. PR is `MERGEABLE`.

**1 HIGH, 3 MEDIUM and 5 LOW closed as written. 2 new MEDIUM, 2 new LOW.**
**Not clean → `needs-remediation`.**

Every pass-1 scenario was re-driven rather than read off the commit message:
the checker findings against dumps I built, the C findings by tracing the live
tree (`vk/surface.c`, `vk/draw.c`) from the flip forward, not the diff. H1's
mechanism is genuinely fixed — I traced the fence the completion waits on and
it is the one the flip's own spin-wait already guaranteed was submitted, so
the steady-state scenario cannot recur. M2's scenario I reproduced exactly as
pass 1 built it and watched it refuse instead of invert.

**Why this is not `fold-ready`.** Both new MEDIUMs are in the code the
remediation wrote, and both are the same shape as the findings they replace —
an artifact making a claim its mechanism does not support:

* **N1** — the image can *still* be a frame behind, in the states where the
  flip's pre-record did not happen. H1's fix completes whatever download was
  outstanding; it never checks that the display surface was one of them. The
  new `img_sync` field is `-1` or a stale frame slot in exactly those states,
  and its documented meaning is the opposite. This is H1's failure in a
  narrower state, with a field that now asserts it did not happen.
* **N2** — the M2 refusal fires on `cb_draws` evidence that *does* settle the
  question. `max_cb >= 2` means a command buffer held two draws, which no
  per-draw finish can produce at any sample size; the checker throws that
  verdict away and prints "Neither column can distinguish the two paths on
  this dump", which is false of such a dump. A soak that answered the
  question comes back reading as if it had not.

Both fixes are small and neither touches the headline claim. N1 is one test
against `disp->draw_dirty` after the completion; N2 is one more term in the
refusal condition.

---

## H1 — CLOSED. The image is now written after the fence its own records were
submitted under

Pass 1's scenario: a soak arms `30,after120` on a normal 3D title, the display
surface is `draw_dirty` at every flip, `prerecord_display_download()` returns
true each time, and every PPM holds the most recently *completed* download
rather than the frame whose draw records it is filed under.

Pass 1 asked pass 2 to **check the mechanism, not the words**. Traced forward
from the flip on the live tree:

1. `pgraph_vk_prerecord_display_download(d)` (`renderer.c:2223`) records the
   copy and, by way of `download_surface_record_deferred()`, leaves
   `num_deferred_downloads >= 1` (`surface.c:781`) with
   `display_predownload_pending = true` and
   `display_predownload_frame_index = r->current_frame`
   (`surface.c:1651-1652`).
2. `pgraph_vk_finish(FLIP_STALL)` sets `deferred_downloads_frame =
   r->current_frame` at `draw.c:3459` — this runs *before* the deferred/
   immediate branch, so it happens on the deferred path too — then enqueues
   and spin-waits on `frame_submitted[deferred_frame]` (`draw.c:3581-3585`).
   The frame-rotation block completes only for `next_frame`
   (`draw.c:3663`), which is not `current_frame` for `num_active_frames >= 2`.
   Pass 1's step-by-step is correct and still correct.
3. `fdump_end_frame()` (`renderer.c:2113-2121`) now calls
   `pgraph_vk_download_surface_complete_deferred(d)` **before** the VRAM read.
   That function takes its first branch (`surface.c:918-927`) because
   `display_predownload_pending` is true: it waits
   `frame_fences[display_predownload_frame_index]` — guarded by
   `frame_submitted[fi]`, which the step-2 spin-wait has already set for that
   exact slot — and then runs `pgraph_vk_complete_staged_downloads()`
   (`surface.c:942`), the staging→`dest_ptr` memcpy, where `dest_ptr` is
   `d->vram_ptr + surface->vram_addr` (`surface.c:784`, the pointer prerecord
   passed at `surface.c:1629`). The same pointer `dump_surface_ppm()` reads.

So in the scenario as pass 1 wrote it, the pixels are in VRAM before the read,
and the fence waited on is the one this frame's draws were submitted under.
The scenario cannot recur.

Two things I checked rather than assumed:

* **The falsifier columns are untouched.** `complete_deferred` on this path
  issues no `vkQueueSubmit` — it waits an existing fence and memcpys. The
  `else` branch that would call `pgraph_vk_finish(SURFACE_DOWN)`
  (`surface.c:937`) is unreachable here: it requires
  `deferred_downloads_frame < 0`, and step 2 has just set it. `submit_count`
  and `draws_in_cb` are therefore unmoved by construction, not by argument.
  The lane is still right that a device should re-read them.
* **The call is safe where it now sits.** `flip_stall` already does far more
  Vulkan work at this point when a diag capture is active —
  `pgraph_vk_finish(SURFACE_DOWN)` and `pgraph_vk_surface_download_if_dirty()`
  at `renderer.c:2275-2302`, in the same function on the same thread — and
  `pgraph_vk_process_pending_downloads()` calls the identical function from
  the same pfifo/pgraph thread (`surface.c:1692`). Nothing new is introduced.

Chosen option (a), which pass 1 costed honestly; the three places pass 1 named
as asserting the old belief (`fdump_end_frame`'s comment, `NOTES.md`, the
`AGENTS.md` section) and the PR body all now say the opposite and say why. One
place was missed — see N3.

## M1 — CLOSED. Android has no fallback directory, and both refusals log

Pass 1's scenario: a soak arms `--env XEMU_FRAME_DUMP=30,after120` on a device
without writable external storage; `fdump_base_dir()` falls through to
`xemu_settings_get_base_path()` (internal storage), the env arm fires, and 30
frames plus ~27 MB of PPMs are written where `--pull` cannot see them, with a
success line naming the path.

`fdump_base_dir()` now returns `NULL` under `__ANDROID__`
(`renderer.c:1612-1616`); desktop keeps the fallback. Both consumers refuse:
`fdump_begin()` returns with a `FDUMP_LOG` line before opening anything
(`renderer.c:1792-1799`), and `fdump_poll_marker()` returns early with a
one-time WARN (`renderer.c:1924-1935`) placed *above* the pending/env-arm
handling, so the env arm is covered and not only the marker. `grep` confirms
these are the only two callers of `fdump_base_dir()` — the marker path's
second use at the old `renderer.c:1827` now reuses the checked `base`. The
`XEMU_FRAME_DUMP_DIR` override is read first and so still works on Android.
The scenario cannot recur: there is no path for an Android run to open a dump
file under internal storage.

L2 closed with it — `xemu_android.cpp:1136-1156` is one `else` covering both
the storage-state failure and a NULL/empty external path, at WARN on `hakuX`.

## M2 — CLOSED. The low-draw dump is refused, and the mutant is not swallowed

Pass 1's scenario, rebuilt to its stated shape (`per_draw_finish: false`, 30
frames, one `cb_draws: 1` draw and one submit each) and run against this head:

```
cb_draws  max=1  distribution={1: 30}
submits   no frame carried both a draw count and a submit delta with >=4 draws

INSUFFICIENT SAMPLE: 30 draws over 30 frames, 0 of them with >=4 draws. ...
```

Exit **3**. No `SERIALISED`, and the `INSTRUMENT DISAGREES WITH ITSELF` line
is gone with it — the refusal returns before both, which is what pass 1 asked
for: the disagreement check rests on the same independence that fails at low
draw counts.

The gate does not buy the refusal by hiding the falsifier. Driven against this
head:

| dump | result |
|---|---|
| 30 frames × 1 draw, `cb_draws=1` (pass 1's) | exit 3, INSUFFICIENT SAMPLE, no verdict |
| 30 frames × 40 draws, `cb_draws=1`, `per_draw_finish: true` | exit 1, **SERIALISED** on both columns |
| same, `per_draw_finish: false` (the `liar`) | exit 1, SERIALISED **and** INSTRUMENT DISAGREES |
| 30 frames × 40 draws, `cb_draws=17` | exit 0, NOT SERIALISED |

The selftest passes on this tree (`framedump_check selftest: ok`) and now
carries both refusal legs plus the not-swallowed assertion.

The scenario cannot recur. What the new gate does to a *different* dump is
N2 below.

## M3 — CLOSED. The control arm ends with the dump it is the control for

Pass 1's scenario: `30,diag` closes the dump after 30 `flip_stall`s while the
diag capture, which counts guest frames, keeps its per-draw finish running for
on the order of 900 more.

`fdump_close()` now calls `fdump_end_armed_diag()` (`renderer.c:1693-1694`,
body at `renderer.c:1619-1663`). Checked against the path it mirrors:

* It cancels **only its own arm**: `fdump.diag_armed_frames` is set to
  `MIN(frames, DIAG_MAX_FRAMES)` (`renderer.c:1877`), which is exactly what
  `nv2a_dbg_trigger_diag_frames()` writes into `diag_frame_pending`
  (`renderer.c:571-578`) for every `frames >= 1` — and `fdump_parse_spec()`
  only ever assigns `frames` from a token with `v >= 1` (`renderer.c:1771-1775`),
  so the two values cannot disagree. The `qatomic_cmpxchg` leaves a UI-armed
  capture alone and says so when it finds one.
* The teardown body is the abort path at `renderer.c:2408-2416` line for
  line: `diag_total_frames = diag_current_frame_index`, write the session JSON
  if anything was captured, `diag_cleanup_session()`, clear `diag_frame_active`.
  Partial data is written rather than discarded, as claimed.
* Ordering within a flip is right: the diag block runs at `renderer.c:2256`,
  `fdump_end_frame()` → `fdump_close()` at `renderer.c:2434`, so the frame the
  dump closes on is captured by the diag arm before the teardown runs.

The scenario cannot recur. The spec comment (`renderer.c:1731-1737`) and
`AGENTS.md` both now say the frame count is an upper bound on the control arm
and not its duration. One residue, N4.

## L1–L5 — all CLOSED

* **L1** `dump_surface_ppm()` returns `bool` (`renderer.c:446-497`), covering
  the `bytes_per_pixel == 0` return the caller's width/height test did not,
  the `fopen` failure, and now `ferror`/`fclose` as well. The caller names the
  image and charges `w*h*3` only on success and logs the failure on
  `FDUMP_LOG` (`renderer.c:2133-2146`); the record carries `"image": null`.
* **L2** closed with M1 above.
* **L3** verified by running it: a dump whose draw records carry no
  `cb_draws` now prints *"no draw record carries cb_draws: this dump cannot be
  read by this checker (schema=2, known=2)"* and exits 1, where pass 1 got a
  `ValueError` traceback. The checker reads `session["schema"]` in three
  places now, which was L3's other half.
* **L4** `fdump_clear_previous()` runs after the `fopen` succeeds
  (`renderer.c:1811-1822`) and takes a `keep` argument for this run's own
  file, which by then exists and matches `FDUMP_PREFIX` like any other. An arm
  that cannot open its output no longer destroys the previous dump.
* **L5** the `noimages` comment gives both figures (`renderer.c:1725-1730`).

---

## New findings

### N1 (MEDIUM) — `renderer.c:2113-2127`: the completion is not checked to have covered the display surface, and `img_sync` asserts that it did

The fix completes *whatever download was outstanding*. It never tests whether
the display surface was one of them. That test exists and is one line: after
`pgraph_vk_complete_staged_downloads()`, a surface whose download landed has
`draw_dirty == false` (`surface.c:892-897` for the batched entries,
`surface.c:944-963` for the display pre-download specifically). `disp` is
fetched immediately after the completion, so `disp->draw_dirty` at
`renderer.c:2127` is exactly the question "does VRAM hold this frame".

`pgraph_vk_prerecord_display_download()` has four early returns
(`surface.c:1606-1626`). Two of them leave the display surface dirty and
un-recorded:

* `num_deferred_downloads != 0` (`surface.c:1614`). A deferred download
  recorded during the frame and not yet completed. These are ordinary
  per-frame events: surface eviction (`surface.c:3654`), shelving
  (`surface.c:3761`), and the non-TCG flush at `surface.c:2195` all call
  `download_surface_deferred()`.
* `!r->in_command_buffer` (`surface.c:1610`) — the CB was ended by an earlier
  finish and no draw has reopened it (`draw.c:3772`, `draw.c:3806`).

**Scenario.** A soak arms `30,after120`. On flip *N* an eviction earlier in
the frame left one deferred download outstanding, so `prerecord` returns false
at `surface.c:1614` and the display surface's pixels stay in its `VkImage`.
`fdump_end_frame()` sees `num_deferred_downloads > 0`, records
`img_sync = r->deferred_downloads_frame` — a non-negative fence slot, and if
that field was already set from an earlier frame it is an *older* slot — waits
that fence, completes the evicted surface's copy, and reads the display
surface out of VRAM, which still holds the last completed display download.
The PPM is frame *N−1*'s or older, filed under frame *N*'s records, and the
frame record carries a fence slot that a reader (and `framedump_check.py`) is
told means the pairing was established. The `!in_command_buffer` variant is
worse in one way: `num_deferred_downloads` is 0, so `img_sync` is **−1**,
whose documented meaning (`renderer.c:1539-1541`, `renderer.c:2100-2102`) is
"nothing was outstanding and VRAM already held the frame".

This is H1's failure mode surviving in a narrower state, with the artifact now
asserting the opposite. It is not the steady state — in the common case
`prerecord` succeeds and H1 is properly closed — and it is intermittent rather
than systematic, which for #77's method ("decide from the PPMs which frames
show the artifact, then read those frames' draws") is the harder kind to undo
afterwards: pass 1 named non-constancy as the aggravator and it applies here.

**Limit, stated.** This is a code-path argument, like H1 before it. I cannot
say how often `prerecord` bails on a real title; I can say both early returns
are reachable from paths that run every frame, and that nothing in the artifact
distinguishes the two cases.

**Remediation.** After the completion, test it: if `disp->draw_dirty` is still
true, the image is not this frame's — either do not write it (record
`"image": null` with a `FDUMP_LOG` line saying why) or write it with a
distinct `img_sync` value meaning "stale, the flip did not pre-record this
surface", and teach `framedump_check.py` to flag that value the way it already
flags a schema-1 dump's images. Do **not** fix it by forcing a download here:
that would be a `pgraph_vk_finish(SURFACE_DOWN)` at the flip, which is a cost
the headline claim should not quietly acquire. Whichever is chosen,
`renderer.c:1539-1541` and `renderer.c:2100-2102` must stop saying `-1` means
VRAM held the frame.

### N2 (MEDIUM) — `framedump_check.py:177`: `INSUFFICIENT SAMPLE` also refuses dumps whose `cb_draws` column settles the question, and says something false about them

The refusal is `if not usable or len(draws) < MIN_TOTAL_DRAWS`, where `usable`
counts frames with `>= 4` draws. Neither term looks at `max_cb`. But
`max_cb >= 2` means some command buffer held two draws, which a per-draw
finish cannot produce at *any* sample size — it is precisely the inference the
checker itself prints twenty lines further down ("NOT SERIALISED by cb_draws:
command buffers held up to N draws, so no finish ran between them"). The
sample-size argument is sound for the `submits` median and for distinguishing
`max_cb == 1`; it does not apply to a dump that has already demonstrated
batching.

**Scenario, reproduced.** A dump of 30 frames × 3 draws, `cb_draws: 3`
throughout — a queued soak whose `afterNN` landed on a light scene, a menu
with some geometry, a title between loads. Run against this head:

```
cb_draws  max=3  distribution={3: 90}
submits   no frame carried both a draw count and a submit delta with >=4 draws

INSUFFICIENT SAMPLE: 90 draws over 30 frames, 0 of them with >=4 draws.
Neither column can distinguish the two paths on this dump -- a per-draw finish
is indistinguishable from a frame that only drew once. ...
```

Exit 3. The first sentence is false of this dump: `cb_draws` distinguishes
them, and it distinguishes them in the direction the lane exists to establish.
The operator reads "re-arm with afterNN onto a scene that is drawing" and
spends another device slot on a question the artifact in hand already answered.

**The selftest pins the wrong behaviour rather than missing it.** The second
refusal case (`framedump_check_selftest.py:166-172`) writes
`write_dump(short, serialised=False, frames=3, draws=5)` and asserts exit 3.
That dump's draw records carry `cb_draws = n` for `n` in `0..4`
(`framedump_check_selftest.py:48`), so its `max_cb` is **4** — every frame
demonstrably held four draws in one command buffer — and the case asserts that
the checker refuses to draw the only conclusion those records support. It is
refused on the `len(draws) < 30` leg. So the remediation has to move that
expectation as well as the condition.

**Remediation.** Refuse only when the columns are actually ambiguous: add
`and max_cb <= 1` to the condition, so a dump that demonstrates batching gets
its `NOT SERIALISED by cb_draws` verdict, with the `submits` line still
suppressed or explicitly marked as carrying no weight at this sample size. A
`SERIALISED` claim must stay refused in the low-draw case — that is M2 and it
is right, and the `thin` selftest case (`cb_draws: 0` throughout) must keep
its exit 3. Change the `short` case to assert `NOT SERIALISED by cb_draws`
instead of the refusal, and add one with `cb_draws: 1` and the same small draw
count asserting the refusal still fires — that pair is the mutant this gate
needs, and it separates "too few draws" from "too few draws to tell".

### N3 (LOW) — `renderer.c:2430-2432`: the call site still says neither call waits on Vulkan work

```c
/* The live frame dump closes the frame here, after the flip's own
 * pgraph_vk_finish above, and then looks for a new arm. Nothing in either
 * call submits, records or waits on Vulkan work. */
```

With images on, `fdump_end_frame()` now waits a fence. The function's own
comment, `NOTES.md`, `AGENTS.md` and the PR body were all corrected; this one
was not, and it is the comment a reader standing in `flip_stall` sees. It is
the same class of claim H1 was about — `grep` finds no other survivor in the
tree. **Remediation:** say "one fence wait per frame when images are on, none
under `noimages`, and nothing per draw", which is the true and stronger claim.

### N4 (LOW) — `renderer.c:1651`, `renderer.c:1658`: the control arm's teardown is announced only on the dropped tag

`fdump_end_armed_diag()` reports both "leaving a pending diag arm it did not
make" and "framedump closed: ending the diag control arm it armed" through
`DIAG_LOG` — `hakuX-diag`, the tag this PR's own commit `ad5d93f489`
established is absent from both logcat specs that serve a dispatched run. M3's
whole point is that the control arm's lifetime was invisible and unbounded; a
dispatched run still cannot see when it ended, or that a UI capture prevented
the teardown. This is L1's finding applied to the code L1's sibling wrote.
**Remediation:** `FDUMP_LOG` for both, as the rest of the dump's lifecycle
uses.

---

## What could not be audited

* **No device.** Every finding here is from the tree. The measurement pass 1
  named is still the one that settles H1 and now N1 as well, and it is
  unchanged by anything in this pass: images on, a title with a moving camera,
  and a check that `framedump_<id>_fNNN.ppm` matches the scene at that frame's
  `nv2a_frame` rather than the one before it — plus a re-read of
  `cb_draws`/`submits` under the fence wait. N1 makes that run more valuable,
  not less: `img_sync` is now in the artifact and a run can check whether it
  is ever `-1` on a frame whose image is stale.
* **No build of my own.** CI's Android and Desktop builds at this head are
  cited instead.
* **The index regeneration** (`docs/testing/nv2a_index.json`, +6 sites, same
  `provenance.tests_commit`) I did not re-derive; the NV2A index `check` is
  SUCCESS at this head and the PR is `MERGEABLE`, which closes pass 1's
  out-of-scope note.

## Definition of done

`Files:` on the PR body matches `git diff --stat origin/master...HEAD` — ten
paths, including both audit records. `NOTES.md` is under
`docs/lanes/diagdump77/`. `Prediction: none` with its reason. The PR is out of
draft. CI is green on the head for all three checks.

## Outside my territory

I claim no files and edited nothing but this audit and its JSON companion,
both under `docs/audits/`.
