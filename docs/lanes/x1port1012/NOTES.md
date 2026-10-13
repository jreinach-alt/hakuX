# lane.x1port1012 -- X1 BOX ports for 0.5.1, Halo #939 (ring flicker), #938 (speech level)

Brief: `/home/justin/hakux-work/briefs/x1port1012.md`. Base `dd5e3cb3c6`. X1 BOX tip `dadced00ce`
(`refs/remotes/x1box/master`), common base `fce5a8d19f`.

## Attempt 3 resume: why attempt 2 did not finish

Attempt 2 (Sonnet, automatic resume while usage is Low) ended the session with two of this requester's
two queue slots full (Crimson Skies smoke run 3, triage-video arm 1) and nothing else to do until one
landed, per `investigate-the-wait-not-the-clock`/this lane's own device-run discipline: it posted
`[lane.x1port1012] waiting:` on both PRs and stopped rather than poll. That is a finished, correct
session per this file's own "End of this session" note below -- not a failure to pick up.

This attempt found both queued runs had completed (`dispatch/results/1791897193-x1port1012-336185` and
`.../1791897357-x1port1012-341157`), merged 11 commits of `origin/master` that had landed since this
branch's base (none touched this lane's territory files -- checked with `git log --oneline HEAD..origin/master
-- <territory paths>` before merging, per the startup hook's instruction to merge before concluding
anything from this tree), judged run 3 (PASS) on the `lane/x1port1012` branch via a second worktree at
`/home/justin/hakux-work/wt/x1port1012-base` (removed after pushing -- NOTES.md/OUTBOX.md/PR.md are
per-branch files, not shared, so updating the base PR needed its own checkout), set that PR's
`State: ready`, and queued triage-video arms 2 and 3 (ref `c838d62772`, the merge commit -- the actual
tree that will build, though none of the merged commits touch this lane's files).

## Attempt 2 resume: why attempt 1 did not finish

Attempt 1 (Opus) did real work past where this file stops: `git log` on `lane/x1port1012-halo` (this
worktree's branch, built on top of `lane/x1port1012`) shows three Phase B commits made after the last
entry below -- f3acdd0912 (`HAKUX_XVSS` switch, the v0-hash skip lead), 18fb351588 (`HAKUX_S2TSHELF`
switch, the shelf lookup lead), 223f216d7c (per-frame staging-buffer memory-properties log, the staging-
coherence lead) -- all three credited `Co-Authored-By: Claude Opus 5.5`. None of that is recorded here or
in OUTBOX.md, the branch was never pushed (`git branch -a` shows only `lane/x1port1012` on `origin`, not
`-halo`), no PR exists for it, and Phase B step 1 (the triage video, which the leads in step 2 exist to be
candidates for) was never queued. The session ended mid-brief with no docs, no push, no PR, nothing
WAITING. Treating that as unfinished rather than complete: the definition of done needs a pushed branch,
an open PR and NOTES/OUTBOX that match the commits, and none of those existed for this branch.

This attempt (Sonnet, automatic resume while usage is Low) picks up: Phase A's two already-queued smoke
runs had in fact completed (results existed under `dispatch/results/`, just never read back into this
file), so they are judged below; the third Phase A smoke title is queued; Phase B's triage video (step 1)
is queued next, now that the three leads from step 2 exist as switches to test against.

## Device-run count (cap 24, all attempts, video arms included)

| # | request id | ref | arm | result |
|---|---|---|---|---|
| 1 | 0-1791876038-x1port1012-2539778 | 310ad08d5b | Phase A smoke: Halo, no route, 180 s, frames 15 | PASS, gfps 59.93 vs 59.98 baseline |
| 2 | 0-1791876042-x1port1012-2540227 | 310ad08d5b | Phase A smoke: GTA VC, route gta-vc, 420 s | PASS, fps_ok_share 0.9859 vs ledger 0.9872 |
| 3 | 1791897193-x1port1012-336185 | 310ad08d5b | Phase A smoke: Crimson Skies, route crimson-skies, 300 s | PASS, fps_ok=1.0 vs ledger 0.95 (judged attempt 3) |
| 4 | 1791897357-x1port1012-341157 | 223f216d7c | #939 triage video 1/3: Halo menu, 8s @ +20s, `HAKUX_SURFGPU=0` | landed clean (no crash/hang); owner-judged, not scored here |
| 5 | 1791900988-x1port1012-549369 | c838d62772 | #939 triage video 2/3: Halo menu, 8s @ +20s, fastpaths off | queued 2026-10-13, attempt 3 |
| 6 | 1791900994-x1port1012-549623 | c838d62772 | #939 triage video 3/3: Halo menu, 8s @ +20s, shipped defaults | queued 2026-10-13, attempt 3 |

6 device runs used of the 24 cap. Phase A smoke batch complete (all three PASS). All three #939 triage
video arms now dispatched; arm 1 has landed, arms 2-3 are in flight.

## Phase A -- ports (branch `lane/x1port1012`)

One commit per port, so lane.local can drop any one at the 0.5.1 cut. Every port is credited in its
commit message (`Ported from X1 BOX <sha> (izzy2lost/xemu).`). Each C file was syntax-checked with
`docs/lanes/x1port1012/ccheck.py <file>` (the newest Release arm64 compile_commands.json); the Kotlin
with `:app:compileDebugKotlin --offline` (exit 0).

| item | X1 BOX source | commit | what was taken, what was not |
|---|---|---|---|
| A1 VP asserts skip the voice | c59b1a7ba7 (vp.c), 51e16997ff | 81b542ca3e | Segment asserts become a skip of that voice (`return -1`) with one log line per kind of bad data per run (`VP_BAD`). |
| A2 texture outside VRAM binds dummy | 39435acbc7, 71604431d6 | de06bd39e3 | `check_texture_dirty` clamps instead of asserting; `create_texture` binds `r->dummy_texture` when the texture (plus palette, if indexed) runs past VRAM; at most four log lines a run. |
| A3 ADPCM step-index clamp | d8d73ed85b | 79981e045c | `CLIP(index, 0, 88)` instead of refusing the block. The refused block was not silence, as the brief said: `adpcm_decode_block`'s return is ignored at vp.c ~1685 and the output is an uninitialised stack array, so it played garbage. |
| A4 NULL guard of e3c1927bdf | d5d64b9dc3, e3c1927bdf | cbda0e85fd | Our tree HAS the dereference, and worse: volk loads `vkCmdSetCullMode` (core) and `...EXT` separately with no aliasing, and with `OPT_DYNAMIC_STATES=1` cull mode and front face are called unconditionally (draw.c ~7274, ~9052). Taken, in instance.c only: the core<-EXT aliases for the seven EDS1 commands; EDS1 off if a depth/stencil command is still NULL; a device with no cull/front-face command is refused with a message instead of crashing. Not taken: making cull/front face static without EDS1 (draw.c restructure), the framebuffer-view invalidation. Changes nothing on a Vulkan 1.3 device (the Nova). |
| A5 setup-wizard BIOS size check | a7765290d1 (validation hunk) | d0eb2410b2 | 256 KB / 512 KB / 1 MB accepted; checked before the copy (`sourceSizeOf`) and after it (`File.length()`, the copy is deleted and the prefs cleared on a bad size); Toast with the file name and size. SettingsActivity's own flash picker is NOT checked: out of territory and out of the brief. |
| A6 HRTF history clear; audio-init failure non-fatal | 55262dde6d (two hunks) | 10c83bfa06 | `hrtf_filter_clear_history()` at voice start (`voice_reset_filters`). `monitor_init`: SDL_Init / SDL_OpenAudioDevice failure warns and returns instead of `exit(1)`/assert; `se_frame` skips the FIFO push when there is no device. Not taken: the menu changes. Follow-up noted, not done: with no device `throttle()` returns early, so the APU runs unpaced (X1 BOX does the same). |
| A7 staging flush; UBO barrier fragment stage | 3d3515faad | d4d292c9ca | `vmaFlushAllocation` before `vkCmdCopyBuffer` in `sync_staging_buffer` (a no-op on coherent memory). The fragment stage in the UBO barrier is OURS, not X1 BOX's: 3d3515faad does not contain it and X1 BOX's tip still has VERTEX only; justified by shaders.c:240-252 (binding 1 is the FRAGMENT-stage UBO). Not taken: an explicit HOST->TRANSFER barrier (submit's implicit host-write dependency covers it), the Mali strict-draw switch. |
| A8 hrtf.h normalisation `break` -> `continue` | ours | d88374737c | Not a port: X1 BOX carries the same `break` (hrtf.h:74-76 at its tip). |
| A9a pipeline-cache retry | 1d10f6cb2a / 67fe8d7b2e | 172d94de1f | A rejected cache file starts an empty cache (warn, retry with no data) instead of `VK_CHECK` aborting. |
| A9b DMA_VERTEX gen bump | b4999f2e97 (pgraph.c hunk) | 4f0111232c | `SET_CONTEXT_DMA_VERTEX_A/B` bump `vertex_attr_gen` when the value changes. vertex.c caches the attribute layout, base addresses resolved through `nv_dma_map(dma_vertex_a/b)`, keyed on that gen (vertex.c:346, 464, 529), so a DMA object swap kept the old addresses. Also a #939 candidate: stale vertex addresses are "geometry at an earlier state". |

### Phase A regression check

- `preflight.sh` passed on 4f0111232c (psh_differ, aci_vmstate, nv2a index, territory, coverage, board files).
- **nv2a_index.json: not regenerated, on purpose.** `nv2a_index.py check` (the gate, line drift tolerated)
  passes. `check --exact` reports 614 MOVED sites and no added/removed symbol: the ports only shifted line
  numbers. Committing a rebuild would rewrite those 614 `loc` lines and conflict with every other PR on
  pgraph.c/draw.c (memory: index line numbers conflict every PR); the fold regenerates it on master.
- **pgraph suites.** `nv2a_index.py blast` on pgraph.c/vk texture.c/draw.c/instance.c names 8 to re-measure
  (Blend surface, Bump env lum, Bump map, Texture format, Texture render target, Volume texture, Clear,
  Texture DXT). Read against the actual hunks, none of them reaches changed behaviour on the Nova except A7's
  barrier stage (every draw) and A9b (only when a test changes DMA_VERTEX, which the suites set once):
  A2 fires only for a texture past VRAM, which a golden-passing test does not bind, A4 and A9a are no-ops on a
  working 1.3 device, the flush is free on coherent memory. Not queued as a separate device run; the smoke
  titles exercise A7 on every draw. If a reviewer wants the suites, one request covers all 8:
  `request.sh --suites "Blend surface,Bump env lum,Bump map,Texture format,Texture render target,Volume texture,Clear,Texture DXT"`.

### Phase A smoke (Nova), how to queue and how to judge -- a Sonnet resume can carry this

Ref: the Phase A head (`lane/x1port1012`). Requester `--who x1port1012`. `HAKUX_RELEASE_PRIO=0` in the
environment: request.sh otherwise reads the issue label over GitHub, and this lane does not touch GitHub.
At most 2 queued at once.

| title | how | ledger reading (pm/playable-accepted.tsv) | same-shape earlier run |
|---|---|---|---|
| Halo: Combat Evolved (4D530004) | no route (master has no `halo-ce.route`; profile gate admits it, clause `profile`, golden 90ebd6a27bd1), `--seconds 180 --frames-every 15` | 0-1791083791-lanelocal-3030989 PASS, 29.97 median in play (that run used the unfolded `halo-ce` route) | 1-1791706605-fastpaths1010-4193827: 180 s no-route, gfps 59.98 (menu) |
| Grand Theft Auto: Vice City (5454000F), the audio-heavy one (radio) | `--route gta-vc --seconds 420` (mark at ~116 s, so ~300 s of play) | 1-1791792688-lane.local-32790 PASS, fps_ok_share 0.9872, 684 s play | same |
| Crimson Skies (4D530021), the Vulkan texture path one | `--route crimson-skies --seconds 300` | 1-1790804473-lane.verdict433-1767161 | 1-1791703775-fastpaths1010-4011126: gfps 59.90 |

The third smoke request, verbatim (queue it only when the queue holds fewer than 2 of ours):

    HAKUX_RELEASE_PRIO=0 docs/testing/request.sh --who x1port1012 --purpose "x1port1012 Phase A smoke (#939): Crimson Skies (Vulkan texture path), route crimson-skies, 300 s, ports A1-A9 at shipped defaults. Expect: no crash/hang, fps within noise of the ledger (1-1790804473-lane.verdict433-1767161) and of 59.90 (1-1791703775-fastpaths1010-4011126)" --title "Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso" --route crimson-skies --seconds 300 --device nova --ref 310ad08d5b --issue 939 --no-expect "smoke: crash/hang and fps against the ledger run, not an A/B"

JSRF was the first audio pick and is refused by the profile gate (`jsrf.route` is first-run and the title
has a kept profile); do not retry it.

Judge each result (`/home/justin/hakux-work/dispatch/results/<id>/`):
1. No crash, no hang: `run.log` ends cleanly; `logcat.txt` has no `FATAL`, `Abort`, `assert`, `SIGSEGV`.
   Also grep `logcat.txt` for the ports' own lines: `vp: bad` (A1), `outside VRAM` (A2), `hakuX-audio` (A6),
   `pipeline cache` (A9a). Any of them firing is a finding to write down, not a failure.
2. Route titles: `python3 docs/testing/title_verdict.py <result-dir>`; compare `fps_ok_share` (and
   `gameplay_s`) with the ledger run's `verdict.json`. A drop of more than ~0.02 in fps_ok_share is a flag.
3. Halo (no route): gfps = sum(vb)*1000/sum(ms) over the `hakuX-pace` lines from app start + 30 s to
   `soak end` (fastpaths1010 NOTES 4.2's method); compare with 59.98. Look at the frames: menu, ring.
4. Write the row into the run table above and a line in OUTBOX.md. If all three hold: set PR.md
   `State: ready`, commit, push.

### Phase A smoke judged (attempt 2, runs 1-2; run 3 queued)

Both results existed on disk already (attempt 1 dispatched them but the session ended before reading them
back): `0-1791876038-x1port1012-2539778` (Halo) and `0-1791876042-x1port1012-2540227` (GTA VC).

- **No crash, no hang** (both): `grep -iE "FATAL|Abort|assert|SIGSEGV" logcat.txt` is empty in both;
  `run.log` ends with the normal `held <iso> for <n>s` / `PERF: restored=...` tail. Port log lines (`vp:
  bad`, `outside VRAM`, `pipeline cache`) do not fire -- expected, nothing in either run's content reaches
  those paths. `hakuX-audio` lines are the routine `submix_headroom` startup log, already in master, not a
  Phase A finding.
- **Halo** (no route, menu/ring only): `hakuX-pace` sums from app start + 30 s (logcat begins right at
  `soak start`, 00:50:40.062, so +30 s = 00:51:10) to `soak end` (00:53:41.411): sum(vb)=9131,
  sum(ms)=152351.9, gfps = 9131*1000/152351.9 = **59.93**, against the 59.98 baseline
  (`1-1791706605-fastpaths1010-4193827`, same shape). PASS, well inside noise.
- **GTA Vice City** (route `gta-vc`): `title_verdict.py` reports `fps_ok=0.9859 crash=False hang=False`
  against the ledger's `fps_ok_share=0.9872` -- diff 0.0013, under the ~0.02 flag. The verdict line also
  says `FAIL(duration: 310 s of gameplay < 600 s screening)`; that is `title_verdict.py`'s own screening
  gate for a full ledger-length run, not this smoke run's bar (the brief: "no crash, no hang, fps within
  the run's own noise" at the smoke's own --seconds). Read as a smoke PASS, not a screening FAIL.
- Both rows are filled in the run table above.

### Phase A smoke judged (attempt 3, run 3): all three now PASS

`1791897193-x1port1012-336185` (Crimson Skies, route `crimson-skies`): `grep -iE "FATAL|Abort|assert|SIGSEGV"
logcat.txt` empty; port log lines (`vp: bad`, `outside VRAM`, `pipeline cache`) do not fire.
`title_verdict.py` reports `fps_ok=1.0 crash=False hang=False` against the ledger's `fps_ok=0.95`
(`1-1790804473-lane.verdict433-1767161`) -- better than the ledger run, well inside noise. The
`FAIL(duration: 194 s of gameplay < 600 s screening)` on that same verdict line is `title_verdict.py`'s
own screening gate for a full ledger-length run, same caveat as GTA VC's smoke judgment above, not this
smoke run's bar. PASS.

All three Phase A smoke titles now PASS. Judged and pushed on `lane/x1port1012` itself (via a second
worktree, see "Attempt 3 resume" above, since NOTES/OUTBOX/PR.md are per-branch): commit `5dfea123a3`,
PR.md `State: ready`, pushed to `origin/lane/x1port1012`.

## Phase B -- #939, the Halo ring world

Attempt 1 wrote three default-off leads as switches (git log on this branch, Phase B leads from the
brief's step 2), each already carrying its own commit message rationale:

| switch | commit | what it changes | ref for `--ref` |
|---|---|---|---|
| `HAKUX_XVSS` | f3acdd0912 | `noskip` runs every `LAUNCH_TRANSFORM_PROGRAM` (X1 BOX removed the v0-hash skip, cf92edbbba); `audit` logs how often the skip's output would have differed (`[xvss]`, hakuX-perf) | f3acdd0912 |
| `HAKUX_S2TSHELF` | 18fb351588 | `0` turns off the shelved-surface lookup in `create_texture` (texture reads VRAM after the range scan instead); `audit` logs each hit's state (`[s2tshelf]`, hakuX-perf) | 18fb351588 |
| (logging only) | 223f216d7c | one line per per-frame staging buffer at init, saying HOST_COHERENT or not (next to the existing create line) | 223f216d7c (current HEAD) |

Step 0 (owner logs) was not attempted this session -- the brief says skip it after a few minutes if not
found quickly, and finding them is a search through session logs outside this worktree; left for whichever
session does step 3's owner review to check if convenient, not a blocker.

Step 1, the triage video (3 arms: shipped defaults, `HAKUX_SURFGPU=0`, all eight fast paths off), was not
queued by attempt 1 despite the leads existing to test. Queuing it now:

- Halo has no route (confirmed again this session: no `halo-ce.route` under `docs/testing/routes/`), so
  all three arms use the no-route soak, matching Phase A smoke run 1's shape.
- The ring + HUD-overlay scene the owner described is on screen early: Phase A smoke run 1's captured
  frame `f00003.png` (soak start + 17 s) already shows the ring curvature with a clock-style overlay
  (`19:18:18:06`, a circular icon) drawn on top of it -- this is very likely the menu backdrop the owner
  means. `--video-after 20` lands just past that, with margin for the pace lines to have reached steady
  state (by +11 s in run 1).
- Fast-path switch names, from `MainActivity.kt`'s `FASTPATHS_VARS` (the eight the "Fast renderer paths"
  setting sets together): `HAKUX_REPORT_ASYNC`, `HAKUX_TEXSCAN`, `HAKUX_DRAWREC`, `HAKUX_UNI_BULK`,
  `HAKUX_UNI_UBERCACHE`, `HAKUX_UNI_FOGCACHE`, `HAKUX_POSTED_PUT`, `HAKUX_LOCKFREE_WAKE`.
- `--env` writes the app's `env_vars` pref and outlives the run until the next dispatched request clears
  or replaces it (checked `apply_env_pref` in `dispatch/bin/dispatcher.sh`: a request with no `--env` DOES
  clear a previous dispatcher-set env, via the `.env_pref.<dev>` marker, so queuing shipped-defaults with
  no `--env` last is sufficient, not just cosmetic). Order: SURFGPU=0, then fastpaths-off, then shipped
  defaults last.
All three arms are now dispatched:
  - **Arm 1, `HAKUX_SURFGPU=0`**: `1791897357-x1port1012-341157`, queued attempt 2, landed attempt 3.
    `grep -iE "FATAL|Abort|assert|SIGSEGV" logcat.txt` empty; `video/v00001.mp4` captured (8.0 s, 1.50 MB).
    Not judged for content here -- the brief reserves that for the owner.
  - **Arm 2, fastpaths off**: `1791900988-x1port1012-549369`, queued attempt 3, ref `c838d62772`
    (current HEAD after the origin/master merge -- none of the merged commits touch this lane's files).
    Verbatim as sent:

        HAKUX_RELEASE_PRIO=0 docs/testing/request.sh --who x1port1012 --purpose "x1port1012 #939 triage video arm 2/3: Halo ring-world menu, all eight fast renderer paths off, 8s video 20s after soak start, no route." --title "Halo Combat Evolved.iso" --seconds 60 --video-seconds 8 --video-after 20 --env HAKUX_REPORT_ASYNC=0 --env HAKUX_TEXSCAN=0 --env HAKUX_DRAWREC=0 --env HAKUX_UNI_BULK=0 --env HAKUX_UNI_UBERCACHE=0 --env HAKUX_UNI_FOGCACHE=0 --env HAKUX_POSTED_PUT=0 --env HAKUX_LOCKFREE_WAKE=0 --device nova --ref c838d62772 --issue 939 --no-expect "triage video, owner-judged, not an automated A/B"

  - **Arm 3, shipped defaults** (queued LAST, after arm 2, no `--env` at all, so the dispatcher clears the
    env pref back to shipped): `1791900994-x1port1012-549623`, queued attempt 3, ref `c838d62772`.
    Verbatim as sent:

        HAKUX_RELEASE_PRIO=0 docs/testing/request.sh --who x1port1012 --purpose "x1port1012 #939 triage video arm 3/3: Halo ring-world menu, shipped defaults, 8s video 20s after soak start, no route." --title "Halo Combat Evolved.iso" --seconds 60 --video-seconds 8 --video-after 20 --device nova --ref c838d62772 --issue 939 --no-expect "triage video, owner-judged, not an automated A/B"

Not done this session: the `HAKUX_XVSS=audit` and `HAKUX_S2TSHELF=audit` runs that would say whether Halo's
ring scene reaches either lead's changed-output case at all (the brief's leads table calls these out as
the way to size P before a fix, not just a switch existing). Candidate next queue items once the triage
video is judged, same no-route Halo shape, `--env HAKUX_XVSS=audit` / `--env HAKUX_S2TSHELF=audit`
separately.

**WAITING**: once all three triage-video arms have results, judging which arm (if any) removes the
ring/overlay glitch -- and whether to call a lead confirmed -- is an owner-reviewed call per the brief
("Do not call any arm fixed on your own reading of the frames", "the owner judges the videos"). That is
also the kind of cause call the brief reserves for an Opus resume. This session queues and documents; it
does not judge the videos. `owner resume x1port1012 on Opus: judge #939 triage video arms (ids: run 4
HAKUX_SURFGPU=0 landed, run 5 fastpaths-off and run 6 shipped-defaults queued) once all three have
landed, and decide whether XVSS/S2TSHELF audit runs are worth queuing before or after that judgment.`

## End of this session (attempt 3): waiting on the queue

Both of this requester's two queue slots are now full again (run 5 fastpaths-off, run 6 shipped-defaults)
and neither has started running yet (checked `dispatch/running/` and `dispatch/queue/` before stopping).
Nothing to do in-session until one finishes -- arm 1 already landed and arm 2/3 landing completes the
triage-video set, at which point the three video paths go in OUTBOX.md and the owner review is the next
step (Opus, per the WAITING line above). Posted `[lane.x1port1012] waiting:` on both PRs naming run ids
5 and 6 as the signal. A future resume should re-check `dispatch/results/` for
`1791900988-x1port1012-549369` and `1791900994-x1port1012-549623` first; if both have landed, list all
three video paths in OUTBOX.md and leave the WAITING line above for an Opus resume to judge.
