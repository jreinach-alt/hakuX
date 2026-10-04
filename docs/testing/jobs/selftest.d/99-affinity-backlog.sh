# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check, and the live prediction ($EXP).
# Not executable, no shebang, no exit -- `fail` is shared and is the run's
# verdict.
#
# affinity: a new A/B pair goes to the handheld with less work ahead of it.
#
# WHY. affinity.py rule 3 hashed an unpinned pair's prediction name over the
# pooled handhelds and never looked at the queue. On 2026-09-27 forza414's
# pair hashed to the nova behind nine `device: nova` soaks (~2 h) while the
# thor served idle-tier `z-*` sweep legs; it waited 94 min for a hand re-pin
# (#502). The arms job now asks `affinity.py --choose` once per pair and
# writes the answer into BOTH arms, so the choice is made by one writer and
# the rule-2 race the hash was built to close stays closed.
#
# Builds its own dispatch trees under $T/afb and $T/afbw; touches nothing the
# other fragments read. Starts its own live pid and kills it at the end.

echo "== affinity: a new pair goes to the handheld with less work queued ahead of it"
AB="$T/afb"; mkdir -p "$AB"/{lanes,queue,running,results,splits}
AFF="$TESTING/affinity.py"
sleep 600 & ABLIVE=$!
sleep 0   & ABDEAD=$!; wait "$ABDEAD" 2>/dev/null
printf '%s\n' "$ABLIVE" > "$AB/lanes/nova"; printf '%s\n' "$ABLIVE" > "$AB/lanes/thor"

# A prediction name that rule 3 sends to the nova, found rather than assumed:
# the fixture is only the incident if the hash really points at the backlog.
abkey() {  # first "<stem>N.json" whose rule-3 hash over [nova, thor] is <device>
    python3 - "$1" "$2" <<'PY'
import hashlib, sys
stem, want = sys.argv[1:]
devs = ["nova", "thor"]
for i in range(1000):
    k = "%s%d.json" % (stem, i)
    if devs[int(hashlib.sha256(k.encode()).hexdigest()[:8], 16) % 2] == want:
        print(k); break
PY
}
K=$(abkey forza414-coalesce- nova)
aff() { python3 "$AFF" "$AB" "$1" 2>/dev/null; }
abreq() {  # <file> <json>
    printf '%s\n' "$2" > "$1"
}

# --- (a) the incident. Nine nova-pinned soaks ahead of the pair (~76 min by
# the pilot-gate estimate), one short request running on the thor. Behind the
# pair, and so NOT its problem: an idle-tier sweep leg and a later request,
# both pinned to the thor and each weighing more than the whole nova backlog.
# If either were counted the answer would flip to the nova.
for i in 0 1 2 3 4 5 6 7 8; do
    abreq "$AB/queue/1-179053000$i-titleplay-$i.req" \
        '{"requester":"titleplay","device":"nova","title":"t'"$i"'","seconds":420,"runs":1}'
done
abreq "$AB/queue/z-8fde5c2f78-001-2D_Lines.req" '{"requester":"full-sweep","device":"thor","seconds":99999}'
abreq "$AB/queue/1-1790540000-later-1.req"      '{"requester":"later","device":"thor","seconds":99999}'
abreq "$AB/running/0-1790533000-probe-1.req"    '{"requester":"probe","seconds":600,"runs":1}'
printf 'thor\n' > "$AB/running/0-1790533000-probe-1.owner"
BEFORE="1-1790534057"

check "fixture: rule 3 alone sends this prediction to the nova" \
    [ "$(python3 -c 'import hashlib,sys; print(["nova","thor"][int(hashlib.sha256(sys.argv[1].encode()).hexdigest()[:8],16)%2])' "$K")" = nova ]
abbl=$(python3 "$AFF" "$AB" --backlog "$BEFORE" 2>/dev/null)
check "--backlog prices the nine nova soaks at 9 x (420+90) s" grep -qx 'nova 4590' <<< "$abbl"
check "--backlog counts what remains of the running request on the thor, and nothing sorting after the pair" \
    python3 -c 'import sys; t=int([l.split()[1] for l in sys.stdin if l.startswith("thor ")][0]); sys.exit(0 if 600 <= t <= 690 else 1)' <<< "$abbl"
ABPIN=$(python3 "$AFF" "$AB" --choose "$K" "$BEFORE" 2>/dev/null)
check "--choose names the thor for a pair that hashes to the backlogged nova" [ "$ABPIN" = thor ]

