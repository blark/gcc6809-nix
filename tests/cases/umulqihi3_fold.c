// EXPECT: 0
// An unsigned byte product folded from a value the compiler knows.
// Before the umulqihi3 operand fix, the pattern held a constant factor as a
// signed byte (200 as -56), so at -O2/-O3/-Os CSE learned v == -3 from the
// test and folded 253 * 200 as 253 * -56 = 51368 instead of 50600.
// Returns 0, or the number of the first wrong product.
union pun { unsigned char u; signed char s; };
union pun v;
unsigned char byte;

__attribute__((noinline)) unsigned int times200(void)
{ if (v.s == -3) return v.u * 200u; return 1; }

__attribute__((noinline)) unsigned int times129(void)
{ if (v.s == -3) return v.u * 129u; return 1; }

__attribute__((noinline)) unsigned int times255(unsigned char *p)
{ if (*(signed char *)p == -1) return *p * 255u; return 1; }

int main(void)
{
    v.u = 253;
    if (times200() != 50600u) return 1;
    if (times129() != 32637u) return 2;
    byte = 255;
    if (times255(&byte) != 65025u) return 3;
    return 0;
}
