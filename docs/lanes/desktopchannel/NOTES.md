# lane.desktopchannel — a desktop GL execution channel on this host

**Outcome: the channel exists and works.** xemu builds on this host, starts
headless on the OpenGL renderer, runs a pgraph test, and writes a capture that
`extract_results.py` pulls off the disk image — in **17 seconds** per run. The
scheduler has been taught never to send anything there by accident.

---

## The brief's premises, checked first

The brief says of this host: *"Nothing is missing. It has simply never been
built here."* The first half is **false as written** and the second half is
**true**. Both matter, so they are recorded before anything else.

### True: no desktop build had ever existed on this host

`/home/justin/hakuX/build` existed and contained exactly three entries —
`auto-created-by-configure`, `config-temp`, `config.log`. The log's first line
was

    # QEMU configure log Sat Sep 19 06:26:23 PDT 2026
    # Configured with: '/home/justin/hakuX/configure' '--help'

i.e. it was the artifact of the board running `configure --help` while writing
this brief, a few minutes before the lane started. No `build.ninja`, no
`config-host.mak`, no `qemu-system-i386`.

### False: six build dependencies were absent, three of them hard

The brief's evidence was `pkg-config sdl2: yes` and `pkg-config gl: yes`. Those
two were indeed present. Probing the rest of what `.github/workflows/desktop.yml`
installs found **glib-2.0, sdl2, libpcre2-8, zlib, samplerate and gl present**,
and **pixman-1, epoxy, gtk+-3.0, vulkan, libpng and slirp missing**.

Three of those six stop `configure` dead and cannot be configured away:

* `meson.build:1852` — `epoxy = dependency('epoxy', required: true)`.
* `meson.build:2007-2010` — `require_gtk = host_os == 'linux'`, then
  `required: require_gtk or get_option('gtk')`. On Linux that is
  `required: true` **whatever `--disable-gtk` says**.
* `meson.build:2360` — `vulkan = dependency('vulkan')`, no `required: false`.

A seventh was invisible to any survey of that workflow's package list, and is
the one that actually cost a build: **`libssl-dev`**. With no system
libcurl-dev, meson falls through to the bundled curl subproject, and
`subprojects/curl-8.12.1/meson.build:532` hard-fails on `Dependency "openssl"
not found`. That is where the first configure attempt died, ~200 checks in,
long after epoxy, gtk and vulkan had all been satisfied.

Tooling, as the brief said: `meson` at `/home/justin/.local/bin/meson`, `ninja`
only at `/home/justin/Android/Sdk/cmake/3.30.3/bin/ninja` and **not on PATH**.
Also missing and not mentioned: `ccache`, `qemu-img`, `xvfb-run`.

### What *is* here, and was not in the brief

`desktop-runs.md` lists "MCPX + flash ROM: yours; the project ships none" as
something to supply. They were already on this host, in the Android device's
data backup at `/home/justin/hakuX/hakux-backup/x1box/`: `mcpx.bin` (512 B),
`flash.bin` (1 MiB), `eeprom.bin` (256 B), `hdd.img` (1,033,568,256 B) and a
`xemu.toml`. The discs are at `/home/justin/nxdk_pgraph_tests_xiso.iso` and
friends; the goldens at `/home/justin/goldens/results` (100 suite dirs).

The GL and Vulkan **runtimes** were present even though the headers were not:
`libGL.so.1`, `libEGL_mesa.so.0`, `libvulkan.so.1.3.275`, mesa's `swrast_dri.so`
(llvmpipe) and `lvp_icd.json` (lavapipe).

---

## How the dependencies were supplied: a rootless prefix

`sudo` is not available to this session, and installing system packages is not
a change a lane should make to a shared host unasked. It turns out not to be
necessary. `apt-get install --print-uris -y --no-install-recommends <pkgs>`
resolves the closure **against what is already installed** — so it yields the
delta, not the whole gtk world — and needs no root. The URIs are fetched with
curl and unpacked with `dpkg-deb -x` into `$WORK/desktop/deps/prefix`.

