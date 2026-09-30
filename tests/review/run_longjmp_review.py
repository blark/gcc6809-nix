#!/usr/bin/env python3
"""Run the longjmp regressions plus an exhaustive ABI check of _longjmp.

The C cases live in tests/cases (longjmp_*.c) and are part of the normal
suite; this runner adds --exhaustive, which links the real _longjmp from
libc and executes it for every 16-bit val. Dependencies: the same Python
environment as tests/run_tests.py. See LONGJMP.md here for the history and
for building a libc without the fix to reproduce the baseline failure.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_tests as harness


HERE = Path(__file__).resolve().parent


def exhaustive_longjmp(runner):
    """Execute the linked library routine for all 65,536 16-bit val patterns.

    This is an assembly-level ABI test: supply an already-saved jmp_buf,
    then check X, Y, U, S, DP, CC and PC after longjmp. The C tests separately
    exercise setjmp saving contexts and compiler handling of returns-twice.
    """
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        source = tmp / "probe.s"
        source.write_text("\t.area .text\n\t.globl _main, _longjmp\n"
                          "_main:\n\tjmp _longjmp\n")
        subprocess.run([str(runner.asm), "-g", "-o", str(source)],
                       cwd=tmp, check=True, capture_output=True, text=True)
        subprocess.run([str(runner.link), "-s", "-m", "-w", "-o",
                        str(tmp / "probe.s19"), "-b", ".text=0x2000",
                        str(tmp / "probe.rel"), "-l", runner.libc],
                       cwd=tmp, check=True, capture_output=True, text=True)
        code = harness.parse_s19((tmp / "probe.s19").read_text())
        start = harness.parse_map_for_main((tmp / "probe.map").read_text())
        if start is None:
            raise RuntimeError("No _main in exhaustive test map")

    cfg = harness.Config(harness.CFG_DICT)
    memory = harness.Memory64K(cfg)
    cpu = harness.CPU(memory, cfg)
    for address, byte in code.items():
        memory._mem[address] = byte

    env, entry_sp, saved_sp, saved_pc = 0x1000, 0xe000, 0xd000, 0xfffc
    memory._mem[env - 1] = 0xa5
    memory._mem[env + 20] = 0x5a

    def word(address, value):
        memory._mem[address] = value >> 8
        memory._mem[address + 1] = value & 255

    failures = 0
    for value in range(65536):
        saved_y = value ^ 0x5678
        saved_u = value ^ 0x9abc
        saved_dp = value >> 8
        saved_cc = value & 255
        word(env + 4, saved_y)
        word(env + 6, saved_u)
        word(env + 8, saved_sp)
        word(env + 10, saved_pc)
        memory._mem[env + 12] = saved_dp
        memory._mem[env + 13] = saved_cc
        word(entry_sp + 2, value)
        cpu.index_x.set(env)
        cpu.index_y.set(0xaaaa)
        cpu.user_stack_pointer.set(0xbbbb)
        cpu.direct_page.set(0xcc)
        cpu.system_stack_pointer.set(entry_sp)
        cpu.set_cc(0)
        cpu.program_counter.set(start)
        for _ in range(40):
            if cpu.program_counter.value == saved_pc:
                break
            cpu.get_and_call_next_op()
        actual = (cpu.index_x.value, cpu.index_y.value,
                  cpu.user_stack_pointer.value, cpu.system_stack_pointer.value,
                  cpu.direct_page.value, cpu.get_cc_value(), cpu.program_counter.value,
                  memory._mem[env - 1], memory._mem[env + 20])
        expected = (value or 1, saved_y, saved_u, saved_sp, saved_dp, saved_cc,
                    saved_pc, 0xa5, 0x5a)
        if actual != expected:
            failures += 1
            if failures <= 5:
                print(f"longjmp val=0x{value:04x}: got {actual}, expected {expected}")
    print(f"Exhaustive longjmp: {65536 - failures}/65536 passed")
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--newlib", type=Path, help="override newlib prefix")
    parser.add_argument("--include-suite", action="store_true")
    parser.add_argument("--exhaustive", action="store_true")
    args = parser.parse_args()
    runner = harness.GCC6809TestRunner()
    if args.newlib:
        root = args.newlib.resolve() / "m6809-unknown-none"
        runner.libc = str(root / "lib/libc.a")
        runner.cflags = "-I" + str(root / "include")
    cases_dir = HERE.parent / "cases"
    cases = sorted(cases_dir.glob("*.c" if args.include_suite else "longjmp_*.c"))
    passed = failed = 0
    for case in cases:
        expected = harness.parse_expect(case.read_text())
        if expected is None:
            raise RuntimeError(f"Missing EXPECT: {case}")
        for opt in harness.OPT_LEVELS:
            try:
                actual = runner.compile_and_run(case, opt)
                ok = actual == expected
                print(f"{case.stem} {opt}: {'PASS' if ok else 'FAIL'} "
                      f"got {actual}, expected {expected}")
            except Exception as error:
                ok = False
                print(f"{case.stem} {opt}: ERROR {error}")
            passed += int(ok)
            failed += int(not ok)
    print(f"C regressions: {passed} passed, {failed} failed")
    if args.exhaustive:
        failed += exhaustive_longjmp(runner)
    return int(failed != 0)


if __name__ == "__main__":
    sys.exit(main())
