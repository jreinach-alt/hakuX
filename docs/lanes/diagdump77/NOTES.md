# lane.diagdump77 -- a marker-file-armed frame dump that does not serialize

Issue: #77. Base: master @ ab471cc80f. PR #143.

## What this lane is for, in one line

#77 is blocked on a *capability*, not on an analysis: the only per-draw frame
dump this emulator has is reachable from the Debug Capture button and calls
`pgraph_vk_finish` before every draw, so it is blind to exactly the behaviour
a subtle stipple needs visible -- draw merging, deferred submission, barriers.
This lane adds a second instrument with a different trigger and no per-draw
finish, and takes one run with it. It does **not** diagnose the stipple.

## What the existing path does (read, not assumed)

- `nv2a_dbg_trigger_diag_frames()` (hw/xbox/nv2a/pgraph/vk/renderer.c:555) is
  called from exactly one place: `nativeDumpDiagFrames`
  (android/app/src/main/cpp/xemu_android.cpp:1457), a JNI entry point on
  `MainActivity`. There is no file, env var or property that reaches it.
- `nv2a_diag_log_draw_call()` (renderer.c:1049) calls
  `pgraph_vk_finish(pg, VK_FINISH_REASON_SURFACE_DOWN)` **per draw**, to make
  `diag_download_surface` safe. That finish flushes the draw queue and the
  reorder window (vk/draw.c:3188-3217), so under a diag capture no draw is
  ever merged with the one after it and no barrier behaviour survives to be
  observed. This is the blindness #77 names.
- The serialisation also reaches further than merging: texture reuse is keyed
  on `submit_time` against `submit_count` (vk/texture.c:2074), and under a
  per-draw finish that counter advances once per draw.

## What was built

`hw/xbox/nv2a/pgraph/vk/renderer.c`, one self-contained section:

- **Arming.** A marker file `frame_dump.on` in the app's external files dir,
  polled once a second at the flip. Same directory and same idea as apu.c's
  PCM capture marker, for the same reason: the existing trigger is a button,
  and a soak has nobody to press it. `XEMU_FRAME_DUMP=<spec>` arms at startup
  instead, which is what `request.sh --env` can set today.
- **Spec tokens** on the marker's first line: frame count, `noimages`,
  `capNN` (MB), `afterNN` (start NN seconds after the arm is *seen*), `diag`
  (also run the old capture, as the serialising control arm).
