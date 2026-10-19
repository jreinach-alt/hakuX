# fpsdiag1018: what to run during the next GTA III / Blinx 2 / Fable session (#433)

For whoever is holding the device (Nova `ee317437` or Thor `bdc158a5`) while one of these three titles is
being played, not for the owner to type. The owner only ever plays; nothing here touches input, launches,
force-stops, or navigates -- that is `hold.sh`'s own `owner-play*` rule
([[owner-play-attach-never-launch]]), unchanged by this lane.

## Why this is short

`fpsdiag.py analyze` already has four real captures to work from (FINDINGS.md section 4) and does not need a
new owner-play session just to exist. The one thing nothing on disk has yet is the periodic OS-level sampling
(`dumpsys cpuinfo`, `/proc/meminfo`, `/proc/<pid>/task/*/stat`, `dumpsys SurfaceFlinger`) that candidates
c4/c5/c6/c8 need and no logcat tag can ever carry (FINDINGS.md section 4's last paragraph, `gaps`'s six named
gaps). So: the next time any of these three titles is already being played, for any reason, run the one extra
command below alongside it. No session needs to be requested or scheduled for this alone.

## 1. Before anything: confirm the real driver

`adb -s <serial> logcat -d | grep -F 'Driver: PurpleVK'` -- if this is empty, stop
([[never-use-or-test-the-stock-driver]]). A run on the stock driver is void for every candidate in FINDINGS.md.

## 2. Take the hold the normal way -- it starts the logcat capture for you

```
docs/testing/jobs/hold.sh take <nova|thor> owner-play.fpsdiag1018-<title> "owner playing <title> (#433 fpsdiag1018)"
docs/testing/jobs/hold.sh wait-idle <nova|thor> 900
```

An `owner-play*` tag makes `take` start the capture itself (`adb logcat -v threadtime` at the dispatcher's own
`LOGCAT_SPEC`, a transient systemd unit that outlives this shell) and print where it is writing:
`$DISPATCH_DIR/../captures/owner-play-<YYYYMMDD>/logcat-<label>-<HHMMSS>.txt`. If `take` instead prints
`NO CAPTURE: ...` and exits 6, the hold was refused on purpose -- do not take it by hand instead; that is the
exact failure this mechanism exists to prevent ([[owner-hold-means-capture-running-first]]). Note the path it
prints; that is the file `fpsdiag.py analyze` reads afterward.

## 3. Also run this, for the whole length of the session -- the one new thing

`fpsdiag.py capture` is the only thing that produces the periodic samples c4/c5/c6/c8 need. It also starts its
own second `adb logcat`, which is harmless (logd supports more than one reader) but redundant with step 2's --
use step 2's file for `analyze`, this command's `samples/periodic.ndjson` for the rest:

```
python3 docs/testing/perf/fpsdiag/fpsdiag.py capture \
    --serial <serial> --title "<GTA III | Blinx 2 | Fable>" \
    --seconds <expected play length, seconds> \
    --out /home/justin/hakux-work/captures/fpsdiag1018-<title>-<YYYYMMDD> \
    --pid <the title's pid, if known -- `adb -s <serial> shell pidof com.rfandango.haku_x` while it's running>
```

Run it in the background (`setsid nohup ... &`, log redirected) from whichever session is holding the device,
and let it run for the session's real length -- `--seconds` is a loop bound, not a timer to babysit. Stopping
it early just ends the periodic sampling early; it is not a failure.

## 4. When the session ends

Release the hold (`hold.sh release <nova|thor> owner-play.fpsdiag1018-<title>`), then score it:

```
python3 docs/testing/perf/fpsdiag/fpsdiag.py analyze <step 2's logcat-....txt> --title "<title>"
python3 docs/testing/perf/fpsdiag/fpsdiag.py gaps <step 2's logcat-....txt> --title "<title>"
```

If `gaps` still names c4/c5/c6/c8 after this, read `--out`'s `samples/periodic.ndjson` directly -- those four
candidates' checks do not read it yet (no capture had one to read when they were written); that is the next
lane's brief, not this one's (FINDINGS.md section 5).

## What this is not

Not a request to go play these titles. Not a request for a specific route, duration, or scene -- whatever the
session is already doing is the capture; a mix of dip and good stretches is only useful in that it is what
real play produces anyway. Not a device hold by itself -- fold this into a hold already being taken for some
other reason, or an owner-play session already happening.
