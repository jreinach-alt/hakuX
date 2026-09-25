/* The probe's config file parser, in a header so it can be tested.
 *
 * Why a header and not twenty lines inside main.c: main.c is compiled by
 * nothing on this side of the wire -- it needs nxdk, hal/debug.h and an Xbox
 * to run on -- so anything living in it is unreachable by run_tests.sh, which
 * is the suite that exists to mutate this tool's decisions. This file has no
 * Xbox dependency at all, so test_probe_cfg.c compiles it on the host and
 * run_tests.sh mutates it. A parser that decides which host the console dials
 * is not a place for untested code.
 *
 * What it parses: "key=value" per line, from D:\nv2a_probe.cfg next to the
 * XBE. Blank lines and lines starting '#' or ';' are ignored. Keys are host,
 * port, dhcp, ip, mask, gw.
 *
 * Everything it will not parse is REPORTED rather than dropped. The first
 * version dropped silently, and a cfg that was present but wholly unparsed
 * looked, on the console's screen, exactly like no cfg at all -- the probe
 * dialled a compiled-in address and nothing said why.
 */
#ifndef PROBE_CFG_H
#define PROBE_CFG_H

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PROBE_CFG_PATH "D:\\nv2a_probe.cfg"
#define PROBE_CFG_LINE 192

typedef struct {
    char host[64];
    char ip[32];
    char mask[32];
    char gw[32];
    int  port;
    bool dhcp;

    /* Diagnostics. None of this changes behaviour; it exists so the screen can
     * distinguish "no cfg" from "a cfg none of which parsed". */
    bool present;          /* the file was opened */
    int  applied;          /* records that took effect */
    int  rejected;         /* records refused, each one reported */
    char last_reject[80];  /* the most recent one, for the one-line summary */
} probe_cfg_t;

static inline void probe_cfg_defaults(probe_cfg_t *c)
{
    memset(c, 0, sizeof(*c));
    strcpy(c->host, "192.168.50.2");
    strcpy(c->ip,   "192.168.50.1");
    strcpy(c->mask, "255.255.255.0");
    strcpy(c->gw,   "192.168.50.2");
    c->port = 24242;
    c->dhcp = false;
}

static inline void probe_cfg__reject(probe_cfg_t *c, const char *what,
                                     const char *detail)
{
    c->rejected++;
    snprintf(c->last_reject, sizeof(c->last_reject), "%s (%s)", what, detail);
}

/* Trim ASCII whitespace, including \r, from both ends. In place. */
static inline char *probe_cfg__trim(char *s)
{
    char *end;
    while (*s == ' ' || *s == '\t' || *s == '\r' || *s == '\n') ++s;
    end = s + strlen(s);
    while (end > s) {
        char c = end[-1];
        if (c != ' ' && c != '\t' && c != '\r' && c != '\n') break;
        *--end = 0;
    }
    return s;
}

/* A value is copied only if it FITS. Truncating an address silently is how you
 * get a probe dialling a host that is a prefix of the one in the file. */
static inline void probe_cfg__str(probe_cfg_t *c, char *dst, size_t cap,
                                  const char *key, const char *val)
{
    if (!*val) { probe_cfg__reject(c, key, "empty value"); return; }
    if (strlen(val) >= cap) { probe_cfg__reject(c, key, "value too long"); return; }
    strcpy(dst, val);
    c->applied++;
}

/* 1/0, true/false, yes/no, on/off -- case-insensitively. NOT "anything whose
 * first character is 1": `dhcp=true` meant static mode under that rule, and
 * the probe then dialled an address that does not exist under slirp. */
static inline bool probe_cfg__bool(const char *v, bool *out)
{
    static const char *yes[] = { "1", "true", "yes", "on" };
    static const char *no[]  = { "0", "false", "no", "off" };
    char low[8];
    size_t j, n = strlen(v);
    int i;

    if (n >= sizeof(low)) return false;   /* no boolean spelling is this long */
    for (j = 0; j <= n; ++j)
        low[j] = (v[j] >= 'A' && v[j] <= 'Z') ? (char)(v[j] + 32) : v[j];
    for (i = 0; i < 4; ++i) {
        if (!strcmp(low, yes[i])) { *out = true;  return true; }
        if (!strcmp(low, no[i]))  { *out = false; return true; }
    }
    return false;
}

/* Digits only, and inside the range a TCP port can actually be. atoi() gave 0
 * for `port=` and for `port=http`, and the probe then dialled port 0 for the
 * whole 120-second no-host window with nothing on screen naming the cause. */
static inline bool probe_cfg__port(const char *v, int *out)
{
    long n = 0;
    const char *p = v;
    if (!*p) return false;
    for (; *p; ++p) {
        if (*p < '0' || *p > '9') return false;
        n = n * 10 + (*p - '0');
        if (n > 65535) return false;
    }
    if (n < 1) return false;
    *out = (int)n;
    return true;
}

/* Apply one record. `rec` is modified in place. */
static inline void probe_cfg_apply(probe_cfg_t *c, char *rec)
{
    char *key, *val, *eq;

    key = probe_cfg__trim(rec);
    if (!*key || *key == '#' || *key == ';') return;   /* blank or comment */

    eq = strchr(key, '=');
    if (!eq) { probe_cfg__reject(c, key, "no '=' in the line"); return; }
    *eq = 0;
    val = probe_cfg__trim(eq + 1);
    key = probe_cfg__trim(key);

    if (!strcmp(key, "host"))      probe_cfg__str(c, c->host, sizeof(c->host), key, val);
    else if (!strcmp(key, "ip"))   probe_cfg__str(c, c->ip,   sizeof(c->ip),   key, val);
    else if (!strcmp(key, "mask")) probe_cfg__str(c, c->mask, sizeof(c->mask), key, val);
    else if (!strcmp(key, "gw"))   probe_cfg__str(c, c->gw,   sizeof(c->gw),   key, val);
    else if (!strcmp(key, "port")) {
        int p;
        if (probe_cfg__port(val, &p)) { c->port = p; c->applied++; }
        else probe_cfg__reject(c, key, "not a port in 1..65535");
    } else if (!strcmp(key, "dhcp")) {
        bool b;
        if (probe_cfg__bool(val, &b)) { c->dhcp = b; c->applied++; }
        else probe_cfg__reject(c, key, "not a boolean");
    } else {
        probe_cfg__reject(c, key, "unknown key");
    }
}

/* Read a whole config stream. The caller has already called
 * probe_cfg_defaults(); anything not mentioned in the file keeps its default.
 */
static inline void probe_cfg_read(probe_cfg_t *c, FILE *f)
{
    char line[PROBE_CFG_LINE];

    c->present = true;
    while (fgets(line, sizeof(line), f)) {
        size_t n = strlen(line);
        if (n && line[n - 1] != '\n' && !feof(f)) {
            /* The line did not fit. fgets hands back its head and leaves the
             * tail in the stream, where the next read parses it as a fresh
             * record -- so "host=<90 chars>" became a line with no '=' that
             * was silently dropped, or worse, a tail that happened to contain
             * one. Drain the rest of the line and refuse the whole record. */
            int ch;
            while ((ch = fgetc(f)) != EOF && ch != '\n') { }
            probe_cfg__reject(c, "line", "longer than the parser's buffer");
            continue;
        }
        probe_cfg_apply(c, line);
    }
}

#endif /* PROBE_CFG_H */
