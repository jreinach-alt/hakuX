/*
 * lt_check: are the GLSL 4.50 lighting helpers in vsh-ff.c (#569 B1) bit-exact
 * with the forms they replace (the #else branch, which GLSL ES keeps)?
 *
 *   cc -O2 -fwrapv -o lt_check lt_check.c && ./lt_check [millions=50]
 *   cc ... -DMUT=<n> : mutant n (1-10) of a new helper; each must mismatch
 *
 * Both sets are transcribed from vsh-ff.c line by line, in uint words (uint =
 * uint32_t, int = int32_t, -fwrapv for GLSL's wrapping int). Vector helpers
 * are transcribed lane by lane: every GLSL vector op here is componentwise
 * except the scalar results of == / != on vectors (any lane differs), which
 * the transcription spells out. mix(x, y, b) is b ? y : x. GLSL shifts by
 * 0..31 only; the new forms clamp or bound every shift, and the transcription
 * asserts it (SHL/SHR abort on an out-of-range count).
 *
 * Checked, new against old:
 *   ltMkU (scalar, vector)  every s, e in [-64, 320], m in [0, 2^16)
 *   ltM, ltsM, ltVM         specials^2, random words, nearby exponents
 *   ltA3                    specials^3, random, nearby exponents
 *   ltVA (lane = ltA3(a, b, 0)), ltsA   specials^2, random, nearby
 *   ltDp                    ltA3 of three ltM, random and nearby triples
 *   ltR                     all 2^32 inputs
 * Exit 0 iff no mismatch.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef uint32_t uint;
#ifndef MUT
#define MUT 0
#endif
#define M(n, mutant, orig) (MUT == (n) ? (mutant) : (orig))

static const uint LT_NAN = 0x7FFFFC00u, LT_INF = 0x7F800000u;
static const uint ltRcpLut[64] = {
    0x7Fu, 0x7Du, 0x7Bu, 0x79u, 0x77u, 0x75u, 0x74u, 0x72u,
    0x70u, 0x6Fu, 0x6Du, 0x6Cu, 0x6Bu, 0x69u, 0x68u, 0x67u,
    0x65u, 0x64u, 0x63u, 0x62u, 0x60u, 0x5Fu, 0x5Eu, 0x5Du,
    0x5Cu, 0x5Bu, 0x5Au, 0x59u, 0x58u, 0x57u, 0x56u, 0x55u,
    0x54u, 0x54u, 0x53u, 0x52u, 0x51u, 0x50u, 0x4Fu, 0x4Fu,
    0x4Eu, 0x4Du, 0x4Cu, 0x4Cu, 0x4Bu, 0x4Au, 0x4Au, 0x49u,
    0x48u, 0x48u, 0x47u, 0x46u, 0x46u, 0x45u, 0x45u, 0x44u,
    0x43u, 0x43u, 0x42u, 0x42u, 0x41u, 0x41u, 0x40u, 0x40u,
};

static uint SHL(uint x, int n) { if (n < 0 || n > 31) abort(); return x << n; }
static uint SHR(uint x, int n) { if (n < 0 || n > 31) abort(); return x >> n; }
static int clampi(int x, int lo, int hi) { return x < lo ? lo : x > hi ? hi : x; }
static int maxi(int a, int b) { return a > b ? a : b; }
static int mini(int a, int b) { return a < b ? a : b; }
static int findMSB(uint u) { return u ? 31 - __builtin_clz(u) : -1; }
static int iabs(int x) { return x < 0 ? -x : x; } /* GLSL abs(INT_MIN) wraps too */

