# selfdeps: builds fetch nothing from GitHub

Issue #433. Owner, 2026-10-03: "Why would anything in this project be not ours?
Keep going until nothing is pointed at GitHub."

## What changed

| file | change |
|---|---|
| `docs/lanes/selfdeps/mirror_sources.py` | new: clones every git source the builds use (`git clone --mirror`), downloads every archive at its pinned sha256, discovers submodules, and writes the `url.<mirror>.insteadOf` rules |
| `android/app/src/main/cpp/CMakeLists.txt` | `xemu_archive_url()`: SDL2 zip and glib tarball come from `$HAKUX_MIRRORS/archives` (default `~/hakux-work/mirrors/archives`) when the file is there, else upstream. Git FetchContent unchanged |
| `~/.gitconfig` (host, not the repo) | `url.<mirror>.insteadOf` for each mirrored repo, both `.git` and no-`.git` spellings. Written by `mirror_sources.py --insteadof` |
| meson wraps, `meson.build` | **no change.** See "Desktop" below |

Mirror layout: `~/hakux-work/mirrors/git/<host>/<path>` (bare) and
`~/hakux-work/mirrors/archives/<filename>`. Override the root with `HAKUX_MIRRORS`.

## Inventory

Every external fetch the Android and desktop builds can make. "Fetched by" is
where the URL is named. "Mirror" is where the copy lives. GitHub = yes/no.

### Git sources (insteadOf)

| name | upstream | pin | fetched by | GitHub | mirror |
|---|---|---|---|---|---|
| tomlplusplus | https://github.com/marzer/tomlplusplus(.git) | 30172438 | Android FetchContent; meson wrap | yes | git/github.com/marzer/tomlplusplus |
| nv2a_vsh_cpu | https://github.com/xemu-project/nv2a_vsh_cpu | 1115255 | Android FetchContent (only when no `subprojects/nv2a_vsh_cpu` checkout); meson wrap | yes | git/github.com/xemu-project/nv2a_vsh_cpu |
| libslirp | https://gitlab.freedesktop.org/slirp/libslirp(.git) | 26be815 | Android FetchContent; meson wrap `slirp` | no | git/gitlab.freedesktop.org/slirp/libslirp |
| libadrenotools | https://github.com/bylaws/libadrenotools(.git) | **master** (unpinned) | Android FetchContent, `XEMU_ENABLE_VULKAN` | yes | git/github.com/bylaws/libadrenotools |
| liblinkernsbypass | https://github.com/bylaws/liblinkernsbypass | submodule of libadrenotools | git submodule | yes | git/github.com/bylaws/liblinkernsbypass |
| volk | https://github.com/zeux/volk | 0b17a763 | Android FetchContent; meson wrap | yes | git/github.com/zeux/volk |
| glslang | https://github.com/KhronosGroup/glslang(.git) | b5782e52 | Android FetchContent; meson `cmake.subproject` | yes | git/github.com/KhronosGroup/glslang |
| SPIRV-Reflect | https://github.com/KhronosGroup/SPIRV-Reflect(.git) | ef913b3a | Android FetchContent; meson wrap | yes | git/github.com/KhronosGroup/SPIRV-Reflect |
| googletest | https://github.com/google/googletest | submodule of SPIRV-Reflect | git submodule | yes | git/github.com/google/googletest |
| VulkanMemoryAllocator | https://github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator(.git) | 1d8f600f | Android FetchContent; meson wrap | yes | git/github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator |
| genconfig | https://github.com/mborgerson/genconfig | 42f85f9a | meson wrap | yes | git/github.com/mborgerson/genconfig |
| imgui | https://github.com/xemu-project/imgui | b911105f | meson wrap | yes | git/github.com/xemu-project/imgui |
| implot | https://github.com/xemu-project/implot | 8553562d | meson wrap | yes | git/github.com/xemu-project/implot |
| libslirp (desktop) | as above | 26be815 | meson wrap `slirp` | no | as above |
| berkeley-softfloat-3 | https://gitlab.com/qemu-project/berkeley-softfloat-3 | b64af41c | meson wrap (fp tests, `subproject`) | no | git/gitlab.com/qemu-project/berkeley-softfloat-3 |
| berkeley-testfloat-3 | https://gitlab.com/qemu-project/berkeley-testfloat-3 | e7af9751 | meson wrap (fp tests) | no | git/gitlab.com/qemu-project/berkeley-testfloat-3 |
| dtc | https://gitlab.com/qemu-project/dtc | b6910bec | meson wrap `subproject('dtc')` | no | git/gitlab.com/qemu-project/dtc |
| keycodemapdb | https://gitlab.com/qemu-project/keycodemapdb | f5772a62 | meson wrap (`ui/meson.build`) | no | git/gitlab.com/qemu-project/keycodemapdb |
| libvfio-user | https://gitlab.com/qemu-project/libvfio-user | 0b28d205 | meson wrap (vfio-user option) | no | git/gitlab.com/qemu-project/libvfio-user |
| libblkio | https://gitlab.com/libblkio/libblkio | f84cc963 | meson wrap (blkio option) | no | git/gitlab.com/libblkio/libblkio |
| libffi (glib) | https://gitlab.freedesktop.org/gstreamer/meson-ports/libffi.git | branch `meson` | Android glib configure (glib `subprojects/libffi.wrap`, `meson.build:1982`) | no | git/gitlab.freedesktop.org/gstreamer/meson-ports/libffi |
| proxy-libintl (glib) | https://github.com/frida/proxy-libintl.git | 0.1 | Android glib configure (`meson.build:2032`) | yes | git/github.com/frida/proxy-libintl |

