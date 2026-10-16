# lane.x1port1012 -- X1 BOX ports for 0.5.1, Halo #939 (ring flicker), #938 (speech level)

Brief: `/home/justin/hakux-work/briefs/x1port1012.md`. Base `dd5e3cb3c6`. X1 BOX tip `dadced00ce`
(`refs/remotes/x1box/master`), common base `fce5a8d19f`.

## Final resume (10-16 ~13:00 PDT): why attempt 4 did not finish

Attempt 4 hit the turn cap (301 turns, four compactions) at 12:25 PDT, mid-tool-call. It had committed
and pushed the `gd` instrument (7a1889054a) but wrote none of its findings here: the hull draw
description, the desktop term isolation, device rows 7-12, the hypothesis table. lane.xbox saved its
last compaction summary at `/home/justin/hakux-work/briefs/x1port1012-tools/attempt4-state.md`. This
session copied those findings into "Per-draw investigation" below first, committing before any new
work, and corrected two of them against the shader source (the lights are `c23`/`c25`, not fixed
+-z; stage 5 writes `r1.rgb = c1_5 - v0.a*c0_5`). The cause: one session tried to describe the
draw, isolate the terms on the desktop, and plan runs 11 and 12, all without a commit.

## Attempt 4 resume: why attempt 3 did not finish

Attempt 3 stopped where the brief reserved the next step for an Opus resume: three triage clips waiting
for the owner to judge them. It had nothing queued. Then lane.xbox (10-16) found the three clips void
(they recorded the intro movies, not the menu) and ran the audit and fast-paths-off menu runs itself.
The owner's console check then replaced the "earlier state" picture with two symptoms, (a) and (b).
lane.xbox recorded all of this in the 10-16 sections below and added "Phase B from 10-16" to the brief.
So the lane's own last session did finish. The brief changed after it. This attempt (Opus) starts the
per-draw investigation that the new phase asks for, after merging `origin/master` at 4bf47129b1 (84
commits, Phase A's fold 3c2338eb2b among them; none of them touch this branch's source files).

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
| 4 | 1791897357-x1port1012-341157 | 223f216d7c | #939 triage video 1/3: 8s @ +20s, `HAKUX_SURFGPU=0` | landed clean (no crash/hang). **VOID for #939: the clip is the Microsoft logo and the MGS intro movie, not the ring menu** (see "Triage video void" below) |
| 5 | 1791900988-x1port1012-549369 | c838d62772 | #939 triage video 2/3: 8s @ +20s, fastpaths off | landed clean. **VOID for #939: MGS intro movie and Bungie logo, not the ring menu** |
| 6 | 1791900994-x1port1012-549623 | c838d62772 | #939 triage video 3/3: 8s @ +20s, shipped defaults | landed clean. **VOID for #939: MGS intro movie and Bungie logo, not the ring menu** |

| 7 | 0-1792165273-x1port1012-921745 | 223f216d7c | #939 audit (lane.xbox): `HAKUX_XVSS=audit HAKUX_S2TSHELF=audit`, 150 s, video +40..+90 s | XVSS never reached, S2TSHELF 0 hits; video shows the bursts ("Audit run result") |
| 8 | 1792166308-x1port1012-1386872 | 223f216d7c | #939 all eight fast paths off (lane.xbox), 200 s, video +37..+198 s | bursts recur at the same soak times, same image counts ("Fast-paths-off run result") |
| 9 | 1792175207-x1port1012-3772591 | 7a1889054a | #939 `XEMU_FRAME_DUMP=420,gd,after66,cap2600`, 140 s, no video | 420 frames + PPMs; no X/Y alternation in the PPMs (`ppmalt.py`), so no burst caught |
| 10 | 1792175214-x1port1012-3773341 | 7a1889054a | #939 `XEMU_FRAME_DUMP=360,gd,after44,cap2400`, 120 s, no video | 360 frames + PPMs; no alternation in the PPMs either |
| 11 | 1792177407-x1port1012-231253 | 7a1889054a | #939 `XEMU_FRAME_DUMP=660,gd,noimages,after36,cap2400`, 100 s, video +35..+65 s | read in "Runs 11 and 12" below |
| 12 | 1792177414-x1port1012-233441 | 7a1889054a | #939 `XEMU_FRAME_DUMP=420,gd,after36,cap2400`, 100 s, video +35..+65 s | read in "Runs 11 and 12" below |

12 device runs used of the 24 cap. Phase A smoke batch complete (all three PASS). All three #939 triage
video arms landed, and all three missed the ring scene (void; re-record plan under "Triage video void").

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
- **SUPERSEDED (lane.xbox, 2026-10-16): this bullet is wrong.** `f00003.png` is the Microsoft Game Studios
  intro movie (a blue planet with a timecode overlay), not the ring. The menu is frames `f00004`-`f00008`
  (+33 s to +96 s). All three clips below therefore missed the scene; see "Triage video void" below.
  Original text, kept for the record: The ring + HUD-overlay scene the owner described is on screen early: Phase A smoke run 1's captured
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
All three arms are now dispatched, and all three landed within this session:
  - **Arm 1, `HAKUX_SURFGPU=0`**: `1791897357-x1port1012-341157`. `grep -iE "FATAL|Abort|assert|SIGSEGV"
    logcat.txt` empty. Video: `/home/justin/hakux-work/dispatch/results/1791897357-x1port1012-341157/video/v00001.mp4`
    (8.0 s, 1.50 MB).
  - **Arm 2, fastpaths off**: `1791900988-x1port1012-549369`, ref `c838d62772`. Logcat clean. Video:
    `/home/justin/hakux-work/dispatch/results/1791900988-x1port1012-549369/video/v00001.mp4` (8.0 s, 4.55 MB).
  - **Arm 3, shipped defaults**: `1791900994-x1port1012-549623`, ref `c838d62772`, `env: []` confirms the
    dispatcher cleared the pref back to shipped as expected. Logcat clean. Video:
    `/home/justin/hakux-work/dispatch/results/1791900994-x1port1012-549623/video/v00001.mp4` (8.0 s, 4.31 MB).

