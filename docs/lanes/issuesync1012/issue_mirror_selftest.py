#!/usr/bin/env python3
"""issue_mirror_selftest.py -- lane.issuesync1012 round 2, gap 8.

Runs the REAL issue_mirror.py code (cmd_backfill, cmd_mirror_down, cmd_new, cmd_sync, cmd_seed, cmd_check,
secret_scan) against in-memory fakes (FakeGH, FakeFG below) that implement the exact same interface as the real
GH/FG clients (all_issues/comments/pull_detail/create/patch/comment). No subprocess, no curl, no network call of
any kind -- the fakes never touch a socket, which is a stronger guarantee than "localhost only".

State/lock/log files issue_mirror.py would otherwise read/write under host-tools/ are redirected to a scratch
temp path for the duration of each test (see `isolated`), so this file never touches real lane state.

Usage: python3 issue_mirror_selftest.py
Exit 0 and a line "issue_mirror_selftest: N/N passed" if every case passed; exit 1 otherwise, with FAIL lines
naming which case(s) broke.
"""
import contextlib
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import issue_mirror as im


# --------------------------------------------------------------------------------------------------------------
# Fakes -- same interface as im.GH / im.FG, backed by plain dicts, no I/O at all.
# --------------------------------------------------------------------------------------------------------------

class FakeGH:
    def __init__(self):
        self.items = {}
        self.comments_store = {}
        self._next_comment_id = 1000
        self._reachable = True
        self.force_wrong_number = None
        self.force_failure_once = False
        self.create_calls = 0

    def reachable(self):
        return self._reachable

    def all_issues(self, **kw):
        return dict(self.items)

    def comments(self, number):
        return list(self.comments_store.get(number, []))

    def create(self, title, body='', labels=(), state=None):
        prob = im.secret_scan(title, body)
        if prob:
            raise im.MirrorStop('REFUSED: %s -- GitHub create blocked' % prob)
        if self.force_failure_once:
            self.force_failure_once = False
            raise RuntimeError('simulated transient GitHub failure (nothing was spent)')
        self.create_calls += 1
        if self.force_wrong_number is not None:
            n, self.force_wrong_number = self.force_wrong_number, None
        else:
            n = (max(self.items) + 1) if self.items else 1
        self.items[n] = {'number': n, 'title': title, 'body': body, 'state': state or 'open',
                          'labels': [{'name': l} for l in labels], 'comments': 0}
        return n

    def patch(self, number, title=None, body=None, state=None, labels=None):
        prob = im.secret_scan(title or '', body or '')
        if prob:
            raise im.MirrorStop('REFUSED: %s -- GitHub patch #%d blocked' % (prob, number))
        it = self.items[number]
        if title is not None:
            it['title'] = title
        if body is not None:
            it['body'] = body
        if state is not None:
            it['state'] = state
        if labels is not None:
            it['labels'] = [{'name': l} for l in labels]
        return True

    def comment(self, number, body):
        prob = im.secret_scan(body)
        if prob:
            raise im.MirrorStop('REFUSED: %s -- GitHub comment on #%d blocked' % (prob, number))
        cid = self._next_comment_id
        self._next_comment_id += 1
        self.comments_store.setdefault(number, []).append(
            {'id': cid, 'user': {'login': 'gh-user'}, 'created_at': '2026-10-12T00:00:00Z', 'body': body})
        self.items[number]['comments'] = self.items[number].get('comments', 0) + 1
        return str(cid)


