/*
 * NV2A hardware probe, phase one.
 *
 * Four operations over a TCP socket the CONSOLE opens to the host:
 *
 *     R <off>            read32  at NV2A BAR + off
 *     W <off> <val>      write32 at NV2A BAR + off   (journalled first)
 *     S                  status
 *     X                  soft reset
 *
 * Three things are deliberate and load-bearing.
 *
 * THE WIRE CARRIES OFFSETS, NOT ADDRESSES. The brief spells the commands
 * `read32 <addr>`. An absolute address is not accepted here, and the base is
 * added on this side. That makes an access outside the NV2A BAR unrepresentable
 * rather than merely rejected: there is no 32-bit value a confused or hostile
 * host can send that reaches flash at 0xff000000. Reads are bounded by the BAR;
 * writes additionally by the modelled block list in nv2a_window.h.
 *
 * WRITES CANNOT HAPPEN WITHOUT A JOURNAL ACK. mmio_commit_write() is the only
 * code in this file that stores to the BAR, and it takes a write_grant_t. The
 * only way to obtain one is journal_acquire_grant(), which sends the intent to
 * the host and blocks for the matching ACK. Delete the journal call and this
 * does not compile; corrupt the grant and the commit refuses it. The rule is
 * structural, not a discipline someone has to remember.
 *
 * THE CONSOLE DIALS OUT. Nothing listens here. That buys a boot announcement,
 * removes any inbound firewall concern, and makes a wedged console show up as a
 * dead socket rather than as silence the host has to time out on.
 */

#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <hal/debug.h>
#include <hal/video.h>
#include <hal/xbox.h>
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include <nxdk/net.h>
#include <lwip/sockets.h>
#include <lwip/inet.h>

#include "nv2a_window.h"

/* Cross-checked two ways: nxdk lib/pbkit/outer.h defines VIDEO_BASE as
 * 0xFD000000, and pbkit.c comments place NV_PGRAPH_PARAMETER_A at 0xFD401A88,
 * which is this base plus PGRAPH's 0x400000 offset from the emulator's own
 * blocktable in hw/xbox/nv2a/nv2a.c. */
#define NV2A_BASE 0xFD000000u

#define PROBE_PROTO 1
#define DEFAULT_HOST "192.168.50.2"
#define DEFAULT_PORT 24242
#define WATCHDOG_MS  20000u      /* no command for this long => soft reset */
#define NO_HOST_MS   120000u     /* nobody listening this long => back to dash */
#define ACK_TIMEOUT_MS 10000

static char     g_host[64] = DEFAULT_HOST;
static int      g_port     = DEFAULT_PORT;
static char     g_static_ip[32]  = "192.168.50.1";
static char     g_static_mask[32]= "255.255.255.0";
static char     g_static_gw[32]  = "192.168.50.2";

static bool     g_use_dhcp = false;
static int      g_sock = -1;
static uint32_t g_seq;
static uint32_t g_boot_tick;
static volatile uint32_t g_last_cmd_tick;
static volatile bool     g_watchdog_armed;
static uint32_t g_reads, g_writes, g_refused;
static char     g_last_cmd[96] = "(none)";

/* Read d:\nv2a_probe.cfg if present: "key=value" per line.
 *
 * The probe was born with the host address compiled in, which was fine for one
 * console on one direct link and useless the moment it had to run anywhere
 * else -- under the emulator's slirp the host is 10.0.2.2 and the guest is
 * handed an address by DHCP, so neither the host IP nor the static config
 * compiled in here is right. Reading a file next to the XBE costs nothing and
 * means the same binary runs on hardware and under emulation.
 */
static void load_config(void)
{
    FILE *f = fopen("D:\\nv2a_probe.cfg", "r");
    char line[128];
    if (!f) return;
    while (fgets(line, sizeof(line), f)) {
        char *eq = strchr(line, '=');
        char *nl;
        if (!eq || line[0] == '#') continue;
        *eq = 0;
        for (nl = eq + 1; *nl; ++nl)
            if (*nl == '\r' || *nl == '\n') { *nl = 0; break; }
        if (!strcmp(line, "host"))        strncpy(g_host, eq + 1, sizeof(g_host) - 1);
        else if (!strcmp(line, "port"))   g_port = atoi(eq + 1);
        else if (!strcmp(line, "dhcp"))   g_use_dhcp = (eq[1] == '1');
        else if (!strcmp(line, "ip"))     strncpy(g_static_ip, eq + 1, sizeof(g_static_ip) - 1);
        else if (!strcmp(line, "mask"))   strncpy(g_static_mask, eq + 1, sizeof(g_static_mask) - 1);
        else if (!strcmp(line, "gw"))     strncpy(g_static_gw, eq + 1, sizeof(g_static_gw) - 1);
    }
    fclose(f);
}

