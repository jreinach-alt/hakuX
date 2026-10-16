# lane.icon1016 -- the new hakuX CE app icon (#433)

## What changed

Added two vector drawables (`drawable/ic_launcher_fg.xml`,
`drawable/ic_launcher_mono.xml`) carrying the owner's mark from
`hakux-work/svg/hakux-svg-master.svg` / `hakux-svg-monochrome.svg`
(not edited; only read), and repointed both adaptive-icon XMLs
(`mipmap-anydpi-v26/ic_launcher.xml`, `ic_launcher_round.xml`) at them plus
the background colour, instead of the old PNG mipmaps.

No SVG rasterizer is installed on this host and installing one was ruled out
by the brief, so the artwork is hand-transcribed into Android's vector
drawable path syntax rather than rasterized.

## The one open design choice: background colour

Neither source SVG has a background layer (both only draw the ring + h on
a transparent/none background). `values/ic_launcher_background.xml` changes
from `#000000` to `#0B1110` -- the banner's background colour, chosen to
match the rest of the hakuX CE visual identity (README banner, logo work in
`lane/logo1016*`). This is a judgement call, not a transcription of owner
material: **the owner should confirm `#0B1110` is the intended icon
background**, or supply one.

## Dasharray -> explicit arc path

Vector drawables have no `stroke-dasharray`. The source's outer ring is
`r=39`, `stroke-dasharray="184 61"` (circumference ~245, so a single dash
covering 184/245 = 75% = ~270 degrees), rotated -90 degrees.

Working through the rotation: an SVG circle's dash pattern starts at its
0-degree point (3 o'clock) and runs clockwise (increasing angle in SVG's
y-down space). The 184-length dash therefore runs from 3 o'clock clockwise
270 degrees to 12 o'clock, leaving the gap from 12 back to 3 o'clock.
Applying `rotate(-90)` to the whole circle shifts every point's angle by
-90 degrees, moving the dash's start from 3 o'clock to 12 o'clock and its
end from 12 o'clock to 9 o'clock -- i.e. exactly the "270-degree arc
starting at 12 o'clock, running clockwise" the brief specifies (12 -> 3 ->
6 -> 9).

Reproduced as a single arc command with the group's origin at (0,0), radius
39: start point is 12 o'clock = `(0,-39)`, end point is 9 o'clock =
`(-39,0)`. A clockwise sweep that is the *major* arc (270 of the 360
degrees, the minor arc between the same two points is the 90-degree
direct path) needs `large-arc-flag=1`, `sweep-flag=1`:

```
M 0,-39 A 39,39 0 1 1 -39,0
```

