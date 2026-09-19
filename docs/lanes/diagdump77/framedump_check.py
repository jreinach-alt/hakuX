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

Neither column can separate the paths on a frame that only drew a few times:
a per-draw finish and a frame with one draw produce the same cb_draws and the
same submits-per-draw.  `afterNN` exists because a queued soak cannot choose
its moment, so landing on a loading screen or a pause menu is a normal
outcome, and a confident SERIALISED there would falsify the instrument's whole
thesis from a dump that behaved correctly.  Such a dump is refused, not
inverted: see INSUFFICIENT SAMPLE below.

Exit status:
    0   coherent, and the dump did not serialise
    1   not coherent, or the dump says it serialised -- which for a
        marker-armed run is the falsifier firing and not a tool error
    2   usage
    3   INSUFFICIENT SAMPLE: no verdict is warranted either way
"""

import json
import sys
from collections import Counter

# The newest schema this file knows how to read.  2 added `img_sync` to the
# frame record: in a schema-1 dump the per-frame PPM was read from VRAM before
# the flip's pre-recorded display download had been completed into it, so the
# image is one completed download older than the draw records it is filed
# under.  The records are unaffected -- every verdict below is computed from
# them -- but the images of a schema-1 dump must not be paired with a frame.
SCHEMA_KNOWN = 2

# A frame with fewer draws than this cannot distinguish a per-draw finish from
# a frame that simply drew that few times, on either column.  Four is a
# handful, not a derived threshold: two would technically separate them and
# leaves no margin for a submit that happened for some other reason.
MIN_FRAME_DRAWS = 4
MIN_TOTAL_DRAWS = 30


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

    print("session   id=%s armed_by=%s spec=%r schema=%s" %
          (session.get("id"), session.get("armed_by"), session.get("spec"),
           session.get("schema")))
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
    cb_ints = [k for k in cb if isinstance(k, int)]
    if not cb_ints:
        # The column the whole verdict rests on is absent: an older build, a
        # schema change, or a file that is not a frame dump.  A checker whose
        # job is to say "this is not a frame dump" has to say it here too,
        # rather than exiting on a traceback from max() over nothing.
        print("no draw record carries cb_draws: this dump cannot be read by "
              "this checker (schema=%s, known=%d).  Nothing below would be a "
              "verdict." % (session.get("schema"), SCHEMA_KNOWN))
        return 1
    max_cb = max(cb_ints)
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

    # Only frames that drew enough to tell the two paths apart.  A frame with
    # one draw has one submit -- the flip's own -- whichever path produced it,
    # so including it in the median measures how often the title stopped
    # drawing, not whether a finish ran between draws.
    usable = [r for r in per_frame if r[1] >= MIN_FRAME_DRAWS]
    if usable:
        worst = max(usable, key=lambda r: r[3])
        median = sorted(r[3] for r in usable)[len(usable) // 2]
        print("submits   median %.4f per draw over the %d of %d frames with "
              ">=%d draws, worst frame f%s at %.4f (%d submits over %d draws)"
              % (median, len(usable), len(per_frame), MIN_FRAME_DRAWS,
                 worst[0], worst[3], worst[2], worst[1]))
    else:
        median = None
        print("submits   no frame carried both a draw count and a submit "
              "delta with >=%d draws" % MIN_FRAME_DRAWS)

    # The refusal.  Both columns degrade together at low draw counts -- the
    # independence the two readings rest on does not hold there -- so this
    # covers the disagreement check as well, and returns its own status rather
    # than a verdict nothing supports.
    if not usable or len(draws) < MIN_TOTAL_DRAWS:
        print()
        print("INSUFFICIENT SAMPLE: %d draws over %d frames, %d of them with "
              ">=%d draws.  Neither column can distinguish the two paths on "
              "this dump -- a per-draw finish is indistinguishable from a "
              "frame that only drew once.  A dump armed onto a loading "
              "screen, a pause menu or a video cut looks exactly like this "
              "and is not evidence that the path serialises.  Re-arm with "
              "afterNN onto a scene that is drawing."
              % (len(draws), len(frames), len(usable), MIN_FRAME_DRAWS))
        if not session.get("draw_merge"):
            print("\nSCOPE: draw_merge was OFF in this run, so nothing here "
                  "would have been evidence about MERGED draws either.")
        return 3

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

    # The header's per_draw_finish is a statement about what was ARMED; the two
    # columns above are what the scheduler did.  They are produced by different
    # code on different paths, so a disagreement is a broken instrument and is
    # reported as one rather than being quietly resolved in either direction.
    # (The field was a bare `false` literal once, which would have printed "no
    # finish" on the control arm -- hence a check rather than trust.)
    claimed = session.get("per_draw_finish")
    if claimed is not None and claimed != bool(verdict):
        print("\nINSTRUMENT DISAGREES WITH ITSELF: the session header says "
              "per_draw_finish=%s, the draw records say %s.  Believe the draw "
              "records -- they are read from the scheduler, the header is "
              "read from the spec -- and treat this dump's provenance as "
              "unreliable until that is explained."
              % (claimed, "SERIALISED" if verdict else "NOT SERIALISED"))
        verdict = 1

    # The images are a separate claim from the records, and a weaker one.
    schema = session.get("schema")
    imaged = [f for f in frames if f.get("image")]
    if imaged and not (isinstance(schema, int) and schema >= 2):
        print("\nIMAGES: schema %s predates the per-frame download "
              "completion, so every PPM here holds the most recently "
              "COMPLETED display download rather than the frame it is filed "
              "under -- one frame behind in the steady state, further behind "
              "whenever the display thread had not presented.  The verdicts "
              "above are unaffected (they are read from the records), but do "
              "not pair a picture from this dump with a draw record." % schema)
    elif imaged:
        blind = [f.get("f") for f in imaged if "img_sync" not in f]
        if blind:
            print("\nIMAGES: %d frame record(s) name an image but carry no "
                  "img_sync (first: f%s).  At schema %s the image is supposed "
                  "to be written after a completion that names a fence; a "
                  "record that cannot say which one is not evidence that it "
                  "was." % (len(blind), blind[0], schema))
            verdict = 1
    if isinstance(schema, int) and schema > SCHEMA_KNOWN:
        print("\nNOTE      schema %d is newer than this checker (%d); fields "
              "it does not know about were ignored." % (schema, SCHEMA_KNOWN))

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
