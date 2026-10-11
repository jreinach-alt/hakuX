# Proposed docs/testing/jobs/selftest.d/90-frametrace.sh (lane.frametrace,
# #433). Outside the lane's row, so it lives here until lane.local copies it.
#
# Sourced by ../selftest.sh with $REPO, ok/bad/check. Not executable, no
# shebang, no exit.
#
# The frametrace attribution rule and holder test (hw/xbox/nv2a/pgraph/
# profile.h), compiled on the host: 32 checks, and nine mutants of the header
# that must each FAIL the check named for what they remove. About 7 s; needs
# a C compiler with pthreads, nothing else.

echo "== frametrace: attribution rule, holder split, hitch trigger (#433)"

check "frametrace selftest (32 checks, 9 mutants caught)" \
    python3 "$REPO/docs/lanes/frametrace/selftest.py"
