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

Full commands and logs in NOTES.md ("Proof") and `docs/lanes/selfdeps/logs/`.

| step | result |
|---|---|
| Mirrors | 21 git, 26 archives, 0 problems (`logs/mirror-run3.log`) |
| Android, clean `.cxx`/`build`, GitHub and gitlab unreachable, `gradlew --offline assembleDebug` | **BUILD SUCCESSFUL in 6m 20s** (`logs/android-clean.log`) |
| Desktop, `meson subprojects download`, network dead | all 37 wraps resolved from the mirrors (`logs/meson-subprojects-download.log`) |
| Desktop, `./configure` compile-side | stops at OpenSSL headers absent on this host (curl subproject is unconditional). Filed in OUTBOX.md. Not a fetch failure |
| Dispatcher build + Thor run | queued `1-1791043414-selfdeps-1888089` from `8db47e3a8c`, pending |

Two defects found and fixed on the way: glib's own meson fetches (libffi, zlib)
were missing from the inventory; git 2.43 refuses the file transport for submodules,
which the rewrite triggers. Both are fixed in this PR.

## Next

Mark ready once the Thor run `1-1791043414-selfdeps-1888089` finishes and is not void.
