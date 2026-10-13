#!/usr/bin/env python3
"""github_gateway_selftest.py: round 4, defect 1 + defect 2's GH.create parsing, tested against the REAL
github_gateway.py functions (not the issue_mirror.py fakes, which never exercise this subprocess path at all).

Everything here runs against a temp state file, with token() and the HTTP call (_api) stubbed, so nothing ever
leaves this process: no network call, no token read from the real file, no write to the real
host-tools/.gateway-state.json. Never touches the real host-tools/ state this lane is staged under.

Covers:
  - two separate invocations, each under the run cap, both succeed (defect 1)
  - one invocation over the run cap refuses (defect 1)
  - the day cap refuses at its count (defect 1)
  - GH.create (issue_mirror.py) parses CREATED #N even when the gateway's exit code is non-zero (defect 2)
  - GH.create raises when no CREATED #N appears at all (a genuine create failure, defect 2)
"""
import contextlib
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import github_gateway as gw
import issue_mirror as im


@contextlib.contextmanager
def isolated_gateway():
    """Redirects gw.STATE / gw.WINDOW / gw.LOG to scratch temp files, stubs gw.token() and gw._api() so nothing
    leaves this process, and resets the module-global run-write counter -- restoring everything afterward."""
    tmpdir = tempfile.mkdtemp(prefix='github-gateway-selftest-')
    old = (gw.STATE, gw.WINDOW, gw.LOG, gw.token, gw._api, gw._RUN_WRITES, gw.MAX_WRITES_DAY)
    gw.STATE = os.path.join(tmpdir, 'state.json')
    gw.WINDOW = os.path.join(tmpdir, 'window')
    gw.LOG = os.path.join(tmpdir, 'log')
    gw.token = lambda: 'stub-token-never-real'
    gw._RUN_WRITES = 0
    try:
        yield tmpdir
    finally:
        gw.STATE, gw.WINDOW, gw.LOG, gw.token, gw._api, gw._RUN_WRITES, gw.MAX_WRITES_DAY = old


def new_invocation():
    """Mirrors a fresh `python3 github_gateway.py ...` process start: _RUN_WRITES is naturally 0 at the top of
    every one of those, with no reset logic needed in the real tool -- this just makes that explicit in a test
    that calls the function twice within one Python process."""
    gw._RUN_WRITES = 0


def silent(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*a, **kw)
    return rc, buf.getvalue()


def test_two_invocations_each_under_run_cap_both_succeed():
    """Defect 1: the old code kept the run-write counter in the PERSISTENT per-day bucket, so two separate
    invocations of 15 writes each (30 total, well under the new MAX_WRITES_DAY but over the old de-facto cap
    of MAX_WRITES_RUN_DEFAULT=20 for the whole day) would have refused at write #21 of the SECOND invocation.
    The fix makes each invocation's run cap process-local, so both complete in full."""
    with isolated_gateway():
        created = []

        def fake_api(method, url, tok, data=None, **kw):
            n = len(created) + 1
            created.append(n)
            return 201, {'number': n, 'html_url': 'http://x/%d' % n}

        gw._api = fake_api
        new_invocation()
        for i in range(15):
            rc, out = silent(gw.cmd_issue_create, 't%d' % i, 'b', yes=True, max_writes=20)
            assert rc == 0, 'invocation 1, write %d: rc=%r out=%s' % (i, rc, out)
        new_invocation()   # a brand new interpreter start: _RUN_WRITES is 0 again, with nothing to reset
        for i in range(15, 30):
            rc, out = silent(gw.cmd_issue_create, 't%d' % i, 'b', yes=True, max_writes=20)
            assert rc == 0, 'invocation 2, write %d: rc=%r out=%s' % (i, rc, out)
        s = gw.load_state()
        total = gw.day_counts(s)['writes']
        assert total == 30, 'persisted day writes=%d, expected 30 -- the old per-day-of-20 bug would have ' \
                             'refused write #21 of the second invocation' % total
        return ('two invocations of 15 writes each (run cap 20 each, 30 total) both completed in full -- the '
                'old bug would have refused the 2nd invocation\'s 6th write (the day\'s 21st overall)')


def test_one_invocation_over_run_cap_refuses():
    """Defect 1: within ONE invocation, the run cap still applies and still refuses once exceeded."""
    with isolated_gateway():
        def fake_api(method, url, tok, data=None, **kw):
            return 201, {'number': 1, 'html_url': 'x'}

        gw._api = fake_api
        new_invocation()
        rcs, outs = [], []
        for i in range(4):
            rc, out = silent(gw.cmd_issue_create, 't%d' % i, 'b', yes=True, max_writes=3)
            rcs.append(rc)
            outs.append(out)
        assert rcs[:3] == [0, 0, 0], rcs
        assert rcs[3] == 3, 'expected REFUSED (rc=3) on the 4th write of a run capped at 3: %r' % rcs
        assert 'REFUSED' in outs[3] and 'writes this run exceeds' in outs[3], outs[3]
        return 'one invocation, run cap 3: writes 1-3 succeed, write 4 REFUSED (rc=3)'


