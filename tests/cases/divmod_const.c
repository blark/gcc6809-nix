// EXPECT: 0
// 16-bit / and % by constants.  Power-of-two and other constant divisors
// may be open-coded by the compiler instead of calling _divhi3/_modhi3, and
// the open-coded form still has to truncate toward zero and give the
// remainder the dividend's sign (C99 6.5.5).  The dividend is volatile so
// nothing folds at compile time.  Expected values were computed on the host
// (Python).  Returns 0, or the number of the first failing check.
// INT_MIN / -1 is undefined in C and is checked at the helper level by
// tests/review/run_divmod_review.py.
#define INT_MIN_ (-32767 - 1)

static volatile int a;
static volatile unsigned int u;
static int n;

#define CHECK(cond) do { ++n; if (!(cond)) return n; } while (0)

int main(void)
{
    a = -7;
    CHECK(a / 2 == -3);   CHECK(a % 2 == -1);
    CHECK(a / 4 == -1);   CHECK(a % 4 == -3);
    CHECK(a / 8 == 0);    CHECK(a % 8 == -7);
    CHECK(a / -2 == 3);   CHECK(a % -2 == -1);
    CHECK(a / 256 == 0);  CHECK(a % 256 == -7);
    CHECK(a / -1 == 7);   CHECK(a % -1 == 0);

    a = 5;
    CHECK(a / 2 == 2);    CHECK(a % 2 == 1);
    CHECK(a / -2 == -2);  CHECK(a % -2 == 1);
    CHECK(a / -256 == 0); CHECK(a % -256 == 5);
    CHECK(a / -1 == -5);  CHECK(a % -1 == 0);

    a = -256;
    CHECK(a / 256 == -1); CHECK(a % 256 == 0);
    CHECK(a / 2 == -128); CHECK(a % 2 == 0);
    CHECK(a / 16 == -16); CHECK(a % 16 == 0);

    a = -257;
    CHECK(a / 256 == -1); CHECK(a % 256 == -1);
    CHECK(a / 16 == -16); CHECK(a % 16 == -1);

    a = INT_MIN_;
    CHECK(a / 1 == INT_MIN_);      CHECK(a % 1 == 0);
    CHECK(a / 2 == -16384);        CHECK(a % 2 == 0);
    CHECK(a / 256 == -128);        CHECK(a % 256 == 0);
    CHECK(a / 8192 == -4);         CHECK(a % 8192 == 0);
    CHECK(a / 16384 == -2);        CHECK(a % 16384 == 0);
    CHECK(a / 32767 == -1);        CHECK(a % 32767 == -1);
    CHECK(a / 10 == -3276);        CHECK(a % 10 == -8);

    a = 32767;
    CHECK(a / 2 == 16383);         CHECK(a % 2 == 1);
    CHECK(a / 256 == 127);         CHECK(a % 256 == 255);
    CHECK(a / 16384 == 1);         CHECK(a % 16384 == 16383);
    CHECK(a / -1 == -32767);       CHECK(a % -1 == 0);
    CHECK(a / 10 == 3276);         CHECK(a % 10 == 7);

    a = -32767;
    CHECK(a / -1 == 32767);        CHECK(a % -1 == 0);
    CHECK(a / 2 == -16383);        CHECK(a % 2 == -1);

    u = 65535u;
    CHECK(u / 2 == 32767u);        CHECK(u % 2 == 1);
    CHECK(u / 256 == 255);         CHECK(u % 256 == 255);
    CHECK(u / 32768u == 1);        CHECK(u % 32768u == 32767u);
    CHECK(u / 65535u == 1);        CHECK(u % 65535u == 0);
    CHECK(u / 10 == 6553u);        CHECK(u % 10 == 5);

    u = 32768u;
    CHECK(u / 2 == 16384u);        CHECK(u % 2 == 0);
    CHECK(u / 3 == 10922u);        CHECK(u % 3 == 2);
    CHECK(u / 10 == 3276u);        CHECK(u % 10 == 8);
    CHECK(u / 32768u == 1);        CHECK(u % 32768u == 0);
    CHECK(u / 65535u == 0);        CHECK(u % 65535u == 32768u);

    return 0;
}