Not fetched by either build, not mirrored: the `roms/*` and `tests/lcitool/libvirt-ci`
submodules (gitlab.com). Developers fetch them with `git submodule update`. The
Android and desktop configures never name them.

### Archives (file mirror)

| name | upstream | pin (sha256 prefix) | fetched by | GitHub | mirror file |
|---|---|---|---|---|---|
| SDL2 release zip | https://github.com/libsdl-org/SDL/archive/refs/tags/release-2.32.10.zip | none in CMake (sha `7a3c207b`) | Android FetchContent, **only if `thirdparty/SDL2` is absent** (it is tracked in git, so not fetched) | yes | archives/SDL-release-2.32.10.zip |
| glib 2.66.8 | https://download.gnome.org/sources/glib/2.66/glib-2.66.8.tar.xz | 97bc87dd (URL_HASH in CMake) | Android ExternalProject `glib_ep` | no | archives/glib-2.66.8.tar.xz |
| zlib 1.2.11 (glib) | https://zlib.net/fossils/zlib-1.2.11.tar.gz | c3e5e9fd | Android glib configure (`meson.build:1997`, `subprojects/zlib.wrap`) | no | archives/zlib-1.2.11.tar.gz |
| zlib meson patch (glib) | https://github.com/mesonbuild/zlib/releases/download/1.2.11-3/zlib.zip | f07dc491 | Android glib configure | yes | archives/zlib-1.2.11-3-wrap.zip |
| curl 8.12.1 | https://github.com/curl/curl/releases/download/curl-8_12_1/curl-8.12.1.tar.xz | 0341f1ed | meson wrap `curl` (libcurl dependency fallback) | yes | archives/curl-8.12.1.tar.xz |
| curl wrapdb patch | https://wrapdb.mesonbuild.com/v2/curl_8.12.1-1/get_patch | e7e5c517 | meson wrap `curl` | no | archives/curl_8.12.1-1_patch.zip |
| json 3.2.0 | https://github.com/nlohmann/json/archive/v3.2.0/json-3.2.0.tar.gz | 2de558ff | meson wrap `json` (`ui/thirdparty`) | yes | archives/json-3.2.0.tar.gz |
| json wrapdb patch | https://wrapdb.mesonbuild.com/v2/json_3.2.0-1/get_patch | f6018371 | meson wrap `json` | no | archives/json-3.2.0-1-wrap.zip |
| xxHash 0.8.3 | https://github.com/Cyan4973/xxHash/archive/v0.8.3.tar.gz | aae608df | meson dependency fallback `xxhash` | yes | archives/xxHash-0.8.3.tar.gz |
| xxhash wrapdb patch | https://wrapdb.mesonbuild.com/v2/xxhash_0.8.3-2/get_patch | c7f78fc2 | meson wrap `xxhash` | no | archives/xxhash_0.8.3-2_patch.zip |
| Rust crates (16) | https://crates.io/api/v1/crates/<name>/<ver>/download | per wrap `source_hash` | meson wraps `*-rs` (rust/ subdir, `rust` option) | no | archives/<name>-<ver>.tar.gz |