class FakeFG:
    def __init__(self):
        self.items = {}
        self.comments_store = {}
        self.pulls = {}
        self._next_comment_id = 2000
        self.force_wrong_number = None
        self.create_calls = 0

    def all_issues(self, **kw):
        return dict(self.items)

    def comments(self, number):
        return list(self.comments_store.get(number, []))

    def pull_detail(self, number):
        return dict(self.pulls.get(number, {}))

    def create(self, payload, is_pr=False):
        prob = im.secret_scan(payload.get('title', ''), payload.get('body', ''))
        if prob:
            raise im.MirrorStop('REFUSED: %s -- forge create blocked' % prob)
        self.create_calls += 1
        if self.force_wrong_number is not None:
            n, self.force_wrong_number = self.force_wrong_number, None
        else:
            n = (max(self.items) + 1) if self.items else 1
        labels = [l if isinstance(l, dict) else {'name': l} for l in payload.get('labels', [])]
        item = {'number': n, 'title': payload.get('title', ''), 'body': payload.get('body', ''),
                'state': 'open', 'labels': labels, 'comments': 0}
        if is_pr:
            item['pull_request'] = {'merged': False, 'merged_at': None, 'draft': False, 'html_url': ''}
            self.pulls[n] = {'number': n, 'title': payload.get('title', ''), 'body': payload.get('body', ''),
                              'state': 'open', 'merged': False, 'merge_commit_sha': None,
                              'head': {'ref': payload.get('head', '?')}, 'labels': labels}
        self.items[n] = item
        return n

    def patch(self, number, payload, is_pr=False):
        prob = im.secret_scan(payload.get('title', '') or '', payload.get('body', '') if isinstance(payload.get('body'), str) else '')
        if prob:
            raise im.MirrorStop('REFUSED: %s -- forge patch #%d blocked' % (prob, number))
        it = self.items.get(number)
        if it:
            if 'title' in payload:
                it['title'] = payload['title']
            if 'body' in payload:
                it['body'] = payload['body']
            if 'state' in payload:
                it['state'] = payload['state']
            if 'labels' in payload:
                it['labels'] = [l if isinstance(l, dict) else {'name': l} for l in payload['labels']]
        if number in self.pulls:
            pd = self.pulls[number]
            for k in ('title', 'state', 'merged', 'merge_commit_sha'):
                if k in payload:
                    pd[k] = payload[k]
            if 'labels' in payload:
                pd['labels'] = [l if isinstance(l, dict) else {'name': l} for l in payload['labels']]
        return True

    def comment(self, number, body):
        prob = im.secret_scan(body)
        if prob:
            raise im.MirrorStop('REFUSED: %s -- forge comment on #%d blocked' % (prob, number))
        cid = self._next_comment_id
        self._next_comment_id += 1
        self.comments_store.setdefault(number, []).append(
            {'id': cid, 'user': {'login': 'forge-user'}, 'created_at': '2026-10-12T00:00:00Z', 'body': body})
        self.items[number]['comments'] = self.items[number].get('comments', 0) + 1
        return cid


@contextlib.contextmanager
def isolated():
    """Redirects im.STATE / im.LOCK / im.LOG to scratch temp files for the duration of the block, restoring the
    module globals afterward. Never touches the real host-tools/ state this lane is staged under."""
    tmpdir = tempfile.mkdtemp(prefix='issue-mirror-selftest-')
    old = (im.STATE, im.LOCK, im.LOG)
    im.STATE = os.path.join(tmpdir, 'state.json')
    im.LOCK = os.path.join(tmpdir, 'lock')
    im.LOG = os.path.join(tmpdir, 'log')
    try:
        yield tmpdir
    finally:
        im.STATE, im.LOCK, im.LOG = old


def silent(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*a, **kw)
    return rc, buf.getvalue()


# --------------------------------------------------------------------------------------------------------------
# Test cases
# --------------------------------------------------------------------------------------------------------------

def mk_pair(gh, fg, n, title='item', body='body', state='open', labels=None, kind='issue'):
    labels = labels or []
    item = {'number': n, 'title': title, 'body': body, 'state': state,
            'labels': [{'name': l} for l in labels], 'comments': 0}
    gh.items[n] = dict(item)
    fg.items[n] = dict(item)
    if kind == 'PR':
        gh.items[n]['pull_request'] = {'url': 'x'}   # must be non-empty -- kind_of() treats {} as falsy, same as absent
        fg.items[n]['pull_request'] = {'merged': False, 'merged_at': None}
        fg.pulls[n] = {'number': n, 'title': title, 'body': body, 'state': state, 'merged': False,
                       'merge_commit_sha': None, 'head': {'ref': 'lane/x'}, 'labels': []}


