# hakuX (fork)

An original Xbox emulator for Android, forked from
[rfandango/hakuX](https://github.com/rfandango/hakuX).

## State of the project

**Early, but some games are genuinely playable.** This project rates a title
**Playable** once it boots, reaches real gameplay, and holds it for a timed
run with no crash, hang, audio dropout or hitch — see
[`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) for exactly what that means
and the current list of titles that clear it. Plenty more boot and run with
visible graphical faults, and some have not been tried yet; see
[`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) for known limitations. This is not a
daily driver, and it is not trying to be one yet.

That assessment is measured rather than impressionistic. The
[`nxdk_pgraph_tests`](docs/testing/pgraph-harness.md) suite checks rendering
output against framebuffers captured from real NV2A silicon, test by test,
rather than relying on how a game looks in play. The divergences it finds are
catalogued in the [issue tracker](https://github.com/jreinach-alt/hakuX/issues),
grouped by likely cause, each carrying the suites affected and the pixel
deltas; current pass/fail figures move as that work closes them out, so they
are tracked there rather than quoted here.

Two things worth understanding before reading that list:

- **A long issue list is the product of measurement, not decay.** These defects
  existed before anyone counted them. Counting them is the work. Much of what is
  filed describes state this fork *inherited* — a QEMU-derived codebase carried
  through three hands to Android, with a large amount of hand-optimised
  rendering code that had never been checked against a reference.
- **Where a defect is fork-introduced, it says so.** Several of the sharpest
  accuracy problems trace to optimisations added to the Vulkan and texture paths
  in early 2026 — dated, bounded changes with an upstream reference to diff
  against. Those are ours, and they are labelled `fork-introduced`.

Not a criticism of anyone upstream. Getting an Xbox emulator running at playable
speed on a handheld is the hard part, and that part was already done.

## Where this is going

[`ROADMAP.md`](ROADMAP.md) is the plan. In short:

1. **Repeatable builds and releases** — largely done.
2. **An oracle** — done. Correctness is now measurable against real hardware
   instead of argued about.
3. **Video** — the largest body of work. Divergences are filed and scheduled
   into themed sprints.
4. **Audio** — the DSP is switched off and nobody has established why.
5. **Timing** — hardest, deliberately last. A freeze chased through thirteen
   eliminated hypotheses lives in
   [`docs/investigations/freeze-analysis.md`](docs/investigations/freeze-analysis.md).

The goal is **not** to make every test pass. Most remaining differences are
precision, invisible in play; a smaller number are catastrophic and worth all
the attention. `ROADMAP.md` explains that split and the sprint order that
follows from it.

## Compatibility

See [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) for the titles that pass
this project's Playable bar, and [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) for
known limitations.

## Building

Android build prerequisites and build steps are in
[`android/README.md`](android/README.md).

## Privacy

See [`PRIVACY.md`](PRIVACY.md) for what the app does and does not send over
the network.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how to contribute, and
[`docs/reporting-bugs.md`](docs/reporting-bugs.md) for how to file a bug.
Issues carry their evidence — which suites fail, how many tests, median pixel
delta, and what has already been ruled out — so work can start from a
reproduction rather than from a guess. `docs/investigations/` records ground
already covered; read the relevant file before re-deriving it.

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

The current release is **0.5.0**; see [`docs/releases/`](docs/releases/) for
what changed in this and earlier versions.

Download the APK from [Releases](../../releases). It installs beside an
official hakuX build and appears as **hakuX (fork)**.

It needs Android 10 or later and a 64-bit ARMv8.2 CPU with LSE atomics
(Snapdragon 845 / 865 class or newer). Older ARMv8.0 parts such as the
Snapdragon 835, 660, 665 and 460 are not supported; on them the app shows an
"Unsupported CPU" message and exits.

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
| [`docs/releases/`](docs/releases/) | Release notes, version by version |
| [`CHANGELOG.md`](CHANGELOG.md) | What changed, per release |
| [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) | Titles that pass this project's Playable bar |
| [`PRIVACY.md`](PRIVACY.md) | What data stays on the device, and what little leaves it |
| [`ROADMAP.md`](ROADMAP.md) | Where this is going, and what is deliberately out of scope |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to contribute |
| [`docs/reporting-bugs.md`](docs/reporting-bugs.md) | How to file a bug |
| [`AGENTS.md`](AGENTS.md) | Canonical brief for coding agents and new contributors |
| [Issues](https://github.com/jreinach-alt/hakuX/issues) | Open defects, grouped by cause, with measured evidence |
| [`KNOWN_ISSUES.md`](KNOWN_ISSUES.md) | User-facing behaviour worth knowing before filing a bug |
| [`docs/investigations/`](docs/investigations/) | Long-form records of bugs chased in depth |
| [`docs/es-de/`](docs/es-de/) | ES-DE configuration files and instructions |
| [`docs/testing/pgraph-harness.md`](docs/testing/pgraph-harness.md) | Measuring rendering accuracy against real-hardware captures |
| [`android/README.md`](android/README.md) | Android build prerequisites and build steps |
| [`android/MIGRATING.md`](android/MIGRATING.md) | Moving saves from an official build |
| [`android/RELEASING.md`](android/RELEASING.md) | Signing and publishing a build |

## License

Inherits xemu / QEMU / X1 BOX licensing. Emulator code is primarily **GNU GPL
v2**, with some components under other GPLv2-compatible licences. See
[`LICENSE`](LICENSE), [`COPYING`](COPYING) and [`COPYING.LIB`](COPYING.LIB).

Not affiliated with Microsoft.
