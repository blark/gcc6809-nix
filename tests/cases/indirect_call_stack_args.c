// EXPECT: 63
// Indirect calls with two or more stack arguments.  The function pointer
// lives in a struct reached through a register, in a stack slot (spilled
// local or incoming argument), or in a global.  The pushed arguments move
// the stack pointer before the jsr, and the [n,s]/[n,y] operand must still
// name the right slot (bug 3).
#define NOINLINE __attribute__((noinline))
typedef int (*fn2)(int, int);
typedef int (*fn3)(int, int, int);
struct ops { fn2 f; int pad; fn3 g; };

NOINLINE int sub(int a, int b) { return a - b; }
NOINLINE int mul(int a, int b) { return a * b; }
NOINLINE int sub3(int a, int b, int c) { return a - b - c; }

NOINLINE int via_struct0(struct ops *p, int a) { return p->f(a, 3); }
NOINLINE int via_struct4(struct ops *p, int a) { return p->g(a, 3, 5); }
NOINLINE int twice(fn2 f, int a, int b) { return f(a, b) + f(b, a); }
NOINLINE int four(fn2 f, fn2 g, int a, int b)
{
    int r = f(a, b);
    int s = g(b, a);
    return r + s + f(r, s) + g(s, r);
}
NOINLINE int last_arg(int a, int b, fn2 f) { return f(a, b); }
fn2 gf;
NOINLINE int via_global(int a) { return gf(a, 9); }

int main(void)
{
    int r = 0;
    struct ops o;
    o.f = sub; o.pad = 99; o.g = sub3;
    gf = mul;
    if (via_struct0(&o, 10) == 7)        r |= 1;
    if (via_struct4(&o, 10) == 2)        r |= 2;
    if (twice(sub, 10, 3) == 0)          r |= 4;   /* 7 + -7 */
    /* r = 10-3 = 7, s = 3*10 = 30, f(7,30) = -23, g(30,7) = 210 */
    if (four(sub, mul, 10, 3) == 224)    r |= 8;
    if (last_arg(10, 3, mul) == 30)      r |= 16;
    if (via_global(6) == 54)             r |= 32;
    return r;
}
