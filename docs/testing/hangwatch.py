#!/usr/bin/env python3
"""Catch a locked-up title in about HANG_S seconds, and send it for telemetry, instead of waiting out the budget.

    hangwatch.py selftest
    hangwatch.py scan <logcat.txt>...

A HANG is called on either of two arms, each needing all of its signals bad at once for HANG_S seconds. The owner,
2026-10-04: "If the audio isn't changing and the screen isn't, that's a failure that needs investigating with
telemetry, not waiting around."

  still   the screen did not change (pathfind's own changed(), FPS corner masked): frames fed in by frame()
  quiet   the guest's APU made no new non-flat 50 ms window (hakuX-audio "level L" lines; the counter is
          cumulative since boot, so quiet is "the count did not move over one 5 s report"). A frozen title can
          keep emitting a non-flat hum or looping ambience forever, so quiet alone can miss that freeze; that is
          what `stalled` is for.
  pinned  the vCPU is not progressing: [rr425w] idle_us at most IDLE_US, and one (cause, pc) takes at least
          PIN_SHARE of the window's TB returns ([rr425] it, [rr425pc] top entry; accel/tcg/cpu-exec.c)

  pinned arm:   still + quiet + pinned, the rule above.
  stalled arm:  still, and together: the GPU got no new push-buffer work ([hakuX-perf] fifoskew kicks=0), the
                vCPU spun without idling ([rr425w] idle_us at most IDLE_US, the idle0 half of `pinned` without the
                pc-share test), and the PIC raised no disc interrupt ([pic14] raise=0). This is the freeze class
                `quiet` misses: GPU unfed, vCPU spinning, disc silent, whatever the audio is doing.

A signal the log does not carry is unknown, and unknown never confirms a hang: a run with no telemetry is never
called HANG by this module, on either arm. The telemetry tags are the emulator's own (JC425 gate, tag hakuX at W;
[hakuX-perf] fifoskew at I) and the APU's (hakuX-audio at I), so the run's logcat must carry them (pathfind's
LOGCAT_SPEC does).

Thresholds are calibrated on real logcats in docs/lanes/hangwatch/NOTES.md and docs/lanes/hangstall1013/NOTES.md,
not chosen here.
"""

import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time

HANG_S = 90.0       # all of one arm's signals bad for this long: HANG (the start value; the calibration tables are the evidence)
PIN_SHARE = 0.9     # one (cause, pc) takes this share of a window's TB returns
IDLE_US = 50000     # the vCPU idles at most this much of a 2 s window (2.5%)
UNCHANGED = 0.01    # the same "no change" fraction as pathfind.UNCHANGED
RECHECK_S = 20.0    # after the one press before a verdict: this long, with the screen compared again

PIN_NEED = ("pinned", "quiet", "still")
STALL_NEED = ("still", "kicks0", "idle0", "discsilent")
ARMS = (("pinned", PIN_NEED), ("stalled", STALL_NEED))
NEED = PIN_NEED      # back-compat name for the pinned arm's three signals

LINE = re.compile(r"^(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d\.\d+)\s+[VDIWEF]/(\S+?)\s*\(\s*\d+\):\s?(.*)$")
RR = re.compile(r"\[rr425\] w=(\d+) dt=\d+ it=(\d+)")
PC = re.compile(r"\[rr425pc\] w=(\d+)(.*)$")
PCENT = re.compile(r"(\S):([0-9a-f]{8}):[0-9a-f]{6}:(\d+)")
RRW = re.compile(r"\[rr425w\] w=(\d+) idlepc=([0-9a-f]+) idle_us=(\d+) busy_us=(\d+)")
LEVEL = re.compile(r"level L: [\d.]+ s .*? windows (\d+) counted (\d+) flat")
KICKS = re.compile(r"\bfifoskew\b.*?\bkicks=(\d+)")
RAISE = re.compile(r"\[pic14\]\s+win_us=\d+\s+raise=(\d+)")


def parse(line):
    """One `logcat -v time` line -> (t, tag, msg), or None. t is seconds on a month-day-ordered axis (order only)."""
    m = LINE.match(line.rstrip("\r\n"))
    if not m:
        return None
    mo, d, hh, mm, ss, tag, msg = m.groups()
    t = (int(mo) * 31 + int(d)) * 86400 + int(hh) * 3600 + int(mm) * 60 + float(ss)
    return t, tag, msg


