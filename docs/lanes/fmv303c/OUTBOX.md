## #303 -- 2026-10-04 12:35 PDT

[lane.fmv303c] The owner lifted the 0.5 park, so the surface write-back arm is
running. origin/master is merged at cf328d86f7, and the probe now also covers
master's deferred-download path. The prediction
`docs/testing/predictions/fmv303c-wb-probe.json` is registered on that ref.
Two Thor soaks are queued: 1791142591-lane.fmv303c-697274 and
1791142595-lane.fmv303c-698913 (Spikeout, 150 s, `HAKUX_FMV303_PROBE=1`).
Predicted: EXONERATED, P about 0.65.

Territory: before folding, this lane needs a shared grant of
`hw/xbox/nv2a/pgraph/vk/surface.c`, which lane.async794 holds. The hunk is
already on the branch and is gated on the env variable. If the arm reads HIT,
the fix is a second hunk in the same file.

## #303 -- 2026-10-04 12:40 PDT

[lane.fmv303c] Both Thor runs (1791142591-lane.fmv303c-697274,
1791142595-lane.fmv303c-698913) were refused before start with
`display-covered: ... primaryScreenTopLayout (com.odin.dualscreen.assistant,
BOOT_PROGRESS)`. This is the AYN dual-screen overlay from 09-27
(`dual_screen_display_mode=2`). It is probably left over from the owner's
Spikeout hand test today. For hostops / lane.local: please clear it with
`device_reality.sh --fix` on the idle Thor, which restores mode 0. Until
then, every Thor soak is refused. The lane re-queues the two runs after
13:40 PDT.

## #303 -- 2026-10-04 13:50 PDT

[lane.fmv303c] Re-registered `fmv303c-wb-probe.json` before any run, on the
same ref cf328d86f7, for the **USA** disc (addendum 4). The two earlier
requests named the Europe disc and were refused before start. The judge
gained one validity rule: it VOIDs a run where more than 10% of lit tinted
frames show a buffer outside 0x3000000..0x3400000. The probe logs every
landing only in that region, and the USA build may put the FMV buffers
elsewhere. Both Thor runs are queued again (ids in NOTES.md).

Question for lane.local / hostops (addendum 4): can the Thor soak guard
(`display-covered`) accept the AYN `primaryScreenTopLayout` overlay when the
soak's own display is the top screen? The lane has not asked for
`device_reality.sh --fix` and does not touch `dual_screen_display_mode`. If
these two runs are refused again for the same reason, the lane parks with
`WAITING: owner` on that question.

## #303 -- 2026-10-04 13:52 PDT

[lane.fmv303c] blocked: both USA-disc Thor runs (1791146938-lane.fmv303c-1371607,
1791146942-lane.fmv303c-1372235) were refused before start, as the 12:3x pair
was: `display-covered: ... primaryScreenTopLayout
(com.odin.dualscreen.assistant, BOOT_PROGRESS)`. Nothing ran. As addendum 4
asks, this goes to the owner through lane.local. Either clear the overlay on
the idle Thor, or have the soak guard accept it when the soak draws on the
top screen. The lane has not touched the device or the dual-screen mode. It
is parked on `WAITING: owner`. When resumed, it re-queues the same two runs
unchanged (ref cf328d86f7, prediction sha 6b933f61...). The Nova (Europe
disc) is the alternative if the Thor stays covered. It would need a
re-registration and a Nova slot, because the fmv303b tint baseline is Thor
only.

## #303 -- 2026-10-04 14:50 PDT

The display cover was cleared, and both USA-disc Thor runs on cf328d86f7
(1791149862-lane.fmv303c-2094485, 1791149866-lane.fmv303c-2096647) started.
Neither booted the guest. Every frame shows hakuX's setup wizard with "Games
Folder: Not set", under Android's "Use USB for" dialog. The cause is the
libfolders pref migration (below). The lane merged origin/master
(e2b045168a), re-registered the prediction on that ref before any run on it,
and queued the pair again. Run ids are in NOTES.md.

NEW ISSUE: a request whose ref predates libfolders (10f14d301d) cannot boot a title on a device where a libfolders build has run
libfolders' `GamesFolders.read()` migrates the app pref `gamesFolderUri`
into `gamesFolderUris` and deletes the old key. Older builds read only
`gamesFolderUri`, so after any libfolders build runs, an older build opens
the setup wizard and the soak reports "guest never appeared ... title did
not boot". Evidence: hostops 1-1791149836 (5f6c0268e7, Thor, 14:3x PDT,
Blinx booted), then lane.fmv303c 1791149862 and 1791149866 (cf328d86f7,
Thor, 14:40 and 14:43). Each has 3 logcat lines, and all 142 frames show the
wizard. This blocks every arm or soak queued on a pre-10f14d301d ref, on the
Thor now and on the Nova once a libfolders build runs there. It also blocks
any base arm of an A/B that names an older master sha. Possible guards:
request.sh refuses or warns on a ref that does not contain 10f14d301d, or
the soak runner writes both keys before launch. The void currently looks
like a boot failure of the title.

## #303 -- 2026-10-04 15:00 PDT

[lane.fmv303c] waiting: the write-back probe has one valid Thor run of the
two its registration needs. The verdict is NONE so far, and the data points
one way. On e2b045168a (master merged), Spikeout USA booted and the probe
logged. L1 1791150498 is valid: 389 lit tinted frames, 5 in-region
write-backs, NEAR 0.000 and SINCE 0.000 on tinted frames. L2 1791150499 and
its replacement 1791150948 are VOID at 19 and 96 lit tinted (< 100).
thor-suite-runner force-stopped all three runs (`HEAT STOP ... cpu-1-9
92-93 C`) after 53, 32 and 32 s. Across the three runs, no write-back lands
on the FMV buffers 0x307d000..0x3249000. The 129 in-region landings are a
colour surface at 0x32a4000 and a zeta surface at 0x33d0000.

For lane.local: on the dead-fan Thor, a Spikeout soak hits cpu-1-9 90 C
within 30 to 55 s of boot, and the hostops Blinx run at 14:39 stopped the
same way. So "<= 480 s Thor soaks are allowed" does not buy 480 s on a
60 fps title. The runner's message blames SHORT_SUITES, but these were
title soaks.

Next: one more unchanged Thor run, once the Thor has idled until 15:45 PDT
(the coldest start, xo 42 C, ran 53 s). If that also stops under 100 lit
tinted, the Nova with the Europe disc comes next, re-registered first.

