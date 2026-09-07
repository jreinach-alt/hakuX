# hakuX (fork)

An original Xbox emulator for Android, forked from
[rfandango/hakuX](https://github.com/rfandango/hakuX) to fix launching games
from external frontends.

This fork exists for one reason: launching a game from ES-DE did not work in
any released build. It has since grown a few related fixes, but the upstream
project is the substance here — the emulator, the Android port and the Adreno
work are rfandango's.

## Lineage

```
xemu-project/xemu  →  izzy2lost/xemu (X1 BOX)  →  rfandango/hakuX  →  this fork
```

xemu is a low-level original Xbox emulator built on QEMU. X1 BOX carried it to
Android. hakuX tuned that port for Adreno devices.

## What this fork changes

- **Launching from an external frontend works.** ES-DE hands over a Storage
  Access Framework URI carrying a read grant scoped to the receiving activity;
  it was revoked before the emulator process could open the file, so the
  machine booted with no disc and asked for one. See
  [`CHANGELOG.md`](CHANGELOG.md).
- **Exiting a game returns to the frontend** that launched it, rather than to
  the in-app library.
- **It installs alongside an official build.** The fork ships under its own
  application id, so nothing is uninstalled and no saves are at risk.
- Smaller download, working crash diagnostics, and a build that configures on
  a machine other than its author's.

## Installing

Download the APK from [Releases](../../releases). It installs beside an
official hakuX build and appears as **hakuX (fork)**.

To launch it from ES-DE, two configuration files are needed —
see [`docs/es-de/`](docs/es-de/). Without them ES-DE has no way to find this
build, since its bundled rules target the official package.

Already using an official build? Nothing is at risk, and moving saves across is
optional: [`android/MIGRATING.md`](android/MIGRATING.md).

## What you have to provide

The emulator ships no copyrighted content. You supply, from hardware you own:

- MCPX boot ROM
- Flash ROM / BIOS
- An Xbox hard disk image
- Game images from your own discs

## Documentation

| | |
|---|---|
| [`CHANGELOG.md`](CHANGELOG.md) | What changed, per release |
| [`ROADMAP.md`](ROADMAP.md) | Where this is going, and what is deliberately out of scope |
| [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) | Open problems, with root causes where they are understood |
| [`docs/es-de/`](docs/es-de/) | ES-DE configuration files and instructions |
| [`android/MIGRATING.md`](android/MIGRATING.md) | Moving saves from an official build |
| [`android/RELEASING.md`](android/RELEASING.md) | Signing and publishing a build |

## Contributing upstream

Fixes here are offered back to
[rfandango/hakuX](https://github.com/rfandango/hakuX). This fork is a place to
work, not a destination — if upstream takes a change, the fork does not need to
carry it.

Hardware knowledge must come from public documentation, published
reverse-engineering work such as [XboxDevWiki](https://xboxdevwiki.net), or
behaviour observed on hardware you own. Leaked SDKs, source or internal
documentation cannot be used: they would make the result unusable by every
project it might otherwise help.

## License

Inherits xemu / QEMU / X1 BOX licensing. Emulator code is primarily **GNU GPL
v2**, with some components under other GPLv2-compatible licences. See
[`LICENSE`](LICENSE), [`COPYING`](COPYING) and [`COPYING.LIB`](COPYING.LIB).

Not affiliated with Microsoft.