class Telemetry:
    """Joins the per-window lines by their w= number: [rr425] gives the returns, [rr425pc] the top pc, [rr425w] the
    idle time. The [rr425w] line closes a window and yields its signal (it is emitted last)."""

    def __init__(self):
        self.it = {}
        self.top = {}
        self.last = None

    def feed(self, t, msg):
        """-> (t, pinned, info) when the line closes a window, else None. pinned is None when the window cannot say.
        info["idle_us"] is always present on a non-None return, whether or not pinned can be judged."""
        m = RR.search(msg)
        if m:
            self.it[int(m.group(1))] = int(m.group(2))
            return None
        m = PC.search(msg)
        if m:
            ents = [(c, pc, int(n)) for c, pc, n in PCENT.findall(m.group(2))]
            self.top[int(m.group(1))] = max(ents, key=lambda e: e[2]) if ents else None
            return None
        m = RRW.search(msg)
        if not m:
            return None
        w, idle_us, busy_us = int(m.group(1)), int(m.group(3)), int(m.group(4))
        it = self.it.pop(w, None)
        top = self.top.pop(w, None)
        share = None
        if top is not None and it:
            share = top[2] / it
        pinned = False                  # an idling vCPU is waiting, not stuck
        if idle_us <= IDLE_US:
            if share is not None:
                pinned = share >= PIN_SHARE
            elif it == 0:
                pinned = True           # no TB returned at all in the window, and the vCPU never idled
            else:
                pinned = None           # busy, but the window has no pc line: it cannot say
        self.last = t
        return t, pinned, {"w": w, "it": it, "idle_us": idle_us, "busy_us": busy_us,
                           "share": None if share is None else round(share, 4),
                           "top": None if top is None else f"{top[0]}:{top[1]}"}


class Audio:
    """The APU's level lines are cumulative; quiet is "the non-flat window count did not move since the last L
    line". A frozen title can still drive the APU with a steady hum or looping ambience -- non-flat forever, so
    its window count keeps climbing -- and quiet never fires for it; that freeze is the `stalled` arm's job."""

    def __init__(self):
        self.active = None

    def feed(self, msg):
        m = LEVEL.search(msg)
        if not m:
            return None
        n = int(m.group(1))
        quiet = None if self.active is None else n == self.active
        self.active = n
        return quiet


def streaks(events, need):
    """events: [(t, signal, value)] in time order. -> [(start, end)] for every stretch in which all of `need` are True.
    A signal not yet reported is not True. An open stretch ends at the last event."""
    state, start, out, last_t = {}, None, [], None
    for t, sig, val in events:
        state[sig] = val
        last_t = t
        ok = all(state.get(s) is True for s in need)
        if ok and start is None:
            start = t
        elif not ok and start is not None:
            out.append((start, t))
            start = None
    if start is not None:
        out.append((start, last_t))
    return out


def scan_events(lines):
    """Offline: the (t, signal, value) events of a logcat's telemetry and audio. `still` is not in a logcat: a run's
    frame changes are in its steps (pathfind's `changed`), so an offline scan without frames is an UPPER BOUND
    for either arm's rule (any stretch shorter than HANG_S ends the hang case; `still` can only shrink a stretch,
    never lengthen one)."""
    tel, aud, events, pinned_info = Telemetry(), Audio(), [], []
    for line in lines:
        p = parse(line)
        if p is None:
            continue
        t, tag, msg = p
        r = tel.feed(t, msg)
        if r is not None:
            tt, pinned, info = r
            events.append((tt, "idle0", info["idle_us"] <= IDLE_US))
            if pinned is not None:
                events.append((tt, "pinned", pinned))
                pinned_info.append((tt, info))
        q = aud.feed(msg)
        if q is not None:
            events.append((t, "quiet", q))
        m = KICKS.search(msg)
        if m:
            events.append((t, "kicks0", int(m.group(1)) == 0))
        m = RAISE.search(msg)
        if m:
            events.append((t, "discsilent", int(m.group(1)) == 0))
    return events, pinned_info


def scan(lines):
    """Offline summary of one logcat: the longest stretch of pinned, quiet, pinned+quiet, and the stalled arm's
    three signals together (seconds). `stalled` here has no `still`, same upper-bound caveat as `pinned+quiet`."""
    events, _ = scan_events(lines)
    longest = {}
    for name, need in (("pinned", ("pinned",)), ("quiet", ("quiet",)), ("pinned+quiet", ("pinned", "quiet")),
                       ("stalled", ("kicks0", "idle0", "discsilent"))):
        ev = [e for e in events if e[1] in need]
        spans = streaks(ev, need)
        longest[name] = max((b - a for a, b in spans), default=0.0)
    return longest, events


