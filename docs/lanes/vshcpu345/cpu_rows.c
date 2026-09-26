/*
 * Host harness for lane.vshcpu345 (#345 half 2). Compiled once against the
 * pristine nv2a_vsh_cpu.c and once against the patched one, by
 * cpu_rows.py; it includes the library source directly.
 *
 *   cpu_rows rows    < SPECIAL_raw.txt   the silicon rows, re-evaluated
 *   cpu_rows sweep                      a fixed pseudo-random finite sweep
 *
 * "rows" reads the console's SPECIAL_raw.txt lines (op, inputs, hw=...) and
 * prints each line with the evaluator's own result in place of hw=, in the
 * same format, so the output diffs against silicon line for line.
 * "sweep" prints one line per (op, input) for every op this patch touches,
 * over finite inputs only, so two builds' outputs diff to exactly the finite
 * inputs whose result changed.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "nv2a_vsh_cpu.c"

typedef void (*OpFn)(float *out, const float *inputs);

static float f(uint32_t u) {
  float v;
  memcpy(&v, &u, 4);
  return v;
}

static uint32_t u(float v) {
  uint32_t r;
  memcpy(&r, &v, 4);
  return r;
}

static const struct {
  const char *name;
  OpFn fn;
  int inputs;
  int scalar;
} kOps[] = {
    {"MUL", nv2a_vsh_cpu_mul, 2, 0}, {"MAD", nv2a_vsh_cpu_mad, 3, 0},
    {"DP3", nv2a_vsh_cpu_dp3, 2, 1}, {"DPH", nv2a_vsh_cpu_dph, 2, 1},
    {"DP4", nv2a_vsh_cpu_dp4, 2, 1}, {"RCC", nv2a_vsh_cpu_rcc, 1, 1},
    {"RSQ", nv2a_vsh_cpu_rsq, 1, 1}, {"RCP", nv2a_vsh_cpu_rcp, 1, 1},
};

static int find_op(const char *name) {
  for (size_t i = 0; i < sizeof(kOps) / sizeof(kOps[0]); ++i) {
    if (!strcmp(kOps[i].name, name)) return (int)i;
  }
  return -1;
}

/* A scalar row: "OP a=x,y,z,w [b=x,y,z,w] hw=..."; a vector row gives one
 * component per operand: "OP a=x b=y [c=z] hw=...", replicated to all four. */
static int rows(void) {
  char line[512];
  while (fgets(line, sizeof(line), stdin)) {
    char op[8];
    if (sscanf(line, "%7s", op) != 1) continue;
    int k = find_op(op);
    if (k < 0) {
      fprintf(stderr, "unknown op %s\n", op);
      return 1;
    }
    float in[12] = {0};
    char *p = line + strlen(op);
    int n = 0;
    while (n < kOps[k].inputs) {
      char *eq = strchr(p, '=');
      if (!eq) break;
      uint32_t c[4];
      int got = sscanf(eq + 1, "0x%x,0x%x,0x%x,0x%x", &c[0], &c[1], &c[2], &c[3]);
      if (got == 1) c[1] = c[2] = c[3] = c[0];
      else if (got != 4) break;
      for (int j = 0; j < 4; ++j) in[n * 4 + j] = f(c[j]);
      p = eq + 1;
      ++n;
    }
    float out[4];
    kOps[k].fn(out, in);
    char *hw = strstr(line, " hw=");
    if (!hw) continue;
    *hw = 0;
    if (kOps[k].scalar) {
      printf("%s hw=0x%08X,0x%08X,0x%08X,0x%08X\n", line, u(out[0]), u(out[1]), u(out[2]),
             u(out[3]));
    } else {
      printf("%s hw=0x%08X\n", line, u(out[0]));
    }
  }
  return 0;
}

static uint64_t rng = 0x345345345345345ULL;
static uint32_t next(void) {
  rng ^= rng << 13;
  rng ^= rng >> 7;
  rng ^= rng << 17;
  return (uint32_t)(rng >> 16);
}

/* A finite value, weighted toward the cases the patch could touch: signed
 * zeros, the RCC clamp edges near 2^+-64, and ordinary values. */
static float finite(void) {
  static const uint32_t kEdge[] = {0x00000000, 0x80000000, 0x3F800000, 0xBF800000,
                                   0x1F800000, 0x9F800000, 0x5F800000, 0xDF800000,
                                   0x1F7FFFFD, 0x5F80FFFF, 0x7F7FFFFF, 0xFF7FFFFF};
  for (;;) {
    uint32_t r = next();
    uint32_t v;
    switch (r & 7) {
      case 0: v = kEdge[(r >> 3) % (sizeof(kEdge) / sizeof(kEdge[0]))]; break;
      /* magnitudes within a few binades of 2^64 and 2^-64 */
      case 1: v = ((r >> 3) & 0x80000000u) | (0x5E000000u + (next() & 0x03FFFFFFu)); break;
      case 2: v = (next() & 0x80000000u) | (0x1E000000u + (next() & 0x03FFFFFFu)); break;
      default: v = next() ^ (next() << 16); break;
    }
    float x = f(v);
    if (x == x && x - x == 0.0f) return x; /* finite: not NaN, not inf */
  }
}

static int sweep(long n) {
  for (size_t k = 0; k < sizeof(kOps) / sizeof(kOps[0]); ++k) {
    for (long i = 0; i < n; ++i) {
      float in[12];
      for (int j = 0; j < 12; ++j) in[j] = finite();
      float out[4];
      kOps[k].fn(out, in);
      printf("%s", kOps[k].name);
      for (int j = 0; j < kOps[k].inputs * 4; ++j) printf(" %08X", u(in[j]));
      printf(" ->");
      for (int j = 0; j < 4; ++j) printf(" %08X", u(out[j]));
      printf("\n");
    }
  }
  return 0;
}

int main(int argc, char **argv) {
  if (argc >= 2 && !strcmp(argv[1], "rows")) return rows();
  if (argc >= 2 && !strcmp(argv[1], "sweep")) return sweep(argc >= 3 ? atol(argv[2]) : 200000);
  fprintf(stderr, "usage: %s rows|sweep [n]\n", argv[0]);
  return 2;
}