def test_backfill_happy_path():
    with isolated():
        gh, fg = FakeGH(), FakeFG()
        for n in range(1, 6):
            mk_pair(gh, fg, n)
        mk_pair(gh, fg, 6, kind='never')  # placeholder, overwritten below
        del gh.items[6]
        fg.items[6] = {'number': 6, 'title': 'forge-only issue', 'body': 'b', 'state': 'open', 'labels': [], 'comments': 0}
        fg.items[7] = {'number': 7, 'title': 'forge-only pr', 'body': 'desc', 'state': 'open',
                       'labels': [], 'comments': 0, 'pull_request': {'merged': False, 'merged_at': None}}
        fg.pulls[7] = {'number': 7, 'title': 'forge-only pr', 'body': 'desc', 'state': 'open', 'merged': False,
                       'merge_commit_sha': None, 'head': {'ref': 'lane/foo'}, 'labels': []}
        rc, out = silent(im.cmd_backfill, gh, fg, True, 0, 6000, False)
        assert rc == 0, 'rc=%r out=%s' % (rc, out)
        assert 6 in gh.items and gh.items[6]['title'] == 'forge-only issue', gh.items.get(6)
        assert 7 in gh.items and gh.items[7]['title'] == '[PR] forge-only pr', gh.items.get(7)
        assert gh.items[7]['state'] == 'closed'
        return 'backfill happy path: #6 (issue) and #7 (PR, single shape) created on GitHub'


def test_pre_create_mismatch_refusal():
    with isolated():
        gh, fg = FakeGH(), FakeFG()
        for n in range(1, 7):
            mk_pair(gh, fg, n)   # gh max now 6
        fg.items[8] = {'number': 8, 'title': 'skipped ahead', 'body': 'b', 'state': 'open', 'labels': [], 'comments': 0}
        rc, out = silent(im.cmd_backfill, gh, fg, True, 0, 6000, False)
        assert rc == 3, 'expected REFUSED rc=3, got %r: %s' % (rc, out)
        assert 'REFUSED' in out
        assert gh.create_calls == 0, 'a number was spent despite the mismatch'
        return 'pre-create mismatch refusal: REFUSED, 0 GitHub numbers spent'


def test_post_create_mismatch_stop():
    with isolated():
        gh, fg = FakeGH(), FakeFG()
        for n in range(1, 6):
            mk_pair(gh, fg, n)
        fg.items[6] = {'number': 6, 'title': 'a', 'body': 'b', 'state': 'open', 'labels': [], 'comments': 0}
        fg.items[7] = {'number': 7, 'title': 'c', 'body': 'd', 'state': 'open', 'labels': [], 'comments': 0}
        gh.force_wrong_number = 99   # forge #6's twin comes back as GitHub #99
        rc, out = silent(im.cmd_backfill, gh, fg, True, 0, 6000, False)
        assert rc == 3, out
        assert 'STOP' in out
        assert 7 not in gh.items, 'the second item was created despite the first mismatch'
        st = im.load_state()
        assert st.get('backfill_last_done', 0) == 0, 'resume cursor advanced past a mismatch'
        return 'post-create mismatch stop: STOP on #6->#99, #7 never attempted'


def test_resume_after_stop():
    with isolated():
        gh, fg = FakeGH(), FakeFG()
        for n in range(1, 6):
            mk_pair(gh, fg, n)
        fg.items[6] = {'number': 6, 'title': 'a', 'body': 'b', 'state': 'open', 'labels': [], 'comments': 0}
        fg.items[7] = {'number': 7, 'title': 'c', 'body': 'd', 'state': 'open', 'labels': [], 'comments': 0}
        rc1, out1 = silent(im.cmd_backfill, gh, fg, True, 1, 6000, False)
        assert rc1 == 0 and 6 in gh.items, out1
        gh.force_failure_once = True   # a transient create failure: nothing spent, resume cursor unmoved
        rc2, out2 = silent(im.cmd_backfill, gh, fg, True, 0, 6000, False)
        assert rc2 == 2 and 7 not in gh.items, out2
        assert im.load_state().get('backfill_last_done') == 6, 'resume cursor moved despite the failed create'
        rc3, out3 = silent(im.cmd_backfill, gh, fg, True, 0, 6000, False)
        assert rc3 == 0, out3
        assert 7 in gh.items and gh.items[7]['title'] == 'c', out3
        return 'resume after stop: #6 done, transient failure on #7 (nothing spent), resume completes #7'


