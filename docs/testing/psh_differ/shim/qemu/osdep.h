/*
 * Stand-in for QEMU's osdep.h, for building the pixel-shader generator on its
 * own.
 *
 * The real header needs config-host.h, which only exists inside a configured
 * QEMU build tree. psh.c wants very little from it -- libc, glib, and a
 * handful of utility macros -- so supplying those directly lets the generator
 * compile in a second instead of after a full configure.
 *
 * Nothing here changes what the generator emits. If psh.c ever starts using a
 * real osdep facility, the compile fails loudly rather than drifting.
 */

#ifndef PSH_DIFFER_OSDEP_H
#define PSH_DIFFER_OSDEP_H

#include <assert.h>
#include <ctype.h>
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <math.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <glib.h>

/* qemu/compiler.h */
#define stringify_(s) #s
#define stringify(s) stringify_(s)
#define glue_(x, y) x##y
#define glue(x, y) glue_(x, y)

#ifndef ARRAY_SIZE
#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))
#endif
#ifndef MIN
#define MIN(a, b) (((a) < (b)) ? (a) : (b))
#endif
#ifndef MAX
#define MAX(a, b) (((a) > (b)) ? (a) : (b))
#endif

#define QEMU_BUILD_BUG_ON(x) _Static_assert(!(x), "not expecting: " #x)

#endif
