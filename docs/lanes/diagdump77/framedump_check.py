#!/usr/bin/env python3
"""Read a live frame dump and say whether it serialised.

    docs/lanes/diagdump77/framedump_check.py framedump_<id>.jsonl

The claim this file exists to test is the one the instrument was built for:
that a marker-armed dump does NOT force a pgraph_vk_finish per draw the way
the Debug Capture button does.  It is testable from the dump's own contents
and needs no trace, because a finish submits the command buffer:

    cb_draws   r->draws_in_cb, the draws recorded in the current command
               buffer.  A finish between every draw resets it, so under the
               button path it never exceeds 1.
    submits    r->submit_count.  A finish submits, so under the button path
               it rises once per draw; without one it is flat between flips.

The two are independent readings of the same fact and are reported
separately: a build that changed one and not the other is a bug in the
instrument, not a passing result, so this refuses to average them.

Exit status is 0 if the dump is coherent and 1 if it is not -- including when
the dump says it serialised, which for a marker-armed run is the falsifier
firing and not a tool error.
"""

import json
import sys
from collections import Counter


def load(path):
    session = None
    draws = []
    frames = []
    end = None
    bad = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                # A dump cut off by a crash or a byte cap ends mid-line.  That
                # is a truncated file, not a corrupt one; say so and keep the
                # complete records.
                bad += 1
                continue
            kind = rec.get("t")
            if kind == "session":
                session = rec
            elif kind == "draw":
                draws.append(rec)
            elif kind == "frame":
                frames.append(rec)
            elif kind == "end":
                end = rec
    return session, draws, frames, end, bad


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    path = argv[1]
    session, draws, frames, end, bad = load(path)

    if session is None:
        print("no session header: this is not a frame dump, or its first "
              "line was lost")
        return 1

    print("session   id=%s armed_by=%s spec=%r" %
          (session.get("id"), session.get("armed_by"), session.get("spec")))
    print("          draw_merge=%s draw_reorder=%s surface_scale=%s "
          "submit_frames=%s" %
          (session.get("draw_merge"), session.get("draw_reorder"),
           session.get("surface_scale"), session.get("submit_frames")))
    print("          driver=%s" % session.get("driver"))
    print("frames    %d recorded, %d draws" % (len(frames), len(draws)))
    if end is None:
        print("          NO TRAILER: the dump is truncated -- the app was "
              "killed, or the byte cap hit mid-write.  Frame counts below "
              "are a lower bound.")
    else:
        print("          trailer: %s after %s frames, %s draws, %s bytes" %
              (end.get("why"), end.get("frames"), end.get("draws"),
               end.get("bytes")))

    if not draws:
        print("no draw records: nothing to say about serialisation")
        return 1

    # Did the diag capture run alongside?  A dump armed with "diag" contains
    # both arms and must not be read as one.
    diag_frames = [f for f in frames if f.get("diag_active")]
    if diag_frames:
        print("NOTE      %d of %d frames ran with the diag capture ALSO "
              "active; those frames are the serialising control arm."
              % (len(diag_frames), len(frames)))

    cb = Counter(d.get("cb_draws") for d in draws)
    max_cb = max(k for k in cb if isinstance(k, int))
    print("cb_draws  max=%d  distribution=%s" %
          (max_cb, dict(sorted((k, v) for k, v in cb.items()
                               if isinstance(k, int))[:8])))

    # submits per draw, measured within a frame: the frame record carries the
    # frame's own submit delta, which is the honest denominator.  Draw counts
    # per frame come from the frame record for the same reason.
    per_frame = []
    for f in frames:
        n = f.get("draws") or 0
        s = f.get("submits_in_frame")
        if n and s is not None:
            per_frame.append((f.get("f"), n, s, s / n))
    if per_frame:
        worst = max(per_frame, key=lambda r: r[3])
        median = sorted(r[3] for r in per_frame)[len(per_frame) // 2]
        print("submits   median %.4f per draw, worst frame f%s at %.4f "
              "(%d submits over %d draws)" %
              (median, worst[0], worst[3], worst[2], worst[1]))
    else:
        median = None
        print("submits   no frame record carried both a draw count and a "
              "submit delta")

    print()
    verdict = 0
    if max_cb <= 1:
        print("SERIALISED: no command buffer ever held more than one draw. "
              "That is the signature of a finish between draws -- this dump "
              "reproduces the Debug Capture path's blindness.")
        verdict = 1
    else:
        print("NOT SERIALISED by cb_draws: command buffers held up to %d "
              "draws, so no finish ran between them." % max_cb)

    if median is not None:
        if median >= 0.9:
            print("SERIALISED by submits: %.4f submits per draw is one "
                  "submission each, which is what a per-draw finish does."
                  % median)
            verdict = 1
        else:
            print("NOT SERIALISED by submits: %.4f submits per draw." % median)

    if bad:
        print("\n%d unparseable line(s) skipped (truncation)." % bad)

    # An instrument that reports a finish-free dump with no merging context is
    # easy to over-read; say what this run could and could not have shown.
    if not session.get("draw_merge"):
        print("\nSCOPE: draw_merge was OFF in this run, so nothing here is "
              "evidence about MERGED draws -- only about deferred submission "
              "and command-buffer batching, which are on by default.  A dump "
              "meant to speak about merging must be taken with the pref on.")
    return verdict


if __name__ == "__main__":
    sys.exit(main(sys.argv))
