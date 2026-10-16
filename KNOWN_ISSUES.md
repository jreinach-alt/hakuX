# Known issues

_Last updated 2026-10-12, for version 0.5.0._

What to expect from 0.5.0 before you report a bug. How each tested game runs
is on the [compatibility page](docs/COMPATIBILITY.md); open bugs are in the
[issue tracker](https://github.com/jreinach-alt/hakuX/issues).

## Games

- **Most games are not rated yet.** Many start but show graphical faults, and
  many have not been tried. A game missing from the compatibility page has not
  been rated; it may still run.
- **Some games run below 30 fps** on a Snapdragon 8 Gen 2-class handheld, and
  slower chips run them slower still.
- **Need for Speed: Most Wanted** is Playable, but its frame rate still dips
  in places.
- **A short pause the first time a scene appears**, while its shaders are
  built. The ubershader (Settings → Graphics, on by default) hides most of it,
  and a game you have played before reuses what it built last time.
- **The ubershader can cost frame rate in some games.** ToeJam & Earl III ran
  at 54 fps instead of 60 with it on. It can be turned off for one game.

## Audio

- **Audio effects processing is off by default.** Games that use the Xbox's
  audio effects may sound thin, without reverb. Turn on Settings → Audio →
  Real-time DSP processing; it can cost speed on slower devices.

## Setup and storage

- **This build and the official hakuX are separate apps.** Settings, saves
  and the hard disk image in one do not appear in the other.
  [Moving your saves across](android/MIGRATING.md) is optional.
- **Save states are kept outside the Xbox hard disk image.** The default
  folder is removed when you uninstall the app. To keep your states, choose
  your own folder in Settings → Save States.
- **ES-DE needs two config files** to launch this build. See
  [ES-DE setup](docs/es-de/README.md).
- **Online play is off by default.** Turn it on in Settings → Online /
  Insignia.

## Reporting a bug

See [Reporting a bug](docs/reporting-bugs.md) for what to include. To attach a
frame capture, turn on Settings → Debug → Debug Tools; the pause menu then
shows Debug Capture.