/* ---------------------------------------------------------------- plumbing */

static void note(const char *s)
{
    debugPrint("%s\n", s);
}

static bool send_line(const char *s)
{
    size_t n = strlen(s);
    char buf[256];
    if (n > sizeof(buf) - 2) return false;
    memcpy(buf, s, n);
    buf[n++] = '\n';
    size_t sent = 0;
    while (sent < n) {
        int w = send(g_sock, buf + sent, (int)(n - sent), 0);
        if (w <= 0) return false;
        sent += (size_t)w;
    }
    return true;
}

/* Read one \n-terminated line. Returns length, 0 on timeout, -1 on error. */
static int recv_line(char *out, int cap, uint32_t timeout_ms)
{
    int len = 0;
    uint32_t start = GetTickCount();
    for (;;) {
        char c;
        int r = recv(g_sock, &c, 1, 0);
        if (r == 1) {
            if (c == '\n') { out[len] = 0; return len; }
            if (c != '\r' && len < cap - 1) out[len++] = c;
            continue;
        }
        if (r == 0) return -1;                       /* peer closed */
        if (errno != EAGAIN && errno != EWOULDBLOCK) return -1;
        if (GetTickCount() - start > timeout_ms) return 0;
    }
}

/* ------------------------------------------------------- the only MMIO path */

/* A grant is proof the host journalled this write. It is only ever produced by
 * journal_acquire_grant(); the magic makes a zeroed or fabricated struct fail
 * closed rather than pass as a grant. */
#define GRANT_MAGIC 0x4A524E4Cu   /* 'JRNL' */
typedef struct {
    uint32_t magic;
    uint32_t seq;
    uint32_t offset;
    uint32_t value;
} write_grant_t;

static bool journal_acquire_grant(uint32_t off, uint32_t val, write_grant_t *out)
{
    char line[160], reply[160];
    uint32_t seq = ++g_seq;

    memset(out, 0, sizeof(*out));
    snprintf(line, sizeof(line), "JOURNAL %u W %08X %08X", seq, off, val);
    if (!send_line(line)) return false;

    /* The host must acknowledge THIS sequence number. Anything else -- a
     * timeout, a closed socket, an ack for a different write -- leaves the
     * grant unissued and the store below never runs. */
    for (;;) {
        int r = recv_line(reply, sizeof(reply), ACK_TIMEOUT_MS);
        if (r <= 0) return false;
        unsigned got = 0;
        if (sscanf(reply, "ACK %u", &got) == 1) {
            if (got != seq) return false;
            out->magic  = GRANT_MAGIC;
            out->seq    = seq;
            out->offset = off;
            out->value  = val;
            return true;
        }
        if (strncmp(reply, "NAK", 3) == 0) return false;
    }
}

/* The ONLY store to the NV2A BAR in this program. */
static bool mmio_commit_write(const write_grant_t *g)
{
    if (!g || g->magic != GRANT_MAGIC) return false;
    if (!nv2a_offset_writable(g->offset)) return false;   /* checked again here */
#ifndef PROBE_ALLOW_HAZARDS
    if (nv2a_hazard_name(g->offset)) return false;
#endif
    *(volatile uint32_t *)((uintptr_t)NV2A_BASE + g->offset) = g->value;
    return true;
}

static uint32_t mmio_read(uint32_t off)
{
    return *(volatile uint32_t *)((uintptr_t)NV2A_BASE + off);
}

static const char *block_of(uint32_t off)
{
    for (int i = 0; i < NV2A_NUM_BLOCKS; ++i) {
        const nv2a_block_t *b = &kNv2aBlocks[i];
        if (off >= b->offset && off < b->offset + b->size) return b->name;
    }
    return "(unmodelled)";
}

/* ------------------------------------------------------------- the commands */

static void cmd_read(uint32_t off)
{
    char out[128];
    if (off & 3u) {
        g_refused++;
        snprintf(out, sizeof(out), "ERR EALIGN %08X not 4-byte aligned", off);
        send_line(out); return;
    }
    if (!nv2a_offset_readable(off)) {
        g_refused++;
        snprintf(out, sizeof(out),
                 "ERR EBOUNDS %08X outside the %u MiB NV2A BAR",
                 off, (unsigned)(NV2A_MMIO_SIZE >> 20));
        send_line(out); return;
    }
    uint32_t v = mmio_read(off);
    g_reads++;
    snprintf(out, sizeof(out), "OK R %08X %08X %s", off, v, block_of(off));
    send_line(out);
}

