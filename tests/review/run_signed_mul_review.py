#!/usr/bin/env python3
"""Compile and execute byte multiplication functions against a host oracle.

Default: edge inputs, all GCC6809_OPT levels (or five standard levels).
--exhaustive: all 256 x 256 byte pairs in four signedness combinations,
plus all 256 inputs for multiplication by 3, -3, 255 and 256.
Requires the SEX-corrected MC6809 emulator; never patches the CPU at runtime.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_tests as harness

SOURCE = Path(__file__).resolve().parents[1] / "cases/mulqihi3_signed.c"
BINARY = {"mulqi_ss": (True, True), "mulqi_su": (True, False),
          "mulqi_us": (False, True), "mulqi_uu": (False, False)}
CONSTANT = {"mulqi_3": 3, "mulqi_neg3": -3, "mulqi_255": 255, "mulqi_256": 256}
EDGES = (0, 1, 2, 3, 127, 128, 129, 253, 254, 255)


def signed(byte):
    return byte - 256 if byte & 128 else byte


def command(args, cwd):
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=600)
    if proc.returncode:
        raise RuntimeError(f"{args[0]} failed:\n{proc.stdout}{proc.stderr}")


def build(runner, opt):
    with tempfile.TemporaryDirectory(prefix="gcc6809-signed-mul-") as directory:
        tmp = Path(directory)
        assembly = tmp / "probe.s"
        command([str(runner.gcc), opt, "-std=c99", "-S", str(SOURCE), "-o", str(assembly)], tmp)
        command([str(runner.asm), "-g", "-o", str(assembly)], tmp)
        command([str(runner.link), "-s", "-m", "-w", "-o", str(tmp / "probe.s19"),
                 "-b", ".text=0x2000", str(tmp / "probe.rel"), "-l", runner.libgcc], tmp)
        code = harness.parse_s19((tmp / "probe.s19").read_text())
        link_map = (tmp / "probe.map").read_text()
        entries = {}
        for name in (*BINARY, *CONSTANT):
            match = re.search(rf"^\s*([0-9A-Fa-f]+)\s+_{name}\b", link_map, re.M)
            if match is None:
                raise RuntimeError(f"Missing compiled function _{name}")
            entries[name] = int(match.group(1), 16)
        return code, entries


class Machine:
    SP = 0xe000
    HALT = 0xfffc

    def __init__(self, code):
        cfg = harness.Config(harness.CFG_DICT)
        self.memory = harness.Memory64K(cfg)
        self.cpu = harness.CPU(self.memory, cfg)
        for address, value in code.items():
            self.memory._mem[address] = value

    def call(self, entry, a, b=0):
        cpu, mem = self.cpu, self.memory._mem
        y, u = 0x5600 | a, 0x9a00 | b
        cpu.index_y.set(y)
        cpu.user_stack_pointer.set(u)
        cpu.index_x.set(0xa55a)
        cpu.accu_d.set(0x5a00 | a)  # First byte argument in B; A is unspecified.
        cpu.direct_page.set(0)
        cpu.set_cc(0)
        cpu.system_stack_pointer.set(self.SP)
        cpu.program_counter.set(entry)
        mem[self.SP], mem[self.SP + 1] = self.HALT >> 8, self.HALT & 255
        mem[self.SP + 2] = b  # Second byte argument, not a 16-bit stack slot.
        mem[self.SP + 3], mem[self.SP - 256] = 0x69, 0x96
        for _ in range(512):
            if cpu.program_counter.value == self.HALT:
                break
            try:
                cpu.get_and_call_next_op()
            except (Exception, SystemExit) as error:
                raise RuntimeError(f"CPU error at ${cpu.program_counter.value:04x}: {error}") from error
        else:
            raise RuntimeError("compiled function did not return within 512 instructions")
        got = (cpu.index_y.value, cpu.user_stack_pointer.value,
               cpu.system_stack_pointer.value, mem[self.SP + 3], mem[self.SP - 256])
        if got != (y, u, self.SP + 2, 0x69, 0x96):
            raise RuntimeError(f"callee-save/stack-canary mismatch: {got}")
        return cpu.index_x.value


def check_emulator():
    machine = Machine({0x2000: 0x1d})  # SEX, without any compiler output.
    for before in (0x0080, 0x00ff, 0xff01, 0xff00):
        cpu = machine.cpu
        cpu.accu_d.set(before)
        cpu.program_counter.set(0x2000)
        cpu.get_and_call_next_op()
        if cpu.accu_d.value != signed(before & 255) & 0xffff:
            raise RuntimeError("MC6809 SEX is broken; use the gcc6809-877 emulator fix first")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exhaustive", action="store_true")
    args = parser.parse_args()
    check_emulator()
    runner = harness.GCC6809TestRunner()
    levels = os.environ.get("GCC6809_OPT", "-O0 -O1 -O2 -O3 -Os").split()
    if not levels:
        parser.error("GCC6809_OPT must contain at least one optimization level")
    values = range(256) if args.exhaustive else EDGES
    total = failures = 0
    print(f"Compiler: {runner.gcc}", flush=True)
    for opt in levels:
        code, entries = build(runner, opt)
        machine = Machine(code)
        for name in (*BINARY, *CONSTANT):
            checked = failed = 0
            for a in values:
                for b in values if name in BINARY else (0,):
                    if name in BINARY:
                        sign_a, sign_b = BINARY[name]
                        left, right = signed(a) if sign_a else a, signed(b) if sign_b else b
                    else:
                        left, right = signed(a), CONSTANT[name]
                    expected = (left * right) & 0xffff
                    checked += 1
                    try:
                        actual = machine.call(entries[name], a, b)
                        if actual != expected:
                            raise RuntimeError(f"got 0x{actual:04x}, expected 0x{expected:04x}")
                    except RuntimeError as error:
                        failed += 1
                        if failures + failed <= 12:
                            print(f"FAIL {opt} {name}({left}, {right}): {error}", flush=True)
            total += checked
            failures += failed
            print(f"{opt} {name}: {checked - failed}/{checked} passed", flush=True)
    print(f"Compiled byte multiplication: {total - failures}/{total} passed; {failures} failures")
    return int(failures != 0)


if __name__ == "__main__":
    sys.exit(main())
