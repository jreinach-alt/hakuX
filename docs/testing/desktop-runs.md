# Running the pgraph suite without the handheld

The suite normally needs a device. It does not have to. This records a run that
completed on a stock Linux container with a software GPU, in **18 seconds**,
producing a capture **bit-identical** to the hardware golden.

That does not replace the Nova — see the limits at the end — but it means one
suite can be iterated on twenty times without touching hardware, and it is the
path towards running the suite in CI.

## What it needs

| | |
|---|---|
| Desktop build | `configure --target-list=i386-softmmu --extra-cflags=-DXBOX=1`; deps are listed in [`.github/workflows/desktop.yml`](../../.github/workflows/desktop.yml) |
| Software Vulkan | `mesa-vulkan-drivers` provides lavapipe, a conformant Vulkan 1.4 device. **Note:** writing `renderer = "VULKAN"` into `xemu.toml` does not currently select it — runs come up on OpenGL. Check the `nv2a: renderer:` line in the log before believing a run exercised Vulkan. |
| A virtual display | `xvfb-run`. SDL's `offscreen` driver cannot create a Vulkan surface |
| MCPX + flash ROM | yours; the project ships none |
| A hard disk | generated — [`../../tools/make_xbox_hdd.py`](../../tools/make_xbox_hdd.py) |
| The test ISO | `nxdk_pgraph_tests_xiso.iso`, unconfigured |
| Goldens | `abaire/nxdk_pgraph_tests_golden_results` |

**The BIOS will not boot a disc without a hard disk.** With none attached the
console POSTs to the multilingual "Your Xbox requires service" screen and never
looks at the DVD. A *blank* disk is enough, and blank is all
`make_xbox_hdd.py` makes — no Microsoft content, 124 KiB on disk for a 7.45 GiB
image.

**Use qcow2, not raw.** With a raw image QEMU probes the format and prints

    WARNING: ... probing guessed raw ...
    write operations on block 0 will be restricted

and the guest's writes do not land, so the run completes and extracts nothing.
`qemu-img convert -f raw -O qcow2` after generating.

## The loop

```bash
# 1. a blank disk, once
tools/make_xbox_hdd.py hdd.img --force
qemu-img convert -f raw -O qcow2 hdd.img hdd.qcow2

# 2. a disc that runs exactly one test
mkdir -p empty-results disc
docs/testing/make_isolation_discs.py /dev/null \
    --results empty-results --goldens /path/to/goldens/results \
    --base nxdk_pgraph_tests_xiso.iso --out-dir disc \
    --build-one "Image_blit::ImgBlt_SRCCOPY_XRGB_B00000000"
# prints {"guest_dir": "<tag>", ...} - keep the tag, results land in e:/<tag>

# 3. run it. exit 0 means the guest powered off, i.e. the suite finished
SDL_AUDIODRIVER=dummy xvfb-run -a --server-args="-screen 0 640x480x24" \
    timeout -k 5 420 ./qemu-system-i386 -machine xbox -display none

# 4. extract and compare
docs/testing/extract_results.py hdd.qcow2 -o out -d <tag>
docs/testing/diff_specimen.py -o cmp.html \
    --goldens /path/to/goldens/results --results out --all-differing
```

`~/.local/share/xemu/xemu/xemu.toml` needs `show_welcome = false`. Leave it
true and `-bios` is never added to the command line - `system/vl.c:3057` skips
it on first run so the user can set paths - and the machine comes up with no
BIOS, which reads like a missing file rather than a deliberate guard.

**Take the test name from the goldens directory, not from an issue.** Issue #7
refers to `ImgBlt_SRCCOPY_XRGB`; the real name is
`ImgBlt_SRCCOPY_XRGB_B00000000`. A name the XBE does not know is silently
ignored, `skip_tests_by_default` leaves nothing enabled, and the log says
"Testing completed normally" having run nothing at all.

## What this cannot tell you

**It is not the shipping renderer's driver.** Adreno and lavapipe are different
implementations. A difference seen here and not on the Nova, or the reverse, is
a driver difference until proven otherwise.

**lavapipe lacks `VK_KHR_external_semaphore_fd`.** The xemu UI presents a
Vulkan frame by importing it into GL through external memory, so `-display xemu`
is unavailable here and runs are headless. Any test path that depends on GL/VK
interop will behave differently.

**No screenshots of the UI.** Xvfb has a window but its GLX cannot give the
GL 4.0 the UI wants; SDL's offscreen driver gives GL 4.5 but has no window.
The suite's own framebuffer captures are unaffected - they are what
`diff_specimen.py` reads - but watching a run happen is not currently possible.

**The GL renderer aborts early.** `nv2a: unimplemented color surface format
0x7` kills a run within seconds of the suite starting, so only Vulkan is usable
here today. That is a real defect, not an environment problem - see the
unmapped-format `abort()` in
[`../investigations/nv2a-sweep-2026-09.md`](../investigations/nv2a-sweep-2026-09.md).

**Timings from the guest are wrong.** The progress log reported a completed
test as taking `-25027ms`. Wall-clock timing of the whole run is trustworthy;
the guest's own figure is not.

## First result

```
Starting [1/1] Image blit::ImgBlt_SRCCOPY_XRGB_B00000000
  Completed [1/1] 'ImgBlt_SRCCOPY_XRGB_B00000000' in -25027ms
Testing completed normally, closing log.

nothing to show — every test compared is bit-identical
```

Boot, one test, power-off and extraction in 18 s wall clock, on
`0.3.3-j1-70-g92dcf54`, Vulkan on llvmpipe.
