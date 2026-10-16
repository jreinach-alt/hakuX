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

- All five touched/added XML files parse (`xml.dom.minidom`) -- see build
  log below for the full list.
- Gradle build: **TODO, filled in below before marking ready.**
- `aapt`/badging check on the built APK: **TODO.**
- Thor visual check: **TODO.** Will follow AGENTS.md's device-lease
  (`docs/testing/hold_device.sh`) and fan-temperature (`dumpsys battery`,
  stop if > 42.0 C) rules; only a `.debug`-suffixed install, never `-r` over
  release, never uninstall.
