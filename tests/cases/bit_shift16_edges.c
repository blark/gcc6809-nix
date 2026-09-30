// EXPECT: 0
// Defined unsigned shifts and this target's arithmetic signed right shift.
// Every count is strictly less than the operand width; no signed left shift.
// Golden results are constants, not calculations through the same helpers.
#define NOINLINE __attribute__((noinline))
NOINLINE unsigned int left(unsigned int x, int n) { return x << n; }
NOINLINE unsigned int logical(unsigned int x, int n) { return x >> n; }
NOINLINE int arithmetic(int x, int n) { return x >> n; }
struct vector {
    unsigned int value;
    int signed_value;
    int count;
    unsigned int left, logical, arithmetic;
};
static const struct vector vectors[] = {
    {0x0000U, 0, 0, 0x0000U, 0x0000U, 0x0000U},
    {0x0000U, 0, 1, 0x0000U, 0x0000U, 0x0000U},
    {0x0000U, 0, 7, 0x0000U, 0x0000U, 0x0000U},
    {0x0000U, 0, 8, 0x0000U, 0x0000U, 0x0000U},
    {0x0000U, 0, 14, 0x0000U, 0x0000U, 0x0000U},
    {0x0000U, 0, 15, 0x0000U, 0x0000U, 0x0000U},
    {0x0001U, 1, 0, 0x0001U, 0x0001U, 0x0001U},
    {0x0001U, 1, 1, 0x0002U, 0x0000U, 0x0000U},
    {0x0001U, 1, 7, 0x0080U, 0x0000U, 0x0000U},
    {0x0001U, 1, 8, 0x0100U, 0x0000U, 0x0000U},
    {0x0001U, 1, 14, 0x4000U, 0x0000U, 0x0000U},
    {0x0001U, 1, 15, 0x8000U, 0x0000U, 0x0000U},
    {0x7fffU, 32767, 0, 0x7fffU, 0x7fffU, 0x7fffU},
    {0x7fffU, 32767, 1, 0xfffeU, 0x3fffU, 0x3fffU},
    {0x7fffU, 32767, 7, 0xff80U, 0x00ffU, 0x00ffU},
    {0x7fffU, 32767, 8, 0xff00U, 0x007fU, 0x007fU},
    {0x7fffU, 32767, 14, 0xc000U, 0x0001U, 0x0001U},
    {0x7fffU, 32767, 15, 0x8000U, 0x0000U, 0x0000U},
    {0x8000U, (-32767 - 1), 0, 0x8000U, 0x8000U, 0x8000U},
    {0x8000U, (-32767 - 1), 1, 0x0000U, 0x4000U, 0xc000U},
    {0x8000U, (-32767 - 1), 7, 0x0000U, 0x0100U, 0xff00U},
    {0x8000U, (-32767 - 1), 8, 0x0000U, 0x0080U, 0xff80U},
    {0x8000U, (-32767 - 1), 14, 0x0000U, 0x0002U, 0xfffeU},
    {0x8000U, (-32767 - 1), 15, 0x0000U, 0x0001U, 0xffffU},
    {0x8001U, -32767, 0, 0x8001U, 0x8001U, 0x8001U},
    {0x8001U, -32767, 1, 0x0002U, 0x4000U, 0xc000U},
    {0x8001U, -32767, 7, 0x0080U, 0x0100U, 0xff00U},
    {0x8001U, -32767, 8, 0x0100U, 0x0080U, 0xff80U},
    {0x8001U, -32767, 14, 0x4000U, 0x0002U, 0xfffeU},
    {0x8001U, -32767, 15, 0x8000U, 0x0001U, 0xffffU},
    {0xaaaaU, -21846, 0, 0xaaaaU, 0xaaaaU, 0xaaaaU},
    {0xaaaaU, -21846, 1, 0x5554U, 0x5555U, 0xd555U},
    {0xaaaaU, -21846, 7, 0x5500U, 0x0155U, 0xff55U},
    {0xaaaaU, -21846, 8, 0xaa00U, 0x00aaU, 0xffaaU},
    {0xaaaaU, -21846, 14, 0x8000U, 0x0002U, 0xfffeU},
    {0xaaaaU, -21846, 15, 0x0000U, 0x0001U, 0xffffU},
    {0xffffU, -1, 0, 0xffffU, 0xffffU, 0xffffU},
    {0xffffU, -1, 1, 0xfffeU, 0x7fffU, 0xffffU},
    {0xffffU, -1, 7, 0xff80U, 0x01ffU, 0xffffU},
    {0xffffU, -1, 8, 0xff00U, 0x00ffU, 0xffffU},
    {0xffffU, -1, 14, 0xc000U, 0x0003U, 0xffffU},
    {0xffffU, -1, 15, 0x8000U, 0x0001U, 0xffffU},
};
volatile int runtime_count;
int main(void)
{
    unsigned int i;
    for (i = 0; i < sizeof(vectors) / sizeof(vectors[0]); ++i) {
        runtime_count = vectors[i].count;
        if (left(vectors[i].value, runtime_count) != vectors[i].left)
            return 100 + i;
        if (logical(vectors[i].value, runtime_count) != vectors[i].logical)
            return 200 + i;
        if ((unsigned int)arithmetic(vectors[i].signed_value, runtime_count) != vectors[i].arithmetic)
            return 300 + i;
    }
    return 0;
}