static void cmd_write(uint32_t off, uint32_t val)
{
    char out[160];
    write_grant_t grant;

    if (!nv2a_offset_writable(off)) {
        g_refused++;
        snprintf(out, sizeof(out),
                 "ERR EDENY %08X is not inside a write-enabled NV2A block (%s)",
                 off, block_of(off));
        send_line(out); return;
    }
#ifdef PROBE_ALLOW_HAZARDS
    /* EMULATOR-ONLY BUILD. See the Makefile comment.
     *
     * Deliberately a BUILD flag and not a config key. A config key would mean
     * the console binary could be talked into a hazardous write by editing a
     * file next to it, which is exactly the structural guarantee the hazard
     * list exists to provide. A separate build cannot: the refusal is either
     * compiled in or the binary is not the one on the console. */
#else
    /* Hazard list, refused HERE and not only in the driver.
     *
     * The window allow-list answers "could this write land somewhere fatal to
     * the machine". It does not answer "is this particular register one that
     * stops the console or drives a clock out of spec", and on 2026-09-20 a
     * blind 0 into NV_PMC_ENABLE -- comfortably inside the allow-list --
     * killed the console outright. The host is the thing most likely to carry
     * a bug, so the refusal belongs on this side of the wire too. */
    {
        const char *hz = nv2a_hazard_name(off);
        if (hz) {
            g_refused++;
            snprintf(out, sizeof(out),
                     "ERR EHAZARD %08X is %s, refused by the probe: phase one "
                     "does not write engine-enable, reset, pushbuffer or PLL "
                     "registers", off, hz);
            send_line(out); return;
        }
    }
#endif
    if (!journal_acquire_grant(off, val, &grant)) {
        g_refused++;
        send_line("ERR EJOURNAL write not journalled; refusing to execute it");
        return;
    }
    if (!mmio_commit_write(&grant)) {
        g_refused++;
        send_line("ERR EGRANT grant rejected at the commit point");
        return;
    }
    g_writes++;
    snprintf(out, sizeof(out), "OK W %08X %08X", off, val);
    send_line(out);
}

static void cmd_status(void)
{
    char out[224];
    snprintf(out, sizeof(out),
             "STATUS proto=%d base=%08X size=%08X uptime_ms=%u reads=%u "
             "writes=%u refused=%u watchdog_ms=%u last=%s",
             PROBE_PROTO, NV2A_BASE, NV2A_MMIO_SIZE,
             (unsigned)(GetTickCount() - g_boot_tick),
             g_reads, g_writes, g_refused, WATCHDOG_MS, g_last_cmd);
    send_line(out);
}

/* --------------------------------------------------------------- watchdog */

static DWORD WINAPI watchdog_thread(LPVOID unused)
{
    (void)unused;
    for (;;) {
        Sleep(500);
        if (!g_watchdog_armed) continue;
        if (GetTickCount() - g_last_cmd_tick > WATCHDOG_MS) {
            /* Nothing from the host for WATCHDOG_MS. Either the console wedged
             * or the link died. Both are recovered the same way and neither is
             * improved by waiting. The host reconnects and resumes from its
             * own journal. */
            HalReturnToFirmware(HalRebootRoutine);
        }
    }
}

/* ------------------------------------------------------------------- main */