- **Per draw:** no Vulkan call of any kind. One buffered `fprintf` of host
  state -- registers, bindings, and the scheduler's counters (`in_command_
  buffer`, `draws_in_cb`, `submit_count`, draw queue and reorder window
  counts), plus each stage's bound `VkImage` handle, which is what a stale
  binding would show up in.
- **Per frame:** the display surface, read out of guest VRAM at flip_stall
  after the flip's own `pgraph_vk_finish` **and after the download that finish
  only pre-recorded has been completed into VRAM** -- one fence wait per
  frame, and only when images are on. The first version skipped that
  completion and so wrote a picture one completed download old; see
  "Attempt 3" below. One PPM per frame, named next to the records, with the
  fence slot it waited on in the frame record as `img_sync`.
- **Output:** `framedump_<id>.jsonl` + `framedump_<id>_fNNN.ppm` in the files
  dir, so `--pull 'framedump_*'` collects the lot.

`docs/lanes/diagdump77/framedump_check.py` reads a dump and says whether it
serialised; `framedump_check_selftest.py` builds both arms synthetically and
asserts the checker separates them (the serialising mutant must trip it, or
the "NOT SERIALISED" verdict is free).

## How the claim is falsifiable from the artifact alone

The dump records two independent readings of the same fact, per draw:

| column | under the Debug Capture button | under this path |
|---|---|---|
| `cb_draws` (`r->draws_in_cb`) | never exceeds 1 -- the finish submits the command buffer at every draw | climbs across the frame |
| `submits` (`r->submit_count`) | +1 per draw | flat between flips |

So no external trace is needed and none is cited: the file says which
instrument produced it. `framedump_check.py` prints both and refuses to
average them -- a build that moved one and not the other is a broken
instrument, not a pass.

## What it cannot see -- read this before citing a null result

- **No per-draw image.** Reading a surface back mid-frame is precisely what
  forces the finish. Per draw you get state and schedule; per frame you get
  the picture. A draw-level *pixel* attribution still needs the old path,
  with the old blindness.
- **No clears or blits.** Those hooks are gated on
  `nv2a_dbg_diag_frame_active()` at their call sites in `vk/draw.c:6711` and
  `vk/blit.c:450`, files this lane does not hold. Draws only.
- **Nothing about merging when merging is off.** `draw_merge` and
  `draw_reorder` are prefs defaulting false (vk/draw.c:32,
  SettingsActivity.kt:68). The session header records both and the checker
  prints a scope note, because a dump taken with them off says nothing about
  merged draws. What it *does* show with them off is deferred submission and
  command-buffer batching, which are on by default -- and those are enough to
  break the "one submit per draw" schedule the old capture imposes.
- **Its own timing cost.** One buffered `fprintf` per draw and, with images
  on, one fence wait plus one ~900 KB PPM write per frame, on the pgraph
  thread, to FUSE-backed storage. That is far cheaper than a fence wait per
  *draw* and it does not move `cb_draws` or `submits` (a fence wait is not a
  submission), but it is not free; a frame-time measurement taken during a
  dump describes the dump. `noimages` removes both the wait and the write.

## The gap that is left, and who can close it

Nothing in the dispatch path can touch a file on the device mid-run:
`request.sh` has `--audio-capture` (which `soak_title.sh` turns into a marker
write) but no equivalent for this, and neither file is in this lane's grant.
So on-device arming today goes through `--env XEMU_FRAME_DUMP=...,afterNN`,
which runs the *same* code from one branch earlier. The marker `fopen`/
`unlink` branch is exercised by reading and by the desktop path, not by a
queued soak.

**The ask for whoever holds the harness files:** a `--frame-dump SPEC` flag on
`request.sh` that `soak_title.sh` turns into
`echo SPEC > $GUEST_FILES/frame_dump.on` at a chosen offset into the run --
the audio marker's own shape, including deleting the previous dump first. That
makes the marker trigger reachable from the queue and lets a dump be armed on
a scene rather than on a stopwatch.

## Why attempt 1 did not finish

It ran out with the whole instrument built, AGENTS.md written, PR #143 open
and the first #77 comment posted -- and stopped roughly four minutes before
the run it had queued landed. The soak
`1789811606-diagdump77-4099630` finished at 02:57 with a 4 MB dump and 30
PPMs on disk. Nobody read it. So the lane ended with its falsifier **queued
but unevaluated**, the PR still in draft, and one uncommitted edit in the
tree (the log-tag fix below), which is what a resume costs: not the work,
the last ten minutes of it.

The lesson worth carrying is narrow and mechanical: *a queued run is not a
finished step*. The run was the only thing standing between "built" and
"done", and waiting on it is exactly when a session is most likely to end.
Commit the in-flight edit before the wait, not after.

## Attempt 2: the falsifier, read

### The measured result

`framedump_check.py` on run `1789811606-diagdump77-4099630` --
`pulled/framedump_1789811749.jsonl`, 3,847 draws over 30 frames, armed by
`--env XEMU_FRAME_DUMP=30,after120` at `fbf3b3f5ee` on the Thor:

```
cb_draws  max=132  mean=65.6
submits   0.0078 per draw
NOT SERIALISED by cb_draws: command buffers held up to 132 draws.
NOT SERIALISED by submits: 0.0078 submits per draw.
```

Two details make the reading sharper than the headline:

- `cb_draws == 1` occurs **exactly 30 times in 3,847 draws, and that set is
  exactly the first draw of each frame** -- the flip's own finish, which was
  already there. Every other draw in the run went into a command buffer that
  already held between 1 and 131 earlier draws.
- `submit_count` advanced **29 across the whole dump**, one per frame
  boundary. The button path would have advanced it 3,847 times.

So the instrument's headline claim is not a near miss or a ratio to argue
about; it is off by two orders of magnitude from the serialising path, in
both columns independently.

**Do not count the header as a third witness.** `per_draw_finish` in the
session record was a bare `false` literal in the format string -- it asserted
the claim instead of measuring it, and would have printed `false` on the
control arm, the one run where a finish *is* forced on purpose. Nothing was
invalidated by it (the checker never read the field, and the verdict rests on
`cb_draws`/`submits` from the scheduler), but it was a row that could not
come out the interesting way. It now reports `also_diag`, which is the only
thing that forces a finish in this path, and carries a comment saying it
describes what was ARMED while the draw records are what was MEASURED.

### The control arm is measured, not only synthetic

`framedump_check_selftest.py` builds a serialising dump synthetically and
asserts the check trips on it, which is what makes "NOT SERIALISED" a
non-free verdict. But a synthetic mutant proves the *checker* separates the
two arms; it does not prove the *device* produces the serialising arm when
asked. Run `1789812074-diagdump77-4109990` closes that: same title, same
device, same binary, spec `30,after120,diag`, where the `diag` token fires
`nv2a_dbg_trigger_diag_frames` alongside the live dump.

It came out the opposite way on both columns, and on a third the lane had not
thought to predict. Same binary (`ad5d93f489`), same title, same Thor, same
30-flip window, ~1 s of wall clock each:

| | live arm (1789811606) | control arm (1789812179) |
|---|---|---|
| spec | `30,after120` | `30,after120,diag` |
| frame records | 30 | 30 |
| **distinct guest frames** | **30** (`nv2a_frame` 3168..3197) | **1** (3127, all thirty) |
| draws recorded | 3,847 | 1 |
| `cb_draws` max | 132 | 1 |
| `submit_count` advance | 29 over 3,847 draws | 2 over 1 draw |
| verdict | NOT SERIALISED | SERIALISED |

So the checker's `SERIALISED` branch is not a synthetic-only branch any more:
a real device dump has taken it, and the two arms differ by two orders of
magnitude in the direction the instrument was built to show.

**The third column is the one to carry forward.** Under the diag capture the
guest frame counter did not advance *at all* -- thirty consecutive flip_stall
samples of a single guest frame, 3127. The old path does not merely stop
draws being merged; during its capture window the title does not progress.
That is a stronger statement about the button path's intrusiveness than this
lane set out to make, and it is the clearest answer yet to why a 10-14%
stipple was never caught under it: the capture does not sample the title
running, it samples the title stopped.

Two honest limits on that control, neither of which touches the live arm:

- **Its per-draw sample is one draw.** `cb_draws=1` there is a true reading
  of a real dump, but n=1. The weight of the falsifier is on the live arm's
  3,847 draws; the control's job is to show the other verdict is reachable on
  a device, and it does that.
- **`frames` in a dump counts flip_stall invocations, not distinct guest
  frames.** The control makes that visible for the first time: thirty
  "frames" of one. The dump records `nv2a_frame` per frame record, which is
  the only reason this was noticeable rather than a silent 30x
  over-count -- **dedupe on `nv2a_frame` before treating frame records as
  independent samples.** A later reader who counts rows will be wrong by
  whatever the stall factor was.

The control also produced the new disagreement check's first real firing: it
ran on `ad5d93f489`, which predates the `per_draw_finish` fix below, so its
header claims `false` while its records say SERIALISED, and the checker says
so. The check caught a genuinely stale-provenance dump on its first contact
with real data, which is the evidence that it is not a branch nothing takes.

### The instrument was invisible in the record of its own run -- fixed

Worth stating separately because it is the kind of thing that costs a later
lane a day. The dump's armed/held/closed/failed lines went through
`DIAG_LOG`, tagged `hakuX-diag`. **Neither** logcat spec that serves a
dispatched run lists that tag (`dispatcher.sh:1089`, `soak_title.sh:32`,
both ending `*:S`), so all of them were filtered out before reaching the
record.

This is measured, not inferred: the run above pulled a 4,026,766-byte dump,
and its 1,268-line logcat contains **zero** occurrences of `framedump` and
zero of `hakuX-diag`. A dump that armed perfectly, a dump that never armed,
and a dump whose `fopen` failed all left exactly the same log. The artifact
was the only witness that the instrument had run at all.

`FDUMP_LOG` now goes to `hakuX`, which is in both specs, at WARN because
`soak_title`'s fallback keeps `hakuX` at `:W`. The lines are four and rare by
construction. Both spec strings are in files this lane does not hold, or the
tag would have been added there instead.

**For the next lane:** before trusting a log to tell you an instrument ran,
check your tag against the run's own `result.json` `logcat.spec`. A spec
ending `*:S` is an allowlist, and silence from an unlisted tag is
indistinguishable from silence from a broken instrument.

## Attempt 3: remediating the pass-1 audit

`docs/audits/2026-09-19-diagdump77-pass1.md` read the diff and found 1 HIGH,
3 MEDIUM, 5 LOW. Its clean results are worth as much as its findings and are
not repeated here; what follows is what changed and why, in the audit's own
numbering. Every fix is to the *second* half of the instrument -- the image,
the directory, the control arm and the checker. The headline claim and the
falsifier columns are untouched by all of it, deliberately: nothing added
here submits, so `cb_draws` and `submits` mean exactly what they meant in the
live arm above.

### H1 -- the per-frame image was one completed download old

The per-frame PPM was read from `d->vram_ptr + surface->vram_addr` at
flip_stall, on the belief that the flip's `pgraph_vk_finish` had already put
the frame there. It had not. `FLIP_STALL` is in the deferred set, so off the
render thread the caller spin-waits for *vkQueueSubmit* and not for the
fence; the copy `pgraph_vk_prerecord_display_download()` recorded is still in
the staging buffer, and `pgraph_vk_complete_staged_downloads()` -- the only
writer of staging into VRAM -- is skipped on every branch that path takes.
So each image held the most recently *completed* display download: the
previous frame in the steady state, older when the display thread had not
presented, filed under this frame's draw records with nothing saying so.

This never reached a published number -- the live arm's 3,847 draws and 30
distinct `nv2a_frame` values are read from the records, and nothing in the PR
rests on a PPM -- which is exactly why it was worth fixing before #77 uses
the images: the method the instrument was built for is "decide from the PPMs
which frames show the artifact, then read those frames' draws", and a
display-thread-dependent lag assigns the artifact's state to its neighbour
without ever looking wrong.

Fix: the audit's option (a). `fdump_end_frame()` calls
`pgraph_vk_download_surface_complete_deferred(d)` before reading VRAM, inside
`if (fdump.images)`. That waits `frame_fences[display_predownload_frame_index]`
-- the fence for the submission the spin-wait above already guaranteed had
happened -- and then memcpys. One fence wait per frame, at the flip, where a
stall already lives; nothing at all under `noimages`; **no** per-draw finish
and no new submission, so the falsifier columns cannot have moved. Options
(b) and (c) were rejected: (b) leaves the pairing in the reader's head as
well as in the filename, and (c) gives up the only thing that makes the dump
usable for an artifact hunt.

The mechanism is now checkable from the artifact rather than from a comment.
Frame records carry `img_sync`, the fence slot that was waited on (`-1` =
nothing was outstanding, VRAM already held the frame), the schema is bumped
to 2, and `framedump_check.py` refuses to pair a schema-1 dump's images with
its records and flags a schema-2 record that names an image without naming a
fence.

**Still unmeasured, and it should be the next arm.** No device ran this. The
cheap settling run is the one the audit named: a title with a moving camera,
images on, and a check that `framedump_<id>_fNNN.ppm` matches the scene at
that frame's `nv2a_frame` rather than the one before it. The same run should
re-read `cb_draws`/`submits` rather than assume they held: the claim that a
per-frame fence wait cannot move a per-draw column is an argument from the
code, and this lane's own history says a plausible argument is what the
columns are there to check.

### M1 -- the Android fallback armed into a directory nobody can read

`fdump_base_dir()` ended in `xemu_settings_get_base_path()`, which on Android
is `SDL_GetPrefPath` -- internal storage, the exact thing the entry point's
comment refuses ("a dump written there is a dump nobody can pull"). The
marker branch was inert there anyway, but an env-armed soak would have opened
the file, logged `armed ... -> <path>` at WARN, written 30 frames and ~27 MB
of PPMs, and come back with no dump and a log saying one was written.

Fix: under `__ANDROID__` the fallback is gone -- `fdump_base_dir()` returns
NULL, `fdump_poll_marker()` says so once per run on the tag a dispatched run
keeps and stays unarmed, and `fdump_begin()` refuses. Desktop keeps the
settings-base-path fallback, where it is the right answer. The entry point's
two failure branches (no write state, and an external path that is NULL or
empty) are now one `else` with one WARN, which is L2.

### M2 -- the checker gave a confident verdict on a sample that cannot carry one

`max_cb <= 1` was the whole `SERIALISED` test, with no minimum sample. The
live arm's own measurement says `cb_draws == 1` at the first draw of every
frame, so any dump whose frames drew once satisfies the serialised test
exactly -- and `submits_in_frame / draws` degrades on the same frames, so the
two "independent readings" fail together precisely where a verdict is least
warranted. A dump armed by `afterNN` onto a loading screen, a pause menu or a
video cut would have reported the falsification of this PR's whole thesis and
then called the instrument self-contradictory, from an instrument that
behaved correctly.

Fix: refuse rather than invert. The submits median is taken over the frames
that carry at least `MIN_FRAME_DRAWS` (4) draws and says so in the line; if
no frame does, or the dump holds fewer than `MIN_TOTAL_DRAWS` (30) draws
total, the checker prints `INSUFFICIENT SAMPLE`, suppresses both verdicts and
the disagreement check, and exits **3** -- a status of its own, not 0 and not
1. Two selftest cases cover the two legs (30 frames of one draw; 3 frames of
five), one asserts the refusal carries no verdict text, and one asserts the
serialising mutant is *not* swallowed by the threshold.

### M3 -- the control arm outlived the dump it is the control for

`diag` passed the dump's frame count straight to
`nv2a_dbg_trigger_diag_frames()`, and the two count different things: this
dump's number is flip_stall invocations, the diag session's is guest frames.
The control-arm table above is the measurement of that gap -- 30 frame
records, one distinct guest frame -- so `30,diag` closed the dump after about
a second and left the serialising capture running until the title advanced 29
more guest frames, on the order of 900 flip_stalls, under which every other
measurement that soak was queued for was taken. `DIAG_MAX_FRAMES` bounds the
session's arrays, not its duration.

Fix: `fdump_close()` tears down the capture it armed, through
`fdump_end_armed_diag()`, which mirrors flip_stall's existing abort path and
writes partial data rather than discarding it. It cancels only its own arm
(`qatomic_cmpxchg` against the value it set, clamped the way the trigger
clamps), so a Debug Capture armed from the UI in the meantime is left alone.
The number in the spec is now an upper bound and the spec comment says so.

### The LOWs

L1: `dump_surface_ppm()` returns whether it wrote. The frame record names the
image and charges `w*h*3` to the byte cap only on true, so a failed write no
longer shortens the dump for bytes that do not exist or names a file that is
not there, and the failure is reported on `FDUMP_LOG`'s tag. L2: above.
L3: `max()` over an empty generator is gone; a dump with no `cb_draws` column
is reported as unreadable, with its schema. L4: `fdump_clear_previous()` runs
*after* the output has been opened, so an arm that cannot open its file no
longer deletes the previous run's dump first -- it takes the new file's name
to skip, since that file now exists when the clear runs. L5: the `noimages`
comment said "~1 MB instead of ~1 MB per frame"; it now says what it meant.

### What the fold should know

`docs/testing/nv2a_index.json` conflicted with master and is resolved by
regenerating it after this merge, never by merging it -- `fold.sh:42` says
the same thing.
