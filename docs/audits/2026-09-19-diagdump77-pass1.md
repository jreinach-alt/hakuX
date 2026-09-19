# Audit pass 1 — PR #143, `lane.diagdump77` (#77)

Diff audit of *lane.diagdump77: a marker-file-armed frame dump that does not
serialize*. Machine-readable companion:
[`2026-09-19-diagdump77-pass1.json`](2026-09-19-diagdump77-pass1.json).

| | |
|---|---|
| Auditor | `job.cloud` audit-1, claims no files |
| PR / head | #143, `lane/diagdump77` @ `7fa7d27047` |
| Diff | 8 files, +1352 −56: `hw/xbox/nv2a/pgraph/vk/renderer.c` (+605), `hw/xbox/nv2a/debug.h` (+14), `android/app/src/main/cpp/xemu_android.cpp` (+23), `AGENTS.md` (+55), `docs/lanes/diagdump77/{NOTES.md,framedump_check.py,framedump_check_selftest.py}`, `docs/testing/nv2a_index.json` |
| Method | read the diff; traced the display-download pipeline through `vk/draw.c`'s finish and `vk/surface.c`'s deferred-download machinery; verified every new external symbol and the `NV_PGRAPH_TEX*` register strides against the tree; ran `framedump_check_selftest.py` and built one additional synthetic dump against `framedump_check.py`. No device, no build of my own — CI's own results are cited below instead. |
| CI at this head | Android `build` SUCCESS, Desktop `build` SUCCESS, NV2A index `check` SUCCESS |

## Counts

| Severity | Count |
|---|---|
| HIGH | **1** |
| MEDIUM | 3 |
| LOW | 5 |

**The instrument's headline claim is sound and I could not break it.** The
per-draw path issues no Vulkan work, the `cb_draws`/`submits` falsifier is real
and is read from the scheduler rather than asserted, and the arming discipline
(unlink-on-read, delete-the-previous-dump) is right. Everything below is about
the *second* half of the instrument — the per-frame image, the directory it
writes to, and the checker that reads it back.

The one HIGH is that the per-frame PPM is read out of guest VRAM one step too
early in the pipeline, so it belongs to an earlier frame than the draw records
filed with it. That is not a crash and not a pixel change; it is the instrument
mislabelling its own only pixel oracle, on the issue whose whole shape is
"which frames show the artifact".

## HIGH

### H1 — `renderer.c:1950-1975` — the per-frame PPM is read from VRAM before the flip's pre-recorded display download has been copied there, so every image lags the draw records it is filed under

`fdump_end_frame()` carries this comment, and `NOTES.md:47-49` and the PR body
repeat it:

```c
/* End of a dumped frame. Runs at flip_stall, after the flip's own
 * pgraph_vk_finish, so the display surface is already in guest VRAM and
 * reading it costs nothing and synchronises nothing. */
```

The second clause is true. The first is not, and the two are not the same
claim. `dump_surface_ppm()` reads `d->vram_ptr + surface->vram_addr` directly
(`renderer.c:458`) with no `draw_dirty` test and no download.

Traced forward from the flip:

1. `pgraph_vk_flip_stall()` calls `pgraph_vk_prerecord_display_download(d)`
   (`renderer.c:2047`). That **records** a copy of the display surface into the
   aux command buffer and sets `r->display_predownload_pending = true`
   (`surface.c:1395-1450`). It copies nothing into VRAM itself.
2. `pgraph_vk_finish(pg, VK_FINISH_REASON_FLIP_STALL)` (`renderer.c:2049`).
   `FLIP_STALL` is in the `deferred` set (`draw.c:3331-3334`), and flip_stall
   is not render-thread context, so control takes the `else` branch at
   `draw.c:3400`: the finish is enqueued, and the caller spin-waits only on
   `frame_submitted[deferred_frame]` — *vkQueueSubmit has been issued*, not
   *the fence has signalled*. The two `pgraph_vk_complete_staged_downloads()`
   calls on that path (`draw.c:3391`, `draw.c:3457`) are both inside
   `if (!deferred)` and are skipped.