static void serve(void)
{
    char line[192];
    char hello[224];

    snprintf(hello, sizeof(hello),
             "HELLO %d nv2a-probe%s base=%08X size=%08X blocks=%d watchdog_ms=%u "
             "built=" __DATE__ " " __TIME__,
             PROBE_PROTO,
#ifdef PROBE_ALLOW_HAZARDS
             "-HAZARDS-ALLOWED-EMULATOR-ONLY",
#else
             "",
#endif
             NV2A_BASE, NV2A_MMIO_SIZE, NV2A_NUM_BLOCKS, WATCHDOG_MS);
    if (!send_line(hello)) return;

    /* The watchdog arms on the FIRST command, not on connect.
     *
     * Armed at connect, a probe that dials in before the host has a sweep
     * ready would see no command for WATCHDOG_MS and soft-reset -- then boot,
     * redial, and do it again: a reset loop caused entirely by the recovery
     * mechanism. Waiting for one command costs nothing (a console that wedges
     * before it has been asked to do anything has not been asked to do
     * anything) and it makes an idle connected probe sit still indefinitely. */
    g_last_cmd_tick = GetTickCount();

    for (;;) {
        int r = recv_line(line, sizeof(line), 1000);
        if (r < 0) return;                 /* socket died; reconnect */
        if (r == 0) continue;              /* idle; watchdog owns the deadline */

        g_watchdog_armed = true;
        g_last_cmd_tick = GetTickCount();
        strncpy(g_last_cmd, line, sizeof(g_last_cmd) - 1);
        g_last_cmd[sizeof(g_last_cmd) - 1] = 0;

        unsigned off = 0, val = 0;
        if (sscanf(line, "R %x", &off) == 1) {
            cmd_read(off);
        } else if (sscanf(line, "W %x %x", &off, &val) == 2) {
            cmd_write(off, val);
        } else if (line[0] == 'S' && line[1] == 0) {
            cmd_status();
        } else if (line[0] == 'P' && line[1] == 0) {
            send_line("OK P");
        } else if (line[0] == 'Q' && line[1] == 0) {
            /* The host finished this run on purpose. Without this the probe
             * cannot tell a clean end from a link failure and prints
             * "disconnected; redialling" either way, which reads like a fault
             * to whoever is watching the screen. */
            send_line("BYE run complete");
            g_watchdog_armed = false;
            debugPrint("host finished the run; waiting for the next one\n");
            return;
        } else if (line[0] == 'X' && line[1] == 0) {
            send_line("BYE soft reset");
            Sleep(250);
            g_watchdog_armed = false;
            HalReturnToFirmware(HalRebootRoutine);
        } else {
            send_line("ERR EPARSE unrecognised command");
        }
    }
}

int main(void)
{
    nx_net_parameters_t np;
    struct sockaddr_in addr;

    XVideoSetMode(640, 480, 32, REFRESH_DEFAULT);
    g_boot_tick = GetTickCount();

    debugPrint("NV2A probe (phase one)\n");
    debugPrint("BAR %08X size %08X, %d writable blocks\n",
               NV2A_BASE, NV2A_MMIO_SIZE, NV2A_NUM_BLOCKS);

    load_config();
    memset(&np, 0, sizeof(np));
    np.ipv4_mode    = g_use_dhcp ? NX_NET_DHCP : NX_NET_STATIC;
    np.ipv4_ip      = inet_addr(g_static_ip);
    np.ipv4_netmask = inet_addr(g_static_mask);
    np.ipv4_gateway = inet_addr(g_static_gw);
    if (nxNetInit(&np) != 0) {
        note("network init FAILED");
        while (1) Sleep(1000);
    }
    debugPrint("net up: %s -> host %s:%d\n", g_static_ip, g_host, g_port);

    CreateThread(NULL, 0, watchdog_thread, NULL, 0, NULL);

    uint32_t last_session = GetTickCount();
    for (;;) {
        /* ESCAPE HATCH.
         *
         * Without this, a probe launched while the host is not listening owns
         * the console forever: it redials in a loop, UnleashX is not running
         * so there is no FTP, and the only way out is a controller or the
         * power button. That state was reached for real. Going back to the
         * dashboard after a couple of minutes of nobody answering means the
         * host regains FTP -- and therefore remote control -- on its own, and
         * "stop the probe" becomes "stop listening", which needs no hands.
         *
         * It also makes an auto-relaunch loop safe to switch on: the worst a
         * bad launch can do is cost NO_HOST_MS before the console hands
         * itself back. */
        if (GetTickCount() - last_session > NO_HOST_MS) {
            debugPrint("no host for %us; returning to the dashboard\n",
                       (unsigned)(NO_HOST_MS / 1000));
            Sleep(250);
            HalReturnToFirmware(HalRebootRoutine);
        }
        g_watchdog_armed = false;
        g_sock = socket(AF_INET, SOCK_STREAM, 0);
        if (g_sock < 0) { Sleep(1000); continue; }

        memset(&addr, 0, sizeof(addr));
        addr.sin_family = AF_INET;
        addr.sin_port   = htons((uint16_t)g_port);
        addr.sin_addr.s_addr = inet_addr(g_host);

        if (connect(g_sock, (struct sockaddr *)&addr, sizeof(addr)) == 0) {
            int one = 1;
            setsockopt(g_sock, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one));
            struct timeval tv = { 0, 200000 };
            setsockopt(g_sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
            debugPrint("connected\n");
            last_session = GetTickCount();
            serve();
            last_session = GetTickCount();
            debugPrint("session ended; redialling\n");
        }
        g_watchdog_armed = false;
        closesocket(g_sock);
        g_sock = -1;
        Sleep(1000);
    }
}