/* ---- the old forms (vsh-ff.c, the #else branch) ---- */

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
static uint ltShr(uint m, int sh) { return sh >= 32 ? 0u : (sh >= 0 ? SHR(m, sh) : SHL(m, -sh)); }
static int ltIsNan(uint x) { return (x & 0x7F800000u) == 0x7F800000u && (x & 0x7FFFFFu) != 0u; }
static int ltIsInf(uint x) { return (x & 0x7FFFFFFFu) == 0x7F800000u; }
static uint o_ltMk(uint s, int e, uint m)
{
    if (m == 0u || e <= 0) return s << 31;
    if (e >= 255) return s << 31 | 0x7F7FFFFFu;
    return s << 31 | (uint)e << 23 | (m & 0x1FFFu) << 10;
}
static uint o_ltMulCore(uint a, uint b, int signedInf)
{
    uint s = (a ^ b) >> 31;
    int ea = (int)(a >> 23 & 0xFFu), eb = (int)(b >> 23 & 0xFFu);
    uint ma = (a >> 10 & 0x1FFFu) | 0x2000u, mb = (b >> 10 & 0x1FFFu) | 0x2000u;
    if ((ea == 255 && ma > 0x2000u) || (eb == 255 && mb > 0x2000u)) return LT_NAN;
    if (ea == 0 || eb == 0) return 0u;
    if (ea == 255 || eb == 255) return signedInf ? (s << 31 | LT_INF) : LT_INF;
    int e = ea + eb - 127;
    if (signedInf && e >= 255) return s << 31 | LT_INF;
    uint m = (ma * mb) >> 13;
    if (m > 0x3FFFu) { m >>= 1; e++; }
    if (e <= 0) return s << 31;
    if (e >= 255) { e = 254; m = 0x1FFFu; }
    return s << 31 | (uint)e << 23 | (m & 0x1FFFu) << 10;
}
static uint o_ltM(uint a, uint b) { return o_ltMulCore(a, b, 0); }
static uint o_ltsM(uint a, uint b) { return o_ltMulCore(a, b, 1); }
static uint o_ltA3(uint x0, uint x1, uint x2)
{
    uint v[3] = { x0, x1, x2 };
    int pinf = 0, ninf = 0;
    for (int i = 0; i < 3; i++) if (ltIsNan(v[i])) return LT_NAN;
    for (int i = 0; i < 3; i++)
        if (ltIsInf(v[i])) { if ((v[i] >> 31) != 0u) ninf = 1; else pinf = 1; }
    if (pinf && ninf) return LT_NAN;
    if (pinf || ninf) return LT_INF;
    int er = 0, e[3];
    uint m[3];
    for (int i = 0; i < 3; i++) {
        e[i] = (int)(v[i] >> 23 & 0xFFu);
        m[i] = ((v[i] & 0x7FFFFFu) | (e[i] != 0 ? 0x800000u : 0u)) >> 10;
        er = maxi(er, e[i] + 2);
    }
    int r = 0;
    for (int i = 0; i < 3; i++) {
        int f = (int)ltShr(m[i], er - e[i] - 7);
        r += (v[i] >> 31) != 0u ? -f : f;
    }
    if (r == 0) return 0u;
    uint s = r < 0 ? 1u : 0u;
    uint u = (uint)iabs(r);
    int sh = 20 - ltMsb(u);
    u = SHL(u, sh);
    er -= sh;
    u >>= 7u;
    if (er >= 255) { er = 254; u = 0x3FFFu; }
    return o_ltMk(s, er, u);
}
static uint o_ltA(uint a, uint b) { return o_ltA3(a, b, 0u); }
static uint o_ltDp(const uint a[3], const uint b[3])
{
    return o_ltA3(o_ltM(a[0], b[0]), o_ltM(a[1], b[1]), o_ltM(a[2], b[2]));
}
static uint o_ltsA(uint a, uint b)
{
    if (ltIsNan(a) || ltIsNan(b)) return LT_NAN;
    if (ltIsInf(a) || ltIsInf(b)) {
        if (ltIsInf(a) && ltIsInf(b) && (a >> 31) != (b >> 31)) return LT_NAN;
        return LT_INF;
    }
    int ea = (int)(a >> 23 & 0xFFu), eb = (int)(b >> 23 & 0xFFu);
    uint ma = ea != 0 ? ((a & 0x7FFFFFu) >> 10) | 0x2000u : 0u;
    uint mb = eb != 0 ? ((b & 0x7FFFFFu) >> 10) | 0x2000u : 0u;
    int er = maxi(ea, eb) + 1;
    int fa2 = (int)ltShr(ma, er - ea - 1), fb2 = (int)ltShr(mb, er - eb - 1);
    int r = ((a >> 31) != 0u ? -fa2 : fa2) + ((b >> 31) != 0u ? -fb2 : fb2);
    if (r == 0) return 0u;
    uint s = r < 0 ? 1u : 0u;
    uint u = (uint)iabs(r);
    int sh = 14 - ltMsb(u);
    u = SHL(u, sh);
    er -= sh;
    u >>= 1u;
    return o_ltMk(s, er, u);
}
static uint o_ltR(uint x)
{
    if (ltIsNan(x)) return LT_NAN;
    uint sx = x >> 31;
    int ex = (int)(x >> 23 & 0xFFu);
    if (ex == 0) return LT_INF;
    if (ltIsInf(x)) return 0u;
    int er = 0xFD - ex;
    uint f = ((x & 0x7FFFFFu) + 0x800000u) >> 10;
    uint s0 = ltRcpLut[f >> 7 & 0x3Fu];
    uint s1 = ((((1u << 21) - s0 * f) * s0) >> 14) << 11;
    uint fr = s1 - 0x800000u;
    if (er <= 0) return sx << 31;
    return sx << 31 | (uint)er << 23 | (fr & 0x7FFFFFu);
}