3. The frame-rotation block at `draw.c:3494-3530` completes staged downloads
   only `if (r->deferred_downloads_frame == next_frame)`. The download was
   recorded into `r->current_frame`, and `next_frame != current_frame` for any
   `num_active_frames >= 2`. Skipped.
4. Nothing between `renderer.c:2049` and `renderer.c:2258` calls it either —
   the frame-skip block touches no surfaces, and the diag block is inside
   `if (qatomic_read(&diag_frame_active))`.

`pgraph_vk_complete_staged_downloads()` (`surface.c:636-697`) is the **only**
writer of the staging→`dest_ptr` copy, and `dest_ptr` is
`d->vram_ptr + surface->vram_addr`. So at the moment `fdump_end_frame()` runs,
this frame's rendered pixels are in the staging buffer and not in VRAM. On
Android they reach VRAM later, when the display thread's
`pgraph_vk_get_framebuffer_surface()` → `pgraph_vk_wait_for_surface_download()`
(`surface.c:1455-1477`, which forces `require_download = true` on the CPU/VGA
present path) kicks pfifo into
`pgraph_vk_process_pending_downloads()` → `pgraph_vk_download_surface_complete_deferred()`.

The codebase has already paid for this exact pipeline once: the comment at
`surface.c:679-686` records that crediting a pre-recorded display download with
the *current* generation "made the surface clean with VRAM one draw behind",
and that `Depth buffer fixed function` came back as the clear and no quad in
one run out of three depending on where the flip fell.

**Scenario.** A soak arms `--env XEMU_FRAME_DUMP=30,after120`. The title is a
normal 3D scene, so the display surface is `draw_dirty` at every flip and
`prerecord_display_download()` returns true each time. For flip *N* the dump
writes `framedump_<id>_f0NN.ppm` from VRAM, which still holds the content of
the most recently *completed* download — frame *N−1* in the steady state, and
older whenever the display thread has not presented since. The frame record
written on the same line carries `"f": N`, this frame's `draws`, this frame's
`submits_in_frame` and `"nv2a_frame": <N's counter>`. Nothing in the file says
the image is not frame *N*'s.

This is #77's whole method: decide from the PPMs which of the 30 frames show
the deck/ground stipple, then read those frames' draw records. A systematic
one-frame shift assigns the artifact's draw state to its neighbour — and
because the lag depends on the display thread, it is not even a constant
offset that could be corrected afterwards. The failure is silent: a
one-frame-old display surface is a completely plausible picture.

**Why the measured run did not show it.** The live arm's evidence is 30
distinct `nv2a_frame` values and 3,847 draws — both read from the *records*,
not the images. Nothing published rests on a PPM, and 30 plausible PPMs is
exactly what this defect produces.

**Remediation — and this one is a claim, because the obvious fix costs the
instrument its headline property.** Three shapes, and the lane should pick:

* **(a) Complete the download before reading.** Call
  `pgraph_vk_download_surface_complete_deferred(d)` at the top of
  `fdump_end_frame()`, inside `if (fdump.images)`. It waits
  `frame_fences[display_predownload_frame_index]` and then memcpys — one fence
  wait per *frame*, at the flip, where a stall already lives, and none at all
  under `noimages`. It does add synchronisation the current comment promises
  not to add, so the session header must stop claiming otherwise and should
  record that images force a per-frame completion. It does **not** add a
  per-draw finish, so `cb_draws`/`submits` and the headline claim are
  untouched — that should be re-measured rather than assumed.
* **(b) Publish the image late.** Keep the read where it is and file the PPM
  against the *previous* frame record, which is the frame it actually holds.
  Cheapest in Vulkan terms, and it needs `fdump_end_frame()` to carry the
  previous record's `f` and `nv2a_frame` into the image name so the pairing is
  in the artifact and not in a reader's head.
* **(c) Refuse the image.** Move "no trustworthy per-frame picture" into the
  `WHAT IT CANNOT SEE` list, default `images` to off, and let the display PPM
  come from the existing path. Honest, and it gives up the one thing that
  makes the dump usable for an artifact hunt.