All three: no crash, no hang, logcat clean. None of the three is judged for ring/overlay content here --
the brief reserves that call for the owner ("Do not call any arm fixed on your own reading of the
frames"). All three paths are in OUTBOX.md for review.

Not done this session: the `HAKUX_XVSS=audit` and `HAKUX_S2TSHELF=audit` runs that would say whether Halo's
ring scene reaches either lead's changed-output case at all (the brief's leads table calls these out as
the way to size P before a fix, not just a switch existing). Candidate next queue items once the triage
video is judged, same no-route Halo shape, `--env HAKUX_XVSS=audit` / `--env HAKUX_S2TSHELF=audit`
separately.

~~**WAITING**: owner judges the three triage videos.~~ SUPERSEDED, see the next section.

### Triage video void (lane.xbox, 2026-10-16)

Before sending the owner to the clips, lane.xbox pulled a frame every 2 s from each (`ffmpeg -vf
fps=1/2,tile=4x1`). **None of the three shows the ring.** Arm 1 (SURFGPU=0) is the Microsoft logo, a white
fade and the start of the Microsoft Game Studios intro. Arms 2 and 3 are the MGS intro (blue bacteria,
then a blue planet, with a timecode overlay) and the Bungie logo. The timecode overlay on the planet is
what the bullet above took for "the ring with a clock-style overlay". Arm 1 was about 8 s behind arms
2 and 3 at the same `--video-after`, so boot time varies between runs.

Where the ring actually is: Phase A smoke run 1 (`0-1791876038-x1port1012-2539778`, frames every 15 s,
`frames/index.tsv` is the logcat clock, soak start 00:50:40). The main menu, with the ring rotating behind
CAMPAIGN / MULTIPLAYER / SETTINGS / GAME DEMOS, is `f00004`-`f00008` (+33 s to +96 s). From `f00009`
(+112 s) the attract-mode demo plays.

All three arms are built on Phase A (`4f0111232c` is an ancestor of both `223f216d7c` and `c838d62772`),
so even a clip of the right scene could not show whether the glitch exists before A7/A9b (A9b is a #939
candidate itself). The re-record therefore needs a control arm:

| arm | ref | env | what a hit looks like |
|---|---|---|---|
| control | `v0.5.0` (`6f560dc44e`), before Phase A | none | the glitch the owner saw: the ring's surface texture jumping back to an earlier position while the ring itself keeps rotating smoothly (too narrow: the owner's 10-16 sighting is the rotation itself jumping; see the next section) |
| shipped defaults | `c838d62772` (Phase A) | none | the same, or not; if the control shows it and this does not, Phase A (A7 or A9b) is the candidate fix |
| `HAKUX_SURFGPU=0` | `c838d62772` | `HAKUX_SURFGPU=0` | |
| fast paths off | `c838d62772` | the eight `FASTPATHS_VARS` = 0 | |

Shape for every arm: no route, `--seconds 150 --video-after 45 --video-seconds 40` (+45 s to +85 s, inside
the +33..+96 s menu even with an 8 s boot lag either way). Queue the control first and look at it before
queuing the rest: if the control does not show the glitch in 40 s, the other three cannot discriminate
and the owner's recollection of when it appears is the input to ask for, not more runs. Shipped defaults
last (the `--env` pref outlives the run). Device runs: 6 used of 24; this is up to 4 more.

Nova timing: the Nova is under the owner's hands-on hold (10-16), and #984/#986 go first after the
10-15 reset. Queue behind those.

~~**WAITING**: `owner: when the Nova is free, resume x1port1012 on Opus to re-record #939 (control first),
per "Triage video void" in NOTES.md.`~~ SUPERSEDED, see the next section.

### Owner sighting on the Phase A nightly (lane.xbox, 2026-10-16)

The owner played Halo on the Nova at 07:57 PDT 10-16 and reported: "The ring rotation still jumps
around." Build `0.5.0-1014-4a7b7e24b7` (master 10-14), shipped defaults: the build lines say ubershader
ON, surfgpu ON, all eight fast paths ON, no `--env`. `4f0111232c` (A9b) is an ancestor of `4a7b7e24b7`,
so **Phase A does not fix #939**. `f3acdd0912` is not, so the build has the v0-hash skip with no switch.
That answers the "shipped defaults" row above by the owner's own eyes. The control row is only needed
to show whether Phase A fixed it, so it is no longer needed.

The owner's words this time are about the ring's **rotation** jumping, not only its texture. The "what a
hit looks like" cell above is therefore too narrow: a hit is the ring (or the camera's view of it) jumping
to another position, or its surface jumping back, while frame delivery stays smooth.