**81 packages, all of them small dev packages.** Two fix-ups are required and
both were found by the build failing:

1. **Dangling symlinks.** A Debian `-dev` package ships
   `/usr/lib/<ma>/libfoo.so` as a *relative* symlink to `libfoo.so.N`, which
   lives in the runtime package and so is not in the prefix. Extracted alone
   the link dangles and `-lfoo` fails at link, blaming the linker. Each is
   repointed at the system copy — **in a loop until a pass changes nothing**,
   because the links form chains: `libpng.so -> libpng16.so -> libpng16.so.16`,
   and on a single pass the outer link is tested before the inner one is
   repaired and is reported broken when it is about to be fine.
2. **`.pc` prefixes.** They say `prefix=/usr`, which points every `-I` and
   `-L` at the system tree that does not have these headers.

The one non-`-dev` package in the list is **`libibverbs1`**, and it is there
for a reason worth writing down: `libpcap-dev` depends on `libibverbs-dev`,
`pcap.pc` puts `-libverbs` on the link line, and this host had the headers but
never the runtime `.so`. The build linked clean and the binary died with
`error while loading shared libraries: libibverbs.so.1` — which reads like a
broken system rather than a missing dependency of ours. `build` now runs `ldd`
on its own output and names any unmet `NEEDED` entry, so the next one costs a
line of output instead of a debugging session.

**The sudo alternative, for anyone who has it:** the same set is one
`apt-get install` of `.github/workflows/desktop.yml`'s list plus `libssl-dev`.
The rootless path is not better, only available.

---

## The build

    docs/testing/desktop_channel.sh deps
    docs/testing/desktop_channel.sh build [<ref>]
    docs/testing/desktop_channel.sh smoke
    docs/testing/desktop_channel.sh run <Suite::Test> [tag] [OPENGL|VULKAN]

Everything lands under `$WORK/desktop`: the prefix, a **private detached git
worktree** at `$WORK/desktop/tree`, and the build at
`$WORK/desktop/tree/build-linux`. The script **refuses** to build if `DC_ROOT`
points inside `/home/justin/hakuX`, which is the tree the dispatcher builds
from. `ninja` and `meson` are located by searching an explicit list of paths
and never taken from the caller's `PATH` — that omission cost every uncached
Android build on 2026-09-18.

Result at `2e93371c1f`: `CONFIGURE_EXIT=0`, `NINJA_EXIT=0`, a 120,973,240-byte
binary, and

    xemu_version: 0.4.0-j1-1597-g2e93371c1f
    nv2a: renderer: OpenGL
    GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
    GL_VERSION:  4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.2

---

## One capture, end to end

    $ desktop_channel.sh run "Image_blit::ImgBlt_SRCCOPY_XRGB_B00000000" proof1
    RUN_EXIT=0  ... 17s
    renderer in use: OpenGL
    Starting  [1/1] Image blit::ImgBlt_SRCCOPY_XRGB_B00000000
    Completed [1/1] 'ImgBlt_SRCCOPY_XRGB_B00000000' in 493ms
    Testing completed normally, closing log.
    35a07060399068d1  Image_blit::ImgBlt_SRCCOPY_XRGB_B00000000.png  19705 bytes

Run twice, unchanged binary: **both captures sha256-identical** to each other.
The run writes a `result.json` recording `device_label: desktop`, the renderer
asked for and the renderer used, the xemu commit, the GL strings, and a sha256
per capture.

### Three things the next lane should not have to re-derive

