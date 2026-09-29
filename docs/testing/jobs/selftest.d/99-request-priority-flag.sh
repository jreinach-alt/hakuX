# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit.
#
# request.sh --priority (defect 22, docs/lanes/dispatch-hardening/NOTES.md).
# A lane names its tier instead of asking the host to rename its file:
# blocker queues 0-<epoch>, sweep queues z-<epoch>, and arm and study keep the
# release-label tiering. Every leg asserts on the id of the file written to its
# own queue and on the JSON's `priority` field, never on the exit code alone.
#
# Against origin/master's request.sh every leg that passes --priority queues
# nothing ("unknown option --priority"). The mutant below keeps the flag and
# the field and names every raised tier 1-, so a blocker lands in the release
# tier; the ordering leg is red on it.

echo "== request.sh --priority names the tier"

RPF="$T/reqpriority"
rm -rf "$RPF"; mkdir -p "$RPF/bin"
RPF_REF=$(git -C "$REPO" rev-parse --short HEAD)
cat > "$RPF/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$RPF_GH_LOG"
case "$RPF_GH" in
    label) printf '%s\n' bug 0.5 ;;
    *)     printf '%s\n' bug ;;
esac
EOF
chmod +x "$RPF/bin/gh"

# rpf_leg <request.sh> <name> <gh answer> <request.sh args...>
# -> the queued id on stdout; stderr in $RPF/<name>.err, gh calls in .gh
rpf_leg() {
    local rq=$1 name=$2 answer=$3; shift 3
    rm -rf "$RPF/$name"; mkdir -p "$RPF/$name/queue"   # one id per call
    ( export PATH="$RPF/bin:$PATH" RPF_GH="$answer" RPF_GH_LOG="$RPF/$name.gh" \
             DISPATCH_DIR="$RPF/$name" DISPATCH_TREE="$REPO" GH_REPO="example/hakux"
      unset HAKUX_RELEASE_LABEL HAKUX_RELEASE_PRIO
      : > "$RPF_GH_LOG"
      bash "$rq" --who "rpf-$name" --suites "Blend surface" --ref "$RPF_REF" \
          --no-expect "selftest: naming only" "$@" ) >/dev/null 2>"$RPF/$name.err"
    ( cd "$RPF/$name/queue" && for f in *.req; do [ -e "$f" ] && echo "${f%.req}"; done )
}
rpf_is() {   # <tier prefix or ""> <id> <who>
    python3 -c "import re,sys; sys.exit(0 if re.fullmatch(re.escape(sys.argv[1]) + r'[0-9]{10}-' + re.escape(sys.argv[3]) + r'-[0-9]+', sys.argv[2]) else 1)" "$@"
}
rpf_field() {   # <name> <id> -> the queued JSON's priority field
    python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('priority', 'ABSENT'))" \
        "$RPF/$1/queue/$2.req" 2>/dev/null
}
RQ="$TESTING/request.sh"

rpf_id=$(rpf_leg "$RQ" blocker label --priority blocker --issue 311 --purpose "repro for the 0.5 blocker")
echo "  blocker:  $rpf_id  [$(grep "^priority" "$RPF/blocker.err")]"
check "--priority blocker --issue 311 queues 0-<epoch>-rpf-blocker-<pid>" rpf_is 0- "$rpf_id" rpf-blocker
check "... records priority blocker in the request" test "$(rpf_field blocker "$rpf_id")" = blocker
check "... and reads no label" test ! -s "$RPF/blocker.gh"
check "... and says why, naming the issue" grep -qF "priority blocker: --priority blocker for 311" "$RPF/blocker.err"

rpf_id=$(rpf_leg "$RQ" blockernone label --priority blocker --purpose "a blocker with no issue")
check "--priority blocker with no issue queues nothing" test -z "$rpf_id"
check "... and says what is missing" grep -qF "refusing to queue: --priority blocker names no issue" "$RPF/blockernone.err"

rpf_id=$(rpf_leg "$RQ" blockerpurpose label --priority blocker --purpose "repro for #311")
check "--priority blocker takes the issue from #N in --purpose" rpf_is 0- "$rpf_id" rpf-blockerpurpose

rpf_id=$(rpf_leg "$RQ" sweep label --priority sweep --purpose "corpus leg for #474")
echo "  sweep:    $rpf_id"
check "--priority sweep queues z-<epoch>-rpf-sweep-<pid>, even for a labelled issue" rpf_is z- "$rpf_id" rpf-sweep
check "... records priority sweep" test "$(rpf_field sweep "$rpf_id")" = sweep
check "... and reads no label" test ! -s "$RPF/sweep.gh"

