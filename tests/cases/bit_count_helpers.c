// EXPECT: 0
// Zero is tested through named runtime helpers, never undefined-zero builtins.
// The zero results below characterize this port, not a portable libgcc ABI.
extern int __clzhi2(unsigned int);
extern int __ctzhi2(unsigned int);
extern int __clzsi2(unsigned long);
extern int __ctzsi2(unsigned long);
volatile unsigned int zero16 = 0;
volatile unsigned long zero32 = 0;

int main(void)
{
    unsigned int small = 1U;
    unsigned long wide = 1UL;
    int bit;
    if (__clzhi2(zero16) != 16 || __ctzhi2(zero16) != -1)
        return 1;
    if (__clzsi2(zero32) != 32 || __ctzsi2(zero32) != 15)
        return 2;
    for (bit = 0; bit < 16; ++bit) {
        if (__clzhi2(small) != 15 - bit || __ctzhi2(small) != bit)
            return 3;
        if (__builtin_clz(small) != 15 - bit || __builtin_ctz(small) != bit)
            return 4;
        small <<= 1;
    }
    for (bit = 0; bit < 32; ++bit) {
        if (__clzsi2(wide) != 31 - bit || __ctzsi2(wide) != bit)
            return 5;
        if (__builtin_clzl(wide) != 31 - bit || __builtin_ctzl(wide) != bit)
            return 6;
        wide <<= 1;
    }
    if (__clzhi2(0xffffU) != 0 || __ctzhi2(0xffffU) != 0)
        return 7;
    if (__clzsi2(0xffffffffUL) != 0 || __ctzsi2(0xffffffffUL) != 0)
        return 8;
    return 0;
}
