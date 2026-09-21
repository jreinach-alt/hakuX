# lane.blendarm50 -- `771c8eb4f1` does not move stack C, and could not have

Issue #50. Brief: build master, dispatch a fresh `Blend tests` `TestDetailed`
run, and score it with `swatchorder50_readings.py --score --unsigned` to see
whether the landed flush `771c8eb4f1` moves stack C off the aliasing model.

**The brief's falsifier fired, and it fired on data that was already on disk.**
Post-flush stack C still scores **1115-1119 / 1120** against the aliasing model
and **1 / 1120** against the correct-stack-C control -- statistically identical
to the pre-flush column PR #186 published. The flush does not fix the bulk of
the captures, and the aliasing site is elsewhere.

No PASS is being forced, and no device time was spent to reach that verdict.

## The flush cannot execute in any configuration we run

This is the part the brief did not know, and it is decidable from source.
`771c8eb4f1` adds to `download_surface_to_buffer()`:

    if (r->reorder_window.count > 0) { pgraph_vk_flush_reorder_window(d); }
    if (r->draw_queue.count > 0)     { pgraph_vk_flush_draw_queue(d); }

Both counters are structurally zero:

- the reorder window is appended to **only** inside
  `if (g_xemu_draw_reorder && ...)` -- `vk/draw.c:6357`;
- the draw queue **only** inside `if (g_xemu_draw_merge && ...)` --
  `vk/draw.c:6415` and `:6472`;
- both globals are `static bool = false` (`vk/draw.c:31,32`), and the only
  callers of `xemu_set_draw_reorder` / `xemu_set_draw_merge` in the whole tree
  are the Android JNI, where `GetPrefBool(..., false)` defaults them off
  (`xemu_android.cpp:949,954`). The desktop build calls neither.

**And the runs say so themselves, which is why this is not just a reading of
the code.** `renderer.c` prints the two switches at startup. All nine
`TestDetailed` runs on the interactive disc print

    draw reorder: OFF
    draw merge: OFF

in their own logcat -- including the most recent pair, `1789819561` and
`1789819556`, from 2026-09-19. So every capture set #50 has ever been argued
from was taken with the flush's body unreachable.

Master's own `vk/surface.c` comment already retracts the fix claim on these
grounds and was committed a week ago. This lane's contribution is not the
retraction; it is **measuring what the retraction predicts**, which nobody had
done.

## The measurement needed no device, because the arm had already run

The brief says "the 1,568 captures at `~/hakux-work/res_oldblend/` all predate
it" and asks for a fresh run. The first half is true -- `res_oldblend` is dated
2026-09-12 02:12, and the flush landed 19:04 the same day. The second half was
already satisfied: **nine full 1,673-capture `TestDetailed` runs on the
interactive disc (`iso:85b525/Blend tests`) exist at ref `49afee8889`, which
contains `771c8eb4f1`.** They had never been scored against these models.

`swatchorder50_readings.py --score --unsigned`, stack C region, 1,120 unsigned
captures:

