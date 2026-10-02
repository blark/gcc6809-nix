#!/usr/bin/env python3
"""Unit tests for the native unsigned-byte RTL regression checker."""

import unittest

from check_umulqihi3_rtl import check_dump, form_at


LEFT = "(zero_extend:HI (reg:QI 27))"


class RTLCheckerTests(unittest.TestCase):
    def check_factor(self, factor):
        return check_dump(f"(mult:HI {LEFT} {factor})")

    def test_extended_register_and_memory(self):
        for operand in ("(reg:QI 28)", "(mem/c/i:QI (reg:HI 4))"):
            with self.subTest(operand=operand):
                self.assertEqual(self.check_factor(f"(zero_extend:HI {operand})"),
                                 (1, 0, []))

    def test_unsigned_constants(self):
        for value in (0, 1, 127, 128, 129, 200, 255):
            with self.subTest(value=value):
                self.assertEqual(self.check_factor(f"(const_int {value})"),
                                 (1, 1, []))

    def test_reject_bare_qi(self):
        for operand in ("(reg:QI 28)", "(mem/c/i:QI (reg:HI 4))"):
            with self.subTest(operand=operand):
                count, constants, errors = self.check_factor(operand)
                self.assertEqual((count, constants, len(errors)), (1, 0, 1))

    def test_reject_signed_or_oversized_hi_constant(self):
        for value in (-128, -127, -56, -1, 256):
            with self.subTest(value=value):
                count, constants, errors = self.check_factor(f"(const_int {value})")
                self.assertEqual((count, constants, len(errors)), (1, 1, 1))

    def test_reject_wrong_extension_source_mode(self):
        self.assertEqual(len(self.check_factor("(zero_extend:HI (reg:HI 28))")[2]), 1)

    def test_ordinary_hi_product_not_native_pattern(self):
        self.assertEqual(check_dump("(mult:HI (reg:HI 27) (reg:HI 28))"), (0, 0, []))

    def test_nested_forms_and_quoted_parentheses(self):
        text = '(mult:HI ' + LEFT + ' (const_int 200)) "ignored (text)"'
        self.assertEqual(form_at(text, 0), text[:text.index(' "ignored')])
        self.assertEqual(form_at('(note "unbalanced ) (" (reg:QI 27)) trailing', 0),
                         '(note "unbalanced ) (" (reg:QI 27))')

    def test_truncated_dump_fails(self):
        with self.assertRaises(ValueError):
            check_dump(f"(mult:HI {LEFT} (reg:QI 28)")


if __name__ == "__main__":
    unittest.main()
