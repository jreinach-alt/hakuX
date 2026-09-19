# Audit pass 2 (round 2) — PR #143, `lane/diagdump77` (#77), over the remediation of pass 2

**Auditor** `job.cloud` audit-2 (claims no files; audit record only).
**Subject** PR #143, branch `lane/diagdump77`, tip **`aff3847634`**.
**Why a second pass-2 record** The first pass-2 record
(`2026-09-19-diagdump77-pass2.md`, head `a8515c65f7`) closed all nine pass-1
findings and raised **N1, N2 (MEDIUM)** and **N3, N4 (LOW)** in the
remediation itself, so the PR went back to `needs-remediation`. This pass
verifies that round. That file is left as written — it is the published record
of a different head — and this one sits beside it.

| commit | what |
|---|---|
| `bcb48cdc4d` | **N1, N2, N3, N4** |
| `bf0e9b55ba` | merge of `origin/master` |
| `aff3847634` | `nv2a_index.json` regenerated over the merged tree |

**Date** 2026-09-19. **Records** `2026-09-19-diagdump77-pass2b.{md,json}`.
**CI at this head** Android `build` SUCCESS, Desktop `build` SUCCESS, NV2A
index `check` SUCCESS — the rollup's `headRefOid` is `aff3847634`, this head.
PR is `MERGEABLE`. `preflight.sh --allow-tracker` passes on this tree.

**2 MEDIUM and 2 LOW closed as written. 1 new LOW, 0 MEDIUM, 0 HIGH.**
**Clean → `fold-ready`.**

Nothing was read off the commit message. The checker findings were re-driven
against dumps I built at this head, and the six new checker invariants were
each mutated to confirm the selftest is the gate it claims to be. The C
findings were traced through the live `vk/surface.c` and `vk/draw.c`, and N1's
fix rests on one implication — *`draw_dirty == false` after the completion
means VRAM holds this frame* — which I attacked from two directions before
accepting it (below).

---

## N1 — CLOSED. The completion is now tested, and the test is sound

Pass 2's scenario: on flip *N* an eviction, a shelving or the non-TCG flush
earlier in the frame left a deferred download outstanding, so
`prerecord_display_download()` bails at `surface.c:1614` and the display
surface's pixels stay in its `VkImage`; the completion waits a real fence for
somebody else's copy, the PPM is written from stale VRAM anyway, and the
record carries a non-negative `img_sync` — or, on the `!in_command_buffer`
variant, `-1`, whose documented meaning was the opposite.

`fdump_end_frame()` now tests `disp->draw_dirty` immediately after the
completion (`renderer.c:2185`). Still dirty writes **no image**: `"image":
null`, `img_sync = FDUMP_IMG_STALE` (−2), one WARN on the first occurrence,
`fdump.images_stale++`, and the count in both the close line and the trailer's
new `images_stale`. No `pgraph_vk_finish(SURFACE_DOWN)` was added, which is
what the audit instructed.

**Is `disp` the surface the pre-record would have covered?** Yes, by
construction: `fdump_end_frame()` selects it with
`pgraph_vk_surface_get_within(d, d->pcrtc.start + vdp.line_offset)`
(`renderer.c:2183-2184`) and `prerecord_display_download()` selects it with the
same expression over the same `VGADisplayParams` (`surface.c:1618-1622`). Both
run inside one `pgraph_vk_flip_stall()`, so nothing moves `pcrtc.start` or
`line_offset` between them. The test is on the surface in question and not on
a neighbour.

**Two attacks on the implication, both of which failed — so I accept it.**

