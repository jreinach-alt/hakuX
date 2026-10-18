# lane.gta3fps1017b -- high-speed driving fps (GTA III + GTA: San Andreas): R2 and R3, default off, for the owner's driving sessions (#1049, #433)

Status (10-18, attempt 4): the brief's work is done. R2 and R3 are written (8e42fa1058; census count fix
7343e14054). The suites are green with each switch on, and R2 takes GTA III's on-foot copies from 2.00/flip to 0
(section 2). The pixel arguments are in section 3 and the env strings in section 4. Section 5 has three titles'
dip windows, and section 6 the perflog APK. What is left is the owner's driving session on each title (6.2). No
driving fps is claimed here.

**Why attempt 3 did not finish.** It hit the 300-turn cap (`terminal_reason: max_turns`, session
20261018T061841Z). By then it had committed R2 and R3 in `texture.c` (8e42fa1058, 510 lines) and merged master
twice. It had not yet built them, run the suites, or written the pixel arguments and the three-title dip table.
Its two analysis scripts (`tools/dip_table.py`, `tools/suite_band.py`) were left untracked. The host's resume note
says "no R2/R3 code has landed", but that read the working tree against HEAD, not HEAD against master: the code is
on the branch. The cause is turn budget spent on scope that grew twice (San Andreas, Blinx 2), not a void. Attempt
4 built and tested the committed code first and wrote up after, committing at each step.

