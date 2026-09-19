# lane.desktopchannel — a desktop GL execution channel on this host

Status: in progress. This file is written as the work happens, so a resumed
session does not repeat the probes.

## The brief's premises, checked first

The brief says of this host: *"Nothing is missing. It has simply never been
built here."* The first half is **false as written** and the second half is
**true**. Both matter, so they are recorded before anything else.

### True: no desktop build has ever existed on this host

`/home/justin/hakuX/build` exists and contains exactly three entries —
`auto-created-by-configure`, `config-temp`, `config.log`. The log's first line
is

    # QEMU configure log Sat Sep 19 06:26:23 PDT 2026
    # Configured with: '/home/justin/hakuX/configure' '--help'

i.e. it is the artifact of the board running `configure --help` while writing
this brief, a few minutes before the lane started. There is no `build.ninja`,
no `config-host.mak`, and no `qemu-system-i386` anywhere under it. Nothing has
ever been configured, let alone built.

### False: six build dependencies are absent

The brief's evidence was `pkg-config sdl2: yes` and `pkg-config gl: yes`. Those
two are indeed present. Probing the rest of what `.github/workflows/desktop.yml`
installs:

| pkg-config module | state |
|---|---|
| glib-2.0 | present, 2.80.0 |
| sdl2 | present, 2.30.0 |
| libpcre2-8 | present, 10.42 |
| zlib | present, 1.3 |
| samplerate | present, 0.2.2 |
| gl | present, 1.2 |
| **pixman-1** | **missing** |
| **epoxy** | **missing** |
| **gtk+-3.0** | **missing** |
| **vulkan** | **missing** |
| **libpng** | **missing** |
| **slirp** | **missing** |

Three of those six are hard requirements that stop `configure` dead, not
optional features:

* `meson.build:1852` — `epoxy = dependency('epoxy', required: true)`.
* `meson.build:2007-2010` — `require_gtk = host_os == 'linux'`, and the
  dependency is then `required: require_gtk or get_option('gtk')`. On Linux
  that is `required: true` **whatever `--disable-gtk` says**, so gtk+-3.0
  cannot be configured away. xemu's own comment above it says GTK is required
  on Linux for the file-selection UI.
* `meson.build:2360` — `vulkan = dependency('vulkan')`, no `required: false`.

`pixman` is genuinely optional (`meson.build:1170-1172` honours
`get_option('pixman')`), and `png`/`slirp` likewise, but they are cheap to
supply once the mechanism for the other three exists.

Tooling, as the brief said: `meson` is at `/home/justin/.local/bin/meson`,
`ninja` only at `/home/justin/Android/Sdk/cmake/3.30.3/bin/ninja` and **not on
PATH**. `gcc` is `/usr/bin/gcc`. Also missing and not mentioned: `ccache`,
`qemu-img`, `xvfb-run`.

## What *is* here, and was not in the brief

The brief's own reference doc (`desktop-runs.md`) lists "MCPX + flash ROM:
yours; the project ships none" as something to supply. They are already on this
host, in the Android device's data backup:

    /home/justin/hakuX/hakux-backup/x1box/mcpx.bin     512 B
    /home/justin/hakuX/hakux-backup/x1box/flash.bin    1,048,576 B
    /home/justin/hakuX/hakux-backup/x1box/eeprom.bin   256 B
    /home/justin/hakuX/hakux-backup/x1box/hdd.img      1,033,568,256 B
    /home/justin/hakuX/hakux-backup/x1box/xemu.toml

and the test discs are at `/home/justin/nxdk_pgraph_tests_xiso.iso` (plus
`_interactive`, `pgraph-smoke.iso`, `pgraph-shard0.iso`), with the goldens at
`/home/justin/goldens/results` (100 suite directories).

The GL and Vulkan **runtimes** are present even though the headers are not:
`libGL.so.1`, `libEGL_mesa.so.0`, `libvulkan.so.1.3.275`, mesa's
`swrast_dri.so` and `kms_swrast_dri.so` (llvmpipe), and `lvp_icd.json`
(lavapipe). So a software GL context is available; only the build-time headers
and `.pc` files are absent.

## More to follow

(sections on the dependency bootstrap, the `desktop` device name, the golden
comparability decision, and the end-to-end capture are appended as they land)