class Watch:
    """Tails one live logcat and judges HANG on either arm. Telemetry and audio come from poll(); the screen comes
    from frame(), stamped with the device log's latest time (the handheld's clock is the only one the log has)."""

    def __init__(self, path, hang_s=HANG_S):
        self.path, self.hang_s = path, hang_s
        self.off, self.partial = 0, ""
        self.tel, self.aud = Telemetry(), Audio()
        self.state, self.now = {}, None
        self.arm_start = {name: None for name, _ in ARMS}
        self.info = None                # latest [rr425w] window info: the pinned arm's diagnostic
        self.stall = {}                 # latest kicks/idle_us/raise numbers: the stalled arm's diagnostic
        self.proc = None                # the adb logcat that writes `path`, when this Watch owns one

    def frame(self, changed):
        """The screen's change since the last look (pathfind's `changed`); None when unknown. Before the first log
        line there is no clock yet, so the state waits for the first telemetry line to judge it."""
        if changed is None:
            return
        self.state["still"] = changed <= UNCHANGED
        if self.now is not None:
            self._judge(self.now)

    def poll(self):
        """Read what the log grew by; -> a HANG dict the moment either arm has held for hang_s, else None."""
        try:
            with open(self.path, "rb") as f:
                f.seek(self.off)
                data = f.read()
        except OSError:
            return None
        self.off += len(data)
        text = self.partial + data.decode("utf-8", "replace")
        lines = text.split("\n")
        self.partial = lines.pop()
        for line in lines:
            p = parse(line)
            if p is None:
                continue
            t, _tag, msg = p
            self.now = t
            r = self.tel.feed(t, msg)
            if r is not None:
                tt, pinned, info = r
                self.info = info
                self.state["idle0"] = info["idle_us"] <= IDLE_US
                self.stall["idle_us"] = info["idle_us"]
                if pinned is not None:
                    self.state["pinned"] = pinned
                hang = self._judge(tt)
                if hang:
                    return hang
            q = self.aud.feed(msg)
            if q is not None:
                self.state["quiet"] = q
                hang = self._judge(t)
                if hang:
                    return hang
            m = KICKS.search(msg)
            if m:
                self.state["kicks0"] = int(m.group(1)) == 0
                self.stall["kicks"] = int(m.group(1))
                hang = self._judge(t)
                if hang:
                    return hang
            m = RAISE.search(msg)
            if m:
                self.state["discsilent"] = int(m.group(1)) == 0
                self.stall["raise"] = int(m.group(1))
                hang = self._judge(t)
                if hang:
                    return hang
        return None

    def _judge(self, t):
        for name, need in ARMS:
            ok = all(self.state.get(s) is True for s in need)
            if not ok:
                self.arm_start[name] = None
                continue
            if self.arm_start[name] is None:
                self.arm_start[name] = t
            if t - self.arm_start[name] >= self.hang_s:
                window = self.info if name == "pinned" else dict(self.stall)
                return {"hang": True, "arm": name, "since": self.arm_start[name], "tripped": t,
                        "state": dict(self.state), "window": window}
        return None


def start(dev, out):
    """Follow the run's live logcat (the emulator's telemetry tags, pathfind's LOGCAT_SPEC) into out/screen-logcat.txt,
    and return the Watch that judges it. None when the device has no logcat (the dry run). Not logcat.txt: the hold
    path writes that file, and two writers on one file truncate each other."""
    path = os.path.join(out, "screen-logcat.txt")
    proc = dev.logcat_start(path)
    if proc is None:
        return None
    watch = Watch(path)
    watch.proc = proc
    return watch


def close(watch):
    if watch is not None and watch.proc is not None:
        watch.proc.terminate()
        watch.proc = None


def _log(out, rec):
    """out/hang.jsonl: every trip, probe and clearance, timestamped (the one press is logged as a probe)."""
    with open(os.path.join(out, "hang.jsonl"), "a") as f:
        f.write(json.dumps(dict(rec, at=round(time.time(), 1))) + "\n")


def _drain(watch):
    """Read everything the log has grown by, to its end. -> the last HANG dict seen (None when no line tripped)."""
    last = None
    while True:
        r = watch.poll()
        if r is None:
            return last
        last = r


