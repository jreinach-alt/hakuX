# Measuring rendering accuracy

Notes toward roadmap item 2: giving this project an oracle.

## Why this matters more than it sounds

Emulator work has no ground truth. Correctness means "behaves as the hardware
did", and for a commercial game whose source nobody has, that cannot be proved
— only observed, usually as a failure minutes into a session. Every graphical
fault here is currently reported as "this game looks wrong", which is not
something you can bisect, regress against, or close.

For the GPU, that problem is already solved by somebody else.

## What exists

| Repository | What it holds |
|---|---|
| [`abaire/nxdk_pgraph_tests`](https://github.com/abaire/nxdk_pgraph_tests) | A test program that builds to an Xbox disc image and runs on real hardware and emulators. 100 test source files: alpha func, antialiasing, attribute carryover and setters, blending, blend surfaces, bump mapping, bump env luminance, clears, texture formats, surface formats, combiners, vertex shaders. |
| [`abaire/nxdk_pgraph_tests_golden_results`](https://github.com/abaire/nxdk_pgraph_tests_golden_results) | 5,608 reference framebuffers **captured from real NV2A silicon**, as `results/<Suite_Name>/<Test_Name>.png`. 769 of them are depth captures. |
| [`abaire/xemu-nxdk_pgraph_tests_results`](https://github.com/abaire/xemu-nxdk_pgraph_tests_results) | Results tracked across xemu versions, with `dev_scripts/compare.py` driving `perceptualdiff`. |
| [`abaire/xemu-pgraph-ci-tools`](https://github.com/abaire/xemu-pgraph-ci-tools) | The package behind `compare.py`. Its `runner` drives a desktop xemu binary and is not usable here; its `comparator` is. |
| [`abaire/nxdk_vsh_tests`](https://github.com/abaire/nxdk_vsh_tests) | Vertex shader tests specifically. |

The hardware goldens are the part that cannot be reproduced without an Xbox and
a devkit. They are published.

## Running it without a device

The whole loop also runs on a desktop build with a software GPU - no handheld,
no Adreno - in about 18 seconds for a single test, and the first capture taken
that way was bit-identical to its hardware golden. Recipe and limits:
[`desktop-runs.md`](desktop-runs.md).

## The disc image

`nxdk_pgraph_tests` publishes a built `nxdk_pgraph_tests_xiso.iso` with its
releases, so **the nxdk toolchain is not needed to run the suite** — only to
change the tests. The image this document was written against:

```
sha256  2371e74342a007999786948629d758672130d5afe7830db21e5d99c6855e4ee0
size    5,767,168 bytes
```

Building it from source, if you ever need to, wants the nxdk as a submodule
from `abaire/nxdk` on the `nxdk_pgraph_tester` branch (the suite needs pbkit
changes upstream nxdk does not carry), `pip3 install nv2a-vsh`, a
`./prewarm-nxdk.sh` bootstrap pass, and a recursive clone.

## What the goldens are, and what "matching" means

`goldens/` is a clone of
[abaire/nxdk_pgraph_tests_golden_results](https://github.com/abaire/nxdk_pgraph_tests_golden_results)
— framebuffer captures of
[abaire/nxdk_pgraph_tests](https://github.com/abaire/nxdk_pgraph_tests) taken on
**real XBOX 1.0 hardware** by the test suite's author. 5,608 PNGs, RGBA, 640x480.

Three things to get right before quoting a number:

**Exactness and tolerance are different claims.** A mean absolute error of
"0.00" is not bit-identity: 1,536 pixels differing by 1 and 87,381 pixels
differing by 8 both round to 0.00. Report **differing-pixel count and max
delta**, which separate "a format is not decoded at all" (max 255) from
"rounding" (max 6) — a distinction a mean destroys, and one that decides whether
a defect is worth chasing.

**Alpha is part of the comparison unless you decide otherwise.** The goldens are
RGBA and differ from our output in alpha on some tests even where RGB is
identical. The upstream README warns its captures respect alpha in a way the
console's final composition may not, so dropping it is defensible — but it must
be a stated decision, not a silent `.convert("RGB")`.

**Upstream's criterion is `perceptualdiff`** (`goldens/scripts/compare.sh`), not
pixel arithmetic. Any threshold used here is ours, and should be labelled as
such rather than presented as "matches hardware".

## Configuring a run

The suite reads `d:\nxdk_pgraph_tests_config.json` — from the disc it booted
from — and **the released image does not carry one**. Run with the defaults and
results are written to `e:\nxdk_pgraph_tests`, which on Android means they are
sealed inside `hdd.img` with no way to get them out.

`make_test_iso.py` adds that file to a copy of the image:

```sh
python3 docs/testing/make_test_iso.py nxdk_pgraph_tests_xiso.iso \
    -o pgraph-configured.iso \
    --ftp-host 192.168.1.50 --ftp-port 2121 \
    --ftp-user pgraph --ftp-password pgraph \
    --shutdown-on-completion
```

Nothing already on the disc moves: the config and a rebuilt root directory
table are appended and the volume descriptor is repointed. The script verifies
its own output by re-reading it and resolving every name through a tree descent
the way the kernel does.

`--shard-count N` with `--shard-index 0..N-1` splits a full run across several
images, which matters — a complete pass is thousands of tests. `--config FILE`
takes a prepared JSON instead, so individual suites can be skipped.

**`sample-config.json` on the disc does not enumerate every test.** It lists
3,465 tests across 65 suites, but the XBE registers more than that — `Blend
surface`, `Surface format`, `Lighting spotlight` and `Texture palette` all run
and appear in results while being absent from that file. Building an allowlist
from it silently skips everything it omits. Prefer `skip_tests_by_default:
false` with explicit skips.

Config semantics, measured on device rather than assumed:

| form | behaviour |
|---|---|
| `skip_tests_by_default: true`, no suites | runs nothing, shuts down cleanly |
| `skip_tests_by_default: true` + `{suite: {skipped: false}}` | enables that suite |
| `skip_tests_by_default: false` + `{suite: {skipped: true}}` | skips that suite |
| `{suite: {test: {skipped: true}}}` | skips that one test |
| `{suite: {test: {skipped: false}}}` under `skip_tests_by_default: true` | does **not** enable a single test |

The per-test key is `skipped`, confirmed against the strings in the XBE
(`[skipped] must be a boolean`). An unrecognised key is ignored silently, so a
typo costs a whole run.

**Always set `enable_progress_log: true`.** It writes
`pgraph_progress_log.txt` alongside the PNGs, naming every test the suite
started and completed:

```
Starting [2/2] Texture DXT::DXT1_plasma_dxt1
  Completed [2/2] 'DXT1_plasma_dxt1' in 80ms
Testing completed normally, closing log.
```

This is the only reliable evidence that a result is from the run you think it
is. `--newer-than` passes files that were never rewritten, FATX mtimes advance
on files whose tests never executed, and run duration says nothing because the
emulator does not exit on guest power-off (issue #20). A conclusion has already
been drawn from a run that never reached its tests.

Copy the configured image into your ROM folder and launch it like a game.

## Getting the results off the device

### Over FTP, which is the reason to configure anything

The suite writes each captured framebuffer to the emulated hard disk **and**,
when an FTP server is configured, uploads it. Uploads are the only copy you can
reach. Two things make this work on Android:

- This build has `INTERNET`, links libslirp, and selects the `nat` backend when
  networking is on, so the guest reaches the LAN through the phone's stack.
- `nxdk_ftp_client_lib` uses **PASV**, so the guest opens both the control and
  the data connection outbound. Nothing has to route back in.

Turn networking on in **Settings → Online / Insignia → "Enable online
networking (Insignia)"**. That switch alone is what the emulator reads; do not
apply the Insignia DNS preset, which is for Xbox Live and unrelated here.

On the machine you will compare on:

```sh
pip install pyftpdlib
python3 -m pyftpdlib -p 2121 -w -u pgraph -P pgraph -d ./ftpdump
```

Point `--ftp-host` at that machine's LAN address, not at a hostname — the
config parses an IPv4 literal and nothing else. Some notes that will save an
afternoon:

- **The server must not be on Windows.** Uploads are named
  `Suite name::Test.png`, and `:` cannot appear in a Windows filename. WSL,
  Linux and macOS are all fine.
- Allow the control port and the passive data ports through the firewall.
  `pyftpdlib` picks ephemeral passive ports unless told otherwise.
- `10.0.2.2` reaches the phone's own localhost through slirp, so an FTP server
  running on the phone is possible — but it has to report a PASV address the
  guest can then connect back to, and a server that answers `127.0.0.1` will
  hang the transfer. The LAN machine is the path of least resistance.

### Off the hard disk — the simpler path

`docs/testing/extract_results.py` reads the results straight out of `hdd.img`
host-side: it parses the qcow2 (no `qemu-img` needed), walks the FATX
filesystem on the E: partition, and writes the files out flat, in the same
`Suite name::Test.png` shape the FTP upload produces, so `collect_results.py`
consumes it unchanged.

```sh
adb pull /sdcard/Android/data/<pkg>/files/x1box/hdd.img
python3 docs/testing/extract_results.py hdd.img -o ./ftpdump
```

**The results directory accumulates across runs**, so `--newer-than` takes a
cutoff and extracts only files written after it. Note the guest clock is offset
from host time — take the cutoff from the image's own newest timestamp before
the run, not from the host clock.

This makes networking optional. The FTP route below still works, but it needs
the emulator's own networking switch enabled (Settings -> Online / Insignia),
and with it disabled the guest hangs indefinitely at "Initializing network..."
rather than failing.

The original note on this section follows; the machinery it describes is what
`extract_results.py` was built from. `e:` lives at offset `0xABE80000` in the image
(`android/app/src/main/cpp/xemu_hdd_tools_jni.c:88`), and a complete FATX
implementation with directory walking and cluster chains is already in-tree at
`android/app/src/main/cpp/xemu_fatx_import.c` — its public surface is
dashboard-specific, but the machinery under it is not. Settings can export the
image (`hdd.img`, qcow2 or raw), so a host-side extractor is also possible.
Either would be a contained, useful change.

## Comparing against hardware

`compare.py` discovers results by walking a directory: the leaf directory names
the suite, the PNG names the test. The uploads arrive flat, so
`collect_results.py` rearranges them:

```sh
python3 docs/testing/collect_results.py ./ftpdump \
    -o local/results --run-id hakuX-0.3.3-j1/Android_arm64/vk_Adreno_740
```

Then, from a checkout of `xemu-nxdk_pgraph_tests_results`:

```sh
python3 -m venv .venv
.venv/bin/pip install -r dev_scripts/requirements.txt
.venv/bin/python3 dev_scripts/compare.py \
    local/results/hakuX-0.3.3-j1/Android_arm64/vk_Adreno_740 -o local/compare
```

Omitting `--against` compares to the hardware goldens, which is the comparison
that matters. `perceptualdiff` must be on `PATH`. The `--run-id` is only a
label, but it is the label that ends up in the report, so name the driver in
it: which driver produced a result is half the finding.

Do not use `dev_scripts/generate_local_site_for_custom_xemu_build.sh` — it
builds and launches a desktop xemu binary, and its `stat -f` is macOS-only.

## What is verified and what is not

Verified here, against the real artifacts:

- The configured image round-trips. Every one of the 31 entries in the stock
  image is byte-identical afterwards, exactly one is added, and a kernel-style
  tree descent resolves it case-insensitively.
- Every key the generated config emits is a key `runtime_config.cpp` actually
  parses. Unknown keys are ignored silently, so a typo would have cost a run.
- `collect_results.py` output feeds the real comparator: a sample rebuilt into
  upload form and passed back through `ResultsInfo` matched its goldens 48 of
  48, with nothing unmatched, and the run identifier parsed as intended.

Verified on device since: the suite runs to completion on a Retroid Pocket
Nova (Adreno 740, Vulkan), 3,132 tests in about 4m20s, and the results have
been compared against the hardware goldens. See `KNOWN_ISSUES.md` for what that
comparison found, and the corrections below for where this document was
wrong.

## The experiment worth running first

This build already supports loading a custom Adreno driver
(`GpuDriverHelper`, via `libadrenotools`). With the suite running, compare
three ways:

- Stock Qualcomm driver against goldens
- A Turnip build against goldens
- The two drivers against each other

Output differing **between drivers** is a driver bug. Output identical between
them but diverging **from the goldens** is this emulator's translation of NV2A
state into Vulkan. Those two are routinely conflated and the distinction
decides who can fix a given fault.

Nobody has published NV2A accuracy figures for an ARM Xbox emulator, per driver
or otherwise.

## What this cannot catch

Framebuffer comparison sees rendering divergence. It is blind to the timing and
interrupt-ordering class of bug — a hang passes every pixel test it never
reaches. [`../investigations/freeze-analysis.md`](../investigations/freeze-analysis.md)
documents one such freeze, chased through
thirteen eliminated hypotheses without a fix. That needs a different oracle:
a deterministic trace of the interrupt, PFIFO and VBLANK event stream, diffed
between desktop xemu and this build. See `ROADMAP.md` item 5.