Whichever is chosen, `renderer.c:1947-1949`, `NOTES.md:47-49`, the PR body and
the `AGENTS.md` section must stop asserting the surface is already in VRAM.
**Pass 2 should check the mechanism, not the words**: that the image written
for frame *N* is produced after a completion that names frame *N*'s fence, or
that the record it is filed under is the one whose pixels it holds.

## MEDIUM

### M1 — `renderer.c:1573-1583` — `fdump_base_dir()` falls back to the settings base path, which is exactly the fallback the Android entry point says it refuses

`xemu_android.cpp:1132-1147` is explicit:

```c
/* Internal storage is NOT a fallback here. It is unreadable to adb on a
 * production build, so a dump written there is a dump nobody can pull and a
 * marker nobody can drop; better to leave the feature unarmed and say so. */
```

and on the failing branch it logs a WARN and leaves `fdump_dir` empty. But
`fdump_base_dir()` ends:

```c
if (fdump_dir[0]) {
    return fdump_dir;
}
return xemu_settings_get_base_path();
```

On Android `xemu_settings_get_base_path()` is `SDL_GetPrefPath("xemu","xemu")`
(`ui/xemu-settings.cc:77-91`), i.e. internal storage. So the feature is not
left unarmed; it is armed into the directory the comment names as unusable.

**Scenario.** A dispatched soak runs with `--env XEMU_FRAME_DUMP=30,after120`
on a device where `SDL_AndroidGetExternalStorageState()` does not report
`WRITE` — the same condition the TB-cache block two lines below treats as
reachable enough to code a fallback for (`xemu_android.cpp:1154-1157`). One
WARN goes to logcat at startup, 120 s before anything happens. The env arm then
fires normally: `fdump_begin()` opens
`/data/data/<pkg>/files/.../framedump_<id>.jsonl`, `FDUMP_LOG` reports
`framedump: armed by env, 30 frames, images=1, cap=96 MB -> <path>` at WARN —
a success line naming a path nobody can reach — and 30 frames plus ~27 MB of
PPMs are written where `--pull 'framedump_*'` cannot see them. The run comes
back with no dump and a log that says one was written. The marker branch is
harmlessly inert in the same state (nobody can drop a marker there either),
which is what makes this easy to miss: only the env arm reaches it.

**Remediation.** Give the Android path an explicit "unarmed" state rather than
letting it fall through: have `nv2a_dbg_set_framedump_dir()` be the only way
the feature turns on when `__ANDROID__` is defined, and make
`fdump_poll_marker()` return early with a one-time WARN when `fdump_dir` is
empty on that platform. Keep the settings-base-path fallback for desktop, where
it is the right answer and is documented as such. Do **not** fix this by
pointing the Android fallback at internal storage deliberately — the comment's
reasoning is correct, and a dump nobody can pull is worse than no dump.

### M2 — `framedump_check.py:131` — a correct live dump of a low-draw scene is reported `SERIALISED`, and then reported as an instrument that "disagrees with itself"

`max_cb <= 1` is the whole `SERIALISED` test and it has no minimum-sample
guard. The PR's own measurement says `cb_draws == 1` occurs in the live arm at
the first draw of every frame — the flip's own finish. So any live dump whose
frames carry one draw each satisfies the serialised test exactly.