Crates: anyhow 1.0.98, arbitrary-int 1.2.7, attrs 0.2.9, bilge 0.2.0,
bilge-impl 0.2.0, either 1.12.0, foreign 0.3.1, glib-sys 0.21.2, itertools
0.11.0, libc 0.2.162, proc-macro-error 1.0.4, proc-macro-error-attr 1.0.4,
proc-macro2 1.0.95, quote 1.0.36, syn 2.0.104, unicode-ident 1.0.12.

Gradle (Android, `android/settings.gradle.kts`): `google()` and
`mavenCentral()`. Not mirrored. `~/.gradle/caches` is populated, and the
Android proof below runs `--offline`. A host with an empty gradle cache still
needs network for the JVM dependencies (not GitHub).

The meson `source_fallback_url` entries (github.com release assets for curl
and xxhash) are never reached: the primary archive is in the mirror.

## Addendum 1: tooling and release path (lane.local 2026-10-03 09:55 PT)

Every GitHub or GitLab reference in the build, tooling and release code lines of
origin/master, and what this PR does about it. "Executed" means a hakuX pipeline runs it.

| file | reaches | executed by | what this PR does |
|---|---|---|---|
| `tools/turnip/build.sh` | gitlab mesa (`MESA_URL`), github glslang tag 15.4.0 (`git clone --branch`) | host Turnip harness | **repo unchanged.** `git clone` goes through the `insteadOf` rules; mesa and glslang are mirrored (table below) |
| `ubuntu-win64-cross/gcc.Dockerfile` | github `mxe/mxe` at `MXE_VERSION` 9c716d73 | Windows toolchain image (CI `build-xemu-win64-toolchain.yml`) | mirrored (git). Dockerfile **unchanged**: see "Windows toolchain" below |
| `ubuntu-win64-cross/llvm.Dockerfile` | github `kleisauke/mxe` at `MXE_TAG` llvm-mingw-20251219 | same | mirrored (git) |
| `ubuntu-win64-cross/{sdl2,libressl,libsamplerate,vulkan-headers}.mk` | github release and archive URLs | MXE package recipes | mirrored (archives, the MXE `$(PKG_FILE)` names, sha256 from the .mk) |
| `ubuntu-win64-cross/{curl,glib}.mk` | curl.haxx.se, download.gnome.org (not GitHub) | same | mirrored (archives) |
| `.github/scripts/gen-changelog.py` | `raw.githubusercontent.com/xemu-project/xdb/main/titles` | `release.yml` (GitHub Actions) | **changed**: title names read from the xdb mirror (`git show main:titles/...`). Missing mirror is an error. Its `gh api` calls go through the forge shim |
| `scripts/gen-license.py` | `raw.githubusercontent.com` / `gitlab` URLs in the `Lib` entries | release licence text | **changed**: the URLs were only a fallback for a missing `licenses/<name>.license.txt`, and that fallback was broken (`fname` undefined). All 31 entries have a cached text (NVAPI at `thirdparty/nvapi/`). The fallback now raises, so the script never fetches |
| `scripts/sign-macos-release.sh` | `gh release view/download/upload` (no github URL in the script) | macOS release signing | **no change.** `gh` on routed hosts is the forge shim (`~/hakux-work/forge/shim/bin/gh`), which implements `release view/create/upload` against the forge. Whether the release host runs the shim is an owner question (below) |
| `scripts/bump-subproject-wraps.py` | `api.github.com` (tags, releases, refs) | `bump-subproject-wraps.yml` (GitHub Actions) | **not changed.** Finding a new upstream pin needs upstream, so mirrors cannot replace it. Owner question (below) |
| `rust/Cargo.lock` | `registry+https://github.com/rust-lang/crates.io-index` (crates.io's canonical id, 0 `git+` sources) | meson `rust` option | **no change.** Cargo maps this id to the sparse index (`index.crates.io`), not github.com. Read from the lock file; not run here. The 16 crate archives are mirrored (table above) |
| `scripts/update-mips-syscall-args.sh` | `raw.githubusercontent.com/strace/strace` | none (developer regenerates a QEMU table by hand) | not changed. Not executed by any hakuX pipeline |
| `scripts/download-macos-libs.py` | MacPorts (urlopen) | macOS build | not GitHub (its github references are comments). No change |
| `scripts/oss-fuzz/build.sh`, `scripts/ci/**`, `scripts/get_maintainer.pl`, `scripts/xml-preprocess.py` | github/gitlab in comments or QEMU's upstream CI | not executed by any hakuX pipeline | out of scope (brief). Listed, not changed |
| `.github/workflows/*.yml` | GitHub Actions itself | GitHub | owner question (below). The forge has no `.forgejo/` workflows in this tree |

### Mirrors added (Addendum)

| name | upstream | pin | fetched by | GitHub | mirror |
|---|---|---|---|---|---|
| mesa | https://gitlab.freedesktop.org/mesa/mesa.git | 4c18636110f0 | tools/turnip/build.sh | no | git/gitlab.freedesktop.org/mesa/mesa |
| glslang tag | https://github.com/KhronosGroup/glslang.git | 15.4.0 | tools/turnip/build.sh | yes | existing git/github.com/KhronosGroup/glslang (tag present) |
| mxe | https://github.com/mxe/mxe.git | 9c716d7337 | ubuntu-win64-cross/gcc.Dockerfile | yes | git/github.com/mxe/mxe |
| kleisauke/mxe | https://github.com/kleisauke/mxe.git | llvm-mingw-20251219 | ubuntu-win64-cross/llvm.Dockerfile | yes | git/github.com/kleisauke/mxe |
| Vulkan-Headers | https://github.com/KhronosGroup/Vulkan-Headers.git | vulkan-sdk-1.4.309.0 | vulkan-headers.mk | yes | git/github.com/KhronosGroup/Vulkan-Headers |
| libsamplerate | https://github.com/libsndfile/libsamplerate.git | 0.2.2 | libsamplerate.mk | yes | git/github.com/libsndfile/libsamplerate |
| xdb | https://github.com/xemu-project/xdb.git | main | gen-changelog.py | yes | git/github.com/xemu-project/xdb |

| archive | upstream | sha256 prefix | fetched by | GitHub | mirror file |
|---|---|---|---|---|---|
| SDL2 2.30.10 | github release | f59adf36 | sdl2.mk | yes | archives/SDL2-2.30.10.tar.gz |
| libressl 4.0.0 | github release | 4d841955 | libressl.mk | yes | archives/libressl-4.0.0.tar.gz |
| libsamplerate 0.2.2 | github archive | 16e88148 | libsamplerate.mk | yes | archives/libsamplerate-0.2.2.tar.gz |
| vulkan-headers vulkan-sdk-1.4.309.0 | github archive | 2bc1b412 | vulkan-headers.mk | yes | archives/vulkan-headers-vulkan-sdk-1.4.309.0.tar.gz |
| curl 8.18.0 | curl.haxx.se | 40df7916 | curl.mk | no | archives/curl-8.18.0.tar.xz |
| glib 2.83.2 | download.gnome.org | 8428d672 | glib.mk | no | archives/glib-2.83.2.tar.xz |

**Windows toolchain: the MXE package set is not inventoried.** MXE builds about two
hundred packages, each with a recipe `src/<pkg>.mk` in the mirrored `mxe/mxe`
tree; the image fetches every one it builds from that recipe's `_URL`. The six
pins above are the Dockerfiles' and the four `.mk` files in this directory. The rest
are MXE's own recipes. Seed MXE's package cache (`/usr/local/mxe/pkg`, the
`--mount=type=cache` in the Dockerfiles) from `archives/` to stop it fetching. No
docker is installed on this host, so the image was not built and that proof is not done.

### Not executed by any hakuX pipeline

`scripts/oss-fuzz/**`, `scripts/ci/**`, `scripts/get_maintainer.pl`, `scripts/xml-preprocess.py`
(a comment's URL), `scripts/update-mips-syscall-args.sh`, and the QEMU upstream `tests/functional/*`
and the vendored SDL's own build scripts. These are upstream QEMU or SDL tooling.

### Owner questions (not decided by this lane)

1. `.github/workflows/*` (release, changelog, nightly, the Windows toolchain image) are GitHub
   Actions. They run only on github.com, so the release path is not on the forge. Moving them is a
   separate lane.
2. `scripts/bump-subproject-wraps.py` needs upstream to find new pins. Keep it (dev tool) or retire it
   (pins bumped by hand)?
3. Does the macOS release host run the forge `gh` shim, so `scripts/sign-macos-release.sh`'s `gh release`
   calls stay on the forge?

## Mechanism

- **Git:** `url.<mirror>.insteadOf <upstream>` in the user's git config. Both
  the `.git` and the no-`.git` spelling get a rule, because git's insteadOf is
  a prefix match and the longest prefix wins. A rule is written only for a
  mirror that exists, so an absent mirror falls back to upstream.
- **Android archives:** `xemu_archive_url()` in `android/app/src/main/cpp/CMakeLists.txt`.
  Same fallback rule.
- **Meson archives:** meson takes a wrap's archive from `MESON_PACKAGE_CACHE_DIR`
  (default `subprojects/packagecache`) when a file with `source_filename` is there
  and matches `source_hash`, and downloads otherwise (`mesonbuild/wrap/wrap.py`,
  `_get_file_internal`). The variable is read from the environment when meson
  starts; it cannot be set from `meson.build`. So the desktop host sets
  `MESON_PACKAGE_CACHE_DIR=~/hakux-work/mirrors/archives` once. That is the one
  host setting the desktop build needs and it is not a repo change.

## Proof

Test environment (`/tmp/selfdeps-gitconfig`, `/tmp/selfdeps-test/*.sh`, test only):

- `GIT_CONFIG_GLOBAL` = the mirror rules plus a catch-all rewrite of
  `https://github.com/`, `https://gitlab.com/` and `https://gitlab.freedesktop.org/`
  to a dead local port. Longest prefix wins, so only the mirrored repos resolve.
- `HTTPS_PROXY`/`HTTP_PROXY`/`ALL_PROXY` = `http://127.0.0.1:9` (dead).
- `MESON_PACKAGE_CACHE_DIR` = the archive mirror (desktop only).
- Verified: `git ls-remote https://github.com/zeux/volk` answers through the mirror;
  `https://github.com/torvalds/linux` does not (timeout, exit 124).

### Findings

0. **The Android build also fetches inside glib.** The first clean run failed in
   glib's own meson configure: its wraps (`glib-2.66.8/subprojects/*.wrap`) clone
   `libffi` from gitlab.freedesktop.org and fetch `zlib` from zlib.net and github. They
   were missing from the first inventory. Fixed: the two git sources and the zlib archive
   and wrapdb patch are mirrored (`mirror_sources.py`, now 21 git / 26 archives), and the
   glib configure step runs under `MESON_PACKAGE_CACHE_DIR=$XEMU_MIRROR_ARCHIVES`
   (`CMakeLists.txt`, ExternalProject `CONFIGURE_COMMAND`). glib's `sysprof` and
   `gtk-doc` wraps are never reached (`gtk-doc` is a documentation option, and
   `sysprof` has no `subproject()` call), so they are not mirrored.
1. **Git refuses file transport for submodules** (git 2.43). The rewrite targets are
   local paths, so `libadrenotools`'s submodule `lib/linkernsbypass` failed:
   `fatal: transport 'file' not allowed` (first clean run, `GRADLE_EXIT=1`; that log was
   overwritten by the rerun). Fixed: `protocol.file.allow=always` in the user's git config,
   written by `mirror_sources.py --insteadof`. Safe here because every rewrite target
   is a local mirror.
2. **Desktop configure cannot finish on this host, regardless of mirrors.** meson
   always builds curl as a subproject when no system libcurl is found
   (`meson.build:1453`, `required: false` does not stop the fallback), and curl
   needs OpenSSL headers. This host has none (`/usr/include/openssl/ssl.h` absent).
   The curl archive and its patch came from the mirror cache; the failure is the
   missing `libssl-dev`. The configure with `--disable-curl` reached the same error,
   so the curl subproject is unconditional. Logs: `logs/desktop-configure.log`,
   `logs/desktop-configure-nocurl.log`.
3. **`meson subprojects download` with the network dead:** all 37 wraps resolved. The
   git wraps cloned at their pinned SHAs from the mirror (`logs/meson-subprojects-download.log`).
   Five wraps (SPIRV-Reflect, nv2a_vsh_cpu, VulkanMemoryAllocator, volk, glslang) are
   cmake-method subprojects; meson's download step prints "Subproject exists but has
   no meson.build file" and a `WARNING` for them. That is meson's check for a
   meson-style subproject, not a fetch failure: the clones succeeded at the pins.
   The 16 crates and the wrapdb patches came from the archive mirror.

### Runs

| step | command | result | log |
|---|---|---|---|
| mirror | `python3 docs/lanes/selfdeps/mirror_sources.py` | 19 git, 24 archives, 0 problems | `logs/mirror-run2.log` |
| insteadOf | `mirror_sources.py --insteadof` | rules written to `~/.gitconfig` and test config | (stdout) |
| Android clean | `android-clean.sh` (`gradlew --offline assembleDebug`, cleared `.cxx`/`build`) | **BUILD SUCCESSFUL in 6m 20s**, `GRADLE_EXIT=0`. Every FetchContent and ExternalProject step came from the mirrors | `logs/android-clean.log` |
| desktop | `desktop-clean.sh` | configure stops at openssl (finding 2) | `logs/desktop-configure*.log` |
| desktop fetch | `meson subprojects download` | all wraps resolved (finding 3) | `logs/meson-subprojects-download.log` |
| addendum mirrors | `python3 docs/lanes/selfdeps/mirror_sources.py --insteadof` | 27 git, 32 archives, 0 problems | `logs/mirror-run4.log` |
| addendum git | `git ls-remote https://github.com/KhronosGroup/glslang.git refs/tags/15.4.0` and mesa `HEAD`, via the insteadOf rules | tag `8a85691a` and mesa HEAD answered from the mirrors | (terminal) |
| addendum xdb | `gen-changelog.get_title_name('4d530001')` | `Oddworld: Munch's Oddysee` from the mirror | (terminal) |
| addendum licences | every `Lib` in `gen-license.py`, `license_text` | 31 of 31 resolve from cache, no network | (terminal) |

## Attempt history

- **Attempt 1** (ended 09:03 PT, last commit `512a38145c`). Did the mirrors, the
  Android clean build and the desktop fetch proof. It queued the Thor run and ended on
  `WAITING` for that run. It did not finish: the desktop compile proof stopped at
  OpenSSL (finding 2), PR.md still named the old base, and nothing had marked the PR
  ready. The lane-local addendum (Addendum 1, 09:55 PT) came after attempt 1 had stopped,
  so the tooling sweep in "Addendum 1" below was not started then.
- **Attempt 2** (this session, from 09:41 PT). Merged `origin/master` (`4630e4bf95`).
  The Thor run finished, so `WAITING` is removed. Work continues below.

### Thor run `1-1791043414-selfdeps-1888089` (step 5): done, not void

- Queued from `8db47e3a8c`, `--suites ZPass_pixel_count --device thor --hard-pin`.
  `result.json`: `ref 8db47e3a8c`, `apk_sha 1838fbb6728f`, shader cache cleared, device
  `bdc158a5` (thor), `DONE` present, `captures 72`, `progress_log_proof: true`,
  logcat captured (`logs/` in the run dir). Scored 26/72 exact, 46 differ at 0.05% px.
  The score is not the point of this run: it proves the dispatcher's build and run path.
  72 of 78 goldens scored; the suite's own note says the gap is probably retired tests.
- Build: `logs/build-8db47e3a8c.log` (dispatch logs), `BUILD SUCCESSFUL in 2m 12s`, with
  no `Cloning into` or fetch lines. **Caveat:** that dispatcher `.cxx` appears warm (no
  clone lines, 2m 12s), so this run proves the build succeeds and does not fetch in this path. The cold-cache
  proof is the clean build in the "Proof" table above.

## Next

Open items:

- **Desktop configure needs OpenSSL headers on this host** (finding 2, filed in OUTBOX.md).
  The fetch side is proven (`meson subprojects download`). A compile-side desktop proof
  needs `libssl-dev` on the host, or meson's curl subproject made optional upstream.
- **libadrenotools is pinned to `master`**, so the mirror holds whatever master is at
  refresh time. Pinning a sha in CMake would make the Android build reproducible. That
  is a behaviour change to the build's pin, so it is left for the owner to decide.
- **`MESON_PACKAGE_CACHE_DIR` is environment-only.** Meson cannot read it from
  `meson.build`, so a bare desktop host must export it. Documented here, not in the repo.
- **Gradle** still needs `~/.gradle/caches` (or network to google/mavenCentral). It is
  not GitHub, and not mirrored.
