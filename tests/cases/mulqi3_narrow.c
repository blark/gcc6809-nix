// EXPECT: 0
// Low-byte products are identical for signed and unsigned input bit patterns.
volatile signed char source_s;
volatile unsigned char source_u;
__attribute__((noinline)) signed char input_s(void) { return source_s; }
__attribute__((noinline)) unsigned char input_u(void) { return source_u; }
__attribute__((noinline)) unsigned char narrow_ss(signed char factor)
{
    return (unsigned char)(input_s() * factor);
}
__attribute__((noinline)) unsigned char narrow_su(unsigned char factor)
{
    return (unsigned char)(input_s() * factor);
}
__attribute__((noinline)) unsigned char narrow_us(signed char factor)
{
    return (unsigned char)(input_u() * factor);
}
__attribute__((noinline)) unsigned char narrow_uu(unsigned char factor)
{
    // Promote to unsigned int to avoid 16-bit signed-int overflow.
    return (unsigned char)((unsigned int)input_u() * factor);
}
int main(void)
{
    source_s = -3;
    source_u = 253;
    if (narrow_ss(-7) != 21 || narrow_ss(7) != 235) return 1;
    if (narrow_su(249) != 21 || narrow_su(7) != 235) return 2;
    if (narrow_us(-7) != 21 || narrow_us(7) != 235) return 3;
    if (narrow_uu(249) != 21 || narrow_uu(7) != 235) return 4;
    return 0;
}
