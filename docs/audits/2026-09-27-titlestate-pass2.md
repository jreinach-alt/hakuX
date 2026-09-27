# Audit pass 2: PR #496, lane.titlestate (route.sh `flush`, GoldenEye: Rogue Agent save route)

Head audited: `41384cacc7` (remediation of pass 1 at `fa9f37de59`).

**Verdict: clean. Both MEDIUMs can no longer occur; LOW 2 is closed; LOW 1 stands as filed
(it does not fire in the tree). Goes to `fold-ready`.**

## MEDIUM 1: a fractional `flush` timeout: closed

The parser now tests the `flush` argument against `^[0-9]+$` (`route.sh:114`), not `isnum`.

- `wait 0 / flush 2.5`: `--check` exits 2 with `:2: flush wants a timeout in whole seconds`.
  On `fa9f37de59` the same file prints `route ok` (reproduced on both heads).
- Every value that now passes the parser is a decimal integer, so `flush_disk`'s
  `[ "$waited" -lt "$1" ]` cannot hit `integer expression expected`. A leading-zero value
  (`flush 0010`) passes and is read as decimal 10 by `test -lt`; `flush_disk` does no `$(( ))`
  arithmetic on it, so there is no octal path. A bare `flush` still passes and defaults to 10.

## MEDIUM 2: input between two flushes: closed

`FLUSH_AT` is now set only on the first `flush` (`route.sh:117`), and the post-flush scan
(`route.sh:125-132`) admits only blank, `wait` and `shot`, so a second `flush` is refused too.

- `flush 1 / press A / flush 1`: exits 2 with `:2: 'press' after flush: flush is the last step`.
  On `fa9f37de59`: `route ok` (reproduced on both heads).
- `flush 1 / repeat 2 { press A } / flush 1` (the repeat variant pass 1 named): exits 2 with
  `:2: 'repeat' after flush`.
- `routes/goldeneye-ra.save.route` still passes `--check` (116 lines).

## LOW 2: selftest coverage: closed

`selftest.d/99-title-state.sh` gains three rows: fractional timeout refused, input between two
flushes refused, and `flush / wait / shot` still accepted (the guard against over-refusal).
Run with only fragment 99 in a scratch worktree: 9 passed on `41384cacc7`; with
`fa9f37de59`'s `route.sh` swapped in, 7 passed and exactly the two new refusal rows FAIL.

## LOW 1: whole-second device clock: stands

Unchanged, as filed. No route backgrounds the app just before a flush, so it does not fire
today; not a fold blocker.