1. **Can a draw land between the pre-record and the completion, so that
   `draw_dirty` is cleared over VRAM that is one draw behind?** This is the
   exact scar `surface.c:878-891` records (`Depth buffer fixed function` back
   as the clear and no quad, one run in three), and the batched loop guards it
   with `if (s->draw_generation == dl->draw_generation)` at `surface.c:892-897`
   — but the display pre-download's own block at `surface.c:944-963` clears
   `draw_dirty` with **no** generation guard. It does not matter here: the
   pre-record is `renderer.c:2296`, the completion is `renderer.c:2179`, and
   between them lies only `pgraph_vk_finish(FLIP_STALL)` and the diag block,
   none of which issues a draw. The generation cannot advance, so the
   unguarded clear and the guarded one agree.
2. **Can a *partial* download clear `draw_dirty` over VRAM that holds only
   some of this frame's rows?** The display block computes `was_partial` from
   `s->download_row_count` at `surface.c:955-956`, but the batched loop has
   already zeroed that field at `surface.c:877` — so `was_partial` would read
   false for a genuinely partial display pre-download and clear `draw_dirty`
   anyway. That would be N1's failure surviving. It cannot fire: the row
   narrowing that is the only producer of a partial range is dead code —
   `if (false && ...)` at `surface.c:1893`, disabled with a comment recording
   the same scar — so `download_row_count` is always `surface->height`,
   `partial` at `surface.c:444` is always false, and every deferred download in
   this tree is a full one. **Stated as a limit:** this is sound for the tree
   as it stands, not for a tree that re-enables that block. Both files are
   outside this PR's diff.

**The falsifier columns are still untouched, confirmed not assumed.** The
completion's `else` branch at `surface.c:937` issues a real
`pgraph_vk_finish(SURFACE_DOWN)` — a submit, which would move `submit_count`,
the column the lane rests on. It is unreachable from `fdump_end_frame()`:
`complete_deferred` returns at `surface.c:911` unless
`num_deferred_downloads > 0`, and whenever that holds,
`pgraph_vk_finish(FLIP_STALL)` has just run `draw.c:3459-3460`
(`if (num_deferred_downloads > 0 && deferred_downloads_frame < 0)
deferred_downloads_frame = current_frame`), so `deferred_downloads_frame >= 0`
and control takes `surface.c:918` or `surface.c:928`, both of which only wait
an existing fence. Nothing between the finish and `fdump_end_frame()` records a
new deferred download: the diag block's only surface work is
`pgraph_vk_surface_download_if_dirty()`, which is the synchronous
`download_surface(d, surface, true)` (`surface.c:2725-2731`) and itself drains
the deferred queue first.

**The `diag` interaction is right and is an improvement, not a hazard.** With
`diag` armed, the diag block at `renderer.c:2373-2376` has already downloaded
the display surface synchronously before `fdump_end_frame()` runs, so
`draw_dirty` is false, `num_deferred_downloads` is 0, the completion
early-returns, and the record carries `img_sync: -1` — which is exactly what
`-1` is documented to mean. The control arm's images are pairable.

The scenario cannot recur, and the `-1` that pass 2 objected to no longer
asserts a pairing that was not checked (`renderer.c:1556-1560`,
`renderer.c:2153-2161`).

## N2 — CLOSED. The refusal is on ambiguity now, and the asymmetry holds

Pass 2's scenario: a 30-frame × 3-draw dump with `cb_draws: 3` throughout —
`afterNN` landing on a light scene, a menu, a title between loads — refused
with *"Neither column can distinguish the two paths on this dump"*, which is
false of a dump that has demonstrated batching, sending its operator back to
the device for an answer already in hand.

The refusal is now `thin and max_cb <= 1` (`framedump_check.py:211`).
Re-driven at this head, building each dump with the selftest's own generator:

| dump | before | now |
|---|---|---|
| pass 2's N2: 30f × 3 draws, `cb_draws: 3` | exit 3, INSUFFICIENT SAMPLE | **exit 0, NOT SERIALISED by cb_draws**, `submits` marked as carrying no weight |
| pass 1's M2: 30f × 1 draw, `cb_draws: 1` | exit 3 | exit 3, INSUFFICIENT SAMPLE — unchanged |
| 30f × 40, `cb_draws: 1`, header `per_draw_finish: true` | exit 1 | exit 1, SERIALISED on both columns |
| the liar: same, header `false` | exit 1 | exit 1, SERIALISED **and** INSTRUMENT DISAGREES |
| 30f × 40, `cb_draws: 17` | exit 0 | exit 0, NOT SERIALISED |