| capture set | date | reading 1 | reading 2 | **aliasing** | **control** |
|---|---|---:|---:|---:|---:|
| `res_oldblend` (pre-flush, PR #186's column) | 09-12 | 9 | 9 | **1119** | **1** |
| `1789819561` nova run 1 (post-flush) | 09-19 | 9 | 9 | **1116** | **1** |
| `1789819556` thor run 1 (post-flush) | 09-19 | 9 | 9 | **1119** | **1** |
| `1789318910` nova (post-flush, first scored) | 09-13 | 9 | 9 | **1115** | **1** |

The goldens control column is identical in all four -- correct-stack-C
1120/1120, aliasing 0/1120 -- so the comparison is not drifting underneath the
numbers.

The 1115 / 1116 / 1119 spread is **not** a trend toward the control. It is the
run-to-run band: across arm `1789819561`'s five nova runs, 15 of 1,568
`TestDetailed` captures move at all (0.96%), and the post-flush thor run lands
on 1119, exactly the pre-flush figure. Control is 1/1120 in every column,
before and after. Nothing moved toward correctness.

## What that means for #50's mechanism

`771c8eb4f1`'s commit message explains the aliasing as "the four queued draws
are not yet recorded" when the texture bind downloads the surface. **With
`draw_reorder` and `draw_merge` off there are no queued draws** -- every draw
is recorded as it arrives. So that story cannot be the mechanism of an aliasing
that is nonetheless real at 1119/1120.

The aliasing itself is not in doubt and PR #186's verdict stands: stack C's
blit shows the render target `DrawColorStack` left at the same guest address,
and readings 1 and 2 stay dead at 9/1120. What is refuted is the **site**. It
is not the reorder window and not the draw queue, because neither exists in a
run we make. Master's comment nominates the reorder path's `surface_dirty`
bookkeeping as "the real one" -- that is also inert with the switch off, so it
cannot be the site either. Whatever returns block 2's image to block 3's
texture bind does so on the plain synchronous path, with no draw deferral
anywhere in the frame.

That is the open question this lane hands on, and it is a narrower one than
#50 started with.

## Arm B: is stack C still wrong on *master*?

Everything above is measured at ref `49afee8889`. Master is **1,193 commits**
later and has never had `TestDetailed` run against it. That is the one thing
here still worth a device slot, so it is registered and queued:

- prediction `docs/testing/predictions/blendarm50-master-stackc.json`
  (sha256 `8d1ea561e79a7ef8...`), a_ref `49afee8889`, b_ref `05177dc522`;
- arm A is the **existing** five-run set `1789819561-blendrace50-nova-415002`,
  so no new baseline run is needed;
- arm B is request `1789963700-blendarm50-1474765` -- master's tree, same
  interactive disc, three runs, pinned to nova so the pair is same-device.

The legs are four **pure stack C** captures: every differing pixel of each lies
inside the stack C region on arm A, so the dispatcher's whole-capture
`differing` column *is* the stack C number. Verified, not assumed, with the
`--where` mode added to `swatchorder50_readings.py` by this lane:

    0_ADD_1-cA    16384  PURE
    0_ADD_1-srcA  12512  PURE
    0_ADD_srcA     8192  PURE
    0_ADD_1           0  clean   <- control: the one no-op capture

Three distinct non-zero magnitudes plus a zero, so a uniform shift cannot
satisfy the set, and all four are identical across all five of arm A's runs, so
a move in arm B is not the device. Prediction: nothing moves. Falsifier: if the
three non-zero rows fall toward 0 while `0_ADD_1` stays 0, something in the
1,193 commits fixed stack C and this lane's source argument, though right about
the flush, is wrong about master.

`expect_counts` is deliberately **not** registered: it is a global tally over
all 1,673 captures, and the 15 known run-scoped movers would decide it instead
of this prediction.

## What the next lane should not repeat

- **Do not run an arm to test `771c8eb4f1`.** Its body cannot execute while
  `draw_reorder`/`draw_merge` are off, the dispatcher cannot turn them on
  (`--env` writes the `env_vars` pref, not these two), and every logcat on disk
  says `OFF`. An arm would return "inert" and mean nothing -- the change was
  never in the binary's path.
- **Do not re-run `TestDetailed` for a post-flush baseline.** Nine runs exist
  at `49afee8889`, four of them scored above; `1789819561` alone carries five
  capture sets on one device.
- **Do not read the 1115/1116/1119 spread as movement.** The run-to-run band on
  this disc is 15 captures of 1,568; the control column is pinned at 1/1120
  throughout.
- **`--score` alone will not tell you whether a prediction leg is about stack
  C.** Use `--where` first: of the 1,120 unsigned captures, 1,119 differ inside
  stack C but only 1,116 differ *only* there.

## Reproduce

    docs/testing/swatchorder50_readings.py --score --unsigned \
        --captures ~/hakux-work/dispatch/results/1789819561-blendrace50-nova-415002/captures1
    docs/testing/swatchorder50_readings.py --where 0_ADD_1-cA,0_ADD_1 --unsigned \
        --captures ~/hakux-work/dispatch/results/1789819561-blendrace50-nova-415002/captures1

No device, no build, no ISO. The switch state is in each run's own
`logcat1.txt`: `grep 'draw reorder'`.
