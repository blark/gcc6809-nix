// EXPECT: 7239
// Many-operand sweep through the 16-bit divide/modulo helpers: signed
// dividends -200..200 by 7 and -10, unsigned dividends 32700..32900
// (straddling 0x8000) by 3 and 257, folded into one 16-bit checksum.
// The fold is a rotate-left-by-one, an add and an xor, so it only depends
// on the operations under test.  The expected value was computed on the
// host with Python (C99 truncation, 16-bit wraparound):
//
//   def cdiv(a, b):
//       q = abs(a) // abs(b)
//       if (a < 0) != (b < 0): q = -q
//       return q, a - q * b
//   M = 0xFFFF
//   acc = 0
//   def fold(q, r):
//       global acc
//       acc = (acc + acc + (acc >= 0x8000)) & M
//       acc = ((acc + (q & M)) & M) ^ (r & M)
//   for d in (7, -10):
//       for i in range(-200, 201): fold(*cdiv(i, d))
//   for d in (3, 257):
//       for u in range(32700, 32901): fold(u // d, u % d)
//   print(acc)   # 7239
//
// The exhaustive helper check (every dividend) lives in
// tests/review/run_divmod_review.py; this case keeps a slice of it in the
// normal suite at every optimization level.

static volatile int sdiv[2] = { 7, -10 };
static volatile unsigned int udiv[2] = { 3, 257 };

static unsigned int acc;

static void fold(unsigned int q, unsigned int r)
{
    acc = acc + acc + (acc >= 0x8000u);
    acc = (acc + q) ^ r;
}

int main(void)
{
    int k;
    for (k = 0; k < 2; ++k) {
        int d = sdiv[k];
        int i;
        for (i = -200; i <= 200; ++i)
            fold((unsigned int)(i / d), (unsigned int)(i % d));
    }
    for (k = 0; k < 2; ++k) {
        unsigned int d = udiv[k];
        unsigned int u;
        for (u = 32700u; u <= 32900u; ++u)
            fold(u / d, u % d);
    }
    return (int)acc;
}
