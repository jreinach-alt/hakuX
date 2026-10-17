# Roadmap

_Last updated 2026-10-16, for version 0.5.1._

Where hakuX CE is heading. Plans change; the
[release notes](docs/releases/README.md) say what actually shipped.

## The goal for 1.0

Most of the original Xbox library playable on a handheld. In numbers: 855
games, nine in ten of the titles that [xemu](https://xemu.app)'s compatibility
list rates Playable or better, each one tested and rated on a handheld here.

## Along the way

- **About 145 more games tested in each release**, with the results on the
  [compatibility page](docs/COMPATIBILITY.md). 0.5.0 measured 175 games and
  rated 52 Playable.
- **Speed.** For most games that fall short of 30 fps, the limit is the
  emulated Xbox CPU, not the handheld's GPU. The main work is making
  translated Xbox code run faster on ARM: quicker memory access, quicker
  jumps between blocks of code, and more of the game's maths run directly on
  the handheld's CPU.
- **The games that fall short.** Each game in the "below 30 fps" and "not
  playable" sections of the compatibility page gets a look of its own: what
  holds it back, and why it crashes or hangs.
- **Higher resolution.** A second rating, Playable at twice the Xbox's
  resolution.
- **Audio.** The Xbox's audio effects processor is off by default. Find out
  what turning it on costs and breaks, and turn it on where it is safe.
- **Graphics that match the hardware.** Rendering keeps being compared with
  frames captured on a real Xbox, and that comparison guards every speed-up
  so it cannot quietly break the picture.

## Not planned

- **Desktop builds.** On a PC, use [xemu](https://xemu.app).
- **A new emulator core.** hakuX already translates Xbox code into native
  ARM64 as it runs. The work is making that translation faster, not starting
  over.
- **Anything built from leaked code or tools.** Public documentation,
  published reverse engineering and hardware we own are enough.
- **Bundled system files or games.** You provide your own.
