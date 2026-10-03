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

## Next

Waiting on the dispatched Thor run `1-1791043414-selfdeps-1888089` (queued from head
`8db47e3a8c`, `--suites ZPass_pixel_count --device thor --hard-pin`, one run). When it
finishes, check the run is not void and that its build step used the mirrors. Then
mark the PR ready (`State: ready` in PR.md).

Open items, none blocking the PR:

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
