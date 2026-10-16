# hakuX CE

_Last updated 2026-10-16, for version 0.5.0._

**Original Xbox games on your Android handheld.** hakuX CE is the Community
Edition: an independent build of the hakuX emulator, tested game by game on
Snapdragon handhelds.

**[Download 0.5.0](https://github.com/jreinach-alt/hakuX/releases/latest)** ·
[87 Playable games](STATUS.md) ·
[What's new](https://github.com/jreinach-alt/hakuX/blob/master/docs/releases/v0.5.0.md) ·
[Sponsor](https://github.com/sponsors/jreinach-alt)

## Highlights

- **87 games rated Playable.** Each one reached real gameplay on a handheld and
  held 30 fps (within 5%) for at least 90% of a timed run, with no crash or
  hang. Among them: Halo: Combat Evolved, Jet Set Radio Future, Panzer Dragoon
  Orta, Grand Theft Auto III and Vice City, Need for Speed: Most Wanted,
  Crimson Skies, Max Payne 2, Mercenaries, Call of Duty 3 and The Simpsons
  Hit & Run. [See them all, with the progress charts.](STATUS.md)
- **Save states.** Ten slots per game plus an auto slot, from the pause menu,
  with undo.
- **Less stutter.** A new scene draws straight away while its shaders compile,
  and a game you have played before reuses what it built last time.
- **Faster.** NBA Live 07 went from 23 to 47 fps, 007: Agent Under Fire from
  17 to 26, and the Need for Speed: Most Wanted race start from 26.4 to 29.8.
- **Graphics checked against a real Xbox.** Rendering is compared with frames
  captured on Xbox hardware, and this release brings fog, texture decoding,
  blending, clipping and line drawing closer to it.
- **Launch from ES-DE**, and land back in ES-DE when you quit.
- **AYN Thor bottom screen.** Games fill it instead of a corner.
- **Several games folders.** The SD card and internal storage in one library.
- **Installs alongside the official hakuX.** Nothing is replaced and your
  saves there are untouched.

## Will it run on my device?

- Android 13 or newer.
- A Snapdragon 845-class chip or better (64-bit ARMv8.2). Older designs such
  as the Snapdragon 835, 660, 665 and 460 are not supported; on them the app
  says so and exits.
- Ratings come from a Retroid Pocket Nova and an AYN Thor, both Snapdragon 8
  Gen 2 (Adreno 740) on Android 13, using the **Turnip Adreno Driver T30
  (@Mr_Purple_666)** GPU driver, installed under Settings → Graphics → GPU
  Driver. On a slower chip, expect fewer games at full speed; with another
  driver, results may differ.

## What you need

hakuX includes no Xbox system files and no games. From your own console and
discs you provide:

- the MCPX boot ROM
- a flash BIOS
- an Xbox hard disk image
- your games, as `.iso`, `.xiso`, `.cso` or `.cci` images

## Get started

1. Download the APK from
   [Releases](https://github.com/jreinach-alt/hakuX/releases/latest) and
   install it. It appears as **hakuX CE**.
2. Open it. Setup asks for the boot ROM, the BIOS, the hard disk image and
   your games folder.
3. Pick a game from the library.

Using ES-DE? It needs [two small config files](https://github.com/jreinach-alt/hakuX/blob/master/docs/es-de/README.md) to find
this build. Coming from the official hakuX?
[Moving your saves across](https://github.com/jreinach-alt/hakuX/blob/master/android/MIGRATING.md) is optional.

## Good to know

- Not every game works yet. Many start but show graphical faults, and many
  have not been tried. The [compatibility list](https://github.com/jreinach-alt/hakuX/blob/master/docs/COMPATIBILITY.md) shows
  what has been tested, including games that run below full speed and games
  that do not run.
- Audio effects processing is off by default. If a game sounds thin, turn on
  Settings → Audio → Real-time DSP processing.
- No account and no analytics. The app goes online only for box art and for
  online play, and both are off until you turn them on. See
  [Privacy](https://github.com/jreinach-alt/hakuX/blob/master/PRIVACY.md).
- 0.5.0 is this build's own version number, not an official hakuX release.
  The official line is at 0.3.1.

## More

| | |
|---|---|
| [Status](STATUS.md) | Every title's status, and how close the next release is, with charts |
| [Compatibility](https://github.com/jreinach-alt/hakuX/blob/master/docs/COMPATIBILITY.md) | Every tested game and how it ran |
| [Release notes](https://github.com/jreinach-alt/hakuX/blob/master/docs/releases/README.md) | What changed in each version |
| [Known issues](https://github.com/jreinach-alt/hakuX/blob/master/KNOWN_ISSUES.md) | What to expect before you report a bug |
| [Roadmap](https://github.com/jreinach-alt/hakuX/blob/master/ROADMAP.md) | What is coming next |
| [ES-DE setup](https://github.com/jreinach-alt/hakuX/blob/master/docs/es-de/README.md) | Launching games from ES-DE |
| [Moving from the official build](https://github.com/jreinach-alt/hakuX/blob/master/android/MIGRATING.md) | Bringing your saves across |
| [Reporting a bug](https://github.com/jreinach-alt/hakuX/blob/master/docs/reporting-bugs.md) | What to include |
| [Privacy](https://github.com/jreinach-alt/hakuX/blob/master/PRIVACY.md) | What stays on your device |
| [Building from source](https://github.com/jreinach-alt/hakuX/blob/master/android/README.md) | For developers |
| [Contributing](https://github.com/jreinach-alt/hakuX/blob/master/CONTRIBUTING.md) | For developers |

## Support the project

hakuX is developed and tested by one person, and paid for out of pocket. If it
is useful to you, you can
[sponsor the work on GitHub](https://github.com/sponsors/jreinach-alt). It is
entirely optional; a good bug report helps just as much.

The emulator underneath is xemu; if you want to support it directly, see the
Patreon link under Credits.

## Source code

The code is on the [master branch](https://github.com/jreinach-alt/hakuX/tree/master). To clone it:

```
git clone -b master https://github.com/jreinach-alt/hakuX.git
```

## Credits

This build stands on the work of:

- **[xemu](https://github.com/xemu-project/xemu)**, the original Xbox
  emulator by Matt Borgerson and contributors.
  [Support xemu on Patreon](https://www.patreon.com/mborgerson).
- **X1 BOX** by izzy2lost, which brought xemu to Android.
- **[hakuX](https://github.com/rfandango/hakuX)** by rfandango, which tuned it
  for Adreno GPUs.
- **[ItsRetroPup/hakuX](https://github.com/ItsRetroPup/hakuX)**, which this
  repository was forked from.
- **[abaire](https://github.com/abaire)**, whose
  [real-hardware captures](https://github.com/abaire/nxdk_pgraph_tests_golden_results)
  the graphics are measured against.

## License

GNU GPL v2, as inherited from xemu and QEMU; some components use other
GPLv2-compatible licences. See [LICENSE](https://github.com/jreinach-alt/hakuX/blob/master/LICENSE). Not affiliated with
Microsoft.
