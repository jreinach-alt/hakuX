/*
 * lta3_check: is C7p's loop-free ltA3 bit-exact with vsh-ff.c's?
 *
 *   cc -O2 -o lta3_check lta3_check.c && ./lta3_check [millions=50]
 *
 * Both GLSL functions transcribed to C line by line (uint = uint32_t, int =
 * int32_t, GLSL shifts by 0..31 only, as both versions guarantee). Inputs:
 * uniformly random bit patterns (NaN, Inf, denormals, zeros all reachable),
 * triples with nearby exponents (the alignment and cancellation paths), and
 * every combination of a list of special values. Exit 0 iff no mismatch.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint32_t uint;
static const uint LT_NAN = 0x7FFFFC00u, LT_INF = 0x7F800000u;

static uint fbits(float f) { uint u; memcpy(&u, &f, 4); return u; }
static float bitsf(uint u) { float f; memcpy(&f, &u, 4); return f; }

static int ltMsb(uint u)
{
    int n = 0;
    if (u >= 0x10000u) { u >>= 16; n += 16; }
    if (u >= 0x100u) { u >>= 8; n += 8; }
    if (u >= 0x10u) { u >>= 4; n += 4; }
    if (u >= 0x4u) { u >>= 2; n += 2; }
    if (u >= 0x2u) { n += 1; }
    return n;
}
static uint ltShr(uint m, int sh) { return sh >= 32 ? 0u : (sh >= 0 ? m >> sh : m << -sh); }
static int ltIsNan(uint x) { return (x & 0x7F800000u) == 0x7F800000u && (x & 0x7FFFFFu) != 0u; }
static int ltIsInf(uint x) { return (x & 0x7FFFFFFFu) == 0x7F800000u; }
static float ltMk(uint s, int e, uint m)
{
    if (m == 0u || e <= 0) return bitsf(s << 31);
    if (e >= 255) return bitsf(s << 31 | 0x7F7FFFFFu);
    return bitsf(s << 31 | (uint)e << 23 | (m & 0x1FFFu) << 10);
}

/* vsh-ff.c:210-243 */
static float ltA3_orig(float x0, float x1, float x2)
{
    uint v[3] = { fbits(x0), fbits(x1), fbits(x2) };
    int pinf = 0, ninf = 0;
    for (int i = 0; i < 3; i++) if (ltIsNan(v[i])) return bitsf(LT_NAN);
    for (int i = 0; i < 3; i++)
        if (ltIsInf(v[i])) { if ((v[i] >> 31) != 0u) ninf = 1; else pinf = 1; }
    if (pinf && ninf) return bitsf(LT_NAN);
    if (pinf || ninf) return bitsf(LT_INF);
    int er = 0, e[3];
    uint m[3];
    for (int i = 0; i < 3; i++) {
        e[i] = (int)(v[i] >> 23 & 0xFFu);
        m[i] = ((v[i] & 0x7FFFFFu) | (e[i] != 0 ? 0x800000u : 0u)) >> 10;
        er = er > e[i] + 2 ? er : e[i] + 2;
    }
    int r = 0;
    for (int i = 0; i < 3; i++) {
        int f = (int)ltShr(m[i], er - e[i] - 7);
        r += (v[i] >> 31) != 0u ? -f : f;
    }
    if (r == 0) return 0.0f;
    uint s = r < 0 ? 1u : 0u;
    uint u = (uint)abs(r);
    int sh = 20 - ltMsb(u);
    u <<= (uint)sh;
    er -= sh;
    u >>= 7u;
    if (er >= 255) { er = 254; u = 0x3FFFu; }
    return ltMk(s, er, u);
}

static int clampi(int x, int lo, int hi) { return x < lo ? lo : x > hi ? hi : x; }
static int findMSB(uint u) { return u ? 31 - __builtin_clz(u) : -1; }

