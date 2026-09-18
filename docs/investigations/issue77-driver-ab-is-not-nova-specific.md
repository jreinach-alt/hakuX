# #77's driver A/B was never Nova-specific, and the two handhelds ship the same stock driver

Checked 2026-09-18 by `lane.nova54`, the morning both handhelds returned to
service. **No emulator run, no soak, no build** -- two read-only `adb` queries
and the results already on disk.

## The claim under test

The Nova's archived hold note, `$DISPATCH_DIR/hold/lifted/nova.why.*`, is the
only place #77's harness was written down, and it says:

> Blocked on its return, and NOT dispatchable this session: #54 (the Galleon
> `--perflog` survey) and #77 (the T30/T26/Qualcomm driver A/B, harness
> `~/hakux-work/drv/swap_driver.sh` -- `driver_ab.sh` cannot be used).

The lifting README repeats it: *"Both are now dispatchable for the first time
since 2026-09-13."* The harness detail is correct and worth keeping --
`swap_driver.sh` pushes `meta.json` + `vulkan.purple.so` into
`files/gpu_driver/` through `run-as`, and its `SERIAL` does default to the
Nova's `ee317437`, which is presumably where the Nova association came from.

**The blockage is false, on three independent counts, and `[issue.77]` had
already corrected the first one.**

## 1. The A/B already ran -- on the Thor

Four arms at `c866527e03`, 180 s each, all with `device_label: thor`:

| arm | result dir | driver |
|---|---|---|
| T30a (survey) | `1789363404-galleon77-survey-3334081` | Turnip T30 |
| T30b | `1789364165-galleon77-t30b-3548320` | Turnip T30 |
| T26 | `1789364831-galleon77-t26-3691881` | Turnip T26 |
| stock | `1789365054-galleon77-stock-3695896` | Qualcomm |

Drivers were verified on-device by payload size (18,869,912 against
18,138,081, since T30 and T26 ship the same `vulkan.purple.so` filename) and
by counting `Loading custom Vulkan driver` lines -- zero for stock, exactly
one per Turnip arm. `[issue.77]`'s `blocked_on` records all of it, including
the outcome: **the artifact did not appear in any arm**, V0 failed on both T30
runs, and those arms are therefore **void by the registration** rather than by
later judgement. So the device was never the constraint, and the work the hold
note said was waiting had in fact been done the day after the note was
written.

## 2. The two handhelds ship a byte-identical stock driver

This is the one thing that could have made a Nova re-run of the **stock** arm
a different measurement, and it does not:

```
bdc158a5  AYN Thor              qti/kalama/kalama:13/TKQ1.231222.001/eng.Thor.20260206.163241
ee317437  Retroid Pocket Nova   qti/kalama/kalama:13/TKQ1.231222.001/eng.RPN.20260722.081626

both:  Adreno (TM) 740, OpenGL ES 3.2 V@0676.53
       (GIT@69e13475cb, I1df7ad3aa9, 1703680572) (Date:12/27/23)
```

Same SoC, same kalama base build, **same driver build string down to the git
hash and the timestamp**. Only the vendor's own build stamp differs. So no arm
of a T30 / T26 / Qualcomm comparison can differ by device: the Turnip arms are
pushed files, identical by construction, and the stock arm is the same driver.

This is the pattern `[issue.54]` already recorded against itself -- *"nobody
ran the one read-only `ls` the function was written to make cheap"*. Here it
is two `getprop`s and a `dumpsys SurfaceFlinger`, and the whole
device-specificity claim falls to them.

## 3. The remaining obstacle is the workload, and it is device-independent

`[issue.77]` and
[`galleon-soak-scene-segments.md`](galleon-soak-scene-segments.md) already
settled this: the blocker's stated mechanism (scene cuts set the bar) is
**refuted**, and what remains is **signal**. An unattended soak renders the
Galleon attract demo, whose ground band reads HF median **0.54-0.70** against
a parked deck's **1.95-3.53** -- three to five times less texture detail under
the bar -- in shots averaging 8.6-12 s with 15-21 cuts per 180 s.

A soak cannot park a camera on either handheld. Nothing about the Nova
changes the content the attract demo renders, so a Nova re-run inherits the
same 25-75% detection efficiency and the same V0 gate that already failed.
**There is no Nova arm that discriminates**, and queueing one would spend
device time to reproduce a null.

## What DID change with the return to service: the Thor's dialog is gone

`[issue.77]` left one live conditional:

> THE OWNER ACTION THIS ISSUE WAS WAITING ON IS WITHDRAWN 2026-09-18. [...]
> **Re-raise the tap only if the handheld returns to service WITH that dialog
> still up.**

It has returned, and the dialog is **not** up. `dumpsys window` on
`bdc158a5` shows no USB confirmation window and no `Usb*Activity` in the
activity stack; focus is the emulator on `primaryScreenTopLayout` with
`com.android.launcher3.secondarydisplay.SecondaryDisplayLauncher` on the
second display. The Nova shows no such dialog either.

So **the condition is not met and the owner tap should not be re-raised.**

What that buys, stated as a bound rather than a rescue: the dialog occluded
rows 275..747 / columns 372..1547 -- 36% of the guest frame, the whole centre
-- at a 0.40 scrim. Removing it returns that region and removes the dim from
absolute HF. It does **not** move the 25-75% detection-efficiency bracket,
which comes from the unknown upscale filter and the founding capture's 2x
nearest upscale, and it does **not** park the camera. The route is still the
marker-file-armed frame dump, which does not exist, must dump **without** the
per-draw `pgraph_vk_finish` or it inherits the diag capture's blindness to
merging and barriers, and needs a source grant no lane holds.

## What could not be closed

  * **The capability gap is unchanged.** `nv2a_dbg_trigger_diag_frames` is
    still reachable only from the Debug Capture button and
    `LauncherActivity` still reads only `rom_path`. That is the work, it is a
    source change, and this lane holds no files.
  * **The Thor's screen fault** is visible in the window dump as a
    primary/secondary display split. Not investigated -- it is the owner's,
    and the owner has declared the device available.
