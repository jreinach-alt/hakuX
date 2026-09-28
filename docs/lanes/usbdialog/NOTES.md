# lane.usbdialog

The soak's foreground wait dismisses a replugged handheld's "Use USB for" dialog.

## The defect

2026-09-27 22:30 PDT: after a charge top-up replug, both handhelds raised the
"Use USB for" dialog, a bare system-alert window (`bebf6bb com.rp.settings` on
the Nova, `com.odin.settings` on the Thor) holding input focus on display 0
over hakuX. soak_title.sh's foreground wait re-issued `am start`, which cannot
close a system alert, and aborted ("ROUTE NOT PLAYED"). Every queued request
on the device aborted the same way until someone pressed BACK.

## The change (docs/testing/soak_title.sh)

`usb_dialog()` answers the package when `hakux_in_front` says a package from
`USB_DIALOG_PKGS` (com.rp.settings, com.odin.settings) "holds input focus on
display 0", AND a second read of `dumpsys input` (live block only; it stops at
the last-ANR snapshot like devices.sh does) shows display 0's focused window
named exactly `<hex> <pkg>`, with no `/`, so it is not an activity.
`hakux_in_front` keeps only the owner package, so the second read is the only
way to see the `/`; devices.sh was not granted.

`fg_wait` sends `input keyevent KEYCODE_BACK` once per wait when that holds,
logs `FOREGROUND: dismissed <pkg> dialog (KEYCODE_BACK)`, sleeps one poll and
re-checks. The BACK comes at first sight, before the `am start` remedy. If
the dialog survives, the existing remedy and abort run unchanged. `fg_watch`
(while the route plays) sends nothing.

The read and the BACK are two adb calls, and Android delivers a key to
whatever holds focus at dispatch. If anything else closes the dialog in that
gap (a person, or the host timer below), our BACK reaches hakuX, whose BACK
opens its pause menu: emulation paused, the overlay a view in hakuX's own
window, so `hakux_in_front` still reads in-front (pass-1 MEDIUM 1). So after a
dialog BACK, once hakuX is in front, `fg_unpaused` reads the
`PauseMenuOverlay{<hash> V|G|I...` line of `dumpsys activity top` (the app is
not minified, so the class name holds). Shown: ONE BACK, now to hakuX,
resumes it and is re-read. Still shown, or no overlay line at all: abort,
`ROUTE ABORTED: not foreground (hakuX-paused)`, no route input. Both reads
now use `adb_call` with the quick timeout (pass-1 LOW 1).

## The proof (selftest.d/99-usb-dialog.sh), all green locally

| leg | focused window on display 0 | BACK closes it | result |
|---|---|---|---|
| (a) | `bebf6bb com.rp.settings` | yes | route plays, 1 BACK, dismissed line, no remedy |
| (a') | `4e5f60 com.odin.settings` | no | exit 5, 1 BACK (not a stream), 1 remedy |
| (b) | `com.odin.settings/...UsbModeChooserActivity` | - | exit 5, 0 BACK |
| (c) | `9a8b7c com.example.overlay` | - | exit 5, 0 BACK |
| (d) | another actor closes it between our read and our BACK | - | our BACK pauses hakuX; 1 more BACK resumes; route plays unpaused |
| (e) | as (d), the resume BACK leaves the menu shown | - | exit 5, 2 BACK, no route input |
| (f) | no PauseMenuOverlay line after the BACK | yes | exit 5, 1 BACK, no route input |
| mutant | (a) with the BACK line removed | - | (a) goes red: rc=5, backs=0 |
| mutant | the pause check skipped | - | (d) goes red: backs=1, route starts paused |

No leg sends keyevent 96. 99-display-covered.sh still passes (23/23), and
`--check-shards 4` covers all 96 fragments.

## For the next lane

- No device run was made; the real dialog needs a replug to raise. The first
  soak after the next replug is the field check: grep its run.log for
  `FOREGROUND: dismissed`, and for `hakuX's pause menu state is unreadable`,
  which would mean the overlay read does not match the device's view dump.
- The host-side interim (host-tools/usb_dialog_dismiss.sh on
  hakux-usbdialog.timer) is a second dismisser, and two dismissers CAN fight:
  each reads then sends BACK, so one BACK can land on hakuX after the other
  closed the dialog. The soak now catches that in its wait (above), but the
  timer can also pause hakuX mid-route if its read-then-BACK straddles a
  dismissal that happens outside the soak's wait. Retire the timer when this
  folds (hostops: stop and disable hakux-usbdialog.timer).
- The fragment has no weight in selftest.sh's shard table (not granted); it
  measured 17 s alone.
