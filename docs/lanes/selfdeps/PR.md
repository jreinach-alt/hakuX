# selfdeps: builds fetch nothing from GitHub (#433)

State: ready

Lane: selfdeps               Issue: #433 (0.5: 50 Playable)
Base: master @ 1d3b6d0148 (merged into the lane branch)
Files: android/app/src/main/cpp/CMakeLists.txt, docs/lanes/selfdeps/NOTES.md, docs/lanes/selfdeps/PR.md, docs/lanes/selfdeps/OUTBOX.md, docs/lanes/selfdeps/mirror_sources.py, scripts/gen-license.py, .github/scripts/gen-changelog.py
Prediction: none: build and release plumbing, no pixel change
Needs device: yes (one short Thor pgraph run, done: run 1-1791043414-selfdeps-1888089, not void)    Needs NDK: yes

Release note (none): build and release tooling only; no player-visible behaviour.

## What this does

A clean build does not need github.com or gitlab.com. Every git source the Android
and desktop builds fetch is mirrored locally, and every archive is mirrored at its
pinned sha256. The Addendum's build and release tooling is covered too.

- `docs/lanes/selfdeps/mirror_sources.py` builds the mirrors under
  `~/hakux-work/mirrors/`. It reads git sources from `subprojects/*.wrap`, a short
  CMake list, the Windows toolchain and Turnip pins, and submodules of mirrored repos.
  `--insteadof` writes the `url.<mirror>.insteadOf` rules.
- `android/app/src/main/cpp/CMakeLists.txt`: the SDL2 zip and the glib tarball come
  from the mirror when the file is there, else upstream.
- `scripts/gen-license.py`: no fetch. Every shipped library's text is already cached in
  the repo (31 of 31 resolve; checked). The old fallback to a GitHub URL was dead
  code and broken (undefined `fname`); it now raises.
- `.github/scripts/gen-changelog.py`: xdb title names come from the local mirror, not
  raw.githubusercontent.com. A missing mirror is an error, not an empty name.
- No meson change. Meson reads its archive cache from `MESON_PACKAGE_CACHE_DIR`, an
  environment variable, so the desktop host sets it once.

NOTES.md has the inventory: the original build table, plus the Addendum table of every
GitHub or GitLab reference in the tooling and release code, what each one does, and the
owner questions (`.github/workflows` is GitHub Actions; `bump-subproject-wraps.py`
needs upstream by design).

## Proof

Full commands in NOTES.md ("Proof"). The logs are local (`*.log` is gitignored) under `docs/lanes/selfdeps/logs/` on the host, and NOTES quotes their result lines.

| step | result |
|---|---|
| Mirrors | 27 git, 32 archives, 0 problems after the Addendum (`logs/mirror-run4.log`; glslang tag 15.4.0 resolves from the existing mirror) |
| Android, clean `.cxx`/`build`, GitHub and gitlab unreachable, `gradlew --offline assembleDebug` | **BUILD SUCCESSFUL in 6m 20s** (`logs/android-clean.log`) |
| Desktop, `meson subprojects download`, network dead | all 37 wraps resolved from the mirrors (`logs/meson-subprojects-download.log`) |
| Desktop, `./configure` compile side | stops at OpenSSL headers absent on this host (meson builds curl unconditionally). Not a fetch failure; filed in OUTBOX.md |
| Dispatcher build + Thor run | `1-1791043414-selfdeps-1888089` from `8db47e3a8c`: DONE, not void, build succeeded (`BUILD SUCCESSFUL in 2m 12s`; warm `.cxx`, so no cold-fetch proof from this run) |
| gen-license, cache only | 31 of 31 license texts resolve with no network |

## Not done, and why

- **Windows toolchain image:** not built. No docker on this host. The MXE package set is
  not inventoried (its recipes are in the mirrored `mxe/mxe` tree).
- **Desktop compile proof:** blocked on OpenSSL headers on this host. Needs `libssl-dev`
  (a host package, owner or sudo).

## Next

- **Windows toolchain image proof** (no docker on this host) and the **desktop compile-side
  proof past `./configure`** (needs `libssl-dev` on a host with network, filed in OUTBOX.md)
  are the two open items; neither blocks `State: ready` since both are "not done, and why"
  above, not a regression in what this PR claims.
  - **P:** high the fix is trivial (install `libssl-dev` or point meson's `openssl`
    dependency at the mirror) once a host has the package; **win:** completes the desktop
    compile proof, no behaviour change. **cost:** needs a host with `apt`/network or sudo,
    which this lane does not have. Leave for the next lane or the owner.
  - The Windows toolchain needs docker, which this host does not have either; same disposition.
