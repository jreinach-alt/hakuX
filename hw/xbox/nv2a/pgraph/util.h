/*
 * QEMU Geforce NV2A implementation
 *
 * Copyright (c) 2012 espes
 * Copyright (c) 2015 Jannik Vogel
 * Copyright (c) 2018-2024 Matt Borgerson
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */

#ifndef HW_XBOX_NV2A_PGRAPH_UTIL_H
#define HW_XBOX_NV2A_PGRAPH_UTIL_H

static const float f16_max = 511.9375f;
static const float f24_max = 1.0E30;

/* 16 bit to [0.0, F16_MAX = 511.9375] */
static inline 
float convert_f16_to_float(uint16_t f16) {
    if (f16 == 0x0000) { return 0.0; }
    uint32_t i = (f16 << 11) + 0x3C000000;
    return *(float*)&i;
}

/* 24 bit to [0.0, F24_MAX] */
static inline 
float convert_f24_to_float(uint32_t f24) {
    assert(!(f24 >> 24));
    f24 &= 0xFFFFFF;
    if (f24 == 0x000000) { return 0.0; }
    uint32_t i = f24 << 7;
    return *(float*)&i;
}

static inline 
uint8_t cliptobyte(int x)
{
    return (uint8_t)((x < 0) ? 0 : ((x > 255) ? 255 : x));
}

/*
 * YCbCr to RGB the way the NV2A does it, derived from hardware goldens.
 *
 * The BT.601 coefficients themselves are right, but the hardware datapath is
 * not a single rounded dot product: each term is quantised to an integer on
 * its own and only then summed. The goldens show this as strict separability
 * -- at fixed Y the difference between two chroma columns is a constant with
 * no +-1 wobble, which a single rounded sum cannot produce. Three of the four
 * chroma terms also carry one bit less than the luma term and so move in
 * steps of two; the blue difference term is the exception.
 *
 * Derived and checked against every unclipped (Y,Cb,Cr) -> RGB pair
 * recoverable from the YUY2 and UYVY texture format goldens: 37497 distinct
 * triples, all three channels exact. The sampled ranges are Y 42..209 and
 * Cb, Cr 17..238; outside those the affine form is extrapolated.
 *
 * Rounding constants are one representative choice; each is free over a small
 * range that a compensating change in the trailing constant absorbs.
 *
 * c = Y - 16, d = Cb - 128, e = Cr - 128.
 */
static inline
void convert_ycbcr_to_rgb(int c, int d, int e,
                          uint8_t *r, uint8_t *g, uint8_t *b)
{
    int luma = (298 * c - 96) >> 8;

    *r = cliptobyte(luma + 2 * ((409 * e + 127) >> 9));
    *g = cliptobyte(luma + 2 * ((-50 * d + 254) >> 8) +
                    2 * ((-104 * e + 248) >> 8) + 1);
    *b = cliptobyte(luma + ((516 * d) >> 8));
}

static inline 
void convert_yuy2_to_rgb(const uint8_t *line, unsigned int ix,
                                uint8_t *r, uint8_t *g, uint8_t* b) {
    int c, d, e;
    c = (int)line[ix * 2] - 16;
    if (ix % 2) {
        d = (int)line[ix * 2 - 1] - 128;
        e = (int)line[ix * 2 + 1] - 128;
    } else {
        d = (int)line[ix * 2 + 1] - 128;
        e = (int)line[ix * 2 + 3] - 128;
    }
    convert_ycbcr_to_rgb(c, d, e, r, g, b);
}

static inline 
void convert_uyvy_to_rgb(const uint8_t *line, unsigned int ix,
                                uint8_t *r, uint8_t *g, uint8_t* b) {
    int c, d, e;
    c = (int)line[ix * 2 + 1] - 16;
    if (ix % 2) {
        d = (int)line[ix * 2 - 2] - 128;
        e = (int)line[ix * 2 + 0] - 128;
    } else {
        d = (int)line[ix * 2 + 0] - 128;
        e = (int)line[ix * 2 + 2] - 128;
    }
    convert_ycbcr_to_rgb(c, d, e, r, g, b);
}

#endif
