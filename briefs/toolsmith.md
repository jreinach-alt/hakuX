# lane.toolsmith -- #94 and #95, both instruments you already own

Base: 55bc6c6c2beed87350cf1c02f67403afddc2acef (origin/master).
Files: your standing claim. #94 is docs/testing/request.sh; #95 is
docs/testing/ab_compare.py plus request.sh. Both are already yours -- nothing
to ask for.
Neither needs a device and neither needs a build.

GOAL:

1. #94, and it is the urgent one: request.sh:76-81 parses --suites, --tests,
   --skip-tests and --only-tests as SCALAR assignments, so a repeated flag
   silently clobbers all but the last. --env) ENV_VARS+=("$2") appends and is
   the shape to copy. Nothing in the parse loop detects a second occurrence.
   Confirmed by reading at HEAD and empirically: disc89-G-pre2 and
   disc89-H-pre8 both carry only_tests length 1 where 2 and 8 were passed.
   THE COST WAS NOT THE WASTED ARMS. disc89-H-pre8 was named for an 8-test
   prefix, ran ONE test, and its pre-registration said "0 puts the threshold
   in 9..32". It read 0. As registered, that arm concludes the threshold is
   9..32 when the answer is 2 -- a confident pre-registered wrong answer.
   Append, and make a repeated flag impossible to lose silently.
2. #95: the prediction schema has no composition field.
   ab_compare.py:1052-1085 writes registered_utc, who, issue, prediction,
   a_ref, b_ref, must_not_move, must_not_regress, expect, expect_counts and
   nothing else; request.sh:837-862 binds disc_id into the REQUEST and never
   into the prediction; ab_compare.py:486-489 refuses a pair whose two arms
   disagree on disc_id. So the easy case is caught and the case that bites --
   an absolute registered on one composition, judged against an arm run on
   another -- is structurally invisible. 1 of 107 prediction files carries a
   disc_id key.
   ORDERING CONSTRAINT, and it is a hard one: adding the field is
   backward-compatible; REFUSING a prediction that lacks it is NOT, and would
   invalidate 106 of 107 live predictions. Grandfather them explicitly and say
   how in the commit message.

FALSIFIER for #94: build a request with one flag per test for 8 tests and read
only_tests length out of the queued .req record. It is 8 or the fix is not in.
Its oracle is the request record itself -- no golden suite scores request.sh.

DONE WHEN: both patched, each with the check above actually run and its output
pasted; #95's grandfather path exercised against a real pre-existing
prediction file, not asserted. Draft PR from lane/toolsmith.
