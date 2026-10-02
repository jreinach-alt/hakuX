#!/usr/bin/env bash
# route.sh -- which harness units get the gh shim (the local forge) instead of /usr/bin/gh.
#
#   route.sh status              every unit below: routed or not, and whether its code is ready
#   route.sh on  <unit|phase1|phase2>...   write the drop-in(s), then daemon-reload
#   route.sh off <unit|all>...             remove the drop-in(s), then daemon-reload
#
# Routing a unit means one drop-in:
#   ~/.config/systemd/user/<unit>.d/zz-forge-shim.conf
# It does three things:
#   - puts ~/hakux-work/forge/shim/bin first on PATH;
#   - sets HAKUX_FORGE=1;
#   - sets the web base the jobs use for forge links.
# Removing the file (route.sh off) routes the unit back to /usr/bin/gh. The
# drop-in is the whole switch, with no other state.
#
# A UNIT IS ROUTED ONLY ONCE THE CODE IT RUNS KNOWS THE FORGE. Under the forge,
# board.sh, handback.sh and fold.sh start nothing:
#   - no board session;
#   - no lane resume;
#   - no merge.
# status.sh never pushes to github.com. But only a copy that contains those
# gates behaves that way. The jobs run origin/master's copy (run-trunk.sh,
# board's re-exec); the handback pacer and the comment sweep run the owner
# checkout's copy. So `on` greps the copy each unit will actually run for its
# gate, and refuses a unit whose copy lacks it. Phase 1 units are safe on any
# copy:
#   - comments, issue-sweep and pr-sweep read, and post at most a comment;
#   - arms posts verdicts.
# They need nothing.
#
# The unit set and what each must find (docs/lanes/localforge/NOTES.md, step 5):
set -u
SHIM_BIN="${FORGE_SHIM_BIN:-$HOME/hakux-work/forge/shim/bin}"
UNITS_DIR="${FORGE_UNITS_DIR:-$HOME/.config/systemd/user}"
REPO="${HAKUX_REPO_DIR:-$HOME/hakuX}"
# master is read from the stand-in bare repo, origin itself: run-trunk.sh
# checks out exactly that, and reading it fetches nothing in anyone's tree.
BARE="${FORGE_SYNC_BARE:-$HOME/hakux-work/offline-git/hakuX.git}"
DROPIN=zz-forge-shim.conf
PHASE1="hakux-comments hakux-issue-sweep hakux-pr-sweep hakux-arms"
PHASE2="hakux-status hakux-board hakux-fold hakux-foldpace hakux-handbackpace"
# NOT ROUTED BY DESIGN: hakux-cloud (a claim starts a session; board.sh's dry
# run already stops its board-tick call) and hakux-hostops (a model session).

# requirement <unit> -> lines "<where> <path> <marker>"; where = master | checkout
requirement() {
    case "$1" in
        hakux-status)       echo "master docs/testing/jobs/status.sh HAKUX_FORGE" ;;
        hakux-board)        echo "master docs/testing/jobs/board.sh BOARD_DRY_RUN" ;;
        hakux-fold)         echo "master docs/testing/jobs/fold.sh FOLD_DRY_RUN"
                            echo "master docs/testing/jobs/handback.sh HANDBACK_DRY_RUN" ;;
        hakux-foldpace)     echo "master docs/testing/jobs/fold.sh FOLD_DRY_RUN" ;;
        hakux-handbackpace) echo "checkout docs/testing/jobs/handback.sh HANDBACK_DRY_RUN" ;;
        hakux-comments|hakux-issue-sweep|hakux-pr-sweep|hakux-arms) ;;
        *) return 1 ;;
    esac
}

# ready <unit> -> exit 0 if every requirement holds; prints the first that does not
ready() {
    local where path marker
    while read -r where path marker; do
        [ -n "$where" ] || continue
        case "$where" in
            master)   git --git-dir "$BARE" show "master:$path" 2>/dev/null | grep -q "$marker" \
                          || { echo "master:$path has no $marker (lane.localforge's PR is not folded yet)"; return 1; } ;;
            checkout) grep -q "$marker" "$REPO/$path" 2>/dev/null \
                          || { echo "$REPO/$path has no $marker (the owner checkout is behind master: git -C $REPO pull --ff-only)"; return 1; } ;;
        esac
    done < <(requirement "$1")
    return 0
}

write_dropin() {
    local u=$1 d="$UNITS_DIR/$1.service.d"
    mkdir -p "$d"
    cat > "$d/$DROPIN.new" <<EOF
# lane.localforge (2026-10-02): this job's \`gh\` is the local forge's shim.
# Remove this file (docs/testing/jobs/gh-shim/route.sh off $u) to route it back
# to /usr/bin/gh. HAKUX_FORGE=1 turns on the jobs' forge behaviour: board,
# handback and fold run dry, and status never pushes to github.com.
[Service]
Environment=PATH=$SHIM_BIN:$HOME/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin
Environment=HAKUX_FORGE=1
Environment=HAKUX_WEB_URL=http://127.0.0.1:3330
Environment=FORGE_USER=jobs
EOF
    mv -f "$d/$DROPIN.new" "$d/$DROPIN"
}

expand() {
    local x
    for x in "$@"; do
        case "$x" in
            phase1) echo $PHASE1 ;;
            phase2) echo $PHASE2 ;;
            all)    echo $PHASE1 $PHASE2 ;;
            *.service) echo "${x%.service}" ;;
            *)      echo "$x" ;;
        esac
    done
}

cmd="${1:-status}"; shift || true
case "$cmd" in
    status)
        [ -x "$SHIM_BIN/gh" ] && echo "shim: $SHIM_BIN/gh ($("$SHIM_BIN/gh" --version 2>&1 | head -1))" \
                               || echo "shim: NOT INSTALLED at $SHIM_BIN/gh (bash docs/testing/jobs/gh-shim/install.sh)"
        for u in $PHASE1 $PHASE2; do
            r=no; [ -f "$UNITS_DIR/$u.service.d/$DROPIN" ] && r=ROUTED
            why=$(ready "$u") && why="code ready"
            printf '%-20s %-7s %s\n' "$u" "$r" "$why"
        done ;;
    on)
        [ -x "$SHIM_BIN/gh" ] || { echo "route.sh: no shim at $SHIM_BIN/gh; install it first" >&2; exit 2; }
        rc=0; did=0
        for u in $(expand "$@"); do
            requirement "$u" >/dev/null || { echo "route.sh: unknown unit $u (known: $PHASE1 $PHASE2)" >&2; rc=2; continue; }
            if why=$(ready "$u"); then
                write_dropin "$u"; did=1; echo "routed $u"
            else
                echo "REFUSED $u: $why" >&2; rc=3
            fi
        done
        [ "$did" = 1 ] && systemctl --user daemon-reload
        exit $rc ;;
    off)
        did=0
        for u in $(expand "$@"); do
            [ -f "$UNITS_DIR/$u.service.d/$DROPIN" ] && { rm -f "$UNITS_DIR/$u.service.d/$DROPIN"; did=1; echo "unrouted $u"; }
        done
        [ "$did" = 1 ] && systemctl --user daemon-reload
        exit 0 ;;
    *) echo "usage: route.sh status | on <unit|phase1|phase2>... | off <unit|all>..." >&2; exit 2 ;;
esac
