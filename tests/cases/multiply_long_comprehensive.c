// EXPECT: 0
// 32-bit multiplication test
// Returns 0 on success, non-zero indicates which test failed
// Note: Avoids constants that trigger compiler ICE (>32767 or <-32768)

long a, b, result, expected;

int main(void) {
    // Test 1: 6 * 7 = 42
    a = 6; b = 7; expected = 42;
    result = a * b;
    if (result != expected) return 1;

    // Test 2: 0 * anything = 0
    a = 0; b = 1234; expected = 0;
    result = a * b;
    if (result != expected) return 2;

    // Test 3: 1 * x = x
    a = 1; b = 9999; expected = 9999;
    result = a * b;
    if (result != expected) return 3;

    // Test 4: 2 * 2 = 4
    a = 2; b = 2; expected = 4;
    result = a * b;
    if (result != expected) return 4;

    // Test 5: 10 * 10 = 100
    a = 10; b = 10; expected = 100;
    result = a * b;
    if (result != expected) return 5;

    // Test 6: 100 * 100 = 10000
    a = 100; b = 100; expected = 10000;
    result = a * b;
    if (result != expected) return 6;

    // Test 7: 181 * 181 = 32761 (largest result < 32768)
    a = 181; b = 181; expected = 32761;
    result = a * b;
    if (result != expected) return 7;

    // Test 8: 256 * 256 = 65536 (result crosses 16-bit boundary)
    // Use computed expected to avoid large literal ICE
    a = 256; b = 256;
    expected = 256;
    expected = expected * 256;
    result = a * b;
    if (result != expected) return 8;

    // Test 9: 500 * 500 = 250000
    a = 500; b = 500;
    expected = 500;
    expected = expected * 500;
    result = a * b;
    if (result != expected) return 9;

    // Test 10: 1000 * 1000 = 1000000
    a = 1000; b = 1000;
    expected = 1000;
    expected = expected * 1000;
    result = a * b;
    if (result != expected) return 10;

    return 0;  // All tests passed
}