/* gen/variants/c7p_lta3_vec.py, component by component */
static float ltA3_vec(float x0, float x1, float x2)
{
    uint v[3] = { fbits(x0), fbits(x1), fbits(x2) };
    uint mn[3], top[3], hasm[3], sgn[3], infv[3], m[3];
    int e[3], sh[3], fi[3];
    int anyNan = 0, pinf = 0, ninf = 0;
    for (int i = 0; i < 3; i++) {
        mn[i] = v[i] & 0x7FFFFFu;
        top[i] = (v[i] & 0x7F800000u) == 0x7F800000u;
        hasm[i] = mn[i] != 0u;
        sgn[i] = v[i] >> 31;
        anyNan |= (top[i] & hasm[i]) != 0u;
        infv[i] = top[i] & (1u - hasm[i]);
        pinf |= (infv[i] & (1u - sgn[i])) != 0u;
        ninf |= (infv[i] & sgn[i]) != 0u;
        e[i] = (int)(v[i] >> 23 & 0xFFu);
        m[i] = (mn[i] | ((uint)(e[i] != 0) << 23)) >> 10;
    }
    int er = e[0] > e[1] ? e[0] : e[1];
#ifndef MUTANT_BIAS  /* -DMUTANT_BIAS=3: the check must then report mismatches */
#define MUTANT_BIAS 2
#endif
    er = (er > e[2] ? er : e[2]) + MUTANT_BIAS;
    int r = 0;
    for (int i = 0; i < 3; i++) {
        sh[i] = er - e[i] - 7;
        uint f = sh[i] >= 0 ? m[i] >> clampi(sh[i], 0, 31) : m[i] << clampi(-sh[i], 0, 31);
        if (sh[i] >= 32) f = 0u;
        fi[i] = (int)f;
        if (sgn[i] != 0u) fi[i] = -fi[i];
        r += fi[i];
    }
    uint s = r < 0 ? 1u : 0u;
    uint u = (uint)abs(r);
    int sh2 = 20 - findMSB(u);
    u = sh2 >= 0 && sh2 < 32 ? u << (uint)sh2 : 0u; /* r == 0: sh2 = 21, u = 0 */
    er -= sh2;
    u >>= 7u;
    int big = er >= 255;
    float res = ltMk(s, big ? 254 : er, big ? 0x3FFFu : u);
    res = r == 0 ? 0.0f : res;
    res = (pinf || ninf) ? bitsf(LT_INF) : res;
    res = (pinf && ninf) ? bitsf(LT_NAN) : res;
    return anyNan ? bitsf(LT_NAN) : res;
}

static uint64_t rs = 0x9E3779B97F4A7C15ull;
static uint rnd(void)
{
    rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17;
    return (uint)(rs >> 16);
}

static long bad, tested;
static void check(uint a, uint b, uint c)
{
    float x = bitsf(a), y = bitsf(b), z = bitsf(c);
    uint o = fbits(ltA3_orig(x, y, z)), n = fbits(ltA3_vec(x, y, z));
    tested++;
    if (o != n && bad++ < 10) {
        printf("MISMATCH %08x %08x %08x: orig %08x vec %08x\n", a, b, c, o, n);
    }
}

int main(int argc, char **argv)
{
    long millions = argc > 1 ? atol(argv[1]) : 50;
    static const uint sp[] = {
        0x00000000u, 0x80000000u, 0x00000001u, 0x807FFFFFu, 0x00800000u, 0x80800000u,
        0x3F800000u, 0xBF800000u, 0x3F800400u, 0x3F7FFC00u, 0x7F7FFFFFu, 0xFF7FFFFFu,
        0x7F800000u, 0xFF800000u, 0x7FC00000u, 0xFFC00000u, 0x7F800001u, 0x3EAAAAABu,
        0x40490FDBu, 0xC0490FDBu, 0x5F000000u, 0x1F800000u, 0x7F000000u, 0x7E800000u,
    };
    int ns = sizeof(sp) / sizeof(sp[0]);
    for (int i = 0; i < ns; i++)
        for (int j = 0; j < ns; j++)
            for (int k = 0; k < ns; k++) check(sp[i], sp[j], sp[k]);
    for (long i = 0; i < millions * 1000000L / 2; i++) {
        check(rnd(), rnd(), rnd());
        /* nearby exponents: shared exponent +-12, random mantissas and signs */
        uint e = rnd() % 254 + 1, t[3];
        for (int k = 0; k < 3; k++) {
            int ek = (int)e + (int)(rnd() % 25) - 12;
            ek = ek < 0 ? 0 : ek > 254 ? 254 : ek;
            t[k] = (rnd() & 0x807FFFFFu) | ((uint)ek << 23);
        }
        check(t[0], t[1], t[2]);
    }
    printf("tested %ld triples, %ld mismatches\n", tested, bad);
    return bad != 0;
}