/* ---- the new forms (vsh-ff.c, #if __VERSION__ >= 450) ---- */

static uint n_ltMkU(uint s, int e, uint m)
{
    uint r = s << 31 | (uint)e << 23 | (m & 0x1FFFu) << 10;
    r = e >= M(1, 254, 255) ? (s << 31 | 0x7F7FFFFFu) : r;
    int z = m == 0u || e <= 0;
    return z ? s << 31 : r;
}
static void n_ltMkU3(const uint s[3], const int e[3], const uint m[3], uint out[3])
{
    for (int i = 0; i < 3; i++) {
        uint r = s[i] << 31 | (uint)e[i] << 23 | (m[i] & 0x1FFFu) << 10;
        r = e[i] >= 255 ? (s[i] << 31 | 0x7F7FFFFFu) : r;
        r = m[i] == 0u ? s[i] << 31 : r;
        out[i] = e[i] <= M(2, 1, 0) ? s[i] << 31 : r;
    }
}
static void n_ltMulV(const uint a[3], const uint b[3], int signedInf, uint out[3])
{
    for (int i = 0; i < 3; i++) {
        uint s = (a[i] ^ b[i]) >> 31;
        int ea = (int)(a[i] >> 23 & 0xFFu), eb = (int)(b[i] >> 23 & 0xFFu);
        uint ma = (a[i] >> 10 & 0x1FFFu) | 0x2000u, mb = (b[i] >> 10 & 0x1FFFu) | 0x2000u;
        int e = ea + eb - M(3, 126, 127);
        uint m = (ma * mb) >> 13;
        uint c = m >> 14;
        int ec = e + (int)c;
        uint r = s << 31 | (uint)ec << 23 | (SHR(m, (int)c) & 0x1FFFu) << 10;
        r = ec >= 255 ? (s << 31 | 0x7F7FFC00u) : r;
        r = ec <= 0 ? s << 31 : r;
        uint si = signedInf ? 1u : 0u;
        uint inf = si ? (s << 31 | LT_INF) : LT_INF;
        r = (si & (e >= 255)) ? inf : r;
        uint ta = ea == 255, tb = eb == 255;
        r = (ta | tb) ? inf : r;
        r = ((uint)(ea == 0) | (uint)(eb == 0)) ? 0u : r;
        uint nan = (ta & (ma > 0x2000u)) | (tb & (mb > 0x2000u));
        out[i] = nan ? LT_NAN : r;
    }
}
static uint n_ltM(uint a, uint b)
{
    uint va[3] = { a, a, a }, vb[3] = { b, b, b }, o[3];
    n_ltMulV(va, vb, 0, o);
    return o[0];
}
static uint n_ltsM(uint a, uint b)
{
    uint va[3] = { a, a, a }, vb[3] = { b, b, b }, o[3];
    n_ltMulV(va, vb, MUT != 10, o);   /* mutant 10: the unsigned multiply */
    return o[0];
}
static uint n_ltA3(uint x0, uint x1, uint x2)
{
    uint v[3] = { x0, x1, x2 }, mn[3], top[3], hasm[3], sgn[3], infv[3], m[3], f[3];
    int e[3], sh[3], fi[3];
    int anyNan = 0, pinf = 0, ninf = 0;
    for (int i = 0; i < 3; i++) {
        mn[i] = v[i] & 0x7FFFFFu;
        top[i] = (v[i] & 0x7F800000u) == 0x7F800000u;
        hasm[i] = mn[i] != 0u;
        sgn[i] = v[i] >> 31;
    }
    for (int i = 0; i < 3; i++) {   /* (top & hasm) != uvec3(0u): any lane */
        anyNan |= (top[i] & hasm[i]) != 0u;
        infv[i] = top[i] & (1u - hasm[i]);
        pinf |= (infv[i] & (1u - sgn[i])) != 0u;
        ninf |= (infv[i] & sgn[i]) != 0u;
        e[i] = (int)(v[i] >> 23 & 0xFFu);
        m[i] = (mn[i] | ((uint)(e[i] != 0) << 23)) >> 10;
    }
    int er = maxi(maxi(e[0], e[1]), e[2]) + M(4, 3, 2);
    for (int i = 0; i < 3; i++) {
        sh[i] = er - e[i] - 7;
        f[i] = sh[i] >= 0 ? SHR(m[i], clampi(sh[i], 0, 31)) : SHL(m[i], clampi(-sh[i], 0, 31));
        f[i] = sh[i] >= 32 ? 0u : f[i];
        fi[i] = (int)f[i];
        fi[i] = sgn[i] != 0u ? -fi[i] : fi[i];
    }
    int r = fi[0] + fi[1] + fi[2];
    uint u = (uint)iabs(r);
    int sh2 = 20 - findMSB(u);
    u = SHL(u, sh2) >> 7u;
    er -= sh2;
    int big = er >= 255;
    uint res = n_ltMkU((uint)(r < 0), big ? 254 : er, big ? 0x3FFFu : u);
    res = r == 0 ? 0u : res;
    int inf = pinf || ninf;
    res = inf ? LT_INF : res;
    int both = pinf && ninf;
    res = both ? LT_NAN : res;
    return anyNan ? LT_NAN : res;
}
static void n_ltVA(const uint a[3], const uint b[3], uint out[3])
{
    uint s[3], mm[3], rr[3];
    int ee[3], r[3];
    uint pinf[3], ninf[3], nan[3];
    for (int i = 0; i < 3; i++) {
        uint mna = a[i] & 0x7FFFFFu, mnb = b[i] & 0x7FFFFFu;
        uint ta = (a[i] & 0x7F800000u) == 0x7F800000u;
        uint tb = (b[i] & 0x7F800000u) == 0x7F800000u;
        uint za = mna == 0u, zb = mnb == 0u;
        uint sa = a[i] >> 31, sb = b[i] >> 31;
        nan[i] = (ta & (1u - za)) | (tb & (1u - zb));
        uint ia = ta & za, ib = tb & zb;
        pinf[i] = (ia & (1u - sa)) | (ib & (1u - sb));
        ninf[i] = (ia & sa) | (ib & sb);
        int ea = (int)(a[i] >> 23 & 0xFFu), eb = (int)(b[i] >> 23 & 0xFFu);
        uint ma = (mna | (uint)(ea != 0) << 23) >> 10;
        uint mb = (mnb | (uint)(eb != 0) << 23) >> 10;
        int er = maxi(ea, eb) + 2;
        int sha = er - ea - 7, shb = er - eb - M(5, 6, 7);
        int fa = (int)(sha >= 0 ? SHR(ma, clampi(sha, 0, 31)) : SHL(ma, clampi(-sha, 0, 31)));
        int fb = (int)(shb >= 0 ? SHR(mb, clampi(shb, 0, 31)) : SHL(mb, clampi(-shb, 0, 31)));
        r[i] = (sa ? -fa : fa) + (sb ? -fb : fb);
        uint u = (uint)iabs(r[i]);
        int sh = 20 - findMSB(u);
        u = SHL(u, sh) >> 7u;
        er -= sh;
        int big = er >= 255;
        s[i] = r[i] < 0;
        ee[i] = big ? 254 : er;
        mm[i] = big ? 0x3FFFu : u;
    }
    n_ltMkU3(s, ee, mm, rr);
    for (int i = 0; i < 3; i++) {
        uint res = rr[i];
        res = r[i] == 0 ? 0u : res;
        res = (pinf[i] | ninf[i]) ? LT_INF : res;
        res = (pinf[i] & ninf[i]) ? LT_NAN : res;
        out[i] = nan[i] ? LT_NAN : res;
    }
}
static uint n_ltDp(const uint a[3], const uint b[3])
{
    uint p[3];
    n_ltMulV(a, b, MUT == 9, p);   /* mutant 9: the signed multiply */
    return n_ltA3(p[0], p[1], p[2]);
}
static uint n_ltsA(uint a, uint b)
{
    int ta = (a & 0x7F800000u) == 0x7F800000u, tb = (b & 0x7F800000u) == 0x7F800000u;
    int za = (a & 0x7FFFFFu) == 0u, zb = (b & 0x7FFFFFu) == 0u;
    int nan = ta && !za;
    int nanb = tb && !zb;
    nan = nan || nanb;
    int ia = ta && za;
    int ib = tb && zb;
    int inf = ia || ib;
    int opp = ((a ^ b) >> 31) != 0u;
    int both = ia && ib;
    both = both && opp;
    int ea = (int)(a >> 23 & 0xFFu), eb = (int)(b >> 23 & 0xFFu);
    uint ma = ea != 0 ? ((a & 0x7FFFFFu) >> 10) | 0x2000u : 0u;
    uint mb = eb != 0 ? ((b & 0x7FFFFFu) >> 10) | 0x2000u : 0u;
    int er = maxi(ea, eb) + 1;
    int fa2 = (int)SHR(ma, mini(er - ea - 1, 31));
    int fb2 = (int)SHR(mb, mini(er - eb - 1, 31));
    int r = ((a >> 31) != 0u ? -fa2 : fa2) + ((b >> 31) != 0u ? -fb2 : fb2);
    uint u = (uint)iabs(r);
    int sh = 14 - findMSB(u);
    uint res = n_ltMkU((uint)(r < 0), er - sh, SHL(u, sh) >> M(6, 2u, 1u));
    res = r == 0 ? 0u : res;
    res = inf ? (both ? LT_NAN : LT_INF) : res;
    return nan ? LT_NAN : res;
}
static uint n_ltR(uint x)
{
    uint sx = x >> 31;
    int ex = (int)(x >> 23 & 0xFFu);
    int er = 0xFD - ex;
    uint f = ((x & 0x7FFFFFu) + 0x800000u) >> 10;
    uint s0 = ltRcpLut[f >> 7 & 0x3Fu];
    uint s1 = ((((1u << 21) - s0 * f) * s0) >> 14) << 11;
    uint fr = s1 - 0x800000u;
    uint res = er <= M(7, 1, 0) ? sx << 31 : (sx << 31 | (uint)er << 23 | (fr & 0x7FFFFFu));
    int top = ex == 255;
    int mz = (x & 0x7FFFFFu) == 0u;
    res = top ? 0u : res;
    res = ex == 0 ? LT_INF : res;
    int nan = top && !mz;
    return nan ? LT_NAN : res;
}
/* ltVM is ltMulV(a, b, false) as a whole vector: its own mutant */
static void n_ltVM(const uint a[3], const uint b[3], uint out[3])
{
    n_ltMulV(a, b, 0, out);
#if MUT == 8
    out[2] = out[1];   /* a lane mix-up: the vector form's own failure */
#endif
}

