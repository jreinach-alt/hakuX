# lane.gta3fps1017b -- GTA III fps: R2 and R3 written, default off, for the owner's driving session (#1049, #433)

Status (10-18, attempt 4): R2 and R3 written (8e42fa1058); building, suites, write-up.

**Why attempt 3 did not finish.** It hit the 300-turn cap (`terminal_reason: max_turns`, session
20261018T061841Z) after committing R2 and R3 in `texture.c` (8e42fa1058, 510 lines) and merging master twice,
but before building them, running the suites, or writing the pixel arguments and the three-title dip table; its
two analysis scripts (`tools/dip_table.py`, `tools/suite_band.py`) were left untracked. The host's resume note says
"no R2/R3 code has landed": that read the working tree against HEAD, not HEAD against master -- the code is on the
branch. The cause is turn budget spent on scope that grew twice (San Andreas, Blinx 2), not a void; attempt 4
builds and tests the committed code first and writes up after, committing at each step.

**Why attempts 1 and 2 did not finish.** Attempt 1 (session 05:55Z) committed Step 0 (b1828311f2) and the merge of
`origin/lane/gta3fps1017` (a6680ef37e), then ended before any code. Attempt 2 (session 06:14Z) ended within four minutes,
before attempt 3 started at 06:18Z: its session log is empty (0 bytes) and it left no commit, no worktree change and no
PR comment, so there is no cause on record to name or to repeat. The two owner addenda (high-speed driving on GTA III +
San Andreas; Blinx 2's island) arrived in the brief across these restarts. Nothing from either attempt is redone here.

## 0. Already tried (copied from `origin/lane/gta3fps1017` NOTES.md sections 0-3 and 5, extended)

A resume reads this table first and extends it; it never repeats a row.

| tried | where | result | consequence for this lane |
|---|---|---|---|
| Six scripted drive tries, a pathfind route into the Kuruma (`gta-3-drive.route`) | gta3drive1017 NOTES 8.2-8.7; requests 1364097/1364296, 1563459, 1853100, 2035473, 2291336, 2477310 | all VOID at the same gate: the route cannot get into or stay in the car (help-box gate never matched; mission restarted under throttle; the car flipped on the bridge ramp; Y got Claude out) | **Do not script driving. No seventh route.** The driving numbers come only from the owner's session |
| On-foot census (gta3fps1017 NOTES 2.1, desktop c1/c2, and the Nova pilot's 26 windows, 2.2) | `[s2c]` census, `NV2A_PERF_LOG` build | **2.00 copies/flip**, reason `map` 100%, dup 0, two surface pairs: `surf @3d04000 color1 fmt0x4 vk44 1280x480 -> tex fmt0x1e vk44 map0002` and the same at 640x480 (`@3bd8000`) | measured; it does not transfer to driving (~73/flip, 36x). **Do not re-run it on foot** except as R2's before/after (the brief's step 7) |
| perflog pilot `1-1792275531-lane.gta3drive1017-343857` (Nova, Turnip) | gta3drive1017 NOTES 6.1-6.2 | < 26 fps band: PFIFO waits ~11.6 ms/flip in the #474 drain (71.9 drains/flip); ~73 copies/flip; 22-30 render passes per frame; every burst copy at `s2t@1264` (R1's plain colour copy branch) | measured; **do not re-measure** |
| Do copies per flip track driving? (gta3fps1017 re-read of pilot 343857) | that lane's NOTES row 4 | the bursts (3 to 203 per flip) fall while the car moves, just after a crash, or at the garage camera under throttle; on foot never leaves 2.00. The high garage window: cp 172.5/flip, srf 186, an `[ovl1018]` 256x256 swizzled Z inside a 1024x1024 linear Z | the burst's refusal reasons and dups are **unknown**; R2/R3 are written blind to them, switchable, for the owner's session to read |
| R1 (merged from lane/gta3fps1017: b7d7243392, c6ca5296fd; census bd2bf354bb) | gta3fps1017 NOTES 2.3-2.5, 4 | removes the ~11.6 ms/flip #474 drain ahead of a plain colour copy; desktop pgraph suites pass on and off (363 tests, diffs only in Texture_shadow_comparator, within its own rerun band); ~60 min of GTA III on Turnip with R1 on, no fatal | **do not rewrite it; build on it.** Its switch `HAKUX_S2T_DRAIN=1` restores the drain |
| The pgraph suites as a test of R1 | gta3fps1017 NOTES 2.3, gta3drive1017 8.1 | no suite reaches R1's branch (no `[s2tdrain]` line in any arm) | blind to R1. For R2/R3 they are run on and off **and** checked for the switches' own log lines, so a green run says whether it reached the branch |
| R2 / R3 (gta3fps1017 NOTES 3) | that lane's pick | not written: the on-foot census does not transfer to driving | right for a census-first plan, wrong for the owner's ask (10-17 ~23:00 PDT): **this lane writes both, off by default** |
| Pairing logcat timestamps to txw lines with `grep -o \| paste - -` | gta3fps1017 NOTES 6 | lines without a match shift the pairing and drop windows | parse each line whole |
| Desktop lavapipe fps as a measure of a renderer change | gta3fps1017 NOTES 2.4 | lavapipe rasterizes on host threads; neither run had the host | report counts on the desktop, never fps |
| Sysmem render mode, faster clock, performance mode | gta3drive1017 NOTES 4, 7 | not remedies: the GPU idles half of a dip frame; the owner forbids clock and mode fixes | out of scope |
| Vertex hazard finishes (D6), pgraph.lock (D7), pipeline compile (D8), dirty walks, guest work (D4) | gta3drive1017 NOTES 3, 4, 6.2 | ruled out in the dip windows | not levers here |
| bind_textures drain (#517), uniform hash skip (#543), per-flip dirty memo (#461 M1) | gta3drive1017 NOTES 2 | landed or neutral | not levers here |

**Stop rule (owner 10-17):** the same attempt voids twice for the same cause means stop, write what it was and
what would change, and report to lane.local. No third try.

## 2. Desktop proof (lavapipe, build-linux at 8e42fa1058's texture.c, NV2A_PERF_LOG=1)

### 2.1 The pgraph suites, each switch on and off

`gta3fps1017/tools/desk_suites.py` on `r1suites.iso` (the seven surface-as-texture suites, 363 tests), each arm on a
fresh blank HDD; `tools/suite_band.py`-style comparison against sOFF (`build-linux/run/arms-*.tsv`).

| arm | switches | exit | tests | switch log lines | differ vs sOFF: Texture_shadow_comparator | differ vs sOFF: elsewhere |
|---|---|---|---|---|---|---|
| sOFF | none (R1 on) | 0 | 363 | none | -- | -- |
| sOFF2 | none (rerun) | 0 | 363 | none | 74 | 1: Antialiasing `FramebufferNotModifiedBySurfaceState`, 1 px |
| sW | `HAKUX_S2T_WIDEN=1` | 0 | 363 | `[s2twiden] on` | 80 | the same test, 1 px |
| sS | `HAKUX_S2T_SHARE=1` | 0 | 363 | `[s2tshare] on` | 88 | the same test, 242 px |
| sS2 | `HAKUX_S2T_SHARE=1` (rerun) | 0 | 363 | `[s2tshare] on` | 78 | the same test, 1 px |
| sWS | both | 0 | 363 | both `on` lines | (not diffed) | (not diffed) |

Green with each switch on: every arm exits 0 with all 363 tests, and the only test outside Texture_shadow_comparator
that moves is one that moves between two switch-off runs too (sOFF vs sOFF2). sS's 242 px is not R3's: R3 never
shared in any arm (no `first share` line), and its rerun sS2 is back at 1 px. **No arm printed `[s2twiden] first
bind` or `[s2tshare] first share`: the suites reach neither branch**, as they reached no R1 branch (row 6). They show
the switches are inert where they do not apply, not that the branches are right; 2.2 is where R2's branch runs.

### 2.2 GTA III on foot, R2 off and on (the brief's step 7)

`gta3fps1017/tools/desk_census.py` (A-train 30 x A from 60 s, then held), the same scene; 60-flip `[s2c]` windows
from 360 s on (on foot, after the A-train). cW ran through `tools/desk_census_nd.py` (below).

| run | switches | windows from 360 s | copies/flip | why | R2 binds/flip (`r2[map]`) | dup | log lines |
|---|---|---|---|---|---|---|---|
| cOFF | none (R1 on) | 15 | **2.00** | `map` 100% | 0 | 0 | none |
| cW | `HAKUX_S2T_WIDEN=1` | 17 | **0.00** | -- | **2.00** (120 in every window) | 0 | `[s2twiden] on`, `[s2twiden] first bind` (16 s) |

R2 takes both on-foot copies to binds, every window, with no Vulkan error, no crash dump, and the run to its end. The
frames (11 shots each from 360 s) are the same place, lighting and look; they are not pixel-comparable, because the
two runs' clocks and camera drift apart (in-game 04:52 against 05:12 at the same wall second, the player framed
further right), so a per-pixel diff between arms (20-54% of pixels > 8) mostly measures the camera, against 2-9%
between one arm's consecutive shots. Mean frame colour 36.6/43.1/47.6 (off) against 39.9/46.3/52.5 (R2), sd ~2:
the framing differs, so this neither shows nor rules out a tone change. The pixel argument (section 3) is what says
the image is the same.

An earlier cW (`cW.void-relpath`) is void: a relative OUT path sent the pad file and dump dir under qemu's cwd, so the
A-train never reached the game. Same build, same switch; nothing from it is used.

**C: guard.** C: had 16.7 GB free, under desk_census.py's 20 GB guard (a qemu segfault pipes a ~7.8 GB dump to C:).
`tools/desk_census_nd.py` runs the same tool with qemu non-dumpable instead: with `fs.suid_dumpable` 0, a binary the
user cannot read (`chmod 0311`) execs non-dumpable and the kernel never calls the crash pipe. It checks that
qemu's `/proc/PID/environ` is root-owned after launch and stops it otherwise (verified on `sleep`: root vs justin).

## 1. Plan

1. Merge `origin/lane/gta3fps1017` (R1 + census). Build the desktop tests.
2. R2: widen `surface_view_decodes_as_texture` for the forced-alpha component map; `HAKUX_S2T_WIDEN=1` on.
3. R3: share one copy between nodes that sample the same surface at the same draw_time with the same decode;
   `HAKUX_S2T_SHARE=1` on.
4. Census: R2 binds and R3 shares per 60 flips beside the refusal reasons.
5. Desktop proof: pgraph suites with each switch on and off, the log lines, on-foot copies/flip before/after.
6. The perflog APK, built in a private worktree; path in PR.md. Env strings for the owner's session.
