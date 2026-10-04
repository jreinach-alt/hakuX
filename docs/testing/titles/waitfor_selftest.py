#!/usr/bin/env python3
# Self-test for waitfor_match.py against fixed fixture crops (no device, no
# dispatch result dir -- those are not durable). The fixtures came from
# castlevania-cod.first-run's 2026-10-01 name-entry timing race: a route
# that pressed into a Name Entry screen before it had loaded, and typed
# nothing for 900s (docs/lanes/titleroutes/NOTES.md, session 60).
#
#   header-black / header-empty / header-typed: the "Name Entry" banner
#   region, still-loading vs. the screen up (empty or with a letter typed --
#   the banner itself does not change either way).
#   field-black / field-empty / field-typed: the name-field region, which
#   DOES change once a letter is typed, and is only ever compared after the
#   header has already matched (so the route never sees field-black).
#
# A region/threshold pair the route actually ships (route.sh's `waitfor`/
# `press-until` steps in castlevania-cod.first-run.route) must pass every
# case here, or the route is making a promise this script cannot back up.
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MATCH_PY = HERE / "waitfor_match.py"
REFDIR = HERE / "routes" / "refs" / "castlevania-cod.first-run"
FIX = REFDIR / "selftest"

HEADER_REGION = "0,0,490,85"
HEADER_THRESHOLD = "15"
FIELD_REGION = "0,0,120,70"
FIELD_THRESHOLD = "8"

# (fixture frame, reference, region, threshold, expect MATCH)
CASES = [
    ("header-black.png", "name-entry-header.png", HEADER_REGION, HEADER_THRESHOLD, False),
    ("header-empty.png", "name-entry-header.png", HEADER_REGION, HEADER_THRESHOLD, True),
    ("header-typed.png", "name-entry-header.png", HEADER_REGION, HEADER_THRESHOLD, True),
    ("field-empty.png", "name-field-empty.png", FIELD_REGION, FIELD_THRESHOLD, True),
    ("field-typed.png", "name-field-empty.png", FIELD_REGION, FIELD_THRESHOLD, False),
]


def run_case(frame, ref, region, threshold, expect_match):
    frame_path = FIX / frame
    ref_path = REFDIR / ref
    out = subprocess.run(
        [sys.executable, str(MATCH_PY), str(frame_path), str(ref_path), region, threshold],
        capture_output=True, text=True,
    )
    matched = out.returncode == 0
    ok = matched == expect_match
    label = "ok" if ok else "FAIL"
    print(f"{label}: {frame} vs {ref} region={region} threshold={threshold} "
          f"-> {out.stdout.strip() or out.stderr.strip()} (expected {'MATCH' if expect_match else 'NOMATCH'})")
    return ok


def main():
    if not MATCH_PY.exists():
        print(f"waitfor_selftest.py: missing {MATCH_PY}", file=sys.stderr)
        return 1
    results = [run_case(*case) for case in CASES]
    if all(results):
        print(f"waitfor_selftest.py: {len(results)}/{len(results)} cases passed")
        return 0
    print(f"waitfor_selftest.py: {results.count(False)}/{len(results)} cases FAILED", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