def test_mirror_down_issue_and_pr():
    with isolated():
        gh, fg = FakeGH(), FakeFG()
        gh.items[1] = {'number': 1, 'title': 'hello', 'body': 'world', 'state': 'closed', 'labels': [{'name': 'bug'}], 'comments': 0}
        gh.items[2] = {'number': 2, 'title': 'add x', 'body': 'pr body', 'state': 'open', 'labels': [],
                       'comments': 0, 'pull_request': {'url': 'x'}}
        # #3 is deliberately absent on GitHub (a gap) to exercise the "reserved placeholder" path too.
        gh.items[4] = {'number': 4, 'title': 'later issue', 'body': 'z', 'state': 'open', 'labels': [], 'comments': 0}
        rc = im.cmd_mirror_down(gh, fg, True)
        assert rc == 0
        assert fg.items[1]['title'] == 'hello' and fg.items[1]['state'] == 'closed' and 'bug' in [l['name'] for l in fg.items[1]['labels']]
        assert im.has_marker(fg.items[1])
        assert fg.items[2]['title'] == '[GitHub PR] add x'
        assert fg.items[3]['title'].startswith('#3: reserved'), fg.items.get(3)
        assert fg.items[3]['state'] == 'closed'
        assert fg.items[4]['title'] == 'later issue'
        return 'mirror-down: public issue, public PR ([GitHub PR] shape), and a GitHub gap (reserved placeholder)'


def test_new_refuses_when_forge_ahead():
    with isolated():
        gh, fg = FakeGH(), FakeFG()
        for n in range(1, 6):
            mk_pair(gh, fg, n)
        fg.items[6] = {'number': 6, 'title': 'ahead', 'body': 'b', 'state': 'open', 'labels': [], 'comments': 0}
        rc, out = silent(im.cmd_new, gh, fg, 'issue', 'new thing', '', 'jobs', True)
        assert rc == 3 and 'REFUSED' in out, out
        assert gh.create_calls == 0 and fg.create_calls == 0
        return 'new refuses when forge is ahead: REFUSED, nothing spent on either side'


def test_new_mirrors_down_first_when_github_ahead():
    with isolated():
        gh, fg = FakeGH(), FakeFG()
        for n in range(1, 6):
            mk_pair(gh, fg, n)
        gh.items[6] = {'number': 6, 'title': 'ahead on github', 'body': 'b', 'state': 'open', 'labels': [], 'comments': 0}
        rc, out = silent(im.cmd_new, gh, fg, 'issue', 'new thing', 'body text', 'jobs', True)
        assert rc == 0, out
        assert 6 in fg.items and fg.items[6]['title'] == 'ahead on github', fg.items.get(6)
        assert 7 in gh.items and 7 in fg.items and gh.items[7]['title'] == 'new thing'
        return 'new mirrors GitHub-ahead #6 down first, then allocates #7 on both sides'


def test_three_way_sync_echo_suppression():
    with isolated():
        gh, fg = FakeGH(), FakeFG()
        # #1 only (no gap below it), so sync's preliminary mirror-down step has nothing to do -- this test is
        # about the field-level three-way merge, not mirror-down.
        mk_pair(gh, fg, 1, title='original title', body='original body', state='open', labels=['keep'])
        rc0, out0 = silent(im.cmd_sync, gh, fg, True)
        assert rc0 == 0, out0
        fg.items[1]['title'] = 'retitled on the forge'
        rc1, out1 = silent(im.cmd_sync, gh, fg, True)
        assert rc1 == 0, out1
        assert gh.items[1]['title'] == 'retitled on the forge', out1
        rc2, out2 = silent(im.cmd_sync, gh, fg, True)
        assert rc2 == 0, out2
        assert '0 field actions' in out2, 'a settled field was re-applied: %s' % out2
        return 'three-way sync: forge title change propagates once, re-run is a no-op (0 field actions)'


def test_pr_twin_status_rewrite_on_fold():
    with isolated():
        gh, fg = FakeGH(), FakeFG()
        # #1 only (no gap below it), so sync's preliminary mirror-down step has nothing to do.
        gh.items[1] = {'number': 1, 'title': '[PR] my change', 'body': 'placeholder', 'state': 'closed', 'labels': [], 'comments': 0}
        fg.items[1] = {'number': 1, 'title': 'my change', 'body': 'desc', 'state': 'open', 'labels': [], 'comments': 0,
                       'pull_request': {'merged': False, 'merged_at': None}}
        fg.pulls[1] = {'number': 1, 'title': 'my change', 'body': 'desc', 'state': 'open', 'merged': False,
                       'merge_commit_sha': None, 'head': {'ref': 'lane/change'}, 'labels': []}
        rc0, _ = silent(im.cmd_sync, gh, fg, True)
        assert rc0 == 0
        assert 'open' in gh.items[1]['body'].lower()
        fg.items[1]['labels'] = [{'name': 'folded'}]
        fg.pulls[1]['labels'] = [{'name': 'folded'}]
        rc1, out1 = silent(im.cmd_sync, gh, fg, True)
        assert rc1 == 0, out1
        assert 'folded' in gh.items[1]['body'].lower() and 'not recorded it as merged yet' in gh.items[1]['body'], gh.items[1]['body']
        return 'PR-twin status rewrite: body status line updates open -> folded-unmerged on a label change'