**Reproduced.** I built a dump with `per_draw_finish: false`, `also_diag:
false`, 30 frames, one `cb_draws: 1` draw per frame and one submit per frame
(the flip's own), and ran the checker unmodified:

```
cb_draws  max=1  distribution={1: 30}
submits   median 1.0000 per draw, worst frame f0 at 1.0000 (1 submits over 1 draws)

SERIALISED: no command buffer ever held more than one draw. ...
SERIALISED by submits: 1.0000 submits per draw is one submission each, ...

INSTRUMENT DISAGREES WITH ITSELF: the session header says per_draw_finish=False,
the draw records say SERIALISED.  Believe the draw records ... and treat this
dump's provenance as unreliable until that is explained.
```

Exit 1. Note that the two columns the file's docstring calls "two independent
readings of the same fact" both fire, because a single draw per frame degrades
*both* of them at once — the independence the checker rests on does not hold at
low draw counts, which is the case where a verdict is least warranted.

**Scenario.** `afterNN` exists precisely because a queued soak cannot choose its
moment. An arm that lands on a loading screen, a pause menu, a video cut or the
tail of a title that has stopped issuing geometry produces this dump. The
reader gets a confident claim that the marker-armed path serialises — the
falsification of the PR's entire thesis — plus an instruction to distrust the
dump's provenance, from an instrument that behaved correctly. The selftest
cannot catch it: `write_dump()` hard-codes `draws=40` and never varies it.

**Remediation.** Refuse the verdict instead of inverting it. Compute the draws
per frame and, below a threshold (a handful per frame, or fewer than some tens
of draws in total), print `INSUFFICIENT SAMPLE: N draws over M frames cannot
distinguish the two paths — a per-draw finish is indistinguishable from a
frame that only drew once` and return a distinct status. The disagreement check
must be suppressed in that state for the same reason. Add a selftest case with
`draws=1` asserting the insufficient-sample branch, since the whole argument
for this checker is that its verdicts have been made to fire deliberately.

### M3 — `renderer.c:1762` — the `diag` token spends one number in two different units, so the control arm outlives the dump it is the control for

`fdump_begin()` passes the dump's frame count straight through:

```c
if (also_diag) {
    nv2a_dbg_trigger_diag_frames(frames);
}
```

`frames` counts **`flip_stall` invocations** — that is what `fdump_end_frame()`
decrements, and the lane established this in `AGENTS.md` and commit `7fa7d27047`.
`nv2a_dbg_trigger_diag_frames()` counts **guest frames**: the diag session
advances on `diag_frame_num = g_nv2a_stats.frame_count` (`renderer.c:2224`,
`:2244`). The PR's own control-arm table is the measurement that these are not
the same number: 30 frame records, **1** distinct guest frame.

**Scenario.** A soak arms `--env XEMU_FRAME_DUMP=30,after120,diag`. The live
dump closes after 30 flip_stalls — by the lane's measurement about one second,
still inside guest frame 3127. The diag capture was asked for 30 *guest* frames
and has completed one. It keeps running, with its `pgraph_vk_finish` before
every draw and its per-frame surface readbacks, for as long as it takes the
frozen title to advance 29 more guest frames, with nothing recording it and
nothing the operator wrote bounding it. Every other measurement that soak was
queued for — frame timing, the artifact rate, anything from `soak_title.sh`'s
own logs — is taken under a serialising capture that the spec said would last
30 frames. `DIAG_MAX_FRAMES` is 64 (`renderer.c:502`) so there is no overrun
and no crash, but the clamp bounds the diag session's *arrays*, not its
duration, and at the measured stall factor 30 guest frames is on the order of
900 flip_stalls.

**Remediation.** Either scale the control arm to the unit the operator typed —
pass a small, explicitly-documented guest-frame count (the number of frames you
actually want the control to cover) rather than `frames` — or close the diag
capture when the dump closes, by calling `nv2a_dbg_trigger_diag_frames(0)`-
equivalent teardown from `fdump_close()` when the dump armed it. The second is
the better shape because it makes "the control arm is the dump's control"
true by construction. Whichever is chosen, say in the spec comment that `diag`
does not end when the dump does, if it still does not.

## LOW

### L1 — `renderer.c:1968` — a failed PPM write is announced only on the tag this lane proved is dropped

`dump_surface_ppm()` reports an `fopen` failure through `DIAG_LOG`
(`renderer.c:462`), which is `hakuX-diag` — the tag commit `ad5d93f489` of this
very PR established is absent from both logcat specs that serve a dispatched
run. It also returns silently when `surface->fmt.bytes_per_pixel` is 0, which
the caller's `disp->width && disp->height` test does not cover. Either way
`fdump_end_frame()` has already committed `image` to the frame record and has
already charged `iw * ih * 3` bytes to the cap, so the dump names a file that
is not there and shortens itself for a write that did not happen — with nothing
in the run's log. This is the same invisibility the lane fixed for its own
lifecycle lines and did not extend to the one call it depends on. **Remediation:**
have `dump_surface_ppm()` report through `FDUMP_LOG` when called from this path
(or give it a return value), and emit `"image": null` when it fails.

### L2 — `xemu_android.cpp:1137-1147` — the empty-path case logs nothing at all

The WARN covers only `SDL_AndroidGetExternalStorageState()`. If the state says
`WRITE` but `SDL_AndroidGetExternalStoragePath()` returns NULL or `""`, the
inner `if` fails and the run produces no line on any tag — the dump is silently
unarmed (or, with M1, silently armed elsewhere). One `else` covering both.

### L3 — `framedump_check.py:104` — `max()` over an empty generator

`max(k for k in cb if isinstance(k, int))` raises `ValueError` and exits with a
traceback if no draw record carries `cb_draws` — the shape a schema change or a
dump from an older build would have. A checker whose job is to say "this is not
a frame dump" should say it here too; `FDUMP_SCHEMA` exists and is in the
header but is never read by the checker.

### L4 — `renderer.c:1697` — an arm that cannot open its output has already deleted the previous dump

`fdump_clear_previous(fdump.base)` runs before the `fopen` at `renderer.c:1712`.
On a failure — read-only path, full filesystem, the M1 directory — the previous
run's dump is gone and the new one does not exist. Moving the clear below the
successful `fopen` costs nothing; the new file's own name never collides with
the old ones, since the session id is a timestamp.

### L5 — `renderer.c:1635` — the `noimages` comment says the same number twice

"records only, ~1 MB instead of ~1 MB per frame". The second figure is meant to
be the with-images size (~900 KB *per frame* on top of the records), and the
sentence as written tells a reader the token changes nothing.

## What held up — the clean results

A clean answer to the question the pass was sent to ask is a result, and these
are the ones that matter most for an instrument.

### The per-draw path really does issue no Vulkan work

Enumerated rather than accepted. `fdump_log_draw()` (`renderer.c:1844-1945`)
calls only: `fprintf` to a `setvbuf`'d `FILE*`, `qatomic_read()` on
`submit_count` and `draw_dirty`, `fast_hash()` over a `ShaderState` already in
memory, `pgraph_vk_reg_r()`, and `pgraph_is_texture_enabled()` — which is
`static inline` over `pgraph_reg_r` (`pgraph.h:542-547`) and touches nothing
else. No `vkCmd*`, no `pgraph_vk_finish`, no fence, no submit, no allocation
(the one buffer is allocated at arm time). The header comment's list is
accurate.

### The falsifier is read from the scheduler, and its selftest is a real mutant

`cb_draws` is `r->draws_in_cb` and `submits` is `qatomic_read(&r->submit_count)`
— both the scheduler's own counters, not derived from the spec, so the dump
can contradict its own header. `framedump_check_selftest.py` passes here
(`framedump_check selftest: ok`) and its `liar` case — a dump whose header
claims `per_draw_finish: false` while its draw records serialise — is the exact
shape the field had before commit `ae6f5f10db`, so the disagreement branch has
been made to fire by something other than its own patch. That is not a
tautological falsifier. M2 is about where that check misfires, not about
whether it is real.

### `per_draw_finish` reports `also_diag`, and that is the right source

The fix in `ae6f5f10db` is correct and its reasoning is too: this path forces no
finish, the `diag` token is the only thing in the spec that arms something which
does, so `also_diag` is the only honest value the header can carry. The comment
at `renderer.c:1726-1738` says so and also says which side to believe on
disagreement (the draw records), which is the right ordering.

### The texture register strides are right

`NV_PGRAPH_TEXFMT0/1` = `0x1A04`/`0x1A08`, `TEXOFFSET0/1` = `0x1A24`/`0x1A28`,
`TEXADDRESS0/1` = `0x19BC`/`0x19C0`, `TEXCTL0_0/1` = `0x19CC`/`0x19D0`,
`TEXCTL1_0/1` = `0x19DC`/`0x19E0`, `TEXFILTER0/1` = `0x19F4`/`0x19F8`
(`nv2a_regs.h`). All six are stride 4, so `+ i * 4` across `NV2A_MAX_TEXTURES`
reads the register it claims to for every stage. Checked because the recorded
per-stage texture state is the instrument's payload for #77 and a wrong stride
would have produced four columns of plausible garbage.

### Arming and recording are on one thread, so the missing atomics are correct

`fdump` carries no atomics while the diag state next to it is full of
`qatomic_*`, which reads at first like an omission. It is not: the diag capture
is armed from the UI thread (`nativeDumpDiagFrames`), whereas `fdump_poll_marker()`
and `fdump_end_frame()` are called from `pgraph_vk_flip_stall()` and
`fdump_log_draw()` from `nv2a_diag_log_draw_call()` — all four `vk/draw.c` call
sites (`:7317`, `:7394`, `:7466`, `:7546`) and the flip are the pgraph thread.
Nothing outside that thread touches the struct. `nv2a_dbg_framedump_active()` is
the one cross-thread-shaped reader and it is only called from the same thread.

### `600,diag` cannot overrun the diag session's arrays

`FDUMP_MAX_FRAMES` is 600 and `DIAG_MAX_FRAMES` is 64, but
`nv2a_dbg_trigger_diag_frames()` clamps its argument (`renderer.c:561-568`)
before `diag_init_session()` sizes anything. No crash path. M3 is about the
duration that clamp does not bound, not about memory.

### The arming discipline carries the scars it says it does

Marker `unlink`ed at `renderer.c:1838` in the same breath as the read;
previous `framedump_*` deleted at arm time; the `end` trailer carries a wall
clock so a dump can be dated against its own run; `FDUMP_MAX_FRAMES`,
`cap_mb` and the byte cap all bound the output. The `frame_dump.on` marker is
not matched by `FDUMP_PREFIX`, so `fdump_clear_previous()` cannot eat a marker
armed for a later run.

### The lane's own scope limits are honest and are enforced in the artifact

"No per-draw image", "no clears or blits" (their hooks are gated on
`nv2a_dbg_diag_frame_active()` at call sites in files this lane does not hold),
and "nothing about merging when `draw_merge` is off" are all correct, and the
third is not just prose — the session header records both prefs and the checker
prints the scope note, which the selftest asserts in both directions. That is
the difference between a stated limit and an enforced one.

### Definition of done

`Files:` on the PR body matches the eight paths in `git diff --stat` exactly.
`NOTES.md` is under `docs/lanes/diagdump77/`, not the branch root.
`Prediction: none` is stated with its reason. The PR is out of draft. CI is
green on the head for Android, Desktop and the NV2A index check, so nothing
here is a compile or link finding.

## What could not be audited

* **No device, and none was asked for.** Every claim above is from reading the
  tree; H1 in particular is a code-path argument, not a measurement. The
  measurement that would settle it is cheap and should be part of the
  remediation, not of pass 2's reading: arm `noimages` off on a title with
  a moving camera and check whether `framedump_<id>_fNNN.ppm` matches the
  scene at that frame's `nv2a_frame` or the one before it.
* **No build of my own.** I cite CI's Android and Desktop builds at this head
  rather than claiming one.
* **No validation-layer run.** Nothing in this diff creates Vulkan objects or
  records commands, which is why I did not treat its absence as a gap here —
  but that is an argument from the code I read, not from a layer run.
* **The `diag` control arm's own numbers.** The PR's control-arm table is the
  only sample and it is `n=1` draw, which the PR states. M2 and M3 are both
  about that sample's shape; neither re-derives it.

## Not in scope, but the fold will hit it

`docs/testing/nv2a_index.json` conflicts with `origin/master` —
`git merge-tree --write-tree origin/master HEAD` returns a single content
conflict on that path and nothing else. The head is 40 commits behind master,
which has since moved the same index (`84ac9b6cab`). The CI runs above are from
before that divergence; a conflicting PR gets no new workflow run, so the green
rollup is evidence about the old head and not about the merge. Merging
`origin/master` in (never rebasing — there is no prediction bound here, but the
rule is the rule) and re-resolving the index is the lane's or the board's, not
the auditor's.

## Outside my territory

I claim no files and edited nothing but this audit and its JSON companion, both
under `docs/audits/`.