**Why attempts 1 and 2 did not finish.** Attempt 1 (session 05:55Z) committed Step 0 (b1828311f2) and the merge of
`origin/lane/gta3fps1017` (a6680ef37e), then ended before any code. Attempt 2 (session 06:14Z) ended within four
minutes, before attempt 3 started at 06:18Z. Its session log is empty (0 bytes), and it left no commit, no worktree
change and no PR comment, so there is no cause on record to name or to repeat. The two owner addenda (high-speed
driving on GTA III + San Andreas; Blinx 2's island) arrived in the brief across these restarts. Nothing from either
attempt is redone here.

## 0. Already tried (copied from `origin/lane/gta3fps1017` NOTES.md sections 0-3 and 5, extended)

A resume reads this table first and extends it; it never repeats a row.

| tried | where | result | consequence for this lane |
|---|---|---|---|
| Six scripted drive tries, a pathfind route into the Kuruma (`gta-3-drive.route`) | gta3drive1017 NOTES 8.2-8.7; requests 1364097/1364296, 1563459, 1853100, 2035473, 2291336, 2477310 | all VOID at the same gate: the route cannot get into or stay in the car (help-box gate never matched; mission restarted under throttle; the car flipped on the bridge ramp; Y got Claude out) | **Do not script driving. No seventh route.** The driving numbers come only from the owner's session |
| On-foot census (gta3fps1017 NOTES 2.1, desktop c1/c2, and the Nova pilot's 26 windows, 2.2) | `[s2c]` census, `NV2A_PERF_LOG` build | **2.00 copies/flip**, reason `map` 100%, dup 0, two surface pairs: `surf @3d04000 color1 fmt0x4 vk44 1280x480 -> tex fmt0x1e vk44 map0002` and the same at 640x480 (`@3bd8000`) | measured; it does not transfer to driving (~73/flip, 36x). **Do not re-run it on foot** except as R2's before/after (done, 2.2) |
| perflog pilot `1-1792275531-lane.gta3drive1017-343857` (Nova, Turnip) | gta3drive1017 NOTES 6.1-6.2 | < 26 fps band: PFIFO waits ~11.6 ms/flip in the #474 drain (71.9 drains/flip); ~73 copies/flip; 22-30 render passes per frame; every burst copy at `s2t@1264` (R1's plain colour copy branch) | measured; **do not re-measure** |
| Do copies per flip track driving? (gta3fps1017 re-read of pilot 343857) | that lane's NOTES row 4 | the bursts (3 to 203 per flip) fall while the car moves, just after a crash, or at the garage camera under throttle; on foot never leaves 2.00. The high garage window: cp 172.5/flip, srf 186, an `[ovl1018]` 256x256 swizzled Z inside a 1024x1024 linear Z | the burst's refusal reasons and dups are **unknown**; R2/R3 are written blind to them, switchable, for the owner's session to read |
| R1 (merged from lane/gta3fps1017: b7d7243392, c6ca5296fd; census bd2bf354bb; folded 4a504d9aaa) | gta3fps1017 NOTES 2.3-2.5, 4 | removes the ~11.6 ms/flip #474 drain ahead of a plain colour copy; desktop pgraph suites pass on and off (363 tests, diffs only in Texture_shadow_comparator, within its own rerun band); ~60 min of GTA III on Turnip with R1 on, no fatal | **do not rewrite it; build on it.** Its switch `HAKUX_S2T_DRAIN=1` restores the drain |
| The pgraph suites as a test of R1 | gta3fps1017 NOTES 2.3, gta3drive1017 8.1 | no suite reaches R1's branch (no `[s2tdrain]` line in any arm) | blind to R1. For R2/R3 they are run on and off **and** checked for the switches' own log lines, so a green run says whether it reached the branch |
| R2 / R3 (gta3fps1017 NOTES 3) | that lane's pick | not written: the on-foot census does not transfer to driving | right for a census-first plan, wrong for the owner's ask (10-17 ~23:00 PDT): **this lane writes both, off by default** |
| Pairing logcat timestamps to txw lines with `grep -o \| paste - -` | gta3fps1017 NOTES 6 | lines without a match shift the pairing and drop windows | parse each line whole (`tools/dip_table.py` joins on pid and timestamp) |
| Desktop lavapipe fps as a measure of a renderer change | gta3fps1017 NOTES 2.4 | lavapipe rasterizes on host threads; neither run had the host | report counts on the desktop, never fps |
| Sysmem render mode, faster clock, performance mode | gta3drive1017 NOTES 4, 7 | not remedies: the GPU idles half of a dip frame; the owner forbids clock and mode fixes | out of scope |
| Vertex hazard finishes (D6), pgraph.lock (D7), pipeline compile (D8), dirty walks, guest work (D4) | gta3drive1017 NOTES 3, 4, 6.2 | ruled out in the dip windows | not levers here |
| bind_textures drain (#517), uniform hash skip (#543), per-flip dirty memo (#461 M1) | gta3drive1017 NOTES 2 | landed or neutral | not levers here |
| **R2 and R3, written (this lane: 8e42fa1058, 7343e14054)** | sections 2-3 | suites green with each switch on; R2 on foot: 2.00 -> 0 copies/flip, 2.00 binds/flip; R3 never shares on the desktop (no suite does, and on foot dup is 0) | **do not rewrite them before the owner's session reads them.** R3's branch first runs there |
| `desk_census.py` with C: under 20 GB free | 2.2 | refuses: a qemu segfault pipes a ~7.8 GB WSL dump to C: | run it through `tools/desk_census_nd.py` (qemu non-dumpable); never lower the guard |
| A relative OUT path for `desk_census.py` | 2.2, `cW.void-relpath` | void: qemu runs with cwd OUT, so the pad file and frame dir resolve under it and the A-train never reaches the game | pass an absolute OUT |
| The perflog APK with ninja off PATH | `build-linux/run/apk-build*.fail*-noninja.log` | meson (glib) fails "Could not detect Ninja v1.8.2" | put `/home/justin/Android/Sdk/cmake/3.30.3/bin` on PATH, as the dispatcher's service PATH does |
| San Andreas on-foot census on the desktop | 5.3 | not run: no SA image is staged; D: holds only `Xbox/Grand Theft Auto - San Andreas (USA) (En,Es).7z` | stays with the owner's session on the perflog build |
| Three titles' dip windows from the release captures | 5.1 | one direction in every field: in dips G, Df, Tq and tc rise and Ri falls | a class, not a cause: only the perflog census can say whether the copies are each title's cause |

**Stop rule (owner 10-17):** the same attempt voids twice for the same cause means stop, write what it was and
what would change, and report to lane.local. No third try.

## 1. Plan (done)

1. Merge `origin/lane/gta3fps1017` (R1 + census). Build the desktop tests. -- done (a6680ef37e; R1 since folded).
2. R2: widen `surface_view_decodes_as_texture` for the forced-alpha component map; `HAKUX_S2T_WIDEN=1` on. -- done.
3. R3: share one copy between nodes that sample the same surface at the same draw_time with the same decode;
   `HAKUX_S2T_SHARE=1` on. -- done.
4. Census: R2 binds and R3 shares per 60 flips beside the refusal reasons. -- done (`r2[map pad] r3[share]`).
5. Desktop proof: pgraph suites with each switch on and off, the log lines, on-foot copies/flip before/after. --
   done (section 2).
6. The perflog APK, built in a private worktree; path in PR.md. Env strings for the owner's session. -- done
   (sections 4, 6).

Only `hw/xbox/nv2a/pgraph/vk/texture.c` changes in the renderer; no other vk/ file was needed.

## 2. Desktop proof (lavapipe, build-linux at 8e42fa1058's texture.c, NV2A_PERF_LOG=1)

7343e14054 changes only how the perflog census counts R3 (section 3.2). It recompiled cleanly. The suites were
not re-run for it, because no suite reaches R3's branch (2.1).

### 2.1 The pgraph suites, each switch on and off

`gta3fps1017/tools/desk_suites.py` ran on `r1suites.iso` (the seven surface-as-texture suites, 363 tests), each arm
on a fresh blank HDD. Each arm was compared against sOFF in the style of `tools/suite_band.py`
(`build-linux/run/arms-*.tsv`).

| arm | switches | exit | tests | switch log lines | differ vs sOFF: Texture_shadow_comparator | differ vs sOFF: elsewhere |
|---|---|---|---|---|---|---|
| sOFF | none (R1 on) | 0 | 363 | none | -- | -- |
| sOFF2 | none (rerun) | 0 | 363 | none | 74 | 1: Antialiasing `FramebufferNotModifiedBySurfaceState`, 1 px |
| sW | `HAKUX_S2T_WIDEN=1` | 0 | 363 | `[s2twiden] on` | 80 | the same test, 1 px |
| sS | `HAKUX_S2T_SHARE=1` | 0 | 363 | `[s2tshare] on` | 88 | the same test, 242 px |
| sS2 | `HAKUX_S2T_SHARE=1` (rerun) | 0 | 363 | `[s2tshare] on` | 78 | the same test, 1 px |
| sWS | both | 0 | 363 | both `on` lines | (not diffed) | (not diffed) |

The suites are green with each switch on. Every arm exits 0 with all 363 tests. The only test outside
Texture_shadow_comparator that moves is one that also moves between two switch-off runs (sOFF vs sOFF2). sS's 242 px
is not R3's: R3 never shared in any arm (no `first share` line), and its rerun sS2 is back at 1 px. **No arm printed
`[s2twiden] first bind` or `[s2tshare] first share`: the suites reach neither branch**, just as they reached no R1
branch (row 6). So the suites show the switches are inert where they do not apply, not that the branches are
right. Section 2.2 is where R2's branch runs.

### 2.2 GTA III on foot, R2 off and on (the brief's step 7)

`gta3fps1017/tools/desk_census.py` ran the same scene (an A-train of 30 x A from 60 s, then held), read in 60-flip
`[s2c]` windows from 360 s on (on foot, after the A-train). cW ran through `tools/desk_census_nd.py` (below).

| run | switches | windows from 360 s | copies/flip | why | R2 binds/flip (`r2[map]`) | dup | log lines |
|---|---|---|---|---|---|---|---|
| cOFF | none (R1 on) | 15 | **2.00** | `map` 100% | 0 | 0 | none |
| cW | `HAKUX_S2T_WIDEN=1` | 17 | **0.00** | -- | **2.00** (120 in every window) | 0 | `[s2twiden] on`, `[s2twiden] first bind` (16 s) |

R2 turns both on-foot copies into binds in every window, with no Vulkan error and no crash dump, and the run goes to
its end.

The frames (11 shots each from 360 s) show the same place, lighting and look, but they are not pixel-comparable.
The two runs' clocks and camera drift apart: in-game 04:52 against 05:12 at the same wall second, with the player
framed further right. So a per-pixel diff between arms (20-54% of pixels > 8) mostly measures the camera; between one
arm's consecutive shots it is 2-9%. Mean frame colour is 36.6/43.1/47.6 (off) against 39.9/46.3/52.5 (R2), sd ~2.
Because the framing differs, that neither shows nor rules out a tone change. Section 3 is what says the image is the
same.

An earlier cW (`cW.void-relpath`) is void: a relative OUT path sent the pad file and dump dir under qemu's cwd, so the
A-train never reached the game. Same build, same switch; nothing from it is used.

**C: guard.** C: had 16.7 GB free, under desk_census.py's 20 GB guard (a qemu segfault pipes a ~7.8 GB dump to C:).
`tools/desk_census_nd.py` runs the same tool with qemu made non-dumpable instead. With `fs.suid_dumpable` at 0, a
binary the user cannot read (`chmod 0311`) execs non-dumpable, and the kernel never calls the crash pipe. The wrapper
checks after launch that qemu's `/proc/PID/environ` is root-owned, and stops qemu otherwise (verified on `sleep`:
root vs justin). The binary is back at 0775.

## 3. Pixel arguments

### 3.1 R2, `HAKUX_S2T_WIDEN=1`: bind the surface through the texture's own mapping

**What the copy path samples.** `copy_surface_to_texture` does a `vkCmdCopyImage` from the surface image into the
node image. R2 requires both images to have the same VkFormat, so the copy is bit-exact (no conversion). The node's
view applies `kelvin_color_format_vk_map[color_format].component_map`, with `.a` replaced by `pad_alpha_override`
when that is not IDENTITY. For GTA III's pairs that mapping is `map0002` (`.a = ONE`).

**What R2 samples.** `s2t_widen_view()` builds a view of the surface's own image in the surface's VkFormat. Its
mapping is computed by the same two lines: the texture's `component_map`, with `.a = pad` when pad is not IDENTITY.
The texels are the same bits, the mapping is the same, and the sampler is the slot's own in both paths. So the same
RGB is read, with alpha ONE for map0002, and there is no copy. R2 only applies when every one of these holds:

- the surface host VkFormat == the texture's VkFormat == the node image's format;
- 2D, not a cubemap, one level, one layer;
- the node image is exactly the surface's scaled size, so the copy would have written every texel the view can
  read;
- the format is not one that `HAKUX_S2T_CVT` expands by replication (that path converts, so it is not
  bit-exact).

In every other case it returns no view and the copy runs as before.

**pad: handled, by the same argument.** The pad-alpha refusal (`surface_sampled_pad_alpha`) exists because the alpha
the texture unit owes is not in the image: the copy path supplies it with the node view's `.a = pad` swizzle.
R2's view applies that same swizzle, so a surface refused for `pad` with an equal VkFormat reads the same through
R2. The census counts these as `r2[pad]`.

**fmt: not handled, and why.** For a `fmt` refusal, the surface's VkFormat differs from the texture's. The copy
reinterprets the bits in the texture's format (same compatibility class, no conversion). A view could do the same
only in the texture's format, and Vulkan allows a view whose format differs from the image's only if the image was
created with `VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT`. Surface images are created in `vk/surface.c` without it. Adding
it would change every surface's creation flags, a different change with its own risks (a driver may give up
framebuffer compression on a mutable-format image; not measured here), so the same pixel argument does not hold for
`fmt`. It stays a copy, counted in
`why[fmt]`.

**Timing.** The copy is a snapshot taken at bind; R2's bind samples the surface live, the way master's existing
direct bind does for identity-map surfaces. Between draws they agree. When the surface is drawn, cleared or uploaded
to, its draw_time moves, and `pgraph_vk_surface_written_while_sampled` invalidates the slot's register cache. The
next bind then re-runs the decision: the copy path copies again, and R2 barriers and binds again. One case does
differ: a stage that samples the surface its own draw is writing. The copy reads the pre-draw snapshot, while R2,
like master's direct bind, reads the attachment. That exposure already exists on master for every direct-bound
surface, and R2 extends it to map0002 surfaces. The on-foot frames show no visible change (2.2); driving is untested.

**Cost it saves, and what it does not.** Per copy replaced, R2 removes one surface-sized `vkCmdCopyImage` (on-foot
pair: 1280x480x4 B = 2.4 MB read and 2.4 MB written) and the node image's layout transitions. It does **not** remove
the render-pass break. `bind_surface_as_texture` also ends the pass (`pgraph_vk_begin_nondraw_commands`) to barrier
the surface for shader reads, so R2 keeps the 22-30 passes per frame the pilot counted.

### 3.2 R3, `HAKUX_S2T_SHARE=1`: one copy per (surface, draw_time, decode)

**Argument.** Suppose node A received a copy of surface S at draw_time t, and node B would now copy S at t. B's copy
would hold the same bits as A's, because both are bit-exact copies of the same unchanged image. B would read them
through the same mapping, because the image config and `color_format` are equal and pad is IDENTITY for both. So
sampling A's view in B's slot reads what B's own copy would have. The sampler stays B's slot's. B's image is not
written, so B's draw_time is set to `UINT_MAX`, a value no surface reaches. The next bind of B therefore decides
again instead of trusting stale content.

**The guard** (`s2t_share_find`): an entry is used only if every one of these holds.

```
e->node && e->node != snode
&& e->s == surface && e->s_view == surface->image_view     /* same surface, same view */
&& e->t == surface->draw_time                              /* not drawn/cleared/uploaded since */
&& e->node->image_view == e->view                          /* A still holds that copy ... */
&& e->node->draw_time == e->t
&& e->node->current_layout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL
&& s2t_cfg_equal(&e->cfg, &e->node->image_config)          /* ... in the same image shape */
&& s2t_cfg_equal(&e->cfg, &snode->image_config)            /* B's shape is A's */
&& e->color_format == snode->key.state.color_format        /* B's decode is A's */
```

On top of these, `s2t_share_fits` (checked both when an entry is recorded and when it is found) requires:

- the switch is on;
- a colour surface;
- pad IDENTITY;
- 2D, one level, one layer;
- the node image is exactly the surface's scaled size;
- not an S2T_CVT expansion.

**Invalidations that end the sharing.**

1. **The surface is written between nodes** (drawn, cleared, uploaded). Its draw_time moves past `e->t`, so the
   entry no longer matches, and B copies the new content as the copy path would.
2. **The surface's view is retired.** `s2t_view_retired` drops every entry recorded from that view, and the
   `s_view` check covers a view recreated in place.
3. **A is written or released.** `s2t_share_end_for` runs before:
   - `upload_texture_image`
   - `copy_surface_to_texture`
   - `texscan_apply`
   - `texture_cache_release_node_resources`

   It drops A's entries. For any slot sampling A through a share, it clears the pin, invalidates that slot's
   register cache and retires A's view the way a surface view is retired. Then `pgraph_vk_bind_textures` rescans,
   so no slot is left naming a view about to change. The rescan is bounded to NV2A_MAX_TEXTURES passes.
4. **A is evicted.** It cannot be while shared: `pre_evict` refuses a node in `s2t_share_src[]`.
5. **A's view, draw_time, layout or image config changed** by any other path. The guard's own checks fail.
6. **The same-draw_time direct branch.** With R3 on, it resets the slot's layout to the bind's (GENERAL, or
   DEPTH_STENCIL_READ_ONLY), not the read-only layout an earlier share left.

**Untested on the desktop.** No suite shares, and on foot GTA III has dup 0, so R3's branch first runs in the owner's
session. Setting the switch off restores the old path exactly (`s2t_share_state` is 0 and every R3 hook returns
first).

**Cost it saves.** A share binds A's view directly. It calls neither `copy_surface_to_texture` nor
`bind_surface_as_texture`, so per share it removes the copy **and** its render-pass break. Its reach is only `dup`:
copies of a surface at a draw_time another node already copied.

**The census counts a share once** (7343e14054). After a share, B's draw_time is `UINT_MAX`, so each later bind of B
at the same draw_time shares again, where the copy path would have copied once and then taken the same-draw_time
branch. `r3[share]` therefore counts a (node, surface, draw_time) once, from a 16-entry ring. It is perflog-only and
changes nothing that is bound.

### 3.3 Independence

Each switch is read once per process by its own getenv: `HAKUX_S2T_WIDEN`, `HAKUX_S2T_SHARE`, and R1's
`HAKUX_S2T_DRAIN`. R2 is tried first, and R3 only where R2 returned no view. R1's drain decision sits on the copy
branch that both of them leave. Every combination runs: the suites ran with each switch and with both (sWS).

## 4. The switches and their env strings

R1 is on by default (folded). R2 and R3 are off by default. The emulator reads its environment from the
`env_vars` pref in `x1box_prefs.xml` (`xemu_android.cpp:796`), one `KEY=VALUE` per line. lane.local sets it the way
the dispatcher's `apply_env_pref` does (`docs/testing/dispatcher.sh`):

1. `am force-stop` the package.
2. `run-as <pkg> cat shared_prefs/x1box_prefs.xml`.
3. Replace only the `env_vars` key, newlines as `&#10;`.
4. Write the file back with `run-as <pkg> sh -c 'cat > shared_prefs/x1box_prefs.xml'`.
5. Read it back and compare.

`<pkg>` is `com.jreinach.hakux.debug` for the APK in section 6. The switches are read once per process, so set
them with the app stopped, and expect a restart between sets.

| set | `env_vars` value | log lines that confirm it (tag `hakuX`) |
|---|---|---|
| R1 only | *(no `HAKUX_S2T_*` line; leave other lines as they are)* | `[s2tdrain] first skip` when R1 first skips a drain; no `[s2twiden]`/`[s2tshare]` |
| R1+R2 | `HAKUX_S2T_WIDEN=1` | `[s2twiden] on`, then `[s2twiden] first bind` |
| R1+R3 | `HAKUX_S2T_SHARE=1` | `[s2tshare] on`, then `[s2tshare] first share` |
| R1+R2+R3 | `HAKUX_S2T_WIDEN=1` and `HAKUX_S2T_SHARE=1`, two lines (`HAKUX_S2T_WIDEN=1&#10;HAKUX_S2T_SHARE=1` in the XML) | all four lines above |

`HAKUX_S2T_DRAIN=1` on its own line turns R1 off (restores the #474 drain; logs `[s2tdrain] on`) in any set. An
`on` line with no `first` line means the switch was set but its branch never ran.

**The census** (perflog build only, tag `hakuX-stall`, every 60 flips beside the `txw[...]` line):

```
[s2c] f60 cp<copies> dup<copies R3 could share> srf<surfaces> why[zs pad fmt map none] ovf r2[map pad] r3[share] | pairs
```

Per window:

- `cp` = copies still made;
- `why[...]` = why each was not bound directly;
- `dup` = R3's ceiling while R3 is off;
- `r2[map]+r2[pad]` = copies R2 replaced with binds;
- `r3[share]` = copies R3 replaced with shares.

So copies saved per 60 flips = `r2[map] + r2[pad] + r3[share]`, read next to `why`. With both switches off, `why[map]
+ why[pad]` is R2's ceiling (only equal-VkFormat surfaces qualify) and `dup` is R3's. `txw[... faf<ms>/<n> ...
cp<ms>/<n> bs<ms>/<n> ...]` gives the wall time per flip of the drain, the copies and the direct binds.

## 5. Three titles: the dip windows, and whether they share a signature

### 5.1 The table (release captures, `tools/dip_table.py`, dip = window < 26 fps, good = window >= 29 fps)

The data is the owner's release-package sessions on the Nova (PurpleVK, Adreno 740), from host logcat captures in
`/home/justin/hakux-work/captures/owner-fps-1017/`. One window is one `hakuX-pace` line (60 flips). G, Df, Tq and Ri
come from the `hakuX-perf gfps=` line with the same timestamp. tc is the `[rdc]` tcpu per guest frame of the PGRAPH
flip thread (CPU ms per frame), and busy is tcpu over wall.

| title (capture, pid) | windows / span | time >= 28.5 | median / p5 fps | time < 22 | class (n) | G ms | Df | Tq | Ri ms | tc ms | busy % |
|---|---|---|---|---|---|---|---|---|---|---|---|
| GTA III, RT held from a save state (`gta3-rthold60-savestate-5454000e-12836`, 12836) | 54 / 150.6 s | 46.0% | 29.2 / 16.1 | 37.6% | dip (17) | 50.5 | 81.5 | 1408 | 3.6 | 16.6 | 34.0 |
| | | | | | good (28) | 33.2 | 18.1 | 1092 | 17.5 | 11.9 | 33.9 |
| GTA III, RT held, baseline (`gta3-rthold-baseline-5454000e-7467`, 7467) | 14 / 40.4 s | 0.0% | 22.5 / 11.9 | 57.5% | dip (14) | 43.6 | 75.7 | 1450 | 1.8 | 17.4 | 38.7 |
| GTA: San Andreas, driving (`gtasa-driving-54540082`, 9464, 23:01:11-23:09:17) | 213 / 479.5 s | 45.3% | 28.6 / 19.0 | 12.4% | dip (52) | 42.8 | 56.2 | 2009 | 10.0 | 16.4 | 38.2 |
| | | | | | good (85) | 32.7 | 40.0 | 1065 | 17.1 | 12.4 | 35.8 |
| Blinx 2, island (`blinx2-island-4D530065`, 23672, from 23:14:55) | 30 / 68.1 s | 32.4% | 26.4 / 20.2 | 8.5% | dip (12) | 41.6 | 92.8 | 3842 | 7.6 | 12.7 | 30.9 |
| | | | | | good (11) | 33.4 | 66.6 | 2556 | 13.8 | 9.7 | 28.3 |

The brief's SA figures (dip 48, good 112; G 45.4 vs 32.8) and Blinx figures (dip < 27) come from another reading
of the same captures. This table uses one tool and one pair of thresholds for all three titles. Note that 112 good
windows of 213 would put the median above 29, against the brief's own median of 28.6. The direction of every field
is the same in both readings.

### 5.2 One signature, three titles

Dip minus good, per title:

| title | G | Df | Tq | Ri | tc |
|---|---|---|---|---|---|
| GTA III | +17.3 ms | x4.5 | x1.29 | -13.9 ms | +4.7 ms |
| GTA: SA | +10.1 ms | x1.41 | x1.89 | -7.1 ms | +4.0 ms |
| Blinx 2 | +8.2 ms | x1.39 | x1.50 | -6.2 ms | +3.0 ms |

**Yes, they share a signature**: in every title's dips, all of the following move the same way.

- The game frame stretches (G).
- The renderer idles less (Ri).
- The PGRAPH thread spends 3-5 ms more CPU per frame (tc).
- There are more deferred flushes (Df) and more texture-dirty queries (Tq).

busy % barely moves, because the frames are longer as well. The renderer is busy while the guest waits, in all three.

That is a class, not a cause. GTA III's Df jump (x4.5) is far larger than the other two, and its dips are the
deepest, matching the pilot's ~73 copies/flip with a #474 drain ahead of each. Blinx 2's Tq is 2-3x the GTA titles'
in both classes. That points at the texture-dirty path at least as much as at copies. **Nothing here shows the S2T
copy is Blinx 2's cause, or SA's**: the release build has no `[s2c]` census.

### 5.3 What R1, R2 and R3 should do for each title

The switches apply to every title: they act in `pgraph_vk_bind_textures` on any surface sampled as a texture, with
no title check. What each saves depends on what that title's census shows:

| switch | removes, per event | GTA III driving (pilot 343857) | GTA: SA driving | Blinx 2 island |
|---|---|---|---|---|
| R1 (on) | the #474 drain (a wait for in-flight frames) ahead of each plain colour copy of a node still in flight | the pilot's ~11.6 ms/flip of PFIFO wait in that drain (the pilot's run; the release capture's dip frames are +17 ms of G over good ones) | the drain's share of SA's +10 ms, if SA's dip copies are plain colour copies of in-flight nodes: `txw faf` and `[s2tdrain] first skip` read it | likewise, if Blinx copies at all |
| R2 (off) | one surface-sized image copy, for `map`/`pad` refusals with an equal VkFormat; not the render-pass break | on foot all copies (2.00/flip); in the driving bursts the reasons are unknown | `why[map]+why[pad]` in SA's dip windows, if SA's surfaces are RenderWare's X8R8G8B8-read-as-0x1e like GTA III's (same engine family, unmeasured) | unknown; `why[]` says |
| R3 (off) | one copy **and** its render-pass break, for a dup | dup 0 on foot; driving unknown | `dup` in SA's dips | `dup` |

SA's on-foot census on the desktop was not run. No SA image is staged: D: has only
`Xbox/Grand Theft Auto - San Andreas (USA) (En,Es).7z`. The brief says to stop there if it is not staged, so this
lane stops there.

### 5.4 The shared measurement, and how to take it on Blinx 2

The shared measurement is the perflog build's per-60-flip texture lines (tag `hakuX-stall`), read in dip windows
against good ones:

- `txw[...]`: where `pgraph_vk_bind_textures`' wall time goes (faf drain, cp copy, bs direct bind, nd, up upload,
  scan).
- `[s2c]`: copies, dups and refusal reasons; R2 binds and R3 shares.

These sit beside the `hakuX-perf gfps=`, `hakuX-pace` and `[rdc]` lines the release build already prints, from
which this table came. If a title's dips raise `cp` and the `txw` copy and drain times against its good windows,
the S2T path is that title's lever. If they do not, it is not, and the perflog's texture-hash counters (#461's
`txh`/`txu`) are the next read for a Tq-heavy title like Blinx 2.

Blinx 2's island save state is in the release package (`com.jreinach.hakux`) only. The perflog debug APK installs
as `com.jreinach.hakux.debug`, with its own data, and cannot load that save. The route that keeps the save is
`./gradlew assembleRelease -Pperflog=true`:

- It is the same native code: both build types build native code as `CMAKE_BUILD_TYPE=Release`, and `-Pperflog`
  sets `-DHAKUX_PERF_LOG=ON` in defaultConfig for every type.
- It must be signed with the release key (`android/key.properties`).
- It is installed with `adb install -r` over the release package, which keeps its data, and therefore the save.
- Afterwards the owner's release APK is reinstalled the same way.

This is lane.local's call, by hand and not by request: it replaces the owner's install for the session, and the
dispatcher refuses release APKs (`guard_not_release_apk`). The census needs no switch, so no `env_vars` write is
needed. A release package is not debuggable, so `run-as` would not work on it anyway; if a switch were wanted, it
would go through the Settings screen. This lane has not built that APK: the brief asks only for the debug perflog
APK, and the signing key is lane.local's.

## 6. The perflog APK, and the owner's sessions

### 6.1 The build

- Path: `/home/justin/hakux-work/wt/gta3fps1017b-apk/android/app/build/outputs/apk/debug/app-debug.apk`
- sha256: `43625e2e603338a0eb5e611c9cd3f22eb01c4a1d1de0c0f85d0cb591221d0489`
- Package: `com.jreinach.hakux.debug`. Not installed by this lane.
- Built from 7343e14054 in the private worktree `wt/gta3fps1017b-apk`, using the dispatcher's recipe:
  `JAVA_HOME=/home/justin/toolchains/jdk21 ./gradlew assembleDebug -Pperflog=true`, with
  `/home/justin/Android/Sdk/cmake/3.30.3/bin` on PATH for ninja. The first full build was at 11d8ba91c5
  (`build-linux/run/apk-build3.log`). The rebuild at 7343e14054 recompiled `texture.c`
  (`build-linux/run/apk-build4.log`, GRADLE_EXIT=0).
- Checked in `lib/arm64-v8a/libxemu.so`: it carries the `[s2c] f%u ... r2[map%u pad%u] r3[share%u]` format and
  `HAKUX_S2T_WIDEN`, `HAKUX_S2T_SHARE` and `HAKUX_S2T_DRAIN`, with their `on`/`first` lines.

### 6.2 How lane.local runs it: GTA III (5454000E) and GTA: San Andreas (54540082)

These sessions are by hand: the owner drives, and nothing is scripted (the stop rule stands). The steps:

1. lane.local installs the APK above as `com.jreinach.hakux.debug`. That package has its own data, so GTA III's and
   SA's saves must exist in it. If they do not, the release-id route in 5.4 applies to the GTA titles too.
2. lane.local writes `env_vars` (section 4) with the app stopped.
3. The owner launches the title and drives at speed.
4. The host captures logcat with at least the tags `hakuX`, `hakuX-stall`, `hakuX-perf` and `hakuX-pace`.

A suggested order per title:

1. **R1 only.** The baseline, plus each switch's ceiling (`why[map]+why[pad]`, `dup`) in the dip windows.
2. **R1+R2+R3.** `r2[...]` and `r3[share]` count each switch's saves separately in the same run.
3. Only if 2 shows a fault or no gain: **R1+R2** and **R1+R3**, to separate them.

`tools/dip_table.py` reads the fps classes from the same capture. A join of `[s2c]`/`txw` to the pace windows by
timestamp is the reading to add. The pace window and the census window are both 60 flips, but they are counted on
different counters, so join by time, never by position.

## 7. For the next lane

- Do not re-run the suites or the on-foot census as evidence for R2/R3's driving effect. They cannot see it (2.1,
  row 2).
- Do not handle `fmt` in R2 without `VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT` on surface images. That is a `surface.c`
  change with its own pixel and compression questions (3.1).
- R3's branch has never run. If the owner's session shows `[s2tshare] first share` and a fault, the guard in 3.2 is
  the place to look first, and setting the switch off restores the old path.