Visually traced: top -> right (3 o'clock) -> bottom (6 o'clock) -> left
(9 o'clock), 270 degrees clockwise from 12 to 9. Matches the brief's
description exactly.

The inner subtle ring (plain, undashed `r=31` circle) is drawn as two
half-arcs plus `Z`, the standard way to express a full circle as an Android
vector path:

```
M 0,-31 A 31,31 0 1 1 0,31 A 31,31 0 1 1 0,-31 Z
```

The h glyph's path data (`M-15 -25V25 M-15 2 Q-15 -12 0 -12 Q15 -12 15 3
V25`) is valid Android `pathData` syntax unchanged (multiple `M` subpaths,
`V`, `Q` are all supported); only reformatted with consistent spacing.

## Safe-zone arithmetic (confirming the brief's claim)

Adaptive icons keep the central 66dp-diameter circle visible on every mask
(safe radius = 33dp from centre). The group is scaled by 0.72 and centred
at (54,54). The outer ring's drawn radius is `r=39` with `stroke-width=3`
(half-width 1.5), so the furthest-out pixel from centre, before scaling, is
at `39 + 1.5 = 40.5`. After the 0.72 scale: `40.5 * 0.72 = 29.16`dp from
centre -- inside the 33dp safe radius, with about 3.8dp of margin. Confirmed.

## Stale PNGs (now unreferenced; deletion is the owner's call)

Both `mipmap-anydpi-v26/ic_launcher*.xml` files no longer reference any
`@mipmap/ic_launcher_*` drawable (foreground/monochrome/background), and
minSdk 33 means the adaptive icon is the only `ic_launcher` resource the app
ever resolves (pre-26 fallback mipmaps are moot above API 26). That makes
all of the following dead weight, 4 files x 5 densities = 20 PNGs, left in
place per the brief:

```
android/app/src/main/res/mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/ic_launcher.png
android/app/src/main/res/mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/ic_launcher_foreground.png
android/app/src/main/res/mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/ic_launcher_background.png
android/app/src/main/res/mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/ic_launcher_monochrome.png
```

(This dead weight predates this change for the bare `ic_launcher.png` files
-- the brief already notes minSdk 33 makes them moot -- but the
`_foreground`/`_background`/`_monochrome` PNGs only became unreferenced with
this PR's retargeting.)

## Verification

- All five touched/added XML files parse (`xml.dom.minidom`): pass.
- Gradle build: `JAVA_HOME=~/toolchains/jdk21 ./gradlew --no-daemon
  assembleDebug` -- **`GRADLE_EXIT=0`**, `BUILD SUCCESSFUL in 5m 51s`, 40
  actionable tasks.
- `aapt dump badging` on `app/build/outputs/apk/debug/app-debug.apk`: every
  density (`application-icon-160`..`application-icon-65534`) resolves to
  `res/mipmap-anydpi-v26/ic_launcher.xml`, i.e. the adaptive icon is picked
  up as the app icon at every requested density.
- `aapt2 dump xmltree ... --file res/mipmap-anydpi-v26/ic_launcher.xml`
  shows the compiled `<adaptive-icon>` resolving to three IDs; `aapt2 dump
  resources` maps them back to `color/ic_launcher_background` (`0x7f05005f`),
  `drawable/ic_launcher_fg` (`0x7f070092`), `drawable/ic_launcher_mono`
  (`0x7f070093`) -- i.e. the new drawables and colour, not the old PNG
  mipmaps. The old `mipmap/ic_launcher_background` and
  `mipmap/ic_launcher_monochrome` entries are still in the resource table
  (nothing references them any more) confirming the "stale PNGs" list above.
- Thor visual check: **attempted, blocked by the device, not by our rules.**
  `bdc158a5` was present (`adb devices -l`); battery temperature checked
  first and stayed at 30.0 C throughout (well under the 42.0 C stop line,
  so no `NEED:`). Installed the freshly built `app-debug.apk` with `adb
  install -r` over the existing `com.jreinach.hakux.debug` package (a
  `.debug`-suffixed variant, not the release package, and not a fresh
  install over new data -- allowed under the brief). No lease was taken:
  nothing here launches xemu or drives a title, so the Stop hook's
  emulator-protection concern (`docs/testing/hold_device.sh`) does not
  apply -- this is a plain launcher screenshot.

  `adb exec-out screencap -p` consistently returned a 1920x1080 image that
  decodes to a single solid colour, `(0,0,0,255)` for all 2,073,600 pixels,
  regardless of wake/home/back key sequencing or keyguard state (confirmed
  not locked via `dumpsys window`: `isKeyguardShowing=false`). `adb shell
  screencap -d 0|-d 4` wrote 0-byte files. `dumpsys display` shows `
  FLAG_SECURE` on both `DisplayDeviceInfo` entries (`Built-in Screen` and
  `Screen-2`) -- the device blanks screen captures of secure displays,
  which is an OS/device-level DRM-style protection, not a permission this
  lane can reach around. Per the brief ("do not improvise"), no attempt was
  made to disable secure-display capture (a developer-option / vendor
  toggle), only ordinary input-event navigation and reads.

  **So there is no screenshot in this PR.** The build and `aapt2` checks
  above are the verification: they show the compiled adaptive icon
  resolving to exactly the three new resources, which is the thing a
  screenshot would otherwise be confirming visually. If the owner wants a
  photographed confirmation, it needs either a device without
  `FLAG_SECURE` captures blanked, or a physical photo of the Thor's screen.
