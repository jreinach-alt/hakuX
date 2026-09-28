# Audit pass 2: PR #542, lane/usbdialog

Head verified: db0f71230e. Remediation for pass 1: db0f71230e (`soak_title.sh`,
`selftest.d/99-usb-dialog.sh`, `docs/lanes/usbdialog/NOTES.md`).

Result: **clean → fold-ready.** The pass-1 MEDIUM scenario no longer reaches
the route. One narrow residual window stays open until the host timer is
retired. It is recorded below as a LOW.

## MEDIUM 1 (a stray BACK pauses hakuX and the route plays into the menu): closed

Pass-1 scenario, forward order: another actor closes the dialog between
`usb_dialog`'s read and our BACK. Our BACK then reaches hakuX and opens the
pause menu. Now, after any dialog BACK (`back=1`), `fg_wait` no longer returns
on the first `in-front` read. It calls `fg_unpaused`, and that function reads
`PauseMenuOverlay{<hash> <vis>` from `dumpsys activity top`:

- `G`/`I` (not shown): the route starts.
- `V` (shown): one BACK goes to hakuX, and the overlay is read again. If it is
  no longer shown, the route starts. If it is still shown or unreadable, the
  soak aborts with `ROUTE ABORTED: not foreground (hakuX-paused)` and sends no
  route input.
- no line: the soak aborts and sends no route input.

I checked this against the app, not just the fixture. `MainActivity.kt:317,356`
constructs `PauseMenuOverlay` and adds it to `mLayout` once. Its constructor
sets `visibility = View.GONE` (`PauseMenuOverlay.kt:30`), and `show`/`hide`
only toggle `VISIBLE`/`GONE` (`:72`, `:76`). So the view is always in the
hierarchy, and View.toString's first flag character is its visibility. The
normal case reads `G` and plays; it does not fall into leg (f)'s abort.
`togglePauseMenu` runs on BACK DOWN (`MainActivity.kt:386-387`), so the
resume BACK is the correct inverse.

Pass-1 scenario, reverse order: the soak closes the dialog, then the timer's
BACK (read earlier) reaches hakuX. After its BACK, the soak sleeps `FG_POLL_S`
(default 2 s). It then runs `hakux_in_front`, and only then does the pause
read. A timer BACK that was read before our dispatch and landed within about
2 to 2.5 s shows up as `V`, and the soak resumes it. See the LOW below for
the window that is left.

NOTES claim: "do not fight each other" is gone. NOTES now says that two
dismissers can fight, and that the timer should be retired when this folds
(hostops: stop and disable `hakux-usbdialog.timer`).

Selftest, run here: `SELFTEST_ONLY=99-usb-dialog` gives 9 passed, 0 failed.
Legs (a) through (f) are green. The BACK mutant turns (a) red, and the
pause-check mutant turns (d) red (`backs=1 PAUSED`).

## LOW 1 (pass 1): closed

`usb_dialog`'s re-read now uses `ADB_RETRIES=1 adb_call "${ADB_QUICK_TIMEOUT:-10}"`,
and so does `hakux_paused`.

## LOW 2, LOW 3 (pass 1): unchanged, accepted

The full `dumpsys input` pull runs at most once per wait. The fragment has no
shard weight: it measured 15 s here, and the partition guard covers it.

## LOW (residual): a timer BACK slower than the soak's pause read

This window stays open while `hakux-usbdialog.timer` runs. Failure scenario:
the timer reads the dialog just before the soak's BACK, but its own BACK
dispatches more than about 2.5 s later, because app_process start is slow on
a loaded or hot device. That is after `fg_unpaused` has read `G` and the route
has started. hakuX is then paused during the route, and nothing sees it.
`fg_watch` reads focus, not the overlay. This needs a replug during a soak's
wait, a timer firing within that second, and an `input` start of more than
2 s, so it is LOW. The remedy is the one NOTES already names: retire the
timer when this folds. That is a host action for hostops, not a change on
this branch.