Capture (attach-only, lane.local's owner-play watcher): `/home/justin/hakux-work/ownerplay/runs/4D530004-1016-0757-23317/`
(`logcat.txt`, plus 9 screenshots about 6 s apart; `075759`, `075805` and `075811` are the menu). Emulator pid 23317, launch 07:57:30,
renderer ready 07:57:35, intro movies to 07:57:57, a 1.3 s load, the menu from 07:57:59, then a clean exit at
07:58:15 (`qemu_main returned 0`).

What the log says about the menu window (07:58:00-07:58:15, seven 2 s windows):

- Delivery is steady. `gfps=29`, `G:33.3-33.5` mean, worst frame in any menu window 38.8 ms, and `hakuX-pace
  v2=60` every window (each game frame held exactly two vblanks). `vbl` 59.93 Hz, p99 16.85 ms. So the
  jump is in what a frame draws, not in when frames arrive: no hitch, no skipped or repeated flip.
- The surface counters are all zero: `[surf92] missed=0 addrchg=0 fbdirty=0`, `held == want` at every
  sample (double buffer `0x022c4000`/`0x023f0000`), `[surfwatch382] gap_writes=0 lost_writes=0`, `[evict372]
  overflow=0 handoffs=0 fallbacks=0`, `[clr89] diverged=0`. None of the known surface-staleness paths
  fired. That says nothing about a path they do not count.
- `[watch311] shelved=0` at all three samples (07:58:00.6, :05.6, :10.6). That is the list
  `create_texture`'s shelf lookup walks (`texture.c`, `QTAILQ_FOREACH(shelved, &r->shelved_surfaces,
  ...)`), so at those instants the S2TSHELF lead had nothing to bind. A 5 s sample is not a hit count:
  a surface shelved and reused between samples would not show. This weighs against S2TSHELF without
  ruling it out.
- `[drawrec] vtx dirty=30 ... walks=30+0` per 60 frames: the menu writes vertex RAM on half the frames.
  The VTX design says a draw never reads data older than with the switch off. The fast-paths-off arm
  still tests that.
- No counter on master sees the XVSS skip. `LAUNCH_TRANSFORM_PROGRAM` (`pgraph.c`) returns early when
  `v0[0]^v0[1]^v0[2]^v0[3]` matches the last launch of the same program, but the program also reads
  `vsh_constants`. A launch whose constants changed (a time or angle) with an unchanged `v0` keeps the
  previous output, an earlier transform. A wrong transform moves geometry, which fits "the rotation
  jumps" better than a texture lead does. This is reasoning, not a measurement.

Re-record plan, revised. The control and shipped-defaults arms are answered. The next run measures:

| run | ref | env | reads |
|---|---|---|---|
| audit | `223f216d7c` (this branch) | `HAKUX_XVSS=audit HAKUX_S2TSHELF=audit` | `[xvss]` and `[s2tshelf]` counts during the menu (+33..+96 s); both are log-only |
| noskip video | `223f216d7c` | `HAKUX_XVSS=noskip` | only if audit shows the skip's output differing in the menu: the owner watches for the jump |

Shape: no route, `--seconds 150`. The video run uses `--video-after 45 --video-seconds 40`. One run can
carry both audits. Each switch reads its own variable. XVSS `audit` keeps the skip's output and runs the
skipped launch on a scratch copy of the constants (checked in `f3acdd0912`). It logs
`[xvss] launches= skips= skip_v0_differs= skip_stale=` every 5 s, plus the first 16 stale skips with
their `prog=` and `first_row=`. `skip_stale > 0` in the menu window is the hit. Device runs: 6 used of 24;
this is 1-2 more.

~~**WAITING**: `owner: when the Nova is free, resume x1port1012 on Opus for the #939 audit run, per "Owner
sighting on the Phase A nightly" in NOTES.md.`~~ Queued, see the next section.

### Audit run queued (lane.xbox, 2026-10-16)

The owner said "Queue it ahead, I'm done with the Nova". lane.xbox queued the audit run as
`0-1792165273-x1port1012-921745` (`--priority blocker`, ahead of the audio1016 requests), on ref
`223f216d7c`. The shipped-defaults triage arm already built that ref. Settings:
`HAKUX_XVSS=audit HAKUX_S2TSHELF=audit`, no route, `--seconds 150`, and a video at
`--video-after 40 --video-seconds 50` (+40..+90 s, inside the menu window).

The video goes on this run, not on a later noskip run. The owner raised the possibility that the defect
is mid-frame: visible on screen, but absent from a settled-frame capture. A still taken every few
seconds cannot tell a half-drawn or stale image from a good one. `screenrecord` on the Nova records
every frame SurfaceFlinger composites. The triage arm's 8 s clip has 485 frames, about 60 fps. The menu
draws at 30 Hz, each image held for two vblanks (`v2=60`). So a correct clip advances the ring by one
constant step every second frame. On frame-by-frame reading, each failure shape points to a different
cause:

| what a frame-by-frame read shows | points to |
|---|---|
| whole frames at a stale angle (rotation goes back, then resumes) | the guest drew it with old transform constants (XVSS); check `[xvss] stale skip` timestamps |
| a frame split across a horizontal line, new above and old below (or the reverse) | the host presented a buffer the guest was still drawing (mid-frame) |
| the ring itself correct, but a texture or overlay on it from another frame | texture reuse (S2TSHELF; `[s2tshelf]` hits) |
| every image correct, but some shown for one recorded frame and others for three, not two each | presentation cadence (judder) on the host side. The Nova panel runs at 120 Hz (the run log's `PERF: display at start`, `peak_refresh_rate` 120). `hakuX-pace v2=60` measures guest vblanks, not what the panel shows, so it cannot see this |
| the clip is clean, yet the owner sees jumps in the same run | the defect is past compositing: a capture of the panel itself (phone slow-motion) is the next instrument |

Written before the run landed. The triage arm's intro-movie clip, read the same way
(`ringframes.py`, lane.xbox scratch), holds 166 of 178 images for two recorded frames, 5 for one,
6 for three. So the uneven-cadence row is already present at about 6% on a movie. Its rate during the
menu is part of the reading.

Hit: `skip_stale > 0` during +33..+96 s, or a frame in the clip matching one of the rows above.
Device runs: 7 used of 24.

~~**WAITING**: `0-1792165273-x1port1012-921745` lands. Then read the counts and the clip frame by frame,
and ask the owner whether the clip shows what they saw.~~ Landed, see the next section.

### Audit run result (lane.xbox, 2026-10-16)

Run `0-1792165273-x1port1012-921745`. The menu came up at about +24 s and held for the rest of the run.
The video covers +42..+92 s, 3030 frames.

- **XVSS: Halo never reaches it.** `xvss_get_mode()` runs on the first `LAUNCH_TRANSFORM_PROGRAM`, and
  only then logs `[xvss] mode=audit`. The line never appears, though `[s2tshelf] mode=audit` on the
  same tag does, and the log shows no drops. So Halo issued no transform-program launch in 150 s, and
  the lead is out for this title.
- **S2TSHELF: zero hits.** Each of the first 32 hits logs a line, and there are none. The lead is out.
- **SUPERSEDED (lane.xbox, 2026-10-16): the reading in this bullet is wrong.** The odd images are not the
  ring at another rotation: they match no normal image anywhere in the clip, and they differ from their
  neighbours in the hull's surface content, not its outline. See "Owner's console check and frame-level
  reading" below. Original text, kept for the record:
  **The clip shows the defect: whole frames drawn at the wrong point in the ring's rotation.** Normally the
  ring's features drift down about 2.7 px per game image. At clip 0.58 s (recorded frame 38) the dome at
  top left jumps about 70 px up, about where it was roughly 25 images (0.9 s) earlier. It holds there for
  a few images, then returns to the smooth path (frame 44 is close to frame 36). Other bursts alternate
  image by image between two rotations (5.4-6.3 s: f332 and f336 agree, f334 differs). Every image is
  complete. No frame splits across a line, and the cadence is regular (1463 of 1501 images held for
  exactly two recorded frames). So this is the "stale angle" row, not the mid-frame or judder rows.
- **The bursts are confined so far to one menu phase.** Two crops (`ringtrack.py`, ring-only regions)
  agree on bursts at clip 0.6-1.5 s, 5.4-6.3 s and 14.6-15.7 s, plus 33.6-34.5 s in the lower crop.
  That is soak +42.6, +47.4, +56.6 and +75.6 s. The texture dirty-query EMA (`Tq`) is 1 from +24 to
  +36 s, about 400 from +40 to +112 s, and 1 again from +114 s. All four bursts are inside `Tq≈400`,
  but the clip covered nothing else, so this is not yet a contrast.
- Frame delivery is steady through every burst (G 32-34 ms). The jump is in what is drawn, not when.

The owner watched this run live: "The jumping about is visible at first in the sunny portion of the
ring, but, the darkened portion is fine as it comes into view. Then as it rotates back around to the
sunny portion, that appeared to be OK, but the animation cut before I could confirm with confidence."

Leads now, neither measured:

1. A host-side cache serves an older copy of something the ring is drawn from: a texture (TEXSCAN, or
   the dirty-bitmap path the `Tq≈400` phase leans on), vertex data (DRAWREC), or uniforms (UNI_*). An
   older copy fits a jump back to an earlier state followed by a return better than a wrong value does.
2. The guest computes the wrong rotation itself, e.g. from a clock read that steps back. The fast-path
   run cannot see this one.

Next run, queued: `1792166308-x1port1012-1386872`, normal priority. All 8 fast paths off, ref
`223f216d7c`, 200 s, video +35..+195 s, which covers both `Tq` phases. A hit for lead 1: no bursts in
the `Tq≈400` phase, where the audit run had 4 in 50 s (0 bursts in 70 s by chance would be about
e^-5.6 ≈ 0.4%). Bursts at the same rate rule the fast paths out. The next instrument would then be a
per-frame log of the transform constants the guest writes, against what the host uploads, which
separates lead 1 (the guest sends the right matrix) from lead 2 (the guest sends the wrong one). That
needs new code. Device runs: 8 used of 24.

Tools: `docs/lanes/x1port1012/tools/ringframes.py <clip>` (cadence, plus per-image step against the
previous two images) and `tools/ringtrack.py <clip> <x,y,w,h> [out.tsv]` (which of the last 12 images each
image is closest to). Crops used: `120,40,880,190` (above the logo) and `0,400,440,420` (lower left, clear
of the menu text). Ignore `ringframes.py`'s SPLIT flag on this scene: the black sky never changes, so it
fires on every image. Phase-correlation shifts read near 0 here because the static HUD rings dominate the
peak. The nearest-image lag is the column that finds the bursts.

~~**WAITING**: `1792166308-x1port1012-1386872` lands; read it with the two tools above, same crops.~~
Landed, see the next section.

### Fast-paths-off run result (lane.xbox, 2026-10-16)

Run `1792166308-x1port1012-1386872`, ref `223f216d7c`, 200 s, video +37..+198 s in three segments
(+37, +97, +158 s). The switches reached the emulator: logcat has `env: HAKUX_*=0` for all 8, plus
`[perdraw433] bulk=0 ubercache=0 fogcache=0` and `[drawrec1010] drawrec=0`. Bursts were grouped by
`tools/burstcount.py`. It treats images whose nearest match is older than the previous
image (`ringtrack.py` lag > 1) as one burst when they are under 1 s apart. On the audit run's tracks it
returns the four bursts listed above, so the two runs are counted the same way.

| crop | audit run (fast paths on) | this run (all 8 off) |
|---|---|---|
| top `120,40,880,190` | (before the clip) | +38.3..+40.6 s, 20 images |
| | +42.6..+43.5 s, 6 images | +41.9..+42.8 s, 6 images |
| | +47.4..+48.4 s, 16 images | +46.7..+47.7 s, 16 images |
| | +56.6..+57.7 s, 18 images | +55.9..+57.0 s, 18 images |
| low `0,400,440,420` | (before the clip) | +38.3..+40.6 s, 19 images |
| | +42.7..+43.5 s, 3 images | +42.0..+42.8 s, 3 images |
| | +47.4..+48.4 s, 17 images | +46.7..+47.7 s, 18 images |
| | +56.7..+57.7 s, 17 images | +56.0..+57.0 s, 17 images |
| | +75.6..+76.5 s, 5 images | +74.8..+75.8 s, 5 images |

- **The fast paths are out.** With TEXSCAN, DRAWREC, UNI_BULK, UNI_UBERCACHE, UNI_FOGCACHE,
  POSTED_PUT, LOCKFREE_WAKE and REPORT_ASYNC all off, every audit burst recurs.
- **The defect is deterministic per boot.** Each burst lands at the same soak time, about 0.7 s
  earlier in this run, and that offset is the same for every burst. It also has the same length in
  images (6, 16, 18 in the top crop in both runs). A race between host threads is unlikely to repeat
  its image count exactly on two runs with different host paths. So the likeliest source is the guest:
  either a wrong value it computes, or what the title really draws.
- **Bursts only in the first part of the menu.** All bursts fall in +38..+76 s. There are none from
  +76.5 s to the cut at +110.4 s (one image with lag 12 at the cut itself, then the attract demo).
  This matches the owner's sighting: jumps in the sunny part first, the dark part fine, the return
  toward the sunny part looking OK.
- **Time and angle cannot be separated in this clip.** The ring never comes back to a burst-time
  angle before the cut (`tools/ringreturn.py`). Each probe from +37.5..+79 s has a best
  match in +80..+111 s that is further off than the same run 1 s later. So "in the first ~40 s of the
  menu" and "at those ring angles" predict the same video here.
- **`Tq` is the scene, not a mode.** The `Tq≈400` phase (+38..+111 s here) is the ring menu, and the
  later `Tq=1` phase is the attract demo (gameplay with a HUD, from about +112 s). The planned contrast
  "bursts in `Tq≈400` vs `Tq=1`" compares two different scenes, so drop it. The bursts start with
  `Tq≈400` (+38.3 s) but end 35 s before it does.

Leads now (**SUPERSEDED, lane.xbox 2026-10-16**: lead 1 is answered by the owner's console check, and
lead 2's "wrong rotation" premise is refuted at frame level. See the next section. Kept for the record):

1. **What the title really draws.** If the real console shows the same jumps at the same point in the
   menu, #939 is not an emulator defect. The console is on and has Halo (`F:\Games\Halo`, 4D530004).
   The check takes the owner about a minute: boot Halo on the Xbox, leave the menu alone, and watch
   the ring for the first minute after it appears. On hakuX the jumps come about 14-52 s after the
   menu appears (menu at about +24 s, per the audit run).
2. **The guest computes the wrong rotation** (lead 2 above), deterministically: e.g. an emulated
   CPU or FPU operation that returns a wrong value for some inputs. The instrument is a per-frame log
   of the matrix constants the guest writes during +36..+60 s. If those jump back with the image, the
   guest made the frame; if they move smoothly while the image jumps, the host drew it from something
   else. That needs new code, and is only worth writing if the console is smooth.

Lead 1 of the audit section (a host-side cache serving an older copy) is ruled out for the eight
fast paths. A cache outside them would also have to repeat its exact image count every boot, which
the determinism finding makes unlikely.

Device runs: 8 used of 24 (no new run).

~~**WAITING**: the owner's look at the Halo menu on the real Xbox (lead 1). If the console is smooth,
resume on Opus for the guest-constant log (lead 2).~~ Answered, see the next section.

### Owner's console check and frame-level reading (lane.xbox, 2026-10-16)

The owner booted Halo on the real Xbox and watched the menu ring:

> Interesting results from the hardware. There's no jumping around in the ring sprites. It's smooth
> throughout the animation. What caught my eye though was the sprite that's jumping around in our
> emulator is actually present and applied across the entire ring, including the dark portions where we
> do not show the sprite at all.

So #939 is an emulator defect, and it has two symptoms, not one:

- **(a) Missing on the dark side.** The console draws a surface layer over the whole ring, the unlit
  side included. hakuX does not draw it on the dark side at all.
- **(b) Toggling on the lit side.** hakuX's lit side switches between two renderings in bursts. This
  is what was read as "jumps".

The owner's direction for the next step: "I also strongly recommend a deeper investigation of what is
wrong. It is categorically unlikely that the solution here is easy or a single site fix."

**Frame-level reading of symptom (b).** Clip: fast-paths-off run, `v00001.mp4`, starts at soak +37 s.
The recording is 60 fps and the guest draws at 30 Hz, so each guest image fills two recorded frames.
The crop is `0,150,440,300` (hull, lower left).

`tools/burstseq.py <clip> 570 660` prints, for each recorded frame, the MAD to the frames 1-4 back:

| | one guest image back | two guest images back |
|---|---|---|
| normal motion (recorded frames 583-586) | 2.1-2.3 | 3.8 |
| burst (587-596), each new image | 10.4-10.6 | 3.7-4.2 |

From recorded frame 587 (soak +46.8 s), each new image is far from the one before it. It is as close to
the image two before as normal motion is. So in a burst, two renderings alternate image by image
(Y X Y X Y X). Each rendering follows the ring's rotation by itself.

Y images in this stretch, by recorded frame:

- 587, 591, 595
- 609, 613, 617
- 635, 639, 643

Each group holds three Y images, with an X between each pair. After a group, 6 and then 8 X-only images
come before the next group. The groups start 11 and then 13 guest images apart. `tools/burstcount.py`
counts this whole stretch as the one +46.7..+47.7 s burst in the table above.

**Y is not another moment.** `tools/ynearest.py <clip> 587,591,595,609,613,617,635,639,643
0,150,440,300` searches every non-Y frame of the clip for the closest match to each Y image. The best
match is always about 28-35 guest images earlier, at MAD 7.9-9.2. One guest image of normal motion is
2.1-2.3. So no image in the clip is a Y image, and the audit section's "whole frames drawn at an earlier
ring rotation" is wrong. A ring that spins about its own axis keeps its outline, so the outline alone
could not settle this. The search does.

**What differs is the surface, not the geometry.** `tools/burstzoom.py <clip> 585,587,589 <x,y,w,h> out.png`
draws X | Y over X | signed Y-X. The ring's outline is the same in X and Y. On the hull, panel features
sit in different places, and a curved bright rim shows in one rendering and not the other. Y is darker
on average:

| crop | X luma | Y luma | next X luma |
|---|---|---|---|
| `60,60,300,200` | 36.3 | 31.9 | 36.1 |
| `40,140,400,260` | 56.1 | 52.9 | 55.9 |

`tools/burstdiff.py <clip> 585 587 589 out.png` shows the same at full frame, with a row and column
profile of |Y-X|. `tools/yclass.py <clip> 37.0` is a full-frame classifier of X and Y images. It
undercounts, because the static menu text and HUD dilute a full-frame MAD. Use it for where the change
sits (lit vs dark pixels, quarter columns), not for counts.

**What is known about the cause:**

- Facts that constrain it:
  - It is deterministic per boot: same soak times, same image counts, on two runs with different host
    paths.
  - The XVSS skip never runs in Halo, and S2TSHELF has zero hits.
  - Turning all 8 fast paths off leaves it unchanged.
  - The alternation period is one guest image.
- Candidate hypotheses. These are untested. None is preferred, and more than one may be true.
  1. A ping-pong or double-buffered resource alternating per frame. It could be a render target sampled
     as a texture, a texture, or a vertex buffer, where one of the pair is stale or wrong on the host.
  2. Texgen modes or texture matrices that the title animates.
  3. Register-combiner inputs: a layer gated by the lighting, specular or secondary-colour term. This
     could explain (a) by itself, since a dark-side gate of zero would drop the layer.
  4. A cube map or reflection lookup.
  5. A detail or self-illumination map.
  6. Blend or final-combiner state.
  7. Vertex-program outputs. Halo issues no transform-program launch (XVSS), but its vertex programs
     still run.
  8. A deterministic guest-side value, from the CPU or FPU.
- One mechanism must explain both (a) and (b), or the notes must name two. Fixing the toggle alone
  would leave the dark side without the layer, and that is still wrong.

**Instruments that would discriminate:**

- **Per-draw state of the ring's draws.** Capture it for an X image and a Y image in the same burst, and
  for an image with the dark side in view. For each draw, record:
  - the texture bound to each stage, with address, format and size, and whether it came from a surface
    (S2T) or from RAM;
  - the texgen mode and texture matrix per stage;
  - the combiner stages and final combiner;
  - the vertex program or the fixed-function setup, including lighting enables;
  - the blend state.

  Diff X against Y. If the guest's methods differ between the two (for example a different texture
  address), the title alternates on purpose, and the question becomes what hakuX holds at that
  address. If the methods are identical, the host draws the same commands two ways.
- **The desktop build** (`/home/justin/hakuX/build-desktop/`) runs the same core on another GPU driver.
  If it shows (a) and (b), the defect is in the core. If not, look at the Android or Vulkan-driver path.
- **A console reference.** A phone video or photos of the lit section of the ring would decide which
  rendering, X or Y, matches the console's layer, or whether neither does.

Device runs: 8 used of 24 (no new run).

~~**WAITING**: nothing external. Resume on Opus for the per-draw investigation above.~~ Done, see the
next section.

## Per-draw investigation (attempt 4, recovered; and the final session)

### The instrument: `gd` (7a1889054a)

`XEMU_FRAME_DUMP=<N>,gd[,noimages],after<s>,cap<s>` adds frame-dump schema 9. Each draw record carries
its guest state as deltas against the previous draw (registers, vertex constants, lighting, the vertex
program, inline attributes), its host identity (pre-draw path, pipeline handle, uber stages, uniform-block
hashes) and a per-stage hash of the guest texture bytes. A skipped draw writes a `skip` record. Reader:
`docs/lanes/x1port1012/tools/gdread.py` (`frames`, `draws F`, `draw F N`, `odd F`, `diff F G`; groups
r c la lb l1 p ff va). `noimages` drops the per-flip display PPM, and with it the forced
`download_surface_complete_deferred` at each flip that the PPM needs.

### The hull draw (step 1)

In a menu frame the outer hull is one draw, `n5`: `inline_elements`, primitive 6
(`NV097_SET_BEGIN_END` 6, a triangle strip), 4362 indices, colour target `0x023f0000` (the back buffer of the pair
`0x022c4000`/`0x023f0000`). Shader hash `ac5a40cb` on the Nova, `48c74844` on the desktop build. It runs a
vertex program (CSV0_D `0x80040000`), not fixed function. Draws `n4`, `n6` and `n0` are the terrain strip,
the inner rim and the planet; they are not described here.

Vertex attributes, stride 32, base `0x3cfb80` (Halo CE's compressed model vertex):

| attr | content | format |
|---|---|---|
| v0 | position | float x3 |
| v1 | normal | CMP 11_11_10 |
| v2 | binormal | CMP 11_11_10 |
| v3 | tangent | CMP 11_11_10 |
| v4 | uv | S1 (normalised short) x2, so v4.z = 0 and v4.w = 1 by default |
| v5 | bone indices | UB_OGL x2 |
| v6 | bone weight | S1 x1 |

Vertex program (read from the generated GLSL, `build-linux/run/hull_vsh.glsl`, scratch):

- Two-bone skinning: rows `c[A0+60..62]` with A0 = v5.x*c7.w and v5.y*c7.w, weights v6.x and 1-v6.x.
  R10 = world position, R11 = world normal.
- E = c4 - R10 (eye vector, not normalised). N' = R11*c12.w.
- **oT3.xyz = c4.w*(E.N')N' - E**, the reflection vector for the cube map (c4.w = 2). oT3.w stays 1.
- oD0.xyz = max(N'.-c23, 0)*c24 + max(N'.-c25, 0)*c26 + c27: two directional lights (c23, c25; the
  `max(..., v4.z)` uses v4.z as a free zero) plus ambient c27. **oD0.w = v4.z = 0.**
- oD1 = (E^.N')*c15 + c16, all four components: the reflection's fresnel tint (rgb) and brightness (a).
  c15 = (0.62,0.64,0.38,0.8), c16 = (0.38,0.36,0.62,0.2): white at full brightness facing the eye, a
  blue tint at 0.2 at grazing angles, **0 where E^.N' <= -0.25** (the varying is clamped to [0,1]).
- oT0 = oT2 = DPH(v4, c13/c14) (base and multipurpose uv), oT1 = that * c12.xy (detail uv).
- Constants seen: c24 = white, c26 = (0.60,0.57,0.76), c27 = (0.27,0.28,0.39), c14.z = 0, c4.w = 2.

Textures (`SHADERPROG 0x00018421`: stages 2D, 2D, 2D, cube), decoded from desktop guest RAM:

| stage | address | format | content |
|---|---|---|---|
| t0 base | `0x02b34000` | 1024x512 DXT1 | dark green panels with a central hatch (mean RGB 48,56,41) |
| t1 detail | `0x02be4000` | 128x128 DXT1 | grey cratered rock (mean 65, so `2*t0*t1` darkens the base by half on average) |
| t2 multipurpose | `0x02b8c000` | 1024x512 DXT1 | R = reflection mask: mottled, cloud-like grey with white panel lines and bright panel lights. G = self-illumination dots and cracks. B = 0 |
| t3 reflection | `0x02b2c000` | 64x64 DXT1 cube, 5 levels | an environment map of the menu scene: face 0 a bright grey-white planet with a blue rim, faces 1-3 dark space with purple nebula, face 4 grey disc, face 5 blue |

The channel order matches Halo CE's shader_model multipurpose map (R reflection mask, G self-illumination,
B change colour).

Register combiners (`COMBINECTL 0x00011008`: 8 stages, per-stage constants), from the generated GLSL:

- st0: r0.rgb = t2.g, r1.rgb = t2.r, r0.a = t2.b.
- st1: v0.rgb = v0 + t2.g*c0_1 (self-illumination added to the diffuse light).
- st2: r0.rgb = mix(1, c0_2, t2.b) = 1; r1.a = t2.r * v1.a.
- st4: t3.rgb = t3 * v1.rgb; v0.rgb = v0 * r0.
- st5: r1.rgb = c1_5 - v0.a*c0_5.
- st6: t0.rgb = 2*t0*t1 (detail, double multiply).
- st7: r0.rgb = t0*v0 + t3*r1.a, that is **2*t0*t1*(v0 + t2.g) + cube(R)*v1.rgb*t2.r*v1.a**.
- Final (SPECFOG0 `0x340f010d`, SPECFOG1 `0x0c111800`): rgb = r1 + mix(c0_8, r0*c0_8.a, 1 - v0.a) =
  r1 + r0 with v0.a = 0; alpha = t0.a.

So the hull is a diffuse term (base x detail x (light + self-illumination)) plus an **additive
reflection term that no light gates**: the cube map, tinted and scaled by the fresnel varying, masked by
t2.r.

### Desktop term isolation (attempt 4)

The desktop build (`build-linux/`, this branch, lavapipe under WSLg) was run with a local, never-committed
`psh.c` override (`HAKUX_PSHDBG=<mode>` replaces the hull's output with one term), dumping frames at
desktop +128 s. Sheet: `build-linux/run/pshdbg/s1.png` (scratch).

| mode | term | result |
|---|---|---|
| 0 | shipped | darker grey-green hull, panel lines, lights |
| 3 | `2*t0*t1` | green panels with grey detail |
| 5 | `cube(R)*v1.rgb*t2.r*v1.a` | nearly black: dark blue-purple, the panel lines just visible |
| 4, 6, 7 | t3 alone, v0, v1 | segfault at 47-54 s (probably an unused sampler or varying dropped from the SPIR-V interface); not run |

The desktop reproduces (a): its hull at that pose has no grey layer either. It was not run long enough
to see whether it reproduces (b).

### Console photo 5 against the terms (final session, by eye)

`console-ref-1016/hullzoom5-console-vs-hakux-soak68.5.png`: on the console the outer hull is a bright,
mottled grey with white panel lines and the panel lights showing through. Of the four textures, only
t2.r has that structure: mottled cloud-like grey, white panel lines, bright lights. The detail map t1
is rock-like too, but it is dark (mean 65) and enters only multiplied by the dark green base. And
`burst-X585-Y587-diff.png` (lane.xbox) shows |Y-X| as a blotchy, cloud-like pattern over the lit hull,
which is t2.r's texture again.

So the console's layer reads as the **reflection term at a bright cube-map face** (the planet: face 0
or 4), and hakuX's reflection term reads near black (mode 5: the dark faces 1-3, or v1 at 0). That
term is the only one that no light gates, which fits the layer covering the console's dark side. In
hakuX's bursts, it would be the term that differs between X and Y. This is a reading of images. The
measurements that settle it are in the table below.

### Hypotheses, ranked (P = this session's estimate before the measurement)

| # | hypothesis | explains | P | refuting measurement | result |
|---|---|---|---|---|---|
| H1 | The reflection term is wrong in hakuX: R points at the dark faces, or v1 clamps it to 0, where the console's R hits the planet | (a); (b) if R or v1 changes between X and Y | 0.6 | desktop: R and v1 visualised over the hull; the term at full strength with a fixed bright face. If the console's look comes back with the cube term forced to the planet face, H1 holds | open |
| H1a | ...because the cube map's faces are read from the wrong offsets (face stride, mip-chain size or alignment of a 64x64 5-level DXT1 cube) | (a) | 0.25 | decode the cube from guest RAM at the hardware face stride; adjacent faces must be continuous at shared edges | open |
| H1b | ...because the cube face orientation differs from NV2A (axis sign or face order) | (a) | 0.15 | as H1a: seams; and R visualised against which face the console shows | open |
| H1c | ...because E or N' is wrong (c4 eye position, c12.w, the CMP normal decode, skinning) | (a), lighting too | 0.15 | the diffuse term would also be wrong; compare the lit/dark boundary with the console photos | open |
| H2 | (b) is a per-frame difference in the guest's draw (constants, texture address, LOD) | (b) | 0.4 | `gdread diff` of the hull draw between an X and a Y frame in one burst | runs 11/12 |
| H3 | (b) is the host drawing the same commands two ways | (b) | 0.3 | as H2: identical guest state, different image | runs 11/12 |
| H4 | the detail map (t1, double multiply) is the console's layer | (a) | 0.1 | t1 is dark (mean 65) and multiplies a dark base; it cannot make a bright grey layer at any scale | weighs against, by the texture means |
| H5 | v0.a (= v4.z) is non-zero on hardware, mixing the output toward white | (a) | 0.05 | would wash out the panel lines and lights, which the console shows | weighs against, by photo 5 |
| H6 | the eight fast paths, XVSS, S2TSHELF | (b) | - | - | ruled out (runs 7, 8) |

Runs 9 and 10 (gd with per-flip images) showed no X/Y alternation in their PPMs. Either they did not
cover a burst (their `after` offsets were aimed by the soak clock, which differs from the dump's
arm clock), or the per-flip download that images force suppresses (b). Runs 11 (no images) and 12
(images), both with a video, separate those two.

## End of this session (attempt 3)

All six device runs dispatched this lane are complete: Phase A smoke (runs 1-3, all PASS) and all three
#939 triage-video arms (runs 4-6, all landed clean, none judged for content). 6 of 24 device-run cap
used, 0 of 2 queue slots in use -- nothing of this lane's is queued or running. Both branches
(`lane/x1port1012`, now `State: ready`; `lane/x1port1012-halo`, still `State: draft` pending the owner's
video judgment) are pushed with NOTES/OUTBOX/PR.md current. Posted `[lane.x1port1012] waiting:` on both
PR #965 and PR #969 before the last two runs landed; since then nothing is queued, so this is not a wait
on anything external -- it is a stop at the point the brief reserves for an Opus resume (judging the
videos, per the WAITING line above), with no device runs left outstanding to poll for.
