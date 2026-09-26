# lane.turnipfork NOTES

Brief: `/home/justin/hakux-work/briefs/turnipfork.md` (issue #68). PR #318.
Base: master @ a7f7c8bda943704323510597f8a6122356d77c6a.
Mesa: `~/hakux-work/mesa-turnipfork`, pinned `4c18636110f0ef2e1d4cecdbfbf4b7126c1d22cc`
(main, 26.3.0-devel, the series T30 is built from).

## Gate 0: done, posted on #68 (2026-09-25)

Report: `docs/investigations/adreno-driver-feasibility.md`. Comment:
https://github.com/jreinach-alt/hakuX/issues/68#issuecomment-5839696041

The headline: nothing needs root to try, and no candidate has a measured gain
that only our own driver can deliver. What was measured, and how:

- **Driver CPU share (e): measured, with no new device run.** The 09-11
  Crimson Skies `perf.data` (`~/hakux-work/perf/perf.data`) was recorded with
  T30 installed. T30 ships unstripped, and its build-id
  (`dd183c11...`) matches the recorded mapping, so the NDK's host simpleperf
  symbolizes it. Turnip is 7.2% inclusive of the pfifo thread; our
  `fast_hash` and `tlb_reset_dirty` are 22% each.
  `tools/turnip/driver_share.py` reproduces the split and refuses a
  mismatched build-id.
- **Compile (d):** 3 of 11,129 pfifo samples are in ir3/NIR. Steady play does
  not compile. Stutter itself needs a cold-cache trace; not measured.
- **Clip (a):** Turnip itself writes `GRAS_CL_CNTL` from userspace, including
  `clip_disable` / `vp_xform_disable` / `persp_division_disable`, in its 3D
  blit path. So the register is writable. But Adreno's own clipper already
  matches NV2A except at |w| ratio >= 2^120 (geom.c:87-95), which PR #250
  fixed at T0. The ceiling is near zero.

**Do not repeat:**
- Do not search `docs/testing/perf/` for the 09-11 reports; they were never
  committed. The raw capture is on the host.
- Do not assume the dispatcher can install a driver. It cannot:
  `request.sh` has no driver field, and `swap_driver.sh` is raw adb.
- `--runs N` on a `--title` soak is refused. Queue N requests.

## Gate 1

### No-build A/Bs on stock T30 (queued 2026-09-25, Nova, ref a7f7c8bda9)

Both use `request.sh --env`. The app `setenv`s `env_vars` at `SDL_main`
start (`xemu_android.cpp:1239`), before adrenotools loads the driver
(`:1784`). Mesa reads driconf overrides and `TU_DEBUG` through `getenv`
first (`util/os_misc.c:238`).

| id | what | variable |
|---|---|---|
| 1790370789-turnipfork-3702404 | (g) texture suites, 12 | none (base) |
| 1790370791-turnipfork-3706030 | (g) texture suites, 12 | `tu_use_tex_coord_round_nearest_even_mode=true` |
| 1790370813-turnipfork-3734492 / -3734624 | (f) Crimson Skies 240 s | autotune (default) |
| 1790370813-turnipfork-3734531 / -3734656 | (f) Crimson Skies 240 s | `TU_DEBUG=sysmem` |
| 1790370813-turnipfork-3734588 / -3734707 | (f) Crimson Skies 240 s | `TU_DEBUG=gmem` |

**Limit of these, stated before the results:** a null result cannot by itself
tell "no effect" from "the env never reached the driver". The source path is
proven above, and the app logs `env: K=V` under its own tag. But T30 is a
packager fork, and nothing in the capture shows its driconf read. If (g) is
flat, the control for that is our own build with the option forced on at
compile time.

### Reproducible build

`tools/turnip/build.sh`: pinned Mesa sha, NDK 29.0.14206865, API 30, meson
1.9.1, mako 1.3.10, glslang 15.4.0 (built on the host; the NDK has only
glslc). KGSL only, `android-strict=false` (T30 exposes Vulkan 1.4 at minApi
30, which strict mode would cap), unstripped. Patches go in
`tools/turnip/patches/*.patch`; the control has none.

**It builds (attempt 2).** Output: `turnip_hakux_4c18636110f0_none.adpkg.zip`. It
took two fixes, both flags and not patches:
- bison needs `M4`, and the nxdk bundle's m4 is not on its bin PATH.
- The pinned `tu_cs.h:295` braces a `size_t` into a `uint16_t`, which NDK
  clang++ rejects (`-Wc++11-narrowing`), so the build passes
  `-Dcpp_args=-Wno-c++11-narrowing`. Upstream builds with gcc and does not hit it.

`tools/turnip/compare_pkg.sh` checks the package against T30 statically:
- Same so far: AArch64 DYN, the same eight NEEDED libraries, and an exported
  `HMI` (Android's Vulkan HAL entry).
- Size: 17.7 MB against 18.9 MB.
- One shape difference: the soname. Ours is `libvulkan_freedreno.so`; T30's is
  `vulkan.purple.so`. Setting it with `-Dc_link_args`/`-Dcpp_link_args` dropped the
  android stub libraries from the link, so it was reverted. **Hypothesis,
  unmeasured:** it does not matter, because adrenotools opens the file by path
  from `libraryName`. The first device load will tell.

**Not bit-reproducible yet.** Two `--clean` builds from the same script and
inputs gave `vulkan.hakux.so` sha256 `df0479cb…` (17,666,808 bytes) and
`f94a1acc…` (17,667,200 bytes). The variance source is unmeasured: build-id,
embedded timestamps or the meson-generated version header are the suspects.
Pin by the package sha, not by rebuilding.

**Do not repeat:** do not grep for `vk_icd*` to check a package. Android builds
export `HMI`, not the desktop loader's entry points.

### Why attempt 1 did not finish (written on the attempt 2 resume)

Attempt 1 ended mid-build with three loose ends. First, the first `meson
setup` failed at `meson.build:747` because `glslangValidator` was not found.
Second, `build.sh` was then extended to build glslang 15.4.0, but that edit was
never committed or run. Third, the last NOTES commit (7328894a0a) was never
pushed, and the driver-swap question it describes as "Asked on #68" was never
posted. Nobody acted on the draft PR in the meantime. Attempt 2 ran the build,
committed the script, and posted the question as a `blocked:` comment.

The control against T30 needs our package installed on a device. That is a
driver swap, which a lane cannot do (see "Do not repeat"). Asked on #68.

### Why the attempt 2 session did not finish (written on the 09-26 resume)

It ended correctly, as a wait. The control needed a driver swap that no lane
could make, and the `blocked:` comment said so. PR #318 was then marked ready,
and it folded at 00:15Z with the Gate 0 report and the build. The host
answered the blocker at 04:23Z, which was after the session had ended:
- It ran the control through `host-tools/turnip_control.sh`.
- It opened a `[lane.turnipfork] driver-run:` channel on #68.

One loose end in the worktree: `build.sh` and `compare_pkg.sh` had lost
their exec bits, uncommitted, for an unknown reason. The resume restored them
from HEAD. This session is on a new branch head and a new PR, because #318 is
merged.

## Gate 1 step 2: ended with no prototype (2026-09-26)

The numbers are in the report's "Gate 1 results" section.

- **Control:** passed, 220 of 220 identical to T30 (host run
  `0-0-0-turnipctl-ours-1790395957`).
- **(g)** Device-wide RNE is worse: 21 rows better, 127 worse, and
  +17,994 differing pixels. Only 3D textures prefer it. A 3D-only policy
  is worth at most 8,140 of 1,408,643 pixels. `TPL1_MODE_CNTL` is a
  per-device static register (`tu6_init_static_regs`), so that policy needs
  a patch, and it does not pay for a bundled driver plus a fallback.
- **(f)** Flat. autotune, sysmem and gmem all give a median of 29 gfps with
  a 33.3 ms guest frame, 2 replicates each. Crimson hands-off is at its
  30 Hz cap, so this can only show a cost, and there is none.
- Therefore **no T1 prototype, no prediction, and no driver-run.** The
  brief's exit clause applies: Gate 0 bounds the driver at 7.2% of the
  renderer thread (about 2 ms per frame), and the two measured surveys gave
  nothing a driver alone can deliver.

**Do not repeat:**
- Do not re-run (g) device-wide. Its sign is settled.
- If 3D-texture rounding matters, try the T0 route first. That is a
  half-subtexel bias on 3D coordinates in the pgraph shader, which is a
  hypothesis: it differs from RNE only at exact ties.
- Do not read (f)'s flatness as "GMEM does not matter" on an uncapped title.
  The instrument could not see a gain here.
- The (g) RNE run moving pixels proves that `request.sh --env` reaches T30's
  driconf. A null result from an env-var survey on T30 is therefore a real
  null.

**Reopen when:** a profile puts GPU time or driver time on the critical path
of an uncapped title. The build (`tools/turnip/build.sh`) and the swap
(`host-tools/turnip_control.sh`) are ready for that.
