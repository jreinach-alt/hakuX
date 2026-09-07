# Changelog

## v0.3.3-j1

Fork build. Suffixed versions distinguish it from upstream releases.

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
- **Smaller release download** — the Vulkan validation layer, a development
  tool, shipped in every build and accounted for roughly a quarter of the
  download. It now ships only in debug builds; the release APK drops from
  30.3 MiB to 23.4 MiB. Requesting validation without the layer present was
  already handled: it logs under `xemu-vk-validation` and carries on with
  validation off.

- **Export EEPROM** — the console EEPROM sits outside the HDD image and had no
  export, so backing up saves left the console's language, video standard,
  aspect ratio and identity keys behind. Settings now exports it beside the
  HDD.

### Included from upstream
- Stale game launches from external frontends (rfandango/hakuX#7), which was
  never released: `dvdUri` was written asynchronously and the emulator process
  could read the previous game's value, or none at all.

### Notes
- Signed with a fork release key, so it will not install over an official
  build. Uninstall first, and export the Xbox HDD from Settings beforehand to
  keep saves. Subsequent releases from this fork upgrade in place.

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
