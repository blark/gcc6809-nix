// EXPECT: 15
// A long multiplied by a constant.  The optimizer turns small constant
// multiplies into shifts and adds, and a loop summing x nine times into x*9;
// these used to hit the 32-bit constant ICE (bug 2).
#define NOINLINE __attribute__((noinline))

NOINLINE long times9(long x) { return x * 9; }
NOINLINE long times10(long x) { return x * 10; }
NOINLINE long times65537(long x) { return x * 0x10001L; }
NOINLINE long sum9(long x)
{
    long s = 0;
    int i;
    for (i = 0; i < 9; i++)
        s += x;
    return s;
}
NOINLINE long count_down(int n)
{
    long x = 0;
    while (n-- > 0)
        x--;
    return x;
}

volatile long vx = 0x00012345L;

int main(void)
{
    int r = 0;
    long x = vx;
    if (times9(x) == 0x000A3D6DL)     r |= 1;
    if (times10(x) == 0x000B60B2L)    r |= 2;
    if (times65537(x) == 0x23462345L) r |= 4;
    if (sum9(x) == 0x000A3D6DL && count_down(3) == -3L) r |= 8;
    return r;
}
