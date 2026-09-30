#!/usr/bin/env python3
"""Check raw SEX for every D value and H/N/Z/V/C input-flag combination."""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_tests as harness


# SEX updates N/Z but preserves H/V/C (6809 CC bits 5, 1 and 0).
PRESERVED_MASK = 0x23
CHECKED_MASK = PRESERVED_MASK | 0x0c
INITIAL_CC = tuple(vch | nz
                   for vch in (0x00, 0x01, 0x02, 0x03, 0x20, 0x21, 0x22, 0x23)
                   for nz in (0x00, 0x04, 0x08, 0x0c))


def main():
    cfg = harness.Config(harness.CFG_DICT)
    memory = harness.Memory64K(cfg)
    cpu = harness.CPU(memory, cfg)
    memory._mem[0x2000] = 0x1d  # SEX: sign-extend B into D, regardless of old A.
    failures = 0
    for initial_cc in INITIAL_CC:
        for initial_d in range(65536):
            cpu.accu_d.set(initial_d)
            cpu.program_counter.set(0x2000)
            cpu.set_cc(initial_cc)
            cpu.get_and_call_next_op()
            b = initial_d & 0xff
            expected = (0xff00 | b) if b & 0x80 else b
            expected_nz = (0x08 if b & 0x80 else 0) | (0x04 if b == 0 else 0)
            expected_cc = (initial_cc & PRESERVED_MASK) | expected_nz
            actual_cc = cpu.get_cc_value() & CHECKED_MASK
            if (cpu.accu_d.value != expected or actual_cc != expected_cc
                    or cpu.program_counter.value != 0x2001):
                failures += 1
                if failures <= 5:
                    print(f"FAIL SEX initial D=0x{initial_d:04x} CC=0x{initial_cc:02x}: "
                          f"got D=0x{cpu.accu_d.value:04x} CC=0x{actual_cc:02x} "
                          f"PC=0x{cpu.program_counter.value:04x}; "
                          f"expected D=0x{expected:04x} CC=0x{expected_cc:02x} PC=0x2001")
    total = 65536 * len(INITIAL_CC)
    print(f"SEX opcode: {total - failures}/{total} passed")
    return int(failures != 0)


if __name__ == "__main__":
    sys.exit(main())
