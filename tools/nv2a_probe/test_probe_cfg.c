/* Tests for the probe's config parser.
 *
 * This file decides which host the console dials and whether it dials at all,
 * and until now nothing compiled it. Checked by mutation the same way the
 * allow-list is: run_tests.sh rebuilds this against deliberately broken copies
 * of probe_cfg.h and requires each one to FAIL.
 *
 * Every case here is one the old parser got wrong. They are not hypothetical
 * shapes -- `dhcp=true` meaning static and `port=http` meaning port 0 are what
 * the file did before.
 */
#include <stdio.h>
#include <string.h>

#include "probe_cfg.h"

static int fails;
#define CHECK(cond, ...) do { if (!(cond)) { \
    printf("  FAIL: "); printf(__VA_ARGS__); printf("\n"); fails++; } } while (0)

/* Parse a config given as a string, exactly as probe_cfg_read would see it. */
static void parse(probe_cfg_t *c, const char *text)
{
    FILE *f = tmpfile();
    probe_cfg_defaults(c);
    if (!f) { printf("  FAIL: tmpfile()\n"); fails++; return; }
    fwrite(text, 1, strlen(text), f);
    rewind(f);
    probe_cfg_read(c, f);
    fclose(f);
}

int main(void)
{
    probe_cfg_t c;

    /* Defaults, with no file at all. */
    probe_cfg_defaults(&c);
    CHECK(!strcmp(c.host, "192.168.50.2"), "default host: %s", c.host);
    CHECK(c.port == 24242, "default port: %d", c.port);
    CHECK(c.dhcp == false, "default mode is static");
    CHECK(c.present == false, "no file means not present");

    /* A normal file. */
    parse(&c, "# the emulator\nhost=10.0.2.2\nport=24242\ndhcp=1\n");
    CHECK(c.present, "the file was read");
    CHECK(!strcmp(c.host, "10.0.2.2"), "host applied: %s", c.host);
    CHECK(c.port == 24242, "port applied: %d", c.port);
    CHECK(c.dhcp == true, "dhcp applied");
    CHECK(c.rejected == 0, "nothing rejected, got %d (%s)", c.rejected, c.last_reject);
    CHECK(c.applied == 3, "three records applied, got %d", c.applied);

    /* Static addressing, all four string keys. */
    parse(&c, "ip=192.168.9.1\nmask=255.255.0.0\ngw=192.168.9.254\nhost=192.168.9.2\n");
    CHECK(!strcmp(c.ip, "192.168.9.1"), "ip: %s", c.ip);
    CHECK(!strcmp(c.mask, "255.255.0.0"), "mask: %s", c.mask);
    CHECK(!strcmp(c.gw, "192.168.9.254"), "gw: %s", c.gw);
    CHECK(c.dhcp == false, "mode stays static when dhcp is absent");

    /* dhcp: the spellings an operator actually writes. `dhcp=true` meaning
     * STATIC is the bug this case exists for. */
    parse(&c, "dhcp=true\n");   CHECK(c.dhcp && !c.rejected, "dhcp=true is true");
    parse(&c, "dhcp=TRUE\n");   CHECK(c.dhcp && !c.rejected, "dhcp=TRUE is true");
    parse(&c, "dhcp=yes\n");    CHECK(c.dhcp && !c.rejected, "dhcp=yes is true");
    parse(&c, "dhcp=on\n");     CHECK(c.dhcp && !c.rejected, "dhcp=on is true");
    parse(&c, "dhcp=1\n");      CHECK(c.dhcp && !c.rejected, "dhcp=1 is true");
    parse(&c, "dhcp=0\n");      CHECK(!c.dhcp && !c.rejected, "dhcp=0 is false");
    parse(&c, "dhcp=false\n");  CHECK(!c.dhcp && !c.rejected, "dhcp=false is false");
    parse(&c, "dhcp=off\n");    CHECK(!c.dhcp && !c.rejected, "dhcp=off is false");

    /* An unparseable boolean keeps the default AND is reported. Silently
     * choosing a network mode is how the probe ended up dialling an address
     * that does not exist under slirp. */
    parse(&c, "dhcp=banana\n");
    CHECK(!c.dhcp, "a bad boolean leaves the default");
    CHECK(c.rejected == 1, "and is rejected, got %d", c.rejected);
    CHECK(strstr(c.last_reject, "dhcp") != NULL, "naming the key: %s", c.last_reject);

    /* port: digits only, 1..65535. atoi() answered 0 for all of these. */
    parse(&c, "port=1\n");      CHECK(c.port == 1 && !c.rejected, "port=1");
    parse(&c, "port=65535\n");  CHECK(c.port == 65535 && !c.rejected, "port=65535");
    parse(&c, "port=http\n");
    CHECK(c.port == 24242 && c.rejected == 1, "port=http refused, port=%d", c.port);
    parse(&c, "port=\n");
    CHECK(c.port == 24242 && c.rejected == 1, "empty port refused, port=%d", c.port);
    parse(&c, "port=0\n");
    CHECK(c.port == 24242 && c.rejected == 1, "port 0 refused, port=%d", c.port);
    parse(&c, "port=65536\n");
    CHECK(c.port == 24242 && c.rejected == 1, "port 65536 refused, port=%d", c.port);
    parse(&c, "port=24242x\n");
    CHECK(c.port == 24242 && c.rejected == 1, "trailing junk refused, port=%d", c.port);

    /* Whitespace around a key defeated strcmp() outright. */
    parse(&c, "  host = 10.0.2.2  \n");
    CHECK(!strcmp(c.host, "10.0.2.2"), "whitespace trimmed: %s", c.host);
    CHECK(c.rejected == 0, "and not rejected: %s", c.last_reject);

    /* Comments, blank lines and CRLF cost nothing and are not errors. */
    parse(&c, "# comment\r\n\r\n; also a comment\r\nhost=10.0.2.2\r\n");
    CHECK(!strcmp(c.host, "10.0.2.2"), "CRLF host: %s", c.host);
    CHECK(c.rejected == 0, "comments and blanks are not rejects: %d", c.rejected);

    /* An unknown key is reported, not dropped. */
    parse(&c, "hosts=10.0.2.2\n");
    CHECK(c.rejected == 1, "unknown key rejected");
    CHECK(!strcmp(c.host, "192.168.50.2"), "and nothing was applied: %s", c.host);

    /* A line with no '=' at all. */
    parse(&c, "just some words\n");
    CHECK(c.rejected == 1, "a line with no '=' is rejected");

    /* A value longer than its field is refused, NOT truncated. A truncated
     * address is a host that exists and is the wrong one. */
    {
        char text[PROBE_CFG_LINE + 64];
        char big[80];
        memset(big, 'a', sizeof(big) - 1);
        big[sizeof(big) - 1] = 0;
        snprintf(text, sizeof(text), "host=%s\n", big);
        parse(&c, text);
        CHECK(!strcmp(c.host, "192.168.50.2"), "over-long host refused: %s", c.host);
        CHECK(c.rejected == 1, "and reported, got %d", c.rejected);
    }

    /* A line longer than the read buffer must be refused WHOLE. fgets splits
     * it, and the old parser read the tail as a fresh record -- so the tail of
     * an over-long host line could set a different key. */
    {
        char text[PROBE_CFG_LINE * 2 + 64];
        char pad[PROBE_CFG_LINE + 8];
        memset(pad, 'a', sizeof(pad) - 1);
        pad[sizeof(pad) - 1] = 0;
        snprintf(text, sizeof(text), "%s=x\nhost=10.0.2.2\n", pad);
        parse(&c, text);
        CHECK(c.rejected == 1, "the split line is one reject, got %d", c.rejected);
        CHECK(!strcmp(c.host, "10.0.2.2"),
              "and the NEXT real line still parses: %s", c.host);
    }
    {
        /* The dangerous half: the tail of a split line must not be applied. */
        char text[PROBE_CFG_LINE * 2 + 64];
        char pad[PROBE_CFG_LINE];
        memset(pad, 'a', sizeof(pad) - 1);
        pad[sizeof(pad) - 1] = 0;
        snprintf(text, sizeof(text), "#%s port=1\n", pad);
        parse(&c, text);
        CHECK(c.port == 24242, "the tail of a split line is not a record: %d", c.port);
    }

    /* An empty file is present and changes nothing. */
    parse(&c, "");
    CHECK(c.present && c.applied == 0 && c.rejected == 0, "empty file is inert");

    if (fails) { printf("%d check(s) failed\n", fails); return 1; }
    printf("all config-parser checks passed\n");
    return 0;
}
