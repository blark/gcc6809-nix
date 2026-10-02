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
__attribute__((noinline)) unsigned char square_s(signed char value)
{
    return (unsigned char)(value * value);
}
__attribute__((noinline)) unsigned char square_u(unsigned char value)
{
    return (unsigned char)((unsigned int)value * value);
}
__attribute__((noinline)) unsigned char square_volatile(void)
{
    signed char value = source_s;
    return (unsigned char)(value * value);
}
__attribute__((noinline)) int wide_square_s(signed char value)
{
    return value * value;
}
__attribute__((noinline)) unsigned int wide_square_u(unsigned char value)
{
    return (unsigned int)value * value;
}
int main(void)
{
    source_s = -3;
    source_u = 253;
    if (narrow_ss(-7) != 21 || narrow_ss(7) != 235) return 1;
    if (narrow_su(249) != 21 || narrow_su(7) != 235) return 2;
    if (narrow_us(-7) != 21 || narrow_us(7) != 235) return 3;
    if (narrow_uu(249) != 21 || narrow_uu(7) != 235) return 4;
    if (square_s(-3) != 9 || square_s(127) != 1) return 5;
    if (square_u(253) != 9 || square_u(255) != 1) return 6;
    if (square_volatile() != 9) return 7;
    if (wide_square_s(-128) != 16384) return 8;
    if (wide_square_u(255) != 65025u) return 9;
    return 0;
}