rpf_id=$(rpf_leg "$RQ" armrel label --priority arm --purpose "arm for #474")
check "--priority arm on a labelled issue keeps the release tier: 1-" rpf_is 1- "$rpf_id" rpf-armrel
check "... records priority arm" test "$(rpf_field armrel "$rpf_id")" = arm
rpf_id=$(rpf_leg "$RQ" armplain nolabel --priority arm --purpose "arm for #999")
check "--priority arm on an unlabelled issue queues a plain id" rpf_is "" "$rpf_id" rpf-armplain

rpf_id=$(rpf_leg "$RQ" default nolabel --purpose "a study of #999")
check "no --priority: a plain id" rpf_is "" "$rpf_id" rpf-default
check "... recorded as study" test "$(rpf_field default "$rpf_id")" = study

rpf_id=$(rpf_leg "$RQ" bogus nolabel --priority urgent --purpose "#999")
check "--priority urgent queues nothing" test -z "$rpf_id"
check "... and names the four tiers" grep -qF "unknown --priority 'urgent': blocker, arm, study or sweep" "$RPF/bogus.err"

# The dispatcher's order over what was just queued, with a host-promoted head
# and a queue_full_sweep leg beside them. The blocker must sort second: behind
# the host's 0-0-x head, ahead of the release arm.
rpf_order() {   # <blocker id> -> the five ids in the dispatcher's glob order
    local q="$RPF/order/queue"; rm -rf "$RPF/order"; mkdir -p "$q"
    touch "$q/0-0-x-1790000000-hostops-1.req" "$q/$1.req" \
          "$q/$(rpf_leg "$RQ" armrel label --priority arm --purpose "arm for #474").req" \
          "$q/$(rpf_leg "$RQ" armplain nolabel --priority arm --purpose "arm for #999").req" \
          "$q/z-sweep-001-Alpha_func.req"
    ( cd "$q" && printf '%s\n' *.req | sed 's/\.req$//; s/-[0-9]*$//' )
}
rpf_order_ok() {   # <order> <blocker who>: host head, blocker, release arm, plain arm, sweep
    case "$1" in
        "0-0-x-1790000000-hostops 0-"*"-$2 1-"*"-rpf-armrel "[0-9]*"-rpf-armplain z-sweep-001-Alpha_func ") return 0 ;;
    esac
    return 1
}
RPF_ORDER=$(rpf_order "$(rpf_leg "$RQ" blocker label --priority blocker --issue 311 --purpose "repro")" | tr '\n' ' ')
echo "  order:    $RPF_ORDER"
if rpf_order_ok "$RPF_ORDER" rpf-blocker; then ok "the dispatcher's order: host head, blocker, release arm, plain arm, sweep"
else bad "the dispatcher's order is wrong: $RPF_ORDER"; fi

# The mutant: every raised tier named 1-. Built in a symlink tree of
# docs/testing whose .git is this repository's, so request.sh still resolves
# the ref (a lone copy resolves nothing and queues nothing).
rpf_mut="$RPF/mut"; rm -rf "$rpf_mut"; mkdir -p "$rpf_mut/docs/testing"
ln -s "$REPO/.git" "$rpf_mut/.git"
for f in "$TESTING"/*; do [ "${f##*/}" = request.sh ] || ln -s "$f" "$rpf_mut/docs/testing/"; done
sed 's/^ID="\${PRIO:+\$PRIO-}/ID="${PRIO:+1-}/' "$RQ" > "$rpf_mut/docs/testing/request.sh"
if cmp -s "$RQ" "$rpf_mut/docs/testing/request.sh"; then
    bad "the mutant request.sh is identical to the real one -- the sed matched nothing"
else
    rpf_id=$(rpf_leg "$rpf_mut/docs/testing/request.sh" mutblocker label --priority blocker --issue 311 --purpose "repro")
    if rpf_is 1- "$rpf_id" rpf-mutblocker; then
        ok "the mutant queues the blocker as 1- (it runs, and it is wrong)"
    else
        bad "the mutant did not queue a 1- blocker: '$rpf_id' $(head -c 300 "$RPF/mutblocker.err")"
    fi
    RQ_SAVE=$RQ; RQ="$rpf_mut/docs/testing/request.sh"
    RPF_MORDER=$(rpf_order "$rpf_id" | tr '\n' ' ')
    RQ=$RQ_SAVE
    echo "  mutant:   $RPF_MORDER"
    if rpf_order_ok "$RPF_MORDER" rpf-mutblocker; then bad "the order check passed the mutant: $RPF_MORDER"
    else ok "the order check fails the mutant (its blocker is not second)"; fi
fi

unset RPF RPF_REF RPF_ORDER RPF_MORDER RQ RQ_SAVE rpf_id rpf_mut
unset -f rpf_leg rpf_is rpf_field rpf_order rpf_order_ok
