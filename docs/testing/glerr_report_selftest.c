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

static char log_lines[256][512];
static size_t log_n;

static int __android_log_print(int prio, const char *tag, const char *fmt, ...)
{
    va_list ap;

    (void)prio;
    (void)tag;
    va_start(ap, fmt);
    vsnprintf(log_lines[log_n], sizeof(log_lines[0]), fmt, ap);
    va_end(ap);
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
    check(log_n == before + 1 &&
          strstr(log_lines[log_n - 1], "GL_OUT_OF_MEMORY") != NULL,
          "a distinct enum is reported despite an earlier one");

    /* Repeats: occurrences 2..9 are counted, 10 prints, 11..99 counted, 100
     * prints. NOTE these suppression legs pass vacuously against a block that
     * prints nothing -- they bound the flood, they do not detect silence. The
     * legs above are the ones that separate reporting from draining. */
    before = log_n;
    for (int i = 2; i <= 9; i++) {
        pending(GL_INVALID_OPERATION, GL_NO_ERROR);
        android_report_pending_gl_errors(&binding);
    }
    check(log_n == before, "occurrences 2..9 of a repeat are suppressed");
    pending(GL_INVALID_OPERATION, GL_NO_ERROR);
    android_report_pending_gl_errors(&binding);
    check(log_n == before + 1, "occurrence 10 prints");
    check(log_n == before + 1 &&
          strstr(log_lines[log_n - 1], "occurrence=10") != NULL,
          "the count that printed is the count reported");
    before = log_n;
    for (int i = 11; i <= 99; i++) {
        pending(GL_INVALID_OPERATION, GL_NO_ERROR);
        android_report_pending_gl_errors(&binding);
    }
    check(log_n == before, "occurrences 11..99 are suppressed");
    pending(GL_INVALID_OPERATION, GL_NO_ERROR);
    android_report_pending_gl_errors(&binding);
    check(log_n == before + 1 &&
          strstr(log_lines[log_n - 1], "occurrence=100") != NULL,
          "occurrence 100 prints");

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

    /* is_power_of_ten is the whole of the suppression rule. */
    check(is_power_of_ten(1) && is_power_of_ten(10) && is_power_of_ten(1000000),
          "powers of ten print");
    check(!is_power_of_ten(0) && !is_power_of_ten(2) &&
          !is_power_of_ten(99999999999ULL),
          "non-powers do not");

    printf("%s\n", failures ? "FAILURES" : "all checks passed");
    return failures != 0;
}
