#!/usr/bin/env python3
"""Exhaustive raw SEX opcode check, independent of compiler/library output."""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_tests as harness


def main():
    cfg = harness.Config(harness.CFG_DICT)
    memory = harness.Memory64K(cfg)
    cpu = harness.CPU(memory, cfg)
    memory._mem[0x2000] = 0x1d  # SEX: sign-extend B into D, regardless of old A.
    failures = 0
    for initial_d in range(65536):
        cpu.accu_d.set(initial_d)
        cpu.program_counter.set(0x2000)
        cpu.set_cc(0)
        cpu.get_and_call_next_op()
        b = initial_d & 0xff
        expected = (0xff00 | b) if b & 0x80 else b
        expected_nz = (0x08 if b & 0x80 else 0) | (0x04 if b == 0 else 0)
        if (cpu.accu_d.value != expected or cpu.get_cc_value() & 0x0c != expected_nz
                or cpu.program_counter.value != 0x2001):
            failures += 1
            if failures <= 5:
                print(f"FAIL SEX D=0x{initial_d:04x}: got D=0x{cpu.accu_d.value:04x}, expected 0x{expected:04x}")
    print(f"SEX opcode: {65536 - failures}/65536 passed")
    return int(failures != 0)


if __name__ == "__main__":
    sys.exit(main())