def test_day_cap_refuses_at_its_count():
    """Defect 1: MAX_WRITES_DAY is a separate, persisted cap -- refuses once the day's total reaches it, even
    on write #1 of a fresh invocation whose run cap is nowhere close to being hit."""
    with isolated_gateway():
        gw.MAX_WRITES_DAY = 5
        s = gw.load_state()
        c = gw.day_counts(s)
        c['writes'] = 5
        gw.save_state(s)
        new_invocation()

        def fake_api(method, url, tok, data=None, **kw):
            return 201, {'number': 1, 'html_url': 'x'}

        gw._api = fake_api
        rc, out = silent(gw.cmd_issue_create, 't', 'b', yes=True, max_writes=20)
        assert rc == 3, 'rc=%r out=%s' % (rc, out)
        assert 'REFUSED' in out and 'day cap' in out, out
        s2 = gw.load_state()
        assert gw.day_counts(s2)['writes'] == 5, 'the persisted day counter must not advance on a refusal'
        return 'day cap 5, already at 5: write #1 of a fresh invocation (run cap 20) REFUSED (rc=3), count unchanged'


class _FakeCompletedProcess:
    def __init__(self, stdout='', stderr='', returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_gh_create_parses_created_number_even_when_close_fails():
    """Defect 2: issue_mirror.py's GH.create() must return the number whenever 'CREATED #N' is in stdout, no
    matter the gateway's exit code -- this is the exact shape a failed follow-up close produces (create
    printed CREATED #N, then cmd_issue_patch failed and the whole subprocess exited non-zero)."""
    old_run = im.subprocess.run
    try:
        # Matches the real gateway's actual stdout shape: cmd_issue_create's own print('CREATED #N ...') is
        # followed, in the SAME process/stdout stream, by cmd_issue_patch's print('STOP: patch HTTP ...') when
        # the follow-up close fails -- both are plain print() calls, so both land on stdout, not stderr.
        im.subprocess.run = lambda args, capture_output=True, text=True: _FakeCompletedProcess(
            stdout='CREATED #42 http://x\nSTOP: patch HTTP 500 {}\n', stderr='', returncode=2)
        gh = im.GH(gateway='/dev/null')
        n, close_err = gh.create('t', 'b', state='closed')
        assert n == 42, n
        assert close_err, 'close_err must be set (non-None) when rc != 0 even though CREATED #N was printed'
        assert '500' in close_err or 'HTTP' in close_err, close_err
        return 'GH.create: CREATED #42 parsed and returned despite rc=2 (failed follow-up close); close_err set'
    finally:
        im.subprocess.run = old_run


def test_gh_create_raises_when_no_created_number_at_all():
    """Defect 2, the other half: when stdout never had 'CREATED #N' at all (a genuine create failure -- the
    POST /issues itself failed), GH.create must still raise, exactly as before. Nothing was spent to recover."""
    old_run = im.subprocess.run
    try:
        im.subprocess.run = lambda args, capture_output=True, text=True: _FakeCompletedProcess(
            stdout='', stderr='STOP: create HTTP 500 {}', returncode=2)
        gh = im.GH(gateway='/dev/null')
        try:
            gh.create('t', 'b')
            assert False, 'expected RuntimeError when no CREATED #N appears in stdout'
        except RuntimeError as e:
            assert '500' in str(e), e
        return 'GH.create: no CREATED #N in stdout -- raises RuntimeError, nothing to recover'
    finally:
        im.subprocess.run = old_run


TESTS = [
    test_two_invocations_each_under_run_cap_both_succeed,
    test_one_invocation_over_run_cap_refuses,
    test_day_cap_refuses_at_its_count,
    test_gh_create_parses_created_number_even_when_close_fails,
    test_gh_create_raises_when_no_created_number_at_all,
]


def main():
    passed, failed = [], []
    for t in TESTS:
        name = t.__name__
        try:
            detail = t()
            print('PASS %s -- %s' % (name, detail))
            passed.append(name)
        except Exception as e:
            print('FAIL %s -- %s: %s' % (name, type(e).__name__, e))
            failed.append(name)
    print('github_gateway_selftest: %d/%d passed%s' %
          (len(passed), len(TESTS), ('' if not failed else ' -- FAILED: ' + ', '.join(failed))))
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
