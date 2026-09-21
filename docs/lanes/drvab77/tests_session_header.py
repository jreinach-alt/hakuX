#!/usr/bin/env python3
"""Both directions of `score_arms.session_header`, on synthetic dumps.

The fix it guards was made AFTER seeing a run, which is the moment to be
loudest about what it may and may not do. It may recover a header whose
driver string contains newlines -- the stock Adreno arm, five physical lines.
It may NOT invent a header where the dump has none, because this lane's
registered guard G2 voids a run on a missing header and a reader that
hallucinates one would silently disarm that guard for every future arm.

So there is a positive case and two negative ones, and the negatives are the
point: run this file against the OLD one-line reader and case 1 fails; run it
against an "accumulate until anything parses" reader with the `t == session`
check dropped and case 3 fails. Neither mutant passes both.

    python3 tests_session_header.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_arms import session_header  # noqa: E402

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


def case(name, lines, want_driver, want_none=False):
    with tempfile.TemporaryDirectory() as d:
        write(d, lines)
        got = session_header(d)
    if want_none:
        ok = got is None
        detail = "expected None, got %r" % (got if got is None else list(got))
    else:
        ok = got is not None and got.get("driver") == want_driver
        detail = "driver=%r" % (got or {}).get("driver")
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

    # 4. A truncated header -- the dump died mid-record. Unbounded
    #    accumulation over a huge file is the other way to "fix" case 1; this
    #    says the answer is still None rather than a scan of the whole dump.
    ok &= case("truncated header stays None",
               ['{"t":"session","driver":"half a stri\n'] +
               ['{"t":"draw","n":%d}\n' % i for i in range(40)],
               None, want_none=True)

    print("ALL PASS" if ok else "FAILURES ABOVE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