The asymmetry pass 2 asked for holds in both directions. `SERIALISED` cannot
print on a thin dump — it requires `max_cb <= 1`, and `thin and max_cb <= 1`
has already returned 3 — so the cheap verdict survives a thin sample and the
expensive one does not.

**The disagreement check is newly reachable in the thin-plus-batching state,
and it is sound there.** I built that case: 3 frames × 3 draws, `cb_draws: 3`,
header `per_draw_finish: true`. It prints `NOT SERIALISED by cb_draws`, marks
`submits` as weightless, then fires `INSTRUMENT DISAGREES WITH ITSELF` and
exits 1. That is correct rather than a M2 relapse: the verdict it contradicts
rests on `cb_draws` alone, which needs one command buffer and not a sample, so
the independence argument that made the old disagreement check unsafe at low
draw counts does not apply.

**The selftest is the gate it claims to be.** Pass 2 noted the `short` case
was pinning the wrong behaviour; it now asserts `NOT SERIALISED`, and a `flat`
case with the same 15 draws and `cb_draws` pinned at 1 asserts the refusal
still fires. I mutated six invariants one at a time in a scratch tree (never
the real path) and each tripped the selftest **with its own message**, which
is the part worth checking — six reds for one reason would be no gate:

| mutation | selftest |
|---|---|
| drop `and max_cb <= 1` from the refusal (restores N2 exactly) | FAIL *the submits column was not marked as carrying no weight on a thin dump* |
| let the `submits` median back into a thin verdict | FAIL *a thin dump's submits median was still read as a verdict* |
| `SCHEMA_IMAGES_PAIRABLE = 2` | FAIL *a schema-2 dump's images were not flagged as unchecked against the display surface* |
| never flag `image` + `img_sync: -2` | FAIL *a record naming an image while claiming the surface was dirty was accepted* |
| never flag a schema-3 image with no `img_sync` | FAIL *a schema-3 image with no img_sync was accepted* |
| never report the stale-frame rate | FAIL *frames with no image were not reported* |

`framedump_check selftest: ok` on the unmutated tree.

## N3, N4 — both CLOSED

* **N3** `flip_stall`'s call-site comment (`renderer.c:2503-2509`) now states
  the true and stronger claim — one fence wait per frame with images on, none
  under `noimages`, nothing per draw. `grep` over the tree for the old belief
  (`already in guest VRAM`, `synchronises nothing`, `waits on Vulkan work`)
  returns only the two audit files quoting it and the `NOTES.md` paragraph
  describing the fix. No survivor asserts it.
* **N4** `fdump_end_armed_diag()`'s two lines are on `FDUMP_LOG`
  (`renderer.c:1681`, `renderer.c:1688`), so a dispatched run can see the
  control arm's teardown and can see when a UI capture prevented it. The
  `DIAG_LOG` calls that remain in the file all belong to the pre-existing diag
  capture, not to the dump's lifecycle.

## Pass-1 findings: no regression

The remediation reworked `fdump_end_frame`, `fdump_close` and the checker, so
I re-checked the pass-1 closures that touch them rather than assuming they
survived. `fdump_base_dir()` still returns `NULL` under `__ANDROID__` with the
desktop fallback intact (M1). `fdump_close()` still calls
`fdump_end_armed_diag()` (`renderer.c:1725`) (M3). `fdump_clear_previous()`
(`renderer.c:1858`) still runs after the `fopen` at `renderer.c:1848` (L4).
`dump_surface_ppm()` still returns `bool` and the caller still names the image
and charges `w*h*3` only on success (L1). M2's refusal still fires on pass 1's
own dump (table above).