# The pair as arms.sh now writes it: --device "$ABPIN" on both arms.
abreq "$AB/queue/$BEFORE-arms-forza414-base-1.req" '{"requester":"arms-forza414-base","expect":"/p/'"$K"'","device":"'"$ABPIN"'"}'
abreq "$AB/queue/$BEFORE-arms-forza414-fix-2.req"  '{"requester":"arms-forza414-fix","expect":"/p/'"$K"'","device":"'"$ABPIN"'"}'
aba=$(aff "$AB/queue/$BEFORE-arms-forza414-base-1.req"); abb=$(aff "$AB/queue/$BEFORE-arms-forza414-fix-2.req")
check "the pair lands on the thor" [ "$aba" = thor ]
check "with both arms on one device" [ -n "$aba" -a "$aba" = "$abb" ]
# MUTANT: the old rule 3 is this same pair with no `device` -- what arms.sh
# queued before. It must fail the check above, or that check sees nothing.
abreq "$AB/m-base.req" '{"requester":"arms-forza414-base","expect":"/p/'"$K"'"}'
abreq "$AB/m-fix.req"  '{"requester":"arms-forza414-fix","expect":"/p/'"$K"'"}'
rm -f "$AB/queue/$BEFORE-arms-forza414-"*.req
check "MUTANT: the unpinned pair (old rule 3) lands on the nova, and so fails 'lands on the thor'" \
    [ "$(aff "$AB/m-base.req")" = nova -a "$(aff "$AB/m-fix.req")" = nova ]

# Nothing to choose between: an empty queue keeps rule 3's answer (a tie goes
# to the hash), and one pooled device writes no pin at all.
mkdir -p "$T/afb0"/{lanes,queue,running,results}
cp "$AB/lanes/nova" "$AB/lanes/thor" "$T/afb0/lanes/"
check "an empty queue gives the device rule 3 would have (tie goes to the hash)" \
    [ "$(python3 "$AFF" "$T/afb0" --choose "$K" "$BEFORE")" = nova ]
rm -f "$T/afb0/lanes/thor"
check "one pooled device: --choose prints nothing, so arms.sh writes no pin" \
    [ -z "$(python3 "$AFF" "$T/afb0" --choose "$K" "$BEFORE")" ]
printf '%s\n' "$ABLIVE" > "$T/afb0/lanes/thor"; printf '%s\n' "$ABLIVE" > "$T/afb0/lanes/desktop"
check "the desktop lane is never chosen, however idle" \
    [ "$(python3 "$AFF" "$T/afb0" --choose "$K" "$BEFORE")" != desktop ]

# --- (b) rule 2 unchanged: an arm that ALREADY RAN on the nova still pulls its
# partner there, backlog or no backlog.
K2=$(abkey ran-on-nova- thor)
mkdir -p "$AB/results/r-base"
abreq "$AB/results/r-base/request.json" '{"expect":"/p/'"$K2"'"}'
abreq "$AB/results/r-base/result.json"  '{"device_label":"nova"}'
abreq "$AB/q-fix.req" '{"requester":"hand-fix","expect":"/p/'"$K2"'"}'
check "a pair whose first arm ran on the nova sends its second arm to the nova" \
    [ "$(aff "$AB/q-fix.req")" = nova ]

# --- (c) the race. Both arms are evaluated before either is claimed, and
# again with one arm caught mid-claim (renamed into running/, owner file not
# yet written) -- the instant rule 2 alone lost #13's pair in.
K3=$(abkey hand-pair- nova)
abreq "$AB/queue/1-1790534100-h-base-1.req" '{"requester":"h-base","expect":"/p/'"$K3"'","device":"thor"}'
abreq "$AB/queue/1-1790534100-h-fix-2.req"  '{"requester":"h-fix","expect":"/p/'"$K3"'"}'
abx=$(aff "$AB/queue/1-1790534100-h-base-1.req"); aby=$(aff "$AB/queue/1-1790534100-h-fix-2.req")
check "rule 2b: a hand-queued arm follows its QUEUED sibling's explicit device" [ "$aby" = thor ]
check "both arms, evaluated before either is claimed, agree" [ "$abx" = "$aby" ]
mv "$AB/queue/1-1790534100-h-base-1.req" "$AB/running/"
check "and still agree with the sibling mid-claim (in running/, no owner file yet)" \
    [ "$(aff "$AB/queue/1-1790534100-h-fix-2.req")" = thor ]
printf 'thor\n' > "$AB/running/1-1790534100-h-base-1.owner"
check "and once its owner file is written" [ "$(aff "$AB/queue/1-1790534100-h-fix-2.req")" = thor ]
rm -f "$AB/running/1-1790534100-h-base-1."*
abreq "$AB/q-free.req" '{"requester":"h-fix","expect":"/p/'"$K3"'"}'
check "CONTROL: without the sibling's pin this arm hashes to the nova, so 2b is what moved it" \
    [ "$(aff "$AB/q-free.req")" = nova ]
K4=$(abkey both-free- thor)
abreq "$AB/queue/1-1790534200-f-base-1.req" '{"requester":"f-base","expect":"/p/'"$K4"'"}'
abreq "$AB/queue/1-1790534200-f-fix-2.req"  '{"requester":"f-fix","expect":"/p/'"$K4"'"}'
check "a pair with no pin at all still agrees through the hash, before either is claimed" \
    [ "$(aff "$AB/queue/1-1790534200-f-base-1.req")" = "$(aff "$AB/queue/1-1790534200-f-fix-2.req")" ]