/* ---- inputs ---- */

static uint64_t rs = 0x9E3779B97F4A7C15ull;
static uint rnd(void)
{
    rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17;
    return (uint)(rs >> 16);
}
static const uint sp[] = {
    0x00000000u, 0x80000000u, 0x00000001u, 0x807FFFFFu, 0x00800000u, 0x80800000u,
    0x3F800000u, 0xBF800000u, 0x3F800400u, 0x3F7FFC00u, 0x7F7FFFFFu, 0xFF7FFFFFu,
    0x7F800000u, 0xFF800000u, 0x7FC00000u, 0xFFC00000u, 0x7F800001u, 0x7F8003FFu,
    0x7F800400u, 0x3EAAAAABu, 0x40490FDBu, 0xC0490FDBu, 0x5F000000u, 0x1F800000u,
    0x7F000000u, 0x7E800000u, 0x3F000000u, 0x00FFFFFFu, 0x3FFFFC00u, 0xBFFFFC00u,
};
#define NSP ((int)(sizeof(sp) / sizeof(sp[0])))
/* a word near exponent e: random mantissa and sign */
static uint near(uint e)
{
    int ek = (int)e + (int)(rnd() % 25) - 12;
    ek = ek < 0 ? 0 : ek > 254 ? 254 : ek;
    return (rnd() & 0x807FFFFFu) | ((uint)ek << 23);
}

