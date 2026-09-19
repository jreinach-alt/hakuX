/*
 * Stub harness for the __ANDROID__ GL-error report in gl/shaders.c (#86).
 *
 * Driven by docs/testing/glerr_report_selftest.sh, which slices the block out
 * of shaders.c and names the slice with -DBLOCK_INC. Nothing here is a copy of
 * the code under test: a copy would drift.
 *
 * The block is Android-only, and an agent worktree has no NDK, so the arm that
 * ships cannot be compiled here at all. What can be done is compile its exact
 * text with a real compiler against stubs of the same shapes -- twice, once
 * with the desktop-GL header set and once without the three error codes GLES
 * does not define -- and run the part with a decision in it against a scripted
 * glGetError backlog.
 *
 * What this does NOT check: that shaders.c compiles, that the NDK's headers
 * define what the guards assume, or that anything reaches logcat. Those need
 * the Android build and a device.
 */
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef unsigned int GLenum;

#define GL_NO_ERROR                      0
#define GL_INVALID_ENUM                  0x0500
#define GL_INVALID_VALUE                 0x0501
#define GL_INVALID_OPERATION             0x0502
#define GL_OUT_OF_MEMORY                 0x0505
#define GL_INVALID_FRAMEBUFFER_OPERATION 0x0506
#ifndef GLES_LIKE
/* The desktop-GL header set. Built again with -DGLES_LIKE to get the GLES one,
 * where these three are absent -- which is the header set the Android arm is
 * actually compiled against, and the reason the switch guards each of them
 * with #ifdef. */
#define GL_STACK_OVERFLOW                0x0503
#define GL_STACK_UNDERFLOW               0x0504
#define GL_CONTEXT_LOST                  0x0507
#endif

#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))

#define ANDROID_LOG_WARN 5

/* The context's backlog, scripted: glGetError() pops the next queued error. */
static GLenum queued[64];
static size_t queued_n, queued_i;

static GLenum glGetError(void)
{
    return queued_i < queued_n ? queued[queued_i++] : GL_NO_ERROR;
}

/* log_n counts every line the block emitted; the store keeps the first 64 of
 * them and, separately, the most recent one. The budget leg deliberately
 * drives more lines than the store holds, and a store that overflowed would
 * corrupt the very count it is checked against -- so the count lives outside
 * the store, and no leg indexes past what was kept. */
static char log_lines[64][512];
static char log_last[512];
static size_t log_n;

static int __android_log_print(int prio, const char *tag, const char *fmt, ...)
{
    va_list ap;

    (void)prio;
    (void)tag;
    va_start(ap, fmt);
    vsnprintf(log_last, sizeof(log_last), fmt, ap);
    va_end(ap);
    if (log_n < sizeof(log_lines) / sizeof(log_lines[0])) {
        snprintf(log_lines[log_n], sizeof(log_lines[0]), "%s", log_last);
    }
    log_n++;
    return 0;
}

typedef struct ShaderBinding {
    struct { uint64_t hash; } node;
} ShaderBinding;

/* Named by the command line, never by a quoted path: a quoted include is
 * resolved against this file's own directory before any -I, so the
 * falsification build silently got the real block the first time this was
 * written, and reported "all checks passed" for the pre-#86 code. */
#ifndef BLOCK_INC
#error "build with -DBLOCK_INC=\"<path to the sliced block>\""
#endif
#include BLOCK_INC

static int failures;

static void check(bool ok, const char *what)
{
    printf("%s %s\n", ok ? "ok  " : "FAIL", what);
    failures += !ok;
}

static void pending(GLenum a, GLenum b)
{
    queued_n = queued_i = 0;
    if (a) {
        queued[queued_n++] = a;
    }
    if (b) {
        queued[queued_n++] = b;
    }
}

