#!/usr/bin/env python3
"""Both directions of `score_arms.session_header`, on synthetic dumps.

The fix it guards was made AFTER seeing a run, which is the moment to be
loudest about what it may and may not do. It may recover a header whose
driver string contains newlines -- the stock Adreno arm, five physical lines.
It may NOT invent a header where the dump has none, because this lane's
registered guard G2 voids a run on a missing header and a reader that
hallucinates one would silently disarm that guard for every future arm.

It may also NOT read the whole dump looking for one: the accumulation is
bounded at `MAX_HEADER_LINES`, and cases 5 and 6 assert THE BOUND rather than
the answer, because asserting the answer does not pin it -- a truncated header
returns None under a bounded reader and under an unbounded one alike, so the
first version of case 4 was green against a reader with the bound deleted.

So there is a positive case and five that constrain it, and the constraints
are the point. Every mutant below was built in a scratch tree and run:

    mutant                                              cases it FAILs
    the OLD one-line `readline` reader                  1, 6
    accumulate, but drop the `t == "session"` check     3
    delete `MAX_HEADER_LINES` and its `break`           5
    off-by-one: `break` at `MAX_HEADER_LINES - 1`       6

No mutant passes all six, and each of 3, 5 and 6 is the SOLE failure of one
of them -- so the `t` check and both edges of the bound are each pinned by a
case that nothing else is keeping green.

    python3 tests_session_header.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_arms import MAX_HEADER_LINES, session_header  # noqa: E402

# The real string, read off 1789950291-drvab77-stock-1-1271457.
ADRENO = ("Qualcomm Technologies Inc. Adreno Vulkan Driver (Driver Build: "
          "69e13475cb, I1df7ad3aa9, 1703680572\nDate: 12/27/23\n"
          "Compiler Version: E031.41.03.47\nDriver Branch: \n)")
TURNIP = "PurpleVK public driver (PurpleVK 26.3.0-devel (git-62ac221a33))"


def write(dirpath, lines):
    with open(os.path.join(dirpath, "framedump_1.jsonl"), "w") as fh:
        fh.write("".join(lines))
    return dirpath


def session_line(driver):
    """As the emulator writes it: json.dumps would ESCAPE the newlines, and
    then there would be no bug to test. The device emits the raw bytes."""
    rec = json.dumps(dict(t="session", id=1, spec="600,after165,cap200",
                          frames=600, driver="DRIVER"))
    return rec.replace("DRIVER", driver) + "\n"


def case(name, lines, want_driver, want_none=False, want_lines=None):
    with tempfile.TemporaryDirectory() as d:
        write(d, lines)
        got = session_header(d)
    if want_none:
        ok = got is None
        detail = "expected None, got %r" % (got if got is None else list(got))
    else:
        ok = got is not None and got.get("driver") == want_driver
        detail = "driver=%r" % (got or {}).get("driver")
        if ok and want_lines is not None:
            # The reader's own count of physical lines consumed. This is the
            # quantity the bound is about, so it is asserted directly rather
            # than inferred from the answer.
            ok = got.get("_header_lines") == want_lines
            detail = "_header_lines=%r, want %d" % (
                got.get("_header_lines"), want_lines)
    print("%-4s %s -- %s" % ("PASS" if ok else "FAIL", name, detail))
    return ok


def main():
    ok = True

    # 1. The stock arm: a five-line driver string. The old reader returns None
    #    here, which is how both stock runs scored `?`.
    ok &= case("multi-line driver recovers", [session_line(ADRENO)], ADRENO)

    # 2. The Turnip arms: one line, must keep working unchanged.
    ok &= case("single-line driver still works", [session_line(TURNIP)],
               TURNIP)

    # 3. NO session record. Must stay None -- G2's void is built on this.
    #    A draw record first, then more draws, all perfectly parseable: an
    #    accumulate-until-it-parses reader without the `t` check returns the
    #    draw and calls the run headed.
    ok &= case("no session record stays None",
               ['{"t":"draw","n":1}\n', '{"t":"draw","n":2}\n'],
               None, want_none=True)

    # 4. A truncated header -- the dump died mid-record. The answer is None.
    #    NOTE what this does NOT test: an unbounded reader answers None here
    #    too, because a dangling string followed by draw records never
    #    re-parses no matter how many lines are added. Cases 5 and 6 are the
    #    ones that pin the bound.
    ok &= case("truncated header stays None",
               ['{"t":"session","driver":"half a stri\n'] +
               ['{"t":"draw","n":%d}\n' % i for i in range(40)],
               None, want_none=True)

    # 5. THE BOUND, from above. A session record whose driver string closes
    #    one line PAST MAX_HEADER_LINES. An unbounded accumulator parses it
    #    and returns a header; the bounded reader must give up and say None.
    #    This is the case that fails on a reader with the bound deleted, and
    #    it is the only one that does.
    too_long = "\n".join("cont %d" % i for i in range(MAX_HEADER_LINES + 1))
    ok &= case("record past the bound is not read",
               [session_line(too_long)], None, want_none=True)

    # 6. THE BOUND, from below, so "stop early" is not a way to pass case 5.
    #    A record spanning EXACTLY MAX_HEADER_LINES physical lines must still
    #    be read, and the reader must report consuming exactly that many.
    #    Fixture sized off the constant, so changing the constant is a
    #    configuration change while an off-by-one in the loop is a failure.
    # m joined pieces carry m-1 newlines, so the record spans m lines.
    exact = "\n".join("cont %d" % i for i in range(MAX_HEADER_LINES))
    ok &= case("record exactly at the bound is read", [session_line(exact)],
               exact, want_lines=MAX_HEADER_LINES)

    print("ALL PASS" if ok else "FAILURES ABOVE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