def look(watch, dev, out, changed, diff, title, intake=None):
    """One look. -> the verdict dict when the run is a HANG (telemetry pulled, identification filed), else None.

    `changed` is this look's screen change (None when unknown), `diff(a, b)` the same measure between two frame
    files. A trip is not yet a verdict: ONE A press is sent and logged as a probe, then the screen and the telemetry
    are checked again over RECHECK_S. A press that moves the screen or makes sound ends the streak: not a HANG.
    Whichever arm tripped (`pinned` or `stalled`) is the one re-checked and named in the verdict's reason."""
    if watch is None:
        return None
    watch.frame(changed)
    trip = watch.poll()
    if trip is None:
        return None
    arm = trip["arm"]
    _drain(watch)                       # the log's clock at the press: everything written so far is before it
    if watch.arm_start[arm] is None:
        return None                     # the streak broke before the press: no HANG to confirm
    hd = os.path.join(out, "hang")
    os.makedirs(hd, exist_ok=True)
    before = os.path.join(hd, "probe-before.png")
    if not dev.capture(before):
        return None                     # no frame to compare against: no press, and the next look asks again
    pressed = watch.now
    dev.pad("press", "A", 120)
    _log(out, {"event": "probe", "action": ["A"], "since": trip["since"], "tripped": trip["tripped"],
               "arm": arm, "window": trip["window"]})
    time.sleep(RECHECK_S)
    after = os.path.join(hd, "probe-after.png")
    moved = diff(before, after) if dev.capture(after) else None
    watch.frame(moved)
    again = _drain(watch) if moved is not None else None
    # the verdict needs the telemetry AFTER the press: the streak still holds at the end of the log, and the log
    # has run RECHECK_S past the press. A guest that recovers in that window ends the streak: not a HANG.
    if again is None or watch.arm_start[arm] is None or watch.now - pressed < RECHECK_S:
        watch.arm_start[arm] = None     # the next trip needs HANG_S of its own
        _log(out, {"event": "probe-cleared", "frame_change": moved})
        return None
    dur = again["tripped"] - trip["since"]
    if arm == "pinned":
        reason = (f"HANG: frames still, audio quiet and the vCPU pinned for {dur:.0f} s; one A press changed "
                  f"nothing (frame change {moved:.3f})")
    else:
        reason = (f"HANG: frames still, the GPU unfed, the vCPU never idle and the disc silent for {dur:.0f} s; "
                  f"one A press changed nothing (frame change {moved:.3f})")
    verdict = {"hang": True, "title_id": title[0], "name": title[1], "since": trip["since"],
               "tripped": again["tripped"], "state": again["state"], "window": again["window"], "arm": arm,
               "probe": {"action": ["A"], "frame_change": round(moved, 4)}, "reason": reason}
    _log(out, {"event": "hang", "verdict": verdict["reason"]})
    stop_for_telemetry(dev, out, verdict, intake)
    return verdict


def stop_for_telemetry(dev, out, verdict, intake=None):
    """The telemetry a HANG is judged on, pulled while the device is still up: the logcat tail, the last frames' names,
    the process's CPU, the crash buffer. Then verdict.json and failure_intake.py's identification (class hang)."""
    hd = os.path.join(out, "hang")
    with open(os.path.join(out, "screen-logcat.txt"), errors="replace") as f:
        tail = f.read().splitlines()[-400:]
    with open(os.path.join(hd, "logcat-tail.txt"), "w") as f:
        f.write("\n".join(tail) + "\n")
    frames = sorted(glob.glob(os.path.join(out, "frames", "*.jpg")))[-10:]
    with open(os.path.join(hd, "last-frames.txt"), "w") as f:
        f.write("\n".join(os.path.basename(p) for p in frames) + "\n")
    with open(os.path.join(hd, "dumpsys.txt"), "w") as f:
        f.write(dev.sh("dumpsys cpuinfo | head -40") + "\n" + dev.sh("ps -A | grep -i xemu") + "\n")
    with open(os.path.join(hd, "tombstone.txt"), "w") as f:
        f.write(dev.sh("logcat -b crash -d -t 300") + "\n")
    with open(os.path.join(out, "verdict.json"), "w") as f:
        json.dump(verdict, f, indent=1)
    script = intake or os.path.join(os.environ.get("HAKUX_WORK", "/home/justin/hakux-work"), "host-tools",
                                    "failure_intake.py")
    subprocess.run(["python3", script, "one", out, "--force"], capture_output=True, text=True, timeout=120)


class _FakeDev:
    """The device half the check needs: a press appends the guest's next pinned windows to the log (as a live run
    would), and a capture writes a file. diff() is injected by the caller."""

    def __init__(self, log_path, lines_after_press):
        self.log_path, self.more = log_path, lines_after_press
        self.pressed, self.n = [], 0

    def pad(self, *args):
        self.pressed.append(args)
        with open(self.log_path, "a") as f:
            f.write("\n".join(self.more) + "\n")

    def capture(self, path):
        self.n += 1
        with open(path, "wb") as f:
            f.write(b"%d" % self.n)
        return True

    def sh(self, cmd, timeout=20):
        return ""


