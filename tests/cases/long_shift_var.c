// EXPECT: 63
// 32-bit shifts by a variable amount go through libgcc (___ashlsi3,
// ___lshrsi3, ___ashrsi3), whose long argument is pushed by the caller.
#define NOINLINE __attribute__((noinline))

NOINLINE long shl(long x, int n) { return x << n; }
NOINLINE unsigned long shr(unsigned long x, int n) { return x >> n; }
NOINLINE long sar(long x, int n) { return x >> n; }

volatile int v1 = 1, v4 = 4, v17 = 17, v31 = 31;
volatile long vx = 0x00010002L;
volatile long vneg = -0x00010000L;

int main(void)
{
    int r = 0;
    long x = vx;
    if (shl(x, v1) == 0x00020004L)               r |= 1;
    if (shl(x, v17) == 0x00040000L)              r |= 2;
    if (shr((unsigned long)x, v1) == 0x00008001L) r |= 4;
    if (shr((unsigned long)x, v17) == 0L)        r |= 8;
    if (sar(vneg, v4) == -0x00001000L)           r |= 16;
    if (sar(vneg, v31) == -1L && shl(1L, v31) == (long)0x80000000L) r |= 32;
    return r;
}