int main(void)
{
    ShaderBinding binding = { .node = { .hash = 0xdeadbeefcafeULL } };
    size_t before;

    /* A clean context logs nothing at all: the common case must stay quiet. */
    for (int i = 0; i < 100; i++) {
        pending(GL_NO_ERROR, GL_NO_ERROR);
        android_report_pending_gl_errors(&binding);
    }
    check(log_n == 0, "no pending error -> no [glerr] line");

    /* The first occurrence of an enum is named, with its enum and its shader.
     * This is the leg #86 is about: under the old silent drain it is what
     * fails, and it fails five ways. */
    pending(GL_INVALID_OPERATION, GL_NO_ERROR);
    android_report_pending_gl_errors(&binding);
    check(log_n == 1, "first pending error -> exactly one line");
    check(log_n == 1 && strstr(log_lines[0], "[glerr]") != NULL,
          "the line carries the [glerr] tag a device run greps for");
    check(log_n == 1 && strstr(log_lines[0], "GL_INVALID_OPERATION") != NULL,
          "names the enum");
    check(log_n == 1 && strstr(log_lines[0], "0x502") != NULL,
          "names the raw code");
    check(log_n == 1 && strstr(log_lines[0], "deadbeefcafe") != NULL,
          "names the shader");

    /* A second distinct enum is not suppressed by the first. */
    before = log_n;
    pending(GL_OUT_OF_MEMORY, GL_NO_ERROR);
    android_report_pending_gl_errors(&binding);
    check(log_n == before + 1 && strstr(log_last, "GL_OUT_OF_MEMORY") != NULL,
          "a distinct enum is reported despite an earlier one");

    /* Repeats print. The call site runs once per shader-cache miss, not once
     * per frame, so the line per load is affordable -- and it is what carries
     * the per-load shader hash, which is the whole diagnostic: a repeat that
     * is counted instead of printed is a hash that never appears. */
    before = log_n;
    for (int i = 0; i < 10; i++) {
        pending(GL_INVALID_OPERATION, GL_NO_ERROR);
        android_report_pending_gl_errors(&binding);
    }
    check(log_n == before + 10,
          "every occurrence of a repeat prints, one line per load");
    check(strstr(log_last, "report=") != NULL,
          "each line carries its report index");

    /* More distinct enums than a small per-enum table has slots for. This is
     * the state the block used to keep and no longer does: a table whose last
     * slot is shared re-keys on every alternation between two codes that land
     * in it, which suppresses nothing at all and reports every line as the
     * first occurrence. Both halves are checked -- the count, and that the
     * index keeps climbing. */
    {
        static const GLenum many[] = {
            GL_INVALID_ENUM, GL_INVALID_VALUE, GL_INVALID_OPERATION,
            GL_OUT_OF_MEMORY, GL_INVALID_FRAMEBUFFER_OPERATION,
            0x8000, 0x8001, 0x8002, 0x8003, 0x8004,
        };

        before = log_n;
        for (size_t i = 0; i < ARRAY_SIZE(many); i++) {
            pending(many[i], GL_NO_ERROR);
            android_report_pending_gl_errors(&binding);
        }
        check(log_n == before + ARRAY_SIZE(many),
              "ten distinct enums, more than any slot table holds -> ten lines");
    }
    {
        char want[64];

        before = log_n;
        for (int i = 0; i < 40; i++) {
            pending(i % 2 ? 0x8005 : 0x8006, GL_NO_ERROR);
            android_report_pending_gl_errors(&binding);
        }
        check(log_n == before + 40,
              "40 loads alternating between two enums -> 40 lines");
        snprintf(want, sizeof(want), "report=%zu", log_n);
        check(strstr(log_last, want) != NULL,
              "the report index counts up rather than resetting to 1");
    }

    /* The drain still drains. A backlog of two must leave the context clean,
     * or the glGetError after glProgramBinary() at the call site reads a stale
     * error and rejects a good shader binary. */
    pending(GL_INVALID_VALUE, GL_INVALID_ENUM);
    android_report_pending_gl_errors(&binding);
    check(glGetError() == GL_NO_ERROR, "the backlog is fully drained");

    /* Every error code this header set defines has a name, and an undefined
     * one still prints rather than being dropped for want of a name. */
    {
        static const GLenum defined_codes[] = {
            GL_INVALID_ENUM, GL_INVALID_VALUE, GL_INVALID_OPERATION,
            GL_OUT_OF_MEMORY, GL_INVALID_FRAMEBUFFER_OPERATION,
#ifndef GLES_LIKE
            GL_STACK_OVERFLOW, GL_STACK_UNDERFLOW, GL_CONTEXT_LOST,
#endif
        };
        bool all_named = true;

        for (size_t i = 0; i < ARRAY_SIZE(defined_codes); i++) {
            const char *n = gl_error_name(defined_codes[i]);

            all_named &= strncmp(n, "GL_", 3) == 0 &&
                         strcmp(n, "GL_ERROR_UNRECOGNISED") != 0;
        }
        check(all_named, "every error code this header set defines has a name");
    }
    check(strcmp(gl_error_name(0x8000), "GL_ERROR_UNRECOGNISED") == 0,
          "a vendor code falls back to a name rather than to nothing");
    before = log_n;
    pending(0x8000, GL_NO_ERROR);
    android_report_pending_gl_errors(&binding);
    check(log_n == before + 1, "a vendor code is reported too");

    /* The budget, driven past on purpose, and last: it is the one piece of
     * state the block keeps, and exhausting it is permanent. A renderer
     * leaving an error pending at most loads must not be able to make the log
     * unreadable, so the count settles at the budget plus the one line that
     * says it stopped -- and the drain keeps running underneath it. */
    for (int i = 0; i < ANDROID_GLERR_MAX_REPORTS + 8; i++) {
        pending(GL_INVALID_VALUE, GL_INVALID_ENUM);
        android_report_pending_gl_errors(&binding);
    }
    check(log_n == (size_t)ANDROID_GLERR_MAX_REPORTS + 1,
          "past the budget the line count stops at the budget plus one");
    check(strstr(log_last, "no longer") != NULL &&
          strstr(log_last, "drained") != NULL,
          "the last line says reporting stopped and draining did not");

    /* Vacuous against silence, like any leg about what is NOT printed: it is
     * here because the drain outliving the budget is the property that keeps
     * the glProgramBinary check below the call site honest. */
    before = log_n;
    pending(GL_INVALID_ENUM, GL_INVALID_VALUE);
    android_report_pending_gl_errors(&binding);
    check(glGetError() == GL_NO_ERROR && log_n == before,
          "past the budget the backlog is still drained, and silently");

    printf("%s\n", failures ? "FAILURES" : "all checks passed");
    return failures != 0;
}