# --- the load pin is a preference. A pair the arms job pinned to the thor,
# with the thor gone, must move -- TOGETHER -- rather than wait for it. A
# `device` written by anyone else stays absolute.
K5=$(abkey pinned-then-gone- thor)
abreq "$AB/queue/1-1790534300-arms-g-base-1.req" '{"requester":"arms-g-base","expect":"/p/'"$K5"'","device":"thor"}'
abreq "$AB/queue/1-1790534300-arms-g-fix-2.req"  '{"requester":"arms-g-fix","expect":"/p/'"$K5"'","device":"thor"}'
printf '%s\n' "$ABDEAD" > "$AB/lanes/thor"
abg1=$(aff "$AB/queue/1-1790534300-arms-g-base-1.req"); abg2=$(aff "$AB/queue/1-1790534300-arms-g-fix-2.req")
# With the thor gone the nova is the only pooled device, so affinity leaves the
# arms free (""), which the nova's worker then takes; what matters is "not thor".
check "an arms-job pin to a device that stopped serving is not a stall" [ "$abg1" != thor ]
check "and both arms move together" [ "$abg1" = "$abg2" ]
abreq "$AB/q-soak.req" '{"requester":"titleplay","device":"thor","title":"only-on-thor","seconds":60}'
check "CONTROL: a hand-written device pin to a gone device still holds (rule 1)" [ "$(aff "$AB/q-soak.req")" = thor ]

# --- the hold lifts between the two claims (audit of #503, H1). The nova took
# the base arm while the thor was gone; the thor comes back before the fix arm
# is claimed. The fix arm's own load pin names the live thor, but its sibling
# is RUNNING on the nova, and the pair must stay there.
mv "$AB/queue/1-1790534300-arms-g-base-1.req" "$AB/running/"
printf 'nova\n' > "$AB/running/1-1790534300-arms-g-base-1.owner"
printf '%s\n' "$ABLIVE" > "$AB/lanes/thor"
check "after a hold lifts, the fix arm follows its base arm running on the nova, not its own load pin" \
    [ "$(aff "$AB/queue/1-1790534300-arms-g-fix-2.req")" = nova ]
# MUTANT: the load pin answered first whenever its device is live (this PR
# before remediation). It must answer thor here, or the check above is blind.
abmut=$(python3 - "$TESTING" "$AB" "$AB/queue/1-1790534300-arms-g-fix-2.req" <<'PY' 2>/dev/null
import os, sys
sys.path.insert(0, sys.argv[1])
import affinity as a
d, p = sys.argv[2], sys.argv[3]
orig = a.decide
def early(d, req, me, **kw):
    e = (req.get("device") or "").strip()
    return e if e and a._live(d, e) else orig(d, req, me, **kw)
print(early(d, a.load(p), os.path.basename(p)))
PY
)
check "MUTANT: a load pin that outranks a running sibling answers thor, and so fails the check above" [ "$abmut" = thor ]
# With nothing landed, the live load pin still decides: the base arm leaves
# running/ and the fix arm goes back to the thor.
rm -f "$AB/running/1-1790534300-arms-g-base-1."*
check "with no sibling landed, a live load pin is still where the arm goes" \
    [ "$(aff "$AB/queue/1-1790534300-arms-g-fix-2.req")" = thor ]
rm -f "$AB/queue/1-1790534300-arms-g-fix-2.req"

# --- the wiring. arms.sh, run for real against a private host whose nova is
# backlogged, queues both arms with --device thor.
ABW="$T/afbw"; ABD="$ABW/dispatch"
mkdir -p "$ABW"/{arms,logs/arms} "$ABD"/{lanes,queue,running,results,expect}
cp "$AB/lanes/nova" "$AB/lanes/thor" "$ABD/lanes/"
cp "$AB"/queue/1-179053000?-titleplay-*.req "$ABD/queue/"
KW=$(abkey arms-wire- nova)
python3 - "$EXP" "$ABD/expect/$KW" <<'PY'
import json, sys, datetime
e = json.load(open(sys.argv[1]))
e["registered_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
e["who"] = "lane.afbwire"
json.dump(e, open(sys.argv[2], "w"), indent=2)
PY
date -u -d '1 minute ago' '+%FT%TZ' > "$ABW/arms/since"
env HAKUX_WORK="$ABW" DISPATCH_DIR="$ABD" ARMS_QUEUE_MAX=50 bash "$HERE/arms.sh" > "$ABW/tick.out" 2>&1
abq=$(ls "$ABD"/queue/*arms-afbwire-*.req 2>/dev/null)
check "arms.sh queued both arms of the wired pair" [ "$(printf '%s\n' "$abq" | grep -c .)" -eq 2 ]
check "arms.sh wrote --device thor into both, away from the backlogged nova" \
    python3 -c 'import json,sys; sys.exit(0 if sorted(json.load(open(p)).get("device") for p in sys.argv[1:]) == ["thor","thor"] else 1)' $abq
check "and says so in its tick log" grep -q "device=thor" "$ABW/tick.out"

kill "$ABLIVE" 2>/dev/null; wait "$ABLIVE" 2>/dev/null