def selftest():
    """Real logcat lines (black-stone-hold2, 10-03; Voodoo Vince 10-13; Die Hard: Vendetta 10-12; KOTOR II 10-11)
    and a window built from the brief's Whiteout numbers."""
    fails = []

    def stamp(sec):
        """A logcat -v time stamp `sec` seconds after 13:40:00 on 10-04."""
        m, s = divmod(sec, 60)
        return f"10-04 13:{40 + int(m):02d}:{s:06.3f}"

    def check(name, cond):
        print(("ok   " if cond else "FAIL ") + name)
        if not cond:
            fails.append(name)

    # 1. a real [rr425w] window that idles: 1.6 s of 2 s idle, the top pc is the idle loop, not a pin
    idle_w = ("10-03 11:37:08.833 W/hakuX   ( 6989): [rr425w] w=85 idlepc=8001b02e idle_us=1597916 busy_us=402085 "
              "n=2259 nb=667 drop=0 30.00:1615:1209910:13002:24/1339/252/0:1454/161/0/0:367")
    idle_rr = ("10-03 11:37:08.833 W/hakuX   ( 6989): [rr425] w=85 dt=2000 it=60307381 e=59935073 en=29902825 "
               "es=29898861 eo=129362 et=0 ej=4025 esh=29898861 m=0 o=0 r=616 g=359479")
    idle_pc = ("10-03 11:37:08.833 W/hakuX   ( 6989): [rr425pc] w=85 e:8001b02f:9090fa:29892497 "
               "e:8001b02e:fb9090:29892497 g:000fbffc:e84f8c:345960")
    tel = Telemetry()
    for line in (idle_rr, idle_pc, idle_w):
        p = parse(line)
        r = tel.feed(p[0], p[2])
    check("real idle window is not pinned", r is not None and r[1] is False)
    check("real idle window reports its share", r is not None and r[2]["share"] is not None and r[2]["share"] > 0.4)

    # 2. the Whiteout shape from the brief: one pc takes 2029 of 2057 returns, idle 0, audio and screen flat
    def pinned_window(w, t):
        rr = f"[rr425] w={w} dt=2000 it=2057 e=2000"
        pc = f"[rr425pc] w={w} r:800151ed:faf4eb:2029 e:00176c8c:d92c24:20"
        rw = f"[rr425w] w={w} idlepc=8001b02e idle_us=0 busy_us=2027976 n=2057 nb=0 drop=0"
        return [f"{stamp(t)} W/hakuX   ( 6989): {x}" for x in (rr, pc, rw)]

    def level_line(t, counted):
        return (f"{stamp(t)} I/hakuX-audio( 6989): level L: 100.000 s  peak 10366 (-10.00 dBFS)  "
                f"acrms -32.16 dBFS  dc -0.003 %FS  p5/25/50/75/95 -59/-37/-33/-28/-23  windows {counted} "
                "counted 1488 flat  clipped 0  zeros 3619988  wrap 0  maxjump 1947")

    lines = []
    for k in range(60):           # 120 s of windows, a level line every 5 s
        lines += pinned_window(100 + k, 2.0 * k)
        if k % 5 == 0:
            lines.append(level_line(2.0 * k + 0.5, 1000))
    d = tempfile.mkdtemp(prefix="hangwatch-")
    path = os.path.join(d, "logcat.txt")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(path) as f:
        long_, _ = scan(f)
    check("whiteout shape: pinned for 118 s", long_["pinned"] >= 110)

    w = Watch(path)
    check("whiteout shape with no frame signal: no HANG (unknown never confirms)",
          w.poll() is None and w.arm_start["pinned"] is None)
    w = Watch(path)
    w.frame(0.0)                  # the screen is still, before the log is read
    hang = w.poll()
    check("whiteout shape, screen still, audio quiet: HANG on the pinned arm", hang is not None and hang.get("arm") == "pinned")
    if hang:
        check("HANG trips HANG_S after the streak started", hang["tripped"] - hang["since"] >= HANG_S)

    # 3. the same pinned windows with a screen that moves: the frame signal breaks the streak
    w2 = Watch(path)
    w2.poll()
    w2.frame(0.4)
    check("moving screen is not HANG", w2.poll() is None and w2.state.get("still") is False)

    # 4. audio that keeps producing windows breaks the pinned-arm streak (a wait-for-input load with music is not
    # a hang on that arm; it has no fifoskew/pic14 lines, so stalled cannot fire either)
    lines_a = []
    for k in range(60):
        lines_a += pinned_window(100 + k, 2.0 * k)
        if k % 5 == 0:
            lines_a.append(level_line(2.0 * k + 0.5, 1000 + k))
    path_a = os.path.join(d, "audio.txt")
    with open(path_a, "w") as f:
        f.write("\n".join(lines_a) + "\n")
    w3 = Watch(path_a)
    w3.poll()
    w3.frame(0.0)
    check("audio still producing windows: not HANG", w3.arm_start["pinned"] is None and w3.arm_start.get("stalled") is None)

    # 5. a guest busy over many PCs (a compute load), idle 0, screen and audio flat: not pinned
    spread = []
    for k in range(60):
        spread.append(f"{stamp(2.0 * k)} W/hakuX   ( 6989): [rr425] w={300 + k} dt=2000 it=2057 e=2000")
        spread.append(f"{stamp(2.0 * k)} W/hakuX   ( 6989): [rr425pc] w={300 + k} "
                      f"e:0017{k:04x}:d92c24:300 e:0018{k:04x}:c39004:200")
        spread.append(f"{stamp(2.0 * k)} W/hakuX   ( 6989): [rr425w] w={300 + k} idlepc=8001b02e "
                      "idle_us=0 busy_us=2027976 n=2057 nb=0 drop=0")
    path_s = os.path.join(d, "spread.txt")
    with open(path_s, "w") as f:
        f.write("\n".join(spread) + "\n")
    w4 = Watch(path_s)
    w4.poll()
    w4.frame(0.0)
    check("busy guest over many pcs is not pinned", w4.state.get("pinned") is False and w4.arm_start["pinned"] is None)

    # 6. a disk-wait load: the vCPU idles (idle_us 1.5 s of 2) while the top pc is the idle loop: not pinned,
    # and idle0 is False too (the vCPU DID idle), so stalled cannot fire on this shape either
    idle = []
    for k in range(60):
        idle.append(f"{stamp(2.0 * k)} W/hakuX   ( 6989): [rr425] w={500 + k} dt=2000 it=60000000 e=1")
        idle.append(f"{stamp(2.0 * k)} W/hakuX   ( 6989): [rr425pc] w={500 + k} "
                    "e:8001b02f:9090fa:29000000")
        idle.append(f"{stamp(2.0 * k)} W/hakuX   ( 6989): [rr425w] w={500 + k} idlepc=8001b02e "
                    "idle_us=1500000 busy_us=500000 n=2057 nb=0 drop=0")
    path_i = os.path.join(d, "idle.txt")
    with open(path_i, "w") as f:
        f.write("\n".join(idle) + "\n")
    w5 = Watch(path_i)
    w5.poll()
    w5.frame(0.0)
    check("a vCPU that idles is not pinned", w5.state.get("pinned") is False and w5.arm_start["pinned"] is None)
    check("a vCPU that idles is not idle0 either", w5.state.get("idle0") is False)

    # 7. no telemetry at all: no HANG, whatever the screen does
    path_n = os.path.join(d, "none.txt")
    with open(path_n, "w") as f:
        f.write("10-04 13:40:00.000 I/hakuX-perf( 6989): [rdc] f=60\n")
    w6 = Watch(path_n)
    w6.poll()
    w6.frame(0.0)
    check("no telemetry: no HANG", w6.poll() is None and w6.arm_start["pinned"] is None and w6.arm_start.get("stalled") is None)

    # 8. the tail reads incrementally: a partial line waits for its newline
    path_t = os.path.join(d, "tail.txt")
    with open(path_t, "w") as f:
        f.write(lines[0][:40])
    w7 = Watch(path_t)
    w7.poll()
    check("a partial line is held, not parsed", w7.off == 40 and w7.partial != "")

    # 9. the verdict path: a trip, one press, then the screen and telemetry checked again. Three cases:
    # confirmed (nothing changed, the guest stays pinned), a press that moves the screen, a telemetry stop.
    global RECHECK_S
    saved, RECHECK_S = RECHECK_S, 0.0
    intake = os.path.join(d, "intake.py")
    with open(intake, "w") as f:
        f.write("import sys\nopen(sys.argv[2] + '/called.txt', 'w').write(' '.join(sys.argv[1:]))\n")
    more = []
    for k in range(10):                 # the guest stays pinned for 20 s after the press
        more += pinned_window(200 + k, 120 + 2.0 * k)
    # the guest wakes up after the press: the log before the press still shows it pinned (the trip is read first)
    recover = [level_line(120.5 + 2.0 * k, 3000 + k) for k in range(10)]
    cases = {}
    for name, diff_v, more_lines in (("confirmed", 0.0, more), ("screen-moved", 0.5, more), ("telemetry-stops", 0.0, []),
                                     ("telemetry-recovers", 0.0, recover)):
        out = os.path.join(d, name)
        os.makedirs(out)
        cpath = os.path.join(out, "screen-logcat.txt")
        with open(cpath, "w") as f:
            f.write("\n".join(lines) + "\n")
        watch = Watch(cpath)
        dev = _FakeDev(cpath, more_lines)
        v = look(watch, dev, out, 0.0, lambda a, b, x=diff_v: x, ("4B4E0001", "Whiteout"), intake)
        cases[name] = (v, dev, out, watch)
    v, dev, out, watch = cases["confirmed"]
    check_name = "confirmed: a HANG verdict, one A press, identification filed"
    check_ok = (v is not None and v.get("hang") is True and v.get("arm") == "pinned" and dev.pressed == [("press", "A", 120)]
                and os.path.exists(os.path.join(out, "verdict.json"))
                and open(os.path.join(out, "called.txt")).read().startswith("one "))
    check(check_name, check_ok)
    v, dev, out, watch = cases["screen-moved"]
    check("a press that moves the screen: not a HANG, streak cleared",
          v is None and watch.arm_start["pinned"] is None and "probe-cleared" in open(os.path.join(out, "hang.jsonl")).read())
    v, dev, out, watch = cases["telemetry-stops"]
    check("a press after which telemetry stops: not a HANG", v is None and watch.arm_start["pinned"] is None)
    v, dev, out, watch = cases["telemetry-recovers"]
    check("a press after which the guest recovers (pre-press pinned lines still unread): not a HANG",
          v is None and watch.arm_start["pinned"] is None)
    RECHECK_S = saved

    # 10. the stalled arm: Voodoo Vince's freeze shape (10-13) -- kicks=0, idle_us=0, pic14 raise=0, screen still,
    # audio steadily non-flat (so quiet never holds; only `stalled` can catch this one)
    def stalled_window(w, t, audio_n):
        fifo = (f"fifoskew win=2000ms kicks=0 behind=0 wrap=0 ring=134197247 backlog(mean=0 max=0) "
                "drain(n=0 mean=0 p50=0 p90=0 p99=0 max=0) bound=0 held(n=0 mean=0 max=0 spun=0 slept=0 gave=0) "
                "scan(n=0 words=0 wmax=0 ns=0 draw=0 nodraw=0 wrap=0 big=0) "
                "gaveby(flip=0 nop=0 ctxsw=0 noaccess=0 other=0) lost=0 posted=0")
        pic = "[pic14] win_us=2000034 raise=0 edge=0 lower=0 ack=0 eoi=0 isr=00 imr=a6"
        rw = (f"[rr425w] w={w} idlepc=8001b02e idle_us=0 busy_us=2000247 n=0 nb=2621 drop=0 "
              "33.02:0:0:2000247:0/0/0/0:0/0/0/0:120 30.00:0:0:0:0/0/0/0:0/0/0/0:1984")
        lvl = (f"level L: 374.411 s  peak 27931 (-1.39 dBFS)  acrms -19.19 dBFS  dc 0.014 %FS  "
               f"p5/25/50/75/95 -33.25/-25.65/-21.35/-16.65/-11.85  windows {audio_n} counted 2103 flat  "
               "clipped 0  zeros 5079678  wrap 0  maxjump 25372")
        return [f"{stamp(t)} I/hakuX-perf( 7814): {fifo}", f"{stamp(t)} W/hakuX   ( 7814): {pic}",
                f"{stamp(t)} W/hakuX   ( 7814): {rw}", f"{stamp(t + 0.5)} I/hakuX-audio( 7814): {lvl}"]

    vince = []
    for k in range(60):
        vince += stalled_window(700 + k, 2.0 * k, 5385 + 20 * k)   # audio count climbs every window: non-flat, never quiet
    path_v = os.path.join(d, "vince.txt")
    with open(path_v, "w") as f:
        f.write("\n".join(vince) + "\n")
    with open(path_v) as f:
        v_longest, _ = scan(f)
    check("Voodoo Vince shape: quiet never holds (audio keeps climbing)", v_longest["quiet"] == 0.0)
    check("Voodoo Vince shape: stalled reaches at least 110 s offline", v_longest["stalled"] >= 110)
    w8 = Watch(path_v)
    w8.frame(0.0)
    hang8 = w8.poll()
    check("Voodoo Vince shape, screen still: HANG on the stalled arm", hang8 is not None and hang8.get("arm") == "stalled")

    # 11. the stalled arm: Die Hard: Vendetta's freeze shape (10-12) -- same fifoskew/pic14/idle0 shape, but the
    # vCPU's busy time is spread over many PCs (low pin share), which the pinned arm's rule misses too
    diehard = []
    for k in range(60):
        w = 800 + k
        diehard.append(f"{stamp(2.0 * k)} W/hakuX   ( 7814): [rr425] w={w} dt=2000 it=2057 e=2000")
        diehard.append(f"{stamp(2.0 * k)} W/hakuX   ( 7814): [rr425pc] w={w} "
                       f"e:0017{k:04x}:d92c24:3 e:0018{k:04x}:c39004:3")
        diehard += stalled_window(w, 2.0 * k, 400)   # audio count flat here, but it does not matter: idle0 and
                                                      # kicks0 and discsilent are what stalled needs; the rr/pc
                                                      # lines above must land before the rw line closes window w
    path_dh = os.path.join(d, "diehard.txt")
    with open(path_dh, "w") as f:
        f.write("\n".join(diehard) + "\n")
    with open(path_dh) as f:
        dh_longest, dh_events = scan(f)
    pinned_vals = [v for _, s, v in dh_events if s == "pinned"]
    check("Die Hard shape: pinned share too low to be pinned", pinned_vals and all(v is False for v in pinned_vals))
    check("Die Hard shape: stalled still reaches at least 110 s offline", dh_longest["stalled"] >= 110)
    w9 = Watch(path_dh)
    w9.frame(0.0)
    hang9 = w9.poll()
    check("Die Hard shape, screen still: HANG on the stalled arm despite a low pin share",
          hang9 is not None and hang9.get("arm") == "stalled")

    # 12. KOTOR II's load shape (10-11): kicks=0 and idle_us=0 too, but the disc keeps raising -- not a HANG on
    # either arm, for 106 s (short of HANG_S regardless)
    kotor = []
    for k in range(53):
        fifo = ("fifoskew win=2000ms kicks=0 behind=0 wrap=0 ring=134197247 backlog(mean=0 max=0) "
                "drain(n=0 mean=0 p50=0 p90=0 p99=0 max=0) bound=0 held(n=0 mean=0 max=0 spun=0 slept=0 gave=0) "
                "scan(n=0 words=0 wmax=0 ns=0 draw=0 nodraw=0 wrap=0 big=0) "
                "gaveby(flip=0 nop=0 ctxsw=0 noaccess=0 other=0) lost=0 posted=0")
        pic = f"[pic14] win_us=2000034 raise={k + 1} edge={k + 1} lower={4 * (k + 1)} ack={k + 1} eoi={k + 1} isr=00 imr=a6"
        rw = (f"[rr425w] w={900 + k} idlepc=8001b02e idle_us=0 busy_us=2000247 n=0 nb=2621 drop=0 "
              "33.02:0:0:2000247:0/0/0/0:0/0/0/0:120")
        kotor.append(f"{stamp(2.0 * k)} I/hakuX-perf(22587): {fifo}")
        kotor.append(f"{stamp(2.0 * k)} W/hakuX   (22587): {pic}")
        kotor.append(f"{stamp(2.0 * k)} W/hakuX   (22587): {rw}")
    path_k = os.path.join(d, "kotor.txt")
    with open(path_k, "w") as f:
        f.write("\n".join(kotor) + "\n")
    with open(path_k) as f:
        k_longest, _ = scan(f)
    check("KOTOR II load shape: discsilent never holds (the disc keeps raising)",
          k_longest["stalled"] < HANG_S)
    w10 = Watch(path_k)
    w10.frame(0.0)
    hang10 = w10.poll()
    check("KOTOR II load shape: not a HANG (the disc is not silent)", hang10 is None)

    # 13. missing fifoskew lines: the stalled arm can never fire, even with idle0 and discsilent both true
    no_fifo = []
    for k in range(60):
        pic = "[pic14] win_us=2000034 raise=0 edge=0 lower=0 ack=0 eoi=0 isr=00 imr=a6"
        rw = (f"[rr425w] w={1000 + k} idlepc=8001b02e idle_us=0 busy_us=2000247 n=0 nb=2621 drop=0 "
              "33.02:0:0:2000247:0/0/0/0:0/0/0/0:120")
        no_fifo.append(f"{stamp(2.0 * k)} W/hakuX   ( 7814): {pic}")
        no_fifo.append(f"{stamp(2.0 * k)} W/hakuX   ( 7814): {rw}")
    path_nf = os.path.join(d, "nofifo.txt")
    with open(path_nf, "w") as f:
        f.write("\n".join(no_fifo) + "\n")
    w11 = Watch(path_nf)
    w11.frame(0.0)
    hang11 = w11.poll()
    check("no fifoskew lines: stalled arm never fires", hang11 is None and w11.arm_start.get("stalled") is None)

    # 14. missing pic14 lines: the stalled arm can never fire, even with idle0 and kicks0 both true
    no_pic = []
    for k in range(60):
        fifo = ("fifoskew win=2000ms kicks=0 behind=0 wrap=0 ring=134197247 backlog(mean=0 max=0) "
                "drain(n=0 mean=0 p50=0 p90=0 p99=0 max=0) bound=0 held(n=0 mean=0 max=0 spun=0 slept=0 gave=0) "
                "scan(n=0 words=0 wmax=0 ns=0 draw=0 nodraw=0 wrap=0 big=0) "
                "gaveby(flip=0 nop=0 ctxsw=0 noaccess=0 other=0) lost=0 posted=0")
        rw = (f"[rr425w] w={1100 + k} idlepc=8001b02e idle_us=0 busy_us=2000247 n=0 nb=2621 drop=0 "
              "33.02:0:0:2000247:0/0/0/0:0/0/0/0:120")
        no_pic.append(f"{stamp(2.0 * k)} I/hakuX-perf( 7814): {fifo}")
        no_pic.append(f"{stamp(2.0 * k)} W/hakuX   ( 7814): {rw}")
    path_np = os.path.join(d, "nopic.txt")
    with open(path_np, "w") as f:
        f.write("\n".join(no_pic) + "\n")
    w12 = Watch(path_np)
    w12.frame(0.0)
    hang12 = w12.poll()
    check("no pic14 lines: stalled arm never fires", hang12 is None and w12.arm_start.get("stalled") is None)

    if fails:
        print(f"hangwatch selftest: {len(fails)} failed")
        return 1
    print("hangwatch selftest: all ok")
    return 0


def main(argv):
    if argv[:1] == ["selftest"]:
        return selftest()
    if argv[:1] == ["scan"] and len(argv) > 1:
        for path in argv[1:]:
            with open(path, errors="replace") as f:
                longest, _ = scan(f)
            print(f"{path}: pinned {longest['pinned']:.0f} s, quiet {longest['quiet']:.0f} s, "
                  f"pinned+quiet {longest['pinned+quiet']:.0f} s, stalled {longest['stalled']:.0f} s "
                  f"(HANG_S {HANG_S:.0f})")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
