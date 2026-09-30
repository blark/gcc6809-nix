// EXPECT: 7
// Functions returning a struct (through the hidden result pointer) whose
// members are longs, built from long arguments.
#define NOINLINE __attribute__((noinline))
struct pair { long lo; long hi; };
struct triple { char tag; long a; int b; };

NOINLINE struct pair make_pair(long a, long b)
{
    struct pair p;
    p.lo = a; p.hi = b;
    return p;
}
NOINLINE struct triple make_triple(char t, long a, int b)
{
    struct triple x;
    x.tag = t; x.a = a * 2; x.b = b;
    return x;
}
NOINLINE long sum_pair(struct pair p) { return p.lo + p.hi; }

volatile long vx = 0x00010002L;

int main(void)
{
    int r = 0;
    long x = vx;
    struct pair p = make_pair(x, -1L);
    struct triple t = make_triple(7, x, 300);
    if (p.lo == 0x00010002L && p.hi == -1L) r |= 1;
    if (t.tag == 7 && t.a == 0x00020004L && t.b == 300) r |= 2;
    if (sum_pair(p) == 0x00010001L) r |= 4;
    return r;
}
