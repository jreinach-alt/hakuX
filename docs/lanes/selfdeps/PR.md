# selfdeps: builds fetch nothing from GitHub (#433)

State: draft

Lane: selfdeps               Issue: #433 (0.5: 50 Playable)
Base: master @ 9d1155f919
Files: android/app/src/main/cpp/CMakeLists.txt, docs/lanes/selfdeps/NOTES.md, docs/lanes/selfdeps/PR.md, docs/lanes/selfdeps/OUTBOX.md, docs/lanes/selfdeps/mirror_sources.py, docs/lanes/selfdeps/logs/
Prediction: none: build plumbing, no pixel change
Needs device: yes (one short Thor pgraph run, step 5 of the brief)    Needs NDK: yes

Release note (none): build-only change; no player-visible behaviour.

## What this does

A clean build no longer needs github.com, gitlab.com or crates.io. Every git
source the Android and desktop builds fetch is mirrored locally, and every
archive is mirrored at its pinned sha256.

- `docs/lanes/selfdeps/mirror_sources.py` builds the mirrors under
  `~/hakux-work/mirrors/` (`git clone --mirror` for git, the exact archive for
  URLs). It reads the sources from `subprojects/*.wrap`, from a short CMake list,
  and from the submodules of the mirrored repos, so a new pin is picked up on the
  next run. `--insteadof` writes the git `url.<mirror>.insteadOf` rules.
- `android/app/src/main/cpp/CMakeLists.txt`: the SDL2 zip and the glib tarball are
  taken from the mirror when the file is there, else from upstream. The git
  FetchContent entries are unchanged; git rewrites them.
- No meson change. Meson reads its archive cache from `MESON_PACKAGE_CACHE_DIR`,
  an environment variable, so the desktop host sets it once.

NOTES.md has the full inventory (name, URL, pin, who fetches it, GitHub or not).

## Proof

Filled in below as each step runs.
