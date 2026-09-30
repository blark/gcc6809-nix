// EXPECT: 1
// Unwind nested frames, preserve a live local, and reuse the outer context.
#include <setjmp.h>

static jmp_buf outer, inner;
static volatile int stage;
static volatile unsigned int checksum;

__attribute__((noinline)) static void jump_inner(int a, int b, int c)
{
    volatile unsigned int words[8];
    words[0] = a;
    words[7] = b + c;
    checksum = words[0] + words[7];
    longjmp(inner, 256);
}

__attribute__((noinline)) static void middle(int a, int b, int c)
{
    volatile unsigned int local = 0x5a39;
    switch (setjmp(inner)) {
    case 0:
        jump_inner(a, b, c);
        break;
    case 256:
        if (local != 0x5a39 || checksum != 60)
            longjmp(outer, 99);
        stage = 1;
        longjmp(outer, 0);
        break;
    default:
        longjmp(outer, 99);
    }
}

int main(void)
{
    volatile unsigned int local = 0x1234;
    switch (setjmp(outer)) {
    case 0:
        if (stage != 0)
            return 0;
        middle(10, 20, 30);
        return 0;
    case 1:
        if (stage != 1 || local != 0x1234)
            return 0;
        stage = 2;
        longjmp(outer, -1);
        return 0;
    case -1:
        return stage == 2 && local == 0x1234 && checksum == 60;
    default:
        return 0;
    }
}
