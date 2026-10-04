# Audit pass 1: PR #542, lane/usbdialog

Head audited: 7fd85c3ad0 (diff against master 548017f7ba). Files:
docs/testing/soak_title.sh, docs/testing/jobs/selftest.d/99-usb-dialog.sh,
docs/lanes/usbdialog/NOTES.md.

Result: **1 MEDIUM, 3 LOW → needs-remediation.**

The gate is sound for what it checks. `usb_dialog` only fires on a
`holds input focus on display 0` line from `hakux_in_front`, for one of the two
vendor packages, and only when a second read of the live `dumpsys input` block
shows a bare `<hex> <pkg>` name for that same package. It fires once per wait
and never in `fg_watch`. The legs cover the dialog, a dialog that survives
BACK, an activity of the vendor package, and another package's bare window.
The mutant removes the BACK and turns leg (a) red. What the gate cannot
cover is the gap between the read and the key.

## MEDIUM 1: a BACK that lands after someone else closed the dialog pauses hakuX, and the route then plays into the pause menu

`fg_wait` does check-then-act across two adb calls: `usb_dialog` reads
`dumpsys input` (soak_title.sh `usb_dialog`), then a separate
`a shell input keyevent KEYCODE_BACK` runs. Android sends a key to whatever
window has focus when the key is dispatched, not to the window that was read.
`input` starts app_process on the device, so the gap between the read and the
dispatch is about 0.5 to 1.5 s.

A second actor closes the same dialog during that gap. NOTES.md ("For the next
lane") tells the lane to keep `host-tools/usb_dialog_dismiss.sh` on
`hakux-usbdialog.timer` (every minute, at :30) until the soak's line has been
seen in a real run. It also says the two "do not fight each other". They can.
The host script does its own check-then-act: `grep mCurrentFocus`, then BACK.

Failure scenario: a handheld is replugged while a soak is in `fg_wait`. At
xx:29.8 `usb_dialog` reads `bebf6bb com.rp.settings`. At xx:30.3 the timer's
BACK closes the dialog, and focus returns to hakuX. At xx:30.6 the soak's BACK
reaches hakuX. `MainActivity.dispatchKeyEvent` handles BACK DOWN with
`togglePauseMenu()`, which calls `nativePauseEmulation()` and shows
`PauseMenuOverlay`. That overlay is a FrameLayout in hakuX's own window, so the
next `hakux_in_front` still reads `in-front`. The route starts: its `press A`
goes to the pause menu and the title stays paused. Nothing logs this; the run
records a paused title as a completed soak. The reverse order fails the same
way: the soak closes the dialog, then the timer's BACK (read before) reaches
hakuX. This is the "input drives the wrong thing" failure that the foreground
wait exists to prevent. It also needs no fault, just two dismissers on a normal
replug. It is bounded (it needs a replug while a soak is in its wait, with the
timer firing within about a second of the soak), so it is MEDIUM, not HIGH.

None of the legs can see this: the fake adb has one dismisser, and its BACK
closes the dialog atomically.

Remedy (any one of these):
- Retire the timer when this folds. Stop and disable `hakux-usbdialog.timer`
  (route that to hostops), and remove "keep it until seen" and "do not fight
  each other" from NOTES.
- Make the host script skip any device whose lease a soak holds, so only one
  actor dismisses at a time.
- After the BACK, confirm that hakuX is not paused before the route starts.
  `hakux_in_front` cannot see this because the overlay is in hakuX's own
  window, so the check would need another signal.

Pass 2 should verify that no path is left where two dismissers can both send
BACK for one dialog, and that the NOTES claim is gone.

## LOW 1: the raw re-read uses the long adb timeout

`usb_dialog` calls `a shell "dumpsys input"`, and `a` uses `ADB_TIMEOUT`
(default 120 s). `hakux_in_front` uses `adb_call` with `ADB_QUICK_TIMEOUT` (10 s)
and one retry. A hung adb holds `fg_wait` for up to 120 s, past `FG_WAIT_S`,
before the remedy runs. The result is late, not wrong, and the soak still
aborts cleanly.

## LOW 2: the second read pulls all of `dumpsys input`

`hakux_in_front` filters on the device with grep. The re-read pulls the whole
dump (the reader and device state included) and filters it on the host. It is
correct, because the awk stops at `  ANR:`. It runs at most once per wait.

## LOW 3: the fragment has no shard weight

The lane says so: `selftest.sh`'s shard table was not granted, and the fragment
takes about 12 s. The partition guard (`--check-shards 4`) covers it. The shard
balance may drift.

## Not findings (checked)

- The ANR snapshot: the fixture puts the dialog in the ANR block too, and the
  awk stops at `  ANR:` or at a second `FocusedDisplayId:`. This matches
  `hakux_in_front`'s live-block rule.
- The regex `^[0-9a-f]+\ ([^/\ ]+)$` rejects `pkg/cls` names, so leg (b) holds.
  The package must equal the owner that `hakux_in_front` reported, so a
  vendor-package match on the second read alone is not enough.
- Only one BACK per wait: `back=1` is set before the key, and a dialog that
  survives it falls through to the unchanged remedy (leg a').
