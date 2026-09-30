#!/usr/bin/env python3
"""Check linked libgcc bit helpers directly, without undefined C expressions.

Uses tests/run_tests.py's toolchain discovery and MC6809 environment.
See BIT_HELPERS.md for ABI details, zero behavior, and overshift limits.
"""

import argparse
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_tests as harness


SHIFTS = {
    16: ("_ashlhi3", "_lshrhi3", "_ashrhi3"),
    32: ("___ashlsi3", "___lshrsi3", "___ashrsi3"),
}
COUNTS = {16: ("___clzhi2", "___ctzhi2"),
          32: ("___clzsi2", "___ctzsi2")}
SYMBOLS = (*SHIFTS[16], *SHIFTS[32], *COUNTS[16], *COUNTS[32])


def edge_values(width):
    mask = (1 << width) - 1
    values = {0, mask, mask // 3, 2 * (mask // 3)}
    for bit in range(width):
        value = 1 << bit
        values.update((value, value - 1, (value + 1) & mask))
    rng = random.Random(6809 + width)
    values.update(rng.getrandbits(width) for _ in range(32))
    return sorted(values)


def shift_result(kind, value, count, width):
    mask = (1 << width) - 1
    if kind == 0:
        return (value << count) & mask if count < width else 0
    if kind == 1:
        return value >> count if count < width else 0
    signed = value - (1 << width) if value & (1 << (width - 1)) else value
    return (signed >> min(count, width)) & mask


def count_result(kind, value, width):
    if value:
        return width - value.bit_length() if kind == 0 else (value & -value).bit_length() - 1
    # Target-specific characterization, NOT a guarantee for __builtin_c[lt]z(0).
    return width if kind == 0 else {16: 0xffff, 32: 15}[width]


class Probe:
    SP = 0xe000
    OUT = 0x1200
    HALT = 0xfffc

    def __init__(self, runner):
        with tempfile.TemporaryDirectory(prefix="gcc6809-bits-") as directory:
            tmp = Path(directory)
            source = tmp / "probe.s"
            text = ["\t.area .text", "\t.globl _main, _abort, __exit", "_main:"]
            for index, symbol in enumerate(SYMBOLS):
                text += [f"\t.globl {symbol}, _probe{index}",
                         f"_probe{index}:", f"\tjmp {symbol}"]
            # A library abort is deliberately not the successful return sentinel.
            text += ["_abort:", "__exit:", "\tbra _abort"]
            source.write_text("\n".join(text) + "\n")
            self.command([str(runner.asm), "-g", "-o", str(source)], tmp)
            self.command([str(runner.link), "-s", "-m", "-w", "-o",
                          str(tmp / "probe.s19"), "-b", ".text=0x2000",
                          str(tmp / "probe.rel"), "-l", runner.libgcc], tmp)
            code = harness.parse_s19((tmp / "probe.s19").read_text())
            link_map = (tmp / "probe.map").read_text()
            self.entries = {}
            for index, symbol in enumerate(SYMBOLS):
                match = re.search(rf"^\s*([0-9A-Fa-f]+)\s+_probe{index}\b", link_map, re.M)
                if match is None:
                    raise RuntimeError(f"Missing linked probe for {symbol}")
                self.entries[symbol] = int(match.group(1), 16)
        cfg = harness.Config(harness.CFG_DICT)
        self.memory = harness.Memory64K(cfg)
        self.cpu = harness.CPU(self.memory, cfg)
        self.mem = self.memory._mem
        for address, byte in code.items():
            self.mem[address] = byte
        self.checked = self.failed = 0

    @staticmethod
    def command(command, cwd):
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=600)
        if result.returncode:
            raise RuntimeError(f"{command[0]} failed:\n{result.stdout}{result.stderr}")

    def put(self, address, value, size=2):
        for offset, byte in enumerate(value.to_bytes(size, "big")):
            self.mem[address + offset] = byte

    def call(self, symbol, value, width, count=None):
        cpu = self.cpu
        saved_y = (value ^ 0x5678) & 0xffff
        saved_u = (value ^ 0x9abc) & 0xffff
        cpu.index_y.set(saved_y)
        cpu.user_stack_pointer.set(saved_u)
        cpu.direct_page.set(0)  # Compiler-generated code assumes the normal direct page.
        cpu.set_cc(0)
        cpu.accu_d.set(0xa55a)
        cpu.index_x.set(0xaaaa)
        cpu.system_stack_pointer.set(self.SP)
        cpu.program_counter.set(self.entries[symbol])
        self.put(self.SP, self.HALT)
        self.put(self.SP + 2, value, width // 8)
        self.put(self.SP + 6, count or 0)
        self.put(self.OUT, 0xa55a5aa5, 4)
        guards = {self.OUT - 1: 0xa5, self.OUT + 4: 0x5a,
                  self.SP - 256: 0x69, self.SP + 8: 0x96}
        for address, byte in guards.items():
            self.mem[address] = byte
        if count is None:
            if width == 16:
                cpu.index_x.set(value)
        elif width == 16:
            cpu.accu_d.set(value)
            cpu.index_x.set(count)
        else:
            cpu.index_x.set(self.OUT)  # Hidden 32-bit return buffer.

        budget = 8 * count + 512 if count is not None and width == 16 else 4096
        for _ in range(budget):
            if cpu.program_counter.value == self.HALT:
                break
            try:
                cpu.get_and_call_next_op()
            except (Exception, SystemExit) as error:
                raise RuntimeError(f"CPU error at ${cpu.program_counter.value:04x}: {error}") from error
        else:
            raise RuntimeError(f"did not return within {budget} instructions")

        actual_abi = (cpu.index_y.value, cpu.user_stack_pointer.value,
                      cpu.system_stack_pointer.value, cpu.program_counter.value,
                      tuple(self.mem[address] for address in guards))
        expected_abi = (saved_y, saved_u, self.SP + 2, self.HALT, tuple(guards.values()))
        if actual_abi != expected_abi:
            raise RuntimeError(f"ABI/canary mismatch: {actual_abi} != {expected_abi}")
        if count is None:
            return cpu.index_x.value
        if width == 16:
            if cpu.index_x.value != count:
                raise RuntimeError("16-bit shift helper did not preserve X/count")
            return cpu.accu_d.value
        return int.from_bytes(self.mem[self.OUT:self.OUT + 4], "big")

    def check(self, symbol, value, width, expected, count=None):
        self.checked += 1
        try:
            actual = self.call(symbol, value, width, count)
            if actual != expected:
                raise RuntimeError(f"got 0x{actual:x}, expected 0x{expected:x}")
        except RuntimeError as error:
            self.failed += 1
            if self.failed <= 20:
                print(f"FAIL {symbol} value=0x{value:0{width // 4}x} count={count}: {error}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exhaustive", action="store_true",
                        help="all 16-bit count inputs; shift inputs at counts 0/15/16; 32-bit count half-word sweeps")
    parser.add_argument("--characterize-overshifts", action="store_true",
                        help="report out-of-contract 32-bit shift values without asserting numeric results")
    args = parser.parse_args()
    runner = harness.GCC6809TestRunner()
    probe = Probe(runner)
    print(f"Linked library: {runner.libgcc}")
    for width in (16, 32):
        for value in edge_values(width):
            for kind, symbol in enumerate(COUNTS[width]):
                probe.check(symbol, value, width, count_result(kind, value, width))
            counts = list(range(width))
            if width == 16:
                counts += [16, 17, 31, 32, 33, 63, 255, 256, 257]
            for count in counts:
                for kind, symbol in enumerate(SHIFTS[width]):
                    probe.check(symbol, value, width, shift_result(kind, value, count, width), count)
        print(f"{width}-bit edge matrix complete: {probe.checked} checks, {probe.failed} failures", flush=True)
    # Include the complete 16-bit count register, not just an 8-bit count.
    for count in (0x7fff, 0x8000, 0xffff):
        for value in (0x7fff, 0x8001):
            for kind, symbol in enumerate(SHIFTS[16]):
                probe.check(symbol, value, 16, shift_result(kind, value, count, 16), count)
    if args.exhaustive:
        for value in range(65536):
            for kind, symbol in enumerate(COUNTS[16]):
                probe.check(symbol, value, 16, count_result(kind, value, 16))
            for count in (0, 15, 16):
                for kind, symbol in enumerate(SHIFTS[16]):
                    probe.check(symbol, value, 16, shift_result(kind, value, count, 16), count)
            for wide_value in (value, value << 16):
                for kind, symbol in enumerate(COUNTS[32]):
                    probe.check(symbol, wide_value, 32, count_result(kind, wide_value, 32))
        print("Exhaustive sweeps complete", flush=True)
    if args.characterize_overshifts:
        for count in (32, 33, 48, 63):
            values = []
            for symbol in SHIFTS[32]:
                # No numeric oracle: libgcc2.c uses out-of-range C shifts here.
                values.append(f"{symbol}=0x{probe.call(symbol, 0x89abcdef, 32, count):08x}")
            print(f"OUT-OF-CONTRACT 32-bit count={count}: " + ", ".join(values))
    print(f"Bit helper checks: {probe.checked - probe.failed}/{probe.checked} passed")
    return int(probe.failed != 0)


if __name__ == "__main__":
    sys.exit(main())
