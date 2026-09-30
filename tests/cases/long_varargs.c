// EXPECT: 7
// Long arguments passed through varargs, read back with va_arg, and through
// newlib's printf family with %ld.
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

__attribute__((noinline)) long sum_longs(int n, ...)
{
    va_list ap;
    long s = 0;
    va_start(ap, n);
    while (n-- > 0)
        s += va_arg(ap, long);
    va_end(ap);
    return s;
}

__attribute__((noinline)) int mixed(int a, ...)
{
    va_list ap;
    int b; long c; char d; long e;
    va_start(ap, a);
    b = va_arg(ap, int);
    c = va_arg(ap, long);
    d = (char)va_arg(ap, int);
    e = va_arg(ap, long);
    va_end(ap);
    return a == 1 && b == 2 && c == 0x00030004L && d == 5 && e == -6L;
}

volatile long vx = 0x00010002L;
char buf[40];

int main(void)
{
    int r = 0;
    long x = vx;
    if (sum_longs(3, x, 0x00020000L, -1L) == 0x00030001L) r |= 1;
    if (mixed(1, 2, 0x00030004L, 5, -6L)) r |= 2;
    sprintf(buf, "%ld %lu %ld", x, 40000UL, -100000L);
    if (strcmp(buf, "65538 40000 -100000") == 0) r |= 4;
    return r;
}
