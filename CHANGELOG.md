# Changelog

## v0.5.2 — 2026-10-17

Halo: Combat Evolved's opening cinematic was running at 17 fps on Android
handhelds; it now holds about 29 fps through the hangar briefing. The fix
answers the game's occlusion (visibility) tests as soon as they are queued
instead of waiting on the GPU to confirm each one, skips a slower texture
path the cinematic's colour surfaces were taking, and stops the CPU
translator recompiling around one floating-point instruction. Answering
occlusion tests early means a visual effect can show a frame
late at a camera cut.

See [docs/releases/v0.5.2.md](https://github.com/jreinach-alt/hakuX/blob/master/docs/releases/v0.5.2.md).

## v0.5.1 — 2026-10-16

The app is renamed hakuX CE and gets a new icon. Halo's menu ring no longer
jumps back in bursts: float-to-integer stores now round the way the Xbox
does. Also fixed: a game with bad audio data no longer closes the emulator,
a texture pointing outside video memory draws blank instead of crashing,
out-of-range ADPCM audio plays instead of producing noise, a corrupt
pipeline cache is discarded instead of crashing at start, a missing audio
device is no longer fatal, and the setup wizard rejects a BIOS file that is
not 256 KB, 512 KB or 1 MB.

See [docs/releases/v0.5.1.md](https://github.com/jreinach-alt/hakuX/blob/master/docs/releases/v0.5.1.md).

## v0.5.0 — 2026-10-12

The first release rated by play rather than by pixel counts alone: 52 titles
reach gameplay and hold it, with no crash, hang, audio dropout or hitch, at
30 fps or better for at least 90% of a timed run, on a Retroid Pocket Nova or
an AYN Thor. Adds save states, several games folders, an Ubershader option
that avoids freezing while an exact shader compiles, pipelines pre-built from
a previous play, faster renderer paths, and GPU surface reuse. Fixes
stuttering and repeated audio in Need for Speed: Most Wanted, hard-edged white
polygons in GTA San Andreas, vanishing cars in RalliSport Challenge, a Forza
Motorsport slowdown over a race, and several crashes and hangs.

Box art lookup is now off until you turn it on. New installs are asked during
setup; an existing install asks once, the first time the library shows the
Cover Grid.

**Needs Android 10 and an ARMv8.2 CPU with LSE atomics** (Snapdragon 845 / 865
class or newer); v0.4.x installed on Android 8. On an older ARMv8.0 part, the
app now shows an "Unsupported CPU" message and exits instead of crashing.

See [`docs/releases/v0.5.0.md`](https://github.com/jreinach-alt/hakuX/blob/master/docs/releases/v0.5.0.md).

## v0.4.1-j1 — 2026-09-26

A frame-rate fix for v0.4.0-j1. Each time the renderer reused a render-target
slot, it dropped the slot's guest-memory access watch without releasing it,
so frame rate collapsed to 1-3 fps after a few minutes in Grabbed by the
Ghoulies, RalliSport Challenge 2 and Conker; the watch is now released before
the slot is reused.

See [`docs/releases/v0.4.1-j1.md`](https://github.com/jreinach-alt/hakuX/blob/master/docs/releases/v0.4.1-j1.md).

## v0.4.0-j1 — 2026-09-10

A rendering-accuracy release, every change measured against framebuffers
captured from a real Xbox (the `nxdk_pgraph_tests` golden results): texture
borders and border colour, wrap modes, cylinder wrap, texture perspective,
signed texture channels, textures the CPU rewrites in place, cube maps, more
texture formats, render targets, depth, fog and fixed-function lighting all
move closer to the hardware. Several emulator aborts and Vulkan
resource-lifetime bugs are fixed, and Android gets a clean exit on guest
power-off, a separate debug build id, and emulator stderr reaching logcat.

See [`docs/releases/v0.4.0-j1.md`](https://github.com/jreinach-alt/hakuX/blob/master/docs/releases/v0.4.0-j1.md).

## v0.3.3-j1

The first release of this fork. It fixes launching a game from an external
frontend such as ES-DE, which did not work in any released build.

**Two things to know before installing:**

- It installs **alongside** an official hakuX build rather than replacing it.
  Nothing is uninstalled and no saves are at risk.
- Launching it from ES-DE needs two configuration files. See
  [`docs/es-de/`](https://github.com/jreinach-alt/hakuX/tree/master/docs/es-de).

### New
- **Installs alongside an official build** — the fork ships under its own
  application id, `com.jreinach.hakux`, and appears as *hakuX (fork)*. An
  official install keeps its HDD image, EEPROM and settings untouched. Moving
  saves across is optional and non-destructive; see
  [`android/MIGRATING.md`](https://github.com/jreinach-alt/hakuX/blob/master/android/MIGRATING.md).
- **Export EEPROM** — the console EEPROM sits outside the HDD image and had no
  export, so backing up saves left the console's language, video standard,
  aspect ratio and identity keys behind. Settings now exports it beside the
  HDD.

### Bug Fixes
- **Fix launching a game from an external frontend** — ES-DE hands over a
  Storage Access Framework `content://` URI carrying only a transient read
  grant, scoped to the activity that receives it. `LauncherActivity` started
  the emulator without forwarding that grant and then finished, revoking it
  before the `:xemu` process could open the file. No disc was attached and the
  machine booted to the dashboard asking for one. The grant is now forwarded to
  `MainActivity`, where it lasts for the emulation session.
- **Fix the crash when a ROM URI cannot be forwarded** — an unforwardable URI
  made `startActivity` raise `SecurityException` and took the process down,
  showing a black screen. It now falls back to a plain intent, so the emulator
  either opens the file through a persisted grant or reports a missing disc.
- **Fix exiting a game launched from a frontend** — quitting always opened the
  hakuX library, even when the frontend had chosen the game. Such a session now
  returns to the frontend it came from.
- **Fix the log capture silencing its own diagnostics** — fourteen tags the
  code logs under were dropped by the capture filter, among them `hakuX-crash`,
  the guest kernel BugCheck detector that KNOWN_ISSUES.md tells people to
  collect.
- **Fix duplicated logs across processes** — the app and the emulator each
  rotated and streamed into one pair of files, so both held two copies of a
  single session. Each process now keeps its own pair, and exporting collects
  all of them.
- **Fix the build pinning one machine's JDK** — `gradle.properties` committed
  an absolute `org.gradle.java.home`, so the build only configured where that
  exact directory existed.

### Improvements
- **Smaller download** — the Vulkan validation layer, a development tool,
  shipped in every build and accounted for roughly a quarter of the download.
  It now ships only in debug builds; the release APK drops from 30.3 MiB to
  23.4 MiB. Requesting validation without the layer present was already
  handled: it logs under `xemu-vk-validation` and carries on with validation
  off.

### Included from upstream
- Stale game launches from external frontends (rfandango/hakuX#7), which was
  never released: `dvdUri` was written asynchronously and the emulator process
  could read the previous game's value, or none at all.

### Notes
- Signed with this fork's own key. Releases from this fork upgrade in place
  with `adb install -r`; an official build is a separate app and is unaffected
  either way.
- Version names carry a `-jN` suffix so they cannot be confused with, or
  collide with, upstream releases.

## v0.3.1

Reconstructed from the commit history; no release notes were published upstream
for this version.

### Improvements
- **Persistent log capture** — continuous background capture to file with
  session rotation, replacing the single-shot logcat export, so a previous
  session's logs survive a crash and restart
- **Profiling instrumentation gated behind `NV2A_PERF_LOG`**, off by default
- **Lazy surface eviction** — eviction downloads are skipped when VRAM data is
  never read, and the remaining ones are inlined to remove a per-eviction
  finish
- **Multi-threaded S3TC texture decompression**, extended to 3D textures
- **XISO converter no longer needs Rust or Cargo** — the Rust xdvdfs converter
  was replaced with extract-xiso

### Bug Fixes
- Fix texture cache thrashing caused by an aggressive memory budget trim
- Fix BC3 corruption by disabling native BC for 3D textures
- Fix per-draw surface dumps and JSON overflow in diagnostic capture

### Reverted
- The GPU compute shader for BC3/DXT5 texture decompression added in v0.3.0

## v0.3.0

Reconstructed from the commit history; no release notes were published upstream
for this version.

### New Features
- **Per-game settings** — overrides stored per title, edited through the
  existing settings UI with changed values highlighted
- **Xbox dashboard management** with NAT networking, Insignia support and HDD
  tools
- **Game compatibility quirks layer** — a title-id lookup applying per-game
  workarounds, starting with a scene-graph cycle breaker for Fable
- **Xbox kernel crash detection** — BugCheck and NULL page fault diagnostics
  with register and stack context
- **Texture dump and replacement infrastructure**
- **Skip boot animation** toggle
- **Debug log export** from settings
- **Diagnostic viewer** and device pull scripts under `debug-tools/`

### Improvements
- Native BC texture upload where `textureCompressionBC` is available, plus
  adaptive BCn compression for uncompressed textures
- Batched render sync events and NEON-optimised blits
- Bindless textures removed in favour of tighter descriptor management
- Vertex shader emulator stub replaced; uniform uploads optimised
- `:xemu` process separation restored, isolating the emulator from the app
- The original ISO is kept after an automatic XISO conversion
- `SettingsActivity` refactored for consistency

### Bug Fixes
- Fix a 30 fps trap caused by a redundant deferral guard
- Fix surface eviction VRAM corruption and stale texture sampling
- Fix a Vulkan pipeline exhaustion crash and a NOP assert on Android
- Fix an RCU SIGSEGV when emulation was restarted quickly
- Fix a shader binding crash alongside conditional VBLANK deferral
- Fix XISO conversion launching the original file when SAF renamed the output
- Fix the XISO converter missing from release builds
- Fix diagnostic frame dumps not starting from the pause menu, and captures
  completing with zero draws

## v0.2.1

### Bug Fixes
- **Fix HDD corruption** — restore block device flush on app terminate and background to persist QCOW2 metadata. Cache partition clear now uses synchronous writes
- **Fix game freeze on TB flush** — disable post-flush rewarm on Android which could hang on self-modified code
- **Fix TB cache prewarm crash** — disable startup prewarm on Android. Add build hash to tb_cache.bin for auto-invalidation on new builds
- **Fix on-screen controller hidden on some devices** — filter out virtual/internal devices (accelerometers, gyroscopes) that falsely report as gamepads

### Improvements
- **Simplified FPS overlay** — shows only FPS count
- **Unified log tags** — all logcat output uses hakuX prefix. Filter with: `adb logcat | grep hakuX`
- **HDD cache clear on background thread** — prevents ANR on large images

## v0.2.0

### New Features
- **OpenGL ES renderer** — experimental alternative to Vulkan, selectable in Graphics settings
- **EEPROM editor** — change Xbox language, video standard, resolution modes, aspect ratio, refresh rate
- **Settings index** — reorganized into 4 sections: hakuX Data, Graphics, Debug, EEPROM
- **System file pickers** — change MCPX ROM, Flash ROM, HDD image from settings
- **HDD export** — save a copy of the Xbox HDD to any folder
- **Games folder in settings** — moved from library screen to settings
- **Game search** — search bar with live filtering in game library
- **Pull-to-refresh** — swipe down to rescan games folder
- **XISO progress bar** — real progress tracking across copy/convert/save phases
- **XISO integrity check** — verifies XISO before launch, auto-rebuilds from ISO if corrupt

### Improvements
- **Controller overlay** — D-pad/stick repositioned, LS/RS as separate buttons, menu button, swipe-up gesture, trigger axis fix (-1.0 for release), per-pointer tracking
- **Pause menu** — actually pauses emulation, simplified UI
- **NEON optimizations** — S3TC decompression and texture swizzle (benefits both renderers)
- **XISO conversion** — staged in temp directory, clean up on interruption, write permission check
- **FPS overlay** — shows driver info or "OpenGL ES" label, frame pacing, shader stats
- **Clear code cache** button in Debug settings
- **Graceful VK texture LRU handling** — skip instead of crash when cache exhausted

### Bug Fixes
- Fix TB cache crash when FP settings change between sessions
- Fix pause/resume not working from in-game menu
- Fix GLES geometry shader crash (gl_PointSize unavailable without extension)
- Fix GLES shader version detection (was hardcoded to 320, now auto-detected)
- Fix shader link failure crash (graceful fallback instead of assert)
- Fix shared GLSL changes breaking VK (gated behind renderer check)

### Rebranding
- Package renamed to `com.rfandango.haku_x`
- Debug builds install alongside release (`com.rfandango.haku_x.debug`)

## v0.1.0

- Initial release
