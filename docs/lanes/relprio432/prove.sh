#!/usr/bin/env bash
# Run only selftest.d/97-release-prio.sh (or the fragment named) on the
# selftest's fake host.
#   bash docs/lanes/relprio432/prove.sh [NN-name.sh]
# selftest.sh is used as-is except for its fragment list, which is narrowed to
# the one fragment: the harness, shims and live prediction are built exactly as
# a full run builds them.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
J="$ROOT/docs/testing/jobs"
F="${1:-97-release-prio.sh}"
R="$(mktemp "$ROOT/.relprio-runner.XXXXXX")"
trap 'rm -f "$R"' EXIT
python3 - "$J/selftest.sh" "$R" "$J" "$F" <<'PY'
import sys
src, out, j, f = sys.argv[1:]
s = open(src).read()
here = 'export HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"'
frag = 'done < <(printf \'%s\\n\' "$HERE/selftest.d/"* | LC_ALL=C sort)'
assert here in s and frag in s, "selftest.sh changed shape; update prove.sh"
s = s.replace(here, 'export HERE="%s"' % j)
s = s.replace(frag, 'done < <(printf \'%s\\n\' "$HERE/selftest.d/' + f + '")')
open(out, "w").write(s)
PY
bash "$R"
