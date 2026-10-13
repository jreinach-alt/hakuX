# lane.x1port1012 -- X1 BOX ports for 0.5.1, Halo #939 (ring flicker), #938 (speech level)

Brief: `/home/justin/hakux-work/briefs/x1port1012.md`. Base `dd5e3cb3c6`. X1 BOX tip `dadced00ce`
(`refs/remotes/x1box/master`), common base `fce5a8d19f`.

## Device-run count (cap 24, all attempts, video arms included)

| # | request id | ref | arm | result |
|---|---|---|---|---|
| 1 | 1791876038-x1port1012-2539778 | 310ad08d5b | Phase A smoke: Halo, no route, 180 s, frames 15 | queued 2026-10-13 |
| 2 | 1791876042-x1port1012-2540227 | 310ad08d5b | Phase A smoke: GTA VC, route gta-vc, 420 s | queued 2026-10-13 |
| 3 | (not yet queued: queue limit 2) | 310ad08d5b | Phase A smoke: Crimson Skies, route crimson-skies, 300 s | queue when 1 or 2 finishes |

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