static long bad[16], tested[16];
static const char *names[16] = {
    "ltMkU", "ltMkU3", "ltM", "ltsM", "ltVM", "ltA3", "ltVA", "ltDp", "ltsA", "ltR",
};
static void report(int k, uint o, uint n, uint a, uint b, uint c)
{
    tested[k]++;
    if (o != n && bad[k]++ < 3) {
        printf("MISMATCH %s %08x %08x %08x: old %08x new %08x\n", names[k], a, b, c, o, n);
    }
}

static void pair(uint a, uint b)
{
    report(2, o_ltM(a, b), n_ltM(a, b), a, b, 0);
    report(3, o_ltsM(a, b), n_ltsM(a, b), a, b, 0);
    report(8, o_ltsA(a, b), n_ltsA(a, b), a, b, 0);
}
static void vec(const uint a[3], const uint b[3])
{
    uint vm[3], va[3];
    n_ltVM(a, b, vm);
    n_ltVA(a, b, va);
    for (int i = 0; i < 3; i++) {
        report(4, o_ltM(a[i], b[i]), vm[i], a[i], b[i], i);
        report(6, o_ltA(a[i], b[i]), va[i], a[i], b[i], i);
    }
    report(7, o_ltDp(a, b), n_ltDp(a, b), a[0], b[0], a[1]);
}
static void triple(uint a, uint b, uint c)
{
    report(5, o_ltA3(a, b, c), n_ltA3(a, b, c), a, b, c);
}