**1. The qcow2 requirement is not general, and raw works here.**
`desktop-runs.md` says to convert the disk to qcow2 because QEMU probes a raw
image and restricts writes, so a run "completes and extracts nothing". That
mattered, because xemu's own `qemu-img` **cannot make a qcow2 on this host**:
it aborts at startup with

    qemu-img: ../util/qemu-thread-posix.c:127: qemu_mutex_unlock_impl:
              Assertion `mutex->initialized' failed.

(the standalone tools did not survive the fork; `--disable-tools` is in the
configure line anyway, and enabling it only gets you a binary that aborts).
So the blocker was tested rather than accepted — and a raw copy of the Android
backup's `hdd.img` runs, the guest's writes land, and the capture extracts.
**No probe warning appears in the run log at all.** Treat that line in
`desktop-runs.md` as scoped to the freshly-generated blank image it was
measured on, not as a property of raw images.

**2. Vulkan does not run headless here, and that is a missing package, not a
defect.** `renderer = 'VULKAN'` fails at `Failed to create main window` in 0
seconds: SDL's `offscreen` driver cannot create a Vulkan surface, exactly as
`desktop-runs.md` says, and `xvfb-run` is not installed. GL does not need it.
Supplying Vulkan on this host means fetching `xvfb` (and an X server's
runtime) into the prefix; nobody has needed it yet, and the channel's whole
purpose is the renderer the handhelds cannot run.

**3. xemu silently falls back on an unrecognised renderer name.** Asked for
`BOGUSGL`, it ran OpenGL and said so only in the `nv2a: renderer:` line. That
is the #29 mechanism — ask for one renderer, silently get the other, believe
the results are the first. `run` therefore compares the renderer it asked for
against the one `nv2a` reports and refuses on a mismatch. **This guard has
been exercised, not merely written**: the `BOGUSGL` run above is how, and it
refused with `REFUSING: asked for BOGUSGL and got 'OpenGL'`.

---

## The naming decision: `--device desktop`

The brief asked for the name and the reason. It is `desktop`, and it is **not
a row in the device table**.

`devices.sh`'s `device_env` is keyed on an adb serial, and `device_list`
iterates `adb devices`. The desktop channel has no serial, so no row and no
regex over that table could ever find it. Instead `devices.sh` now distinguishes
two kinds of execution target:

* **pooled** — the handhelds, derived from the table so a third one needs no
  second edit. These are what an unpinned request may be assigned to.
* **off-pool** — enumerated, because there is nothing to derive them from.
  Today: `desktop`.

exposed as `devices.sh labels | pool | offpool`, and `request.sh` now asks
devices.sh instead of sed-ing its source. (Its old `sed` was
`.*DEVICE_LABEL="\([a-z0-9]*\)"` — unanchored over the whole file, so it would
also have matched the variable's name in a comment.)

### The hazard, and why rule 1 is the only way in

This is the part the brief was right to lead with, and it is sharper than
"don't hash onto it by accident".

`affinity.py` rule 3 hashes an unpinned A/B pair over `serving()` — every lane
with a live pid in `$D/lanes/`. A desktop worker registers there like any other.
The moment it does, the modulus goes from 2 to 3 and **one unpinned pair in
three lands on OpenGL/llvmpipe instead of the Adreno**.

**The failure would have had no symptom at any stage.** The hash is
deterministic, so *both arms go together* — the pair is never split, and
`ab_compare`'s cross-device check never fires. The run completes normally. The
captures are then scored against goldens produced by the Adreno Vulkan path,
and every capture that differs for renderer reasons reads as a defect the arm
introduced. Nothing between the queue and the report says a word.

So `affinity.py` gains `OFFPOOL = frozenset({"desktop"})` and rule 3 hashes
over `pooled()` instead of `serving()`. Deliberately unchanged:

* **Rule 1** — an explicit `device` field — is the only route in, as the brief
  required.
* **Rule 2** is *not* restricted. It pins to where a sibling **actually ran**,
  and a sibling can only have run on the desktop because someone asked for the
  desktop; following it there keeps the pair on one renderer, which is rule 2's
  entire purpose.
* **`--serving`** still reports all three lanes, so a live channel does not
  read as down. A new `--serving-pooled` answers the other question, which is
  the one that explains an empty pin.

`OFFPOOL` is a constant in `affinity.py` rather than a read of `devices.sh`
because the scheduler runs on every claim and a lane that could not be
classified — because a file was briefly unreadable — would fall back to exactly
the silent behaviour above. The duplication is machine-checked instead:
`selftest.d/55-affinity-offpool.sh` fails if the two sets drift.

---

## Comparability: the decision, written down

**The desktop channel scores desktop-against-desktop only.** No golden set of
its own is proposed, and no desktop capture is compared with
`/home/justin/goldens/results` to produce a finding.

The reasoning is the brief's and it holds: those goldens came off an Adreno
running Vulkan. A desktop GL capture that differs from them is evidence of a
different renderer, a different driver and a different rasteriser before it is
evidence of anything about xemu. A GL-only defect needs a desktop A/B anyway,
which is self-consistent by construction.

**One observation that must not be over-read.** The capture produced here is
**bit-identical to its handheld golden** — same 19,705 bytes, same sha256
`35a07060...`. That is one capture, of one flat-content SRCCOPY blit, and it
says nothing about any other capture class. It is recorded because it is
evidence the pipeline is wired correctly end to end, and for **no other
purpose**. It is emphatically not a licence to score desktop runs against
handheld goldens: `desktop-noise-floor.md` already documents the desktop lane
diverging from the Adreno on real content, and `sweep_agreement.py` and
`AGENTS.md` both say deltas are incommensurable when the goldens differ in
shape.

### What is NOT yet true, and is the next lane's first job

`ab_compare.py` does **not refuse** a cross-device pair. The brief says it
"already refuses a pair whose arms ran on different devices"; what it actually
does (`ab_compare.py:654-662`) is **warn**, and the warning's text is premised
on the two handhelds having measured 62 of 62 captures byte-identical:

> "The pair is comparable but CONFOUNDED ... A leg that HOLDS is strictly
> stronger than one device would give."

For two Adreno handhelds that is a fair statement. For a **desktop-GL arm
against a handheld-Vulkan arm it is false and actively reassuring**: such a
pair is not "comparable but confounded", it is incomparable, and a leg that
holds across two renderers is not stronger evidence of anything.

`ab_compare.py` is **lane.toolsmith's file** and this lane did not touch it.
The gap is real but not yet reachable: nothing can produce a `device_label` of
`desktop` in the dispatch results until a desktop *worker* exists (see below),
and this lane's `result.json` is written outside that path. It is raised as a
board request on PR #149 rather than fixed here.

---

## What this lane did NOT do, and why

**There is no desktop queue worker.** A request can now be *spelled*
(`--device desktop`), validated, and kept away from the handhelds by the
scheduler — but nothing claims it off the queue. The claim loop lives in
`dispatcher.sh`, which is **lane.toolsmith's file** and not in this lane's
grant, and duplicating its atomic claim protocol in a second claimer racing on
the same queue directory is precisely the kind of change that should not be
made by a lane that does not own it.

So today the channel is driven directly:

    docs/testing/desktop_channel.sh run "Suite::Test" <tag>

which is enough to answer a GL-only question and was the brief's step 3. Wiring
it to the queue is a `dispatcher.sh` change and belongs to whoever holds that
file. The brief's constraint — "a desktop run must not block a handheld worker,
and a handheld request must never be claimed by the desktop channel" — is
satisfied trivially at present, because the desktop channel does not touch the
queue at all.

**One territory overlap to arbitrate.** `territory.toml` lists
`docs/testing/request.sh` under `[lane.toolsmith]`. This lane's brief granted
it explicitly and `preflight.sh`'s territory gate passes, but the row still
says otherwise; flagged on the PR so the board can settle it rather than
discovering it at fold.

---

## Reproducing all of it

    docs/testing/desktop_channel.sh deps     # ~81 packages, no root, a minute
    docs/testing/desktop_channel.sh build    # ~18 minutes cold
    docs/testing/desktop_channel.sh smoke    # expect EXIT=124 and a renderer line
    docs/testing/desktop_channel.sh run "Image_blit::ImgBlt_SRCCOPY_XRGB_B00000000" p1
    bash docs/testing/jobs/selftest.sh       # 302 passed, 0 failed