---

## New finding

### N5 (LOW) — `framedump_check.py:300-326`: a dump whose PPM writes failed reads as a complete dump

L1's fix made a failed `dump_surface_ppm()` record `"image": null` while
leaving `img_sync` at the fence slot it waited on — correctly, since the
pairing *was* established and only the write failed. N1's fix then gave the
checker two reports over the image column: frames that name an image while
carrying `img_sync: -2` (impossible, flagged), and frames that wrote no image
because the surface was stale (`img_sync == IMG_STALE`, reported as a rate).
Neither covers the L1 shape, and `images_stale` in the trailer does not count
it either — correctly, because those frames were not stale.

**Reproduced.** I took a healthy 30-frame schema-3 dump and turned 12 frames
into the failed-write shape (`"image": null`, `img_sync: 0`). The checker
prints its verdicts and the scope note and says **nothing at all** about the
image column; exit 0. A reader is told 30 frames were recorded and is not told
that 40% of them have no picture.

**Why LOW and not MEDIUM.** Nothing false is asserted — no record claims a
picture that is absent, and `"image": null` is in every one of those records
for a reader who counts. The event is also logged per occurrence on
`FDUMP_LOG` (`renderer.c:2218`), the tag a dispatched run does keep, so the
information reaches the operator by another route. It is a gap in the tool
that reads the artifact, not in the artifact.

**Remediation.** One more list beside the stale one: frames where `"image"` is
null and `img_sync != IMG_STALE`, reported as *"N frame(s) named no image for a
reason other than a stale surface — the PPM write failed; see the run's
`framedump: image ... not written` lines"*. It belongs in the same block for
the same reason the stale rate does: #77's method picks frames from pictures,
so the count of frames without one is what the reader needs, whatever the
cause. A selftest case with that shape, asserting the line, would make it a
gate rather than a print.

---

## What could not be audited

* **No device, still.** Every claim here is from the tree, and N1's fix is a
  code-path argument exactly as H1's was — I say so rather than let the
  re-derivation read as a measurement. The settling run is unchanged from what
  both earlier passes named, and this round adds a free reading to it: the
  trailer's `images_stale` says how often the flip's pre-record actually bails
  on a real title, which is the difference between an instrument that samples
  frames usably and one that hands back a handful of pictures.
* **No build of my own.** CI's Android and Desktop builds at `aff3847634` are
  cited instead. I did not re-run the lane's `assembleDebug`.
* **`docs/testing/nv2a_index.json`.** Regenerated over the merged tree; I did
  not re-derive it. The NV2A index `check` is SUCCESS at this head and
  `preflight.sh` reports `nv2a index ok`.
* **The two `surface.c` observations under N1 are not findings.** The
  unguarded `draw_dirty` clear in the display block and the `was_partial` read
  of a field the batched loop has already zeroed are both real shapes in code
  this PR does not touch, and neither can fire in this tree — the first because
  no draw intervenes, the second because the partial path is disabled. I did
  not chase them further; that is the board's call if anything ever re-enables
  `surface.c:1893`.

## Definition of done

`Files:` on the PR body is 12 paths and matches
`git diff --stat origin/master...HEAD` exactly (this record and its JSON will
make 14 and the lane should extend the line at fold time, or the board can —
they are `docs/audits/` files that no other lane can collide on).
`NOTES.md` is under `docs/lanes/diagdump77/`, not the branch root.
`Prediction: none` is stated with its reason. The PR is out of draft.
`preflight.sh --allow-tracker` passes. CI is green on this head for all three
checks, and the rollup's `headRefOid` is this head rather than an older one.

## Outside my territory

I claim no files and edited nothing but this audit and its JSON companion,
both under `docs/audits/`. The checker mutants were built in `/tmp`, never in
the tree.