int main(int argc, char **argv)
{
    long millions = argc > 1 ? atol(argv[1]) : 50;

    /* ltMkU: every argument the callers can pass and then some */
    for (uint s = 0; s < 2; s++)
        for (int e = -64; e <= 320; e++)
            for (uint m = 0; m < 0x10000u; m++) {
                report(0, o_ltMk(s, e, m), n_ltMkU(s, e, m), s, (uint)e, m);
                if ((m & 0xFFu) == 0) {
                    uint sv[3] = { s, s ^ 1u, s }, mv[3] = { m, m ^ 0x5A5u, m >> 3 };
                    int ev[3] = { e, e + 1, 255 - e };
                    uint n3[3];
                    n_ltMkU3(sv, ev, mv, n3);
                    for (int i = 0; i < 3; i++)
                        report(1, o_ltMk(sv[i], ev[i], mv[i]), n3[i], sv[i], (uint)ev[i], mv[i]);
                }
            }

    /* ltR: exhaustive */
    for (uint64_t x = 0; x <= 0xFFFFFFFFull; x++) {
        report(9, o_ltR((uint)x), n_ltR((uint)x), (uint)x, 0, 0);
    }

    /* specials */
    for (int i = 0; i < NSP; i++)
        for (int j = 0; j < NSP; j++) {
            pair(sp[i], sp[j]);
            for (int k = 0; k < NSP; k++) {
                triple(sp[i], sp[j], sp[k]);
                uint a[3] = { sp[i], sp[j], sp[k] }, b[3] = { sp[k], sp[i], sp[j] };
                vec(a, b);
            }
        }

    /* random words and nearby exponents */
    for (long n = 0; n < millions * 1000000L / 4; n++) {
        pair(rnd(), rnd());
        uint e = rnd() % 254 + 1;
        pair(near(e), near(e));
        triple(rnd(), rnd(), rnd());
        triple(near(e), near(e), near(e));
        uint a[3] = { rnd(), rnd(), rnd() }, b[3] = { rnd(), rnd(), rnd() };
        vec(a, b);
        /* a dot product of unit-ish vectors: exponents near 127 */
        uint e2 = 127 + rnd() % 9 - 6;
        uint c[3] = { near(e2), near(e2), near(e2) }, d[3] = { near(e2), near(e2), near(e2) };
        vec(c, d);
        uint f[3] = { near(e), near(e), near(e) }, g[3] = { near(e), near(e), near(e) };
        vec(f, g);
    }

    long total = 0;
    for (int k = 0; k < 10; k++) {
        printf("%-7s %12ld tested %10ld mismatches\n", names[k], tested[k], bad[k]);
        total += bad[k];
    }
    printf("MUT=%d total mismatches %ld\n", MUT, total);
    return total != 0;
}