def test_comment_mirroring_both_ways_once_each():
    with isolated():
        gh, fg = FakeGH(), FakeFG()
        # #1 only (no gap below it), so sync's preliminary mirror-down step has nothing to do.
        mk_pair(gh, fg, 1, title='t', body='b', state='open', labels=[])
        rc0, _ = silent(im.cmd_sync, gh, fg, True)
        assert rc0 == 0
        gh.comment(1, 'a github comment')
        fg.comment(1, 'a forge comment')
        rc1, out1 = silent(im.cmd_sync, gh, fg, True)
        assert rc1 == 0, out1
        assert len(fg.comments_store[1]) == 2, fg.comments_store[1]   # original forge comment + mirrored github one
        assert len(gh.comments_store[1]) == 2, gh.comments_store[1]
        assert im.COMMENT_MARKER_RE.search(fg.comments_store[1][-1]['body'])
        assert im.COMMENT_MARKER_RE.search(gh.comments_store[1][-1]['body'])
        rc2, out2 = silent(im.cmd_sync, gh, fg, True)
        assert rc2 == 0, out2
        assert len(fg.comments_store[1]) == 2 and len(gh.comments_store[1]) == 2, 'a mirrored comment echoed back'
        return 'comment mirroring: one each way, marker-tagged, no echo on the next run'


def test_seed_then_quiet_sync():
    with isolated():
        gh, fg = FakeGH(), FakeFG()
        mk_pair(gh, fg, 2, title='settled', body='settled body', state='open', labels=[])
        gh.items[16] = {'number': 16, 'title': 'needs closing', 'body': 'b', 'state': 'closed', 'labels': [], 'comments': 0}
        fg.items[16] = {'number': 16, 'title': 'needs closing', 'body': 'b', 'state': 'open', 'labels': [], 'comments': 0}
        gh.items[1] = {'number': 1, 'title': 'real title', 'body': 'real body', 'state': 'open', 'labels': [], 'comments': 0}
        fg.items[1] = {'number': 1, 'title': '#1: not recovered', 'body': '(lost)', 'state': 'open', 'labels': [], 'comments': 0}
        rc, out = silent(im.cmd_seed, gh, fg, True)
        assert rc == 0, out
        assert fg.items[16]['state'] == 'closed', out
        assert fg.items[1]['title'] == 'real title', out
        rc2, out2 = silent(im.cmd_sync, gh, fg, False)
        assert rc2 == 0, out2
        assert '0 field actions, 0 conflicts' in out2, 'seed did not leave a quiet dry-run sync: %s' % out2
        return 'seed applies the resolutions, then a dry-run sync reports 0 actions and 0 conflicts'


def test_secret_scan_refuses_token_body():
    prob = im.secret_scan(None, 'leaked: ghp_' + 'A' * 36)
    assert prob, 'secret_scan missed a token-shaped string'
    gh = FakeGH()
    try:
        gh.create('title', 'body with ghp_' + 'B' * 36)
        assert False, 'create() did not raise on a token-shaped body'
    except im.MirrorStop as e:
        assert 'REFUSED' in str(e)
    assert gh.create_calls == 0 and not gh.items, 'a number was spent despite the secret scan'
    return 'secret scan: refuses a token-shaped body before GitHub create spends a number'


TESTS = [
    test_backfill_happy_path,
    test_pre_create_mismatch_refusal,
    test_post_create_mismatch_stop,
    test_resume_after_stop,
    test_mirror_down_issue_and_pr,
    test_new_refuses_when_forge_ahead,
    test_new_mirrors_down_first_when_github_ahead,
    test_three_way_sync_echo_suppression,
    test_pr_twin_status_rewrite_on_fold,
    test_comment_mirroring_both_ways_once_each,
    test_seed_then_quiet_sync,
    test_secret_scan_refuses_token_body,
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
    print('issue_mirror_selftest: %d/%d passed%s' %
          (len(passed), len(TESTS), ('' if not failed else ' -- FAILED: ' + ', '.join(failed))))
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
