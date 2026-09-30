// EXPECT: 63
// Long arguments passed by value in first, middle and last positions, mixed
// with int and char arguments.  Each function returns a distinguishable
// result; the caller pushes the halves and the callee must see the same value.
// Before the movsi push fix the halves arrived swapped (bug 1).
#define NOINLINE __attribute__((noinline))

NOINLINE long first(long a, int b, char c) { return a + b + c; }
NOINLINE long middle(int a, long b, char c) { return b - a - c; }
NOINLINE long last(char a, int b, long c) { return c * 2 + a + b; }
NOINLINE long two(long a, long b) { return a - b; }
NOINLINE long three(long a, long b, long c) { return a + b - c; }
NOINLINE int longs_equal(long a, long b) { return a == b; }

volatile long vx = 0x00010002L;   /* high half 1, low half 2 */
volatile long vy = 0x0003FFFFL;   /* low half >= 0x8000 */

int main(void)
{
    int r = 0;
    long x = vx, y = vy;

    if (first(x, 5, 3) == 0x0001000AL)            r |= 1;
    if (middle(5, x, 3) == 0x0000FFFAL)           r |= 2;
    if (last(1, 2, x) == 0x00020007L)             r |= 4;
    if (two(y, x) == 0x0002FFFDL)                 r |= 8;
    if (three(x, y, 1L) == 0x00050000L)           r |= 16;
    if (longs_equal(x, 0x00010002L) && !longs_equal(x, 0x00020001L)) r |= 32;
    return r;
}
