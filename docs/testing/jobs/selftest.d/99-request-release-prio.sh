# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $A/$B (the live refs), $GOLDENS, the shims on PATH, ok/bad/check. Not
# executable, no shebang, no exit.
#
# Release priority read by request.sh itself (#432, lane.reqprio). A lane that
# queues straight through request.sh -- a pilot, a soak -- names no
# HAKUX_RELEASE_PRIO, so until this landed its request got a plain id even for
# an issue labelled for the release. request.sh now reads the label of --issue,
# else of the first #N in --purpose. Every leg asserts on the id of the file
# written to its own queue, never on the exit code. gh is a stub on PATH whose
# answer each leg picks; every call is logged, so "no read" is checkable too.
#
# Against origin/master's request.sh the 'label' leg FAILS (it never reads a
# label: plain id), and so does the HAKUX_RELEASE_PRIO=0 leg (':+' made any
# non-empty value, 0 included, a 1- id).

echo "== request.sh reads the release label itself"

RQP="$T/reqprio"
rm -rf "$RQP"; mkdir -p "$RQP/bin"
# Its own ref: an earlier fragment reassigns $B (to a brief's path, in the run
# that caught this), and a --ref that does not resolve queues nothing.
RQP_REF=$(git -C "$REPO" rev-parse --short HEAD)
cat > "$RQP/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$RQP_GH_LOG"
case "$RQP_GH" in
    label)   printf '%s\n' bug 0.5 fps-focus ;;
    nolabel) printf '%s\n' bug fps-focus 0.50 ;;
    label474) if [[ "$*" == *"issues/474 "* ]]; then echo 0.5; else echo bug; fi ;;
    *)      echo "HTTP 502" >&2; exit 1 ;;
esac
EOF
chmod +x "$RQP/bin/gh"

# rqp_leg <name> <gh answer> <HAKUX_RELEASE_PRIO or "unset"> <request.sh args...>
# -> the queued id (from queue/*.req) on stdout; stderr kept in $RQP/<name>.err
rqp_leg() {
    local name=$1 answer=$2 prio=$3; shift 3
    mkdir -p "$RQP/$name/queue"
    ( export PATH="$RQP/bin:$PATH" RQP_GH="$answer" RQP_GH_LOG="$RQP/$name.gh" \
             DISPATCH_DIR="$RQP/$name" DISPATCH_TREE="$REPO" GH_REPO="example/hakux"
      unset HAKUX_RELEASE_LABEL
      if [ "$prio" = unset ]; then unset HAKUX_RELEASE_PRIO; else export HAKUX_RELEASE_PRIO="$prio"; fi
      : > "$RQP_GH_LOG"
      bash "$TESTING/request.sh" --who "rqp-$name" --suites "Blend surface" --ref "$RQP_REF" \
          --no-expect "selftest: naming only" "$@" ) >/dev/null 2>"$RQP/$name.err"
    ( cd "$RQP/$name/queue" && for f in *.req; do [ -e "$f" ] && echo "${f%.req}"; done )
}
rqp_is() {   # <want: prio|plain> <id> <who>
    python3 -c "import re,sys; sys.exit(0 if re.fullmatch(('1-' if sys.argv[1]=='prio' else '') + r'[0-9]{10}-' + re.escape(sys.argv[3]) + r'-[0-9]+', sys.argv[2]) else 1)" "$@"
}

rqp_id=$(rqp_leg label label unset --purpose "drain pilot for #474 (Nova)")
echo "  label:    $rqp_id  [$(grep "^priority" "$RQP/label.err")]"
check "a #474 purpose, labelled 0.5, queues 1-<epoch>-rqp-label-<pid>" rqp_is prio "$rqp_id" rqp-label
check "the label read asked for issue 474" grep -q 'issues/474 ' "$RQP/label.gh"
check "the label read was one call" test "$(wc -l < "$RQP/label.gh")" -eq 1
check "request.sh says why: the label on #474" grep -qF "priority release: '0.5' on #474" "$RQP/label.err"

rqp_id=$(rqp_leg nolabel nolabel unset --purpose "soak for #999, then #474")
echo "  nolabel:  $rqp_id  [$(grep "^priority" "$RQP/nolabel.err")]"
check "an unlabelled issue (0.50 is not 0.5) queues a plain id" rqp_is plain "$rqp_id" rqp-nolabel
check "only the FIRST #N in --purpose is read" grep -q 'issues/999 ' "$RQP/nolabel.gh"
check "... and not the second" bash -c '! grep -q "issues/474" "$1"' _ "$RQP/nolabel.gh"
check "request.sh says why: not labelled" grep -qF "priority plain: '0.5' not on #999" "$RQP/nolabel.err"

rqp_id=$(rqp_leg fail fail unset --purpose "pilot for #474")
echo "  fail:     $rqp_id  [$(grep -c . "$RQP/fail.err") stderr lines]"
check "an unreadable label queues a plain id (never refuses)" rqp_is plain "$rqp_id" rqp-fail
check "an unreadable label logs one line" \
    test "$(grep -c "could not read #474's labels; queueing at normal priority" "$RQP/fail.err")" -eq 1

rqp_id=$(rqp_leg force0 label 0 --purpose "pilot for #474")
echo "  force0:   $rqp_id"
check "HAKUX_RELEASE_PRIO=0 wins over a label: plain id" rqp_is plain "$rqp_id" rqp-force0
check "HAKUX_RELEASE_PRIO=0 reads no label" test ! -s "$RQP/force0.gh"

# ab_run.sh and arms.sh pass their own reader's answer, "" for not labelled.
rqp_id=$(rqp_leg setempty label "" --purpose "arm for #474")
check "HAKUX_RELEASE_PRIO set but empty (the arms callers' 'no'): plain id" rqp_is plain "$rqp_id" rqp-setempty
check "... and reads no label" test ! -s "$RQP/setempty.gh"
rqp_id=$(rqp_leg force1 fail 1 --purpose "no issue here")
check "HAKUX_RELEASE_PRIO=1 still forces 1-, no read" rqp_is prio "$rqp_id" rqp-force1
check "... and reads no label" test ! -s "$RQP/force1.gh"

rqp_id=$(rqp_leg issueflag label474 unset --issue 999,474 --purpose "names #12 in prose only")
check "--issue 999,474 overrides the purpose's #12; any one labelled is enough" rqp_is prio "$rqp_id" rqp-issueflag
check "... read 999 then 474, never 12" \
    bash -c 'grep -q "issues/999 " "$1" && grep -q "issues/474 " "$1" && ! grep -q "issues/12 " "$1"' _ "$RQP/issueflag.gh"

rqp_id=$(rqp_leg none fail unset --purpose "a pilot with no issue")
check "no --issue and no #N: plain id, no read" rqp_is plain "$rqp_id" rqp-none
check "... and no gh call" test ! -s "$RQP/none.gh"
