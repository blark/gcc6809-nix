#!/usr/bin/env python3
"""Broad check of the multiply helpers in libgcc1.s: ___mulsi3 and _mulhi3.

Links the real helpers from libgcc.a and calls them the way GCC does.
___mulsi3: both 32-bit operands on the stack (big-endian words, the
second operand at 2,s and the first at 6,s), a pointer to the 4-byte
result area in X, the caller pops the arguments.  _mulhi3: left operand
in X, right operand at 2,s, product in X.  Expected results come from
Python ((u * v) mod 2^32 or 2^16) so wraparound is defined and
independent of the code under test.  Every call also checks the stack
pointer, the Y/U/DP canaries and guard bytes around the result area.
Dependencies: the same Python environment as tests/run_tests.py.
See MULSI3.md here for the helper contract and results.

    run_mulsi3_review.py [--jobs N] [--random N] [--seed S] [--quick]
"""

import argparse
import multiprocessing
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_tests as harness


HELPERS = ("___mulsi3", "_mulhi3")
M32 = 0xFFFFFFFF
M16 = 0xFFFF

# Operands for the all-pairs edge grid through ___mulsi3.
EDGE32 = [0, 1, 2, 3, 0x7F, 0x80, 0x81, 0xFF, 0x100, 0x101, 0x7FFF, 0x8000,
          0x8001, 0xFFFF, 0x10000, 0x10001, 0x7FFFFF, 0x800000, 0xFFFFFF,
          0x1000000, 0x1000001, 0x40000000, 0x7FFFFFFF, 0x80000000,
          0x80000001, 0xBFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFF, 0x00FF00FF,
          0xFF00FF00, 0x01010101, 0x80808080, 0x0000FFFF, 0xFFFF0000,
          0x00FFFF00, 0xFF0000FF, 0x55555555, 0xAAAAAAAA, 0xDEADBEEF,
          0xCAFEBABE, 0x12345678, 0x9ABCDEF0, 46341, 65537, 0x24924925]

# Right operands for the exhaustive left-operand sweep through _mulhi3.
MULHI_RIGHT = [1, 2, 3, 0x7F, 0xFF, 0x100, 0x101, 0x7FFF, 0x8000, 0x8001,
               0xFFFE, 0xFFFF, 0x5555, 0xAAAA, 0x1234, 46341]
QUICK_MULHI_RIGHT = [3, 0x101, 0x8000, 0xFFFF]

HALT = 0xFFFC       # BRA -2 loop, like the harness's return address
ENTRY_SP = 0xE000
SRET = 0xD000       # result area for ___mulsi3; guard bytes on both sides
GUARD = 8
GUARD_BYTE = 0xA5
MAX_OPS = 1000      # ___mulsi3 takes about 130 instructions


def build_probe(runner):
    """Link a jump table to the helpers; return (code, entry addresses)."""
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        source = tmp / "probe.s"
        lines = ["\t.area .text", "\t.globl _main, " + ", ".join(HELPERS),
                 "\t.globl " + ", ".join(f"call{h}" for h in HELPERS), "_main:"]
        for helper in HELPERS:
            lines += [f"call{helper}:", f"\tjmp {helper}"]
        lines.append("")
        source.write_text("\n".join(lines))
        subprocess.run([str(runner.asm), "-g", "-o", str(source)],
                       cwd=tmp, check=True, capture_output=True, text=True)
        subprocess.run([str(runner.link), "-s", "-m", "-w", "-o",
                        str(tmp / "probe.s19"), "-b", ".text=0x2000",
                        str(tmp / "probe.rel"), "-l", runner.libgcc],
                       cwd=tmp, check=True, capture_output=True, text=True)
        code = harness.parse_s19((tmp / "probe.s19").read_text())
        symbols = {}
        for line in (tmp / "probe.map").read_text().splitlines():
            match = re.match(r"\s*([0-9A-Fa-f]{4})\s+(\S+)", line)
            if match:
                symbols[match.group(2)] = int(match.group(1), 16)
    return code, {h: symbols[f"call{h}"] for h in HELPERS}


class Machine:
    """One emulator instance with the probe loaded."""

    def __init__(self, code):
        cfg = harness.Config(harness.CFG_DICT)
        self.memory = harness.Memory64K(cfg)
        self.cpu = harness.CPU(self.memory, cfg)
        for address, byte in code.items():
            self.memory._mem[address] = byte
        self.memory._mem[HALT] = 0x20
        self.memory._mem[HALT + 1] = 0xFE

    def word(self, address, value=None):
        mem = self.memory._mem
        if value is None:
            return (mem[address] << 8) | mem[address + 1]
        mem[address] = (value >> 8) & 0xFF
        mem[address + 1] = value & 0xFF

    def run(self, entry, x, d, stack_words):
        """Call ENTRY with X, D and STACK_WORDS above the return address.

        Y, U and DP hold canaries derived from the operands so a clobber
        is caught.  Returns (stopped, X, D, S, regs_ok, ops).
        """
        cpu = self.cpu
        canary_y = (x ^ 0x5A5A) & M16
        canary_u = (stack_words[0] ^ 0xA5A5) & M16
        canary_dp = (x >> 8) ^ 0x3C
        self.word(ENTRY_SP, HALT)
        for i, value in enumerate(stack_words):
            self.word(ENTRY_SP + 2 + 2 * i, value & M16)
        cpu.index_x.set(x & M16)
        cpu.accu_d.set(d & M16)
        cpu.index_y.set(canary_y)
        cpu.user_stack_pointer.set(canary_u)
        cpu.direct_page.set(canary_dp)
        cpu.system_stack_pointer.set(ENTRY_SP)
        cpu.set_cc(0)
        cpu.program_counter.set(entry)
        ops = 0
        while cpu.program_counter.value != HALT:
            if ops >= MAX_OPS:
                break
            cpu.get_and_call_next_op()
            ops += 1
        stopped = "halt" if cpu.program_counter.value == HALT else "timeout"
        regs_ok = (cpu.index_y.value == canary_y
                   and cpu.user_stack_pointer.value == canary_u
                   and cpu.direct_page.value == canary_dp)
        return (stopped, cpu.index_x.value, cpu.accu_d.value,
                cpu.system_stack_pointer.value, regs_ok, ops)

    def check_mulsi3(self, entry, u, v):
        """Call ___mulsi3(u, v) as GCC does; None if it met the contract."""
        mem = self.memory._mem
        for i in range(SRET - GUARD, SRET + 4 + GUARD):
            mem[i] = GUARD_BYTE
        # GCC pushes u first, then v: v's high word lands at 2,s, u's at 6,s
        stopped, x, _d, s, regs_ok, ops = self.run(
            entry, SRET, 0x1234, [v >> 16, v & M16, u >> 16, u & M16])
        if stopped != "halt":
            return f"{stopped} after {ops} ops"
        got = (self.word(SRET) << 16) | self.word(SRET + 2)
        want = (u * v) & M32
        problems = []
        if got != want:
            problems.append(f"result 0x{got:08x} want 0x{want:08x}")
        if s != ENTRY_SP + 2:
            problems.append(f"S=0x{s:04x} want 0x{ENTRY_SP + 2:04x}")
        if x != SRET:
            problems.append(f"X=0x{x:04x} want sret 0x{SRET:04x}")
        if not regs_ok:
            problems.append("Y/U/DP clobbered")
        if any(mem[i] != GUARD_BYTE for i in range(SRET - GUARD, SRET)) or \
           any(mem[i] != GUARD_BYTE for i in range(SRET + 4, SRET + 4 + GUARD)):
            problems.append("wrote outside the 4-byte result area")
        return "; ".join(problems) or None

    def check_mulhi3(self, entry, left, right):
        """Call _mulhi3 (left in X, right at 2,s); None if it met the contract."""
        stopped, x, _d, s, regs_ok, ops = self.run(entry, left, 0x1234, [right])
        if stopped != "halt":
            return f"{stopped} after {ops} ops"
        want = (left * right) & M16
        problems = []
        if x != want:
            problems.append(f"X=0x{x:04x} want 0x{want:04x}")
        if s != ENTRY_SP + 2:
            problems.append(f"S=0x{s:04x} want 0x{ENTRY_SP + 2:04x}")
        if not regs_ok:
            problems.append("Y/U/DP clobbered")
        return "; ".join(problems) or None


def job(args):
    """Worker: run one named batch of operand pairs; return failures."""
    code, entries, name, helper, pairs = args
    machine = Machine(code)
    check = machine.check_mulsi3 if helper == "___mulsi3" else machine.check_mulhi3
    failures = []
    for u, v in pairs:
        problem = check(entries[helper], u, v)
        if problem:
            failures.append((u, v, problem))
    return name, helper, len(pairs), failures


def report(name, helper, total, failures):
    width = 8 if helper == "___mulsi3" else 4
    for u, v, problem in failures[:5]:
        print(f"  {name} 0x{u:0{width}x} * 0x{v:0{width}x}: {problem}")
    print(f"{name}: {total - len(failures)}/{total} passed")
    return len(failures)


def byte_position_pairs(i, j):
    """Every byte value at byte I of u times every byte value at byte J of v."""
    return [(bu << (8 * i), bv << (8 * j)) for bu in range(256) for bv in range(256)]


def random_pairs(rng, count):
    """Uniform 32-bit pairs; every other pair has random bytes cleared."""
    pairs = []
    for n in range(count):
        u, v = rng.getrandbits(32), rng.getrandbits(32)
        if n & 1:
            u &= rng.getrandbits(32) | rng.getrandbits(32)
            v &= sum(0xFF << (8 * k) for k in range(4) if rng.getrandbits(1))
        pairs.append((u, v))
    return pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--jobs", type=int, default=multiprocessing.cpu_count())
    parser.add_argument("--random", type=int, default=200000,
                        help="random ___mulsi3 pairs (default 200000)")
    parser.add_argument("--seed", type=int, default=6809)
    parser.add_argument("--quick", action="store_true",
                        help="edge grid, byte positions (0,0) and (3,3), fewer random pairs")
    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)  # progress through a pipe

    runner = harness.GCC6809TestRunner()
    code, entries = build_probe(runner)
    print(f"libgcc: {runner.libgcc}")

    rng = random.Random(args.seed)
    n_random = 5000 if args.quick else args.random
    positions = [(0, 0), (3, 3)] if args.quick else [(i, j) for i in range(4) for j in range(4)]
    mulhi_right = QUICK_MULHI_RIGHT if args.quick else MULHI_RIGHT

    jobs = [(code, entries, "___mulsi3 edge grid", "___mulsi3",
             [(u, v) for u in EDGE32 for v in EDGE32])]
    jobs += [(code, entries, f"___mulsi3 byte {i} x byte {j}", "___mulsi3",
              byte_position_pairs(i, j)) for i, j in positions]
    chunk = max(1, n_random // args.jobs + 1)
    pairs = random_pairs(rng, n_random)
    jobs += [(code, entries, f"___mulsi3 random {k}", "___mulsi3", pairs[k:k + chunk])
             for k in range(0, n_random, chunk)]
    jobs += [(code, entries, f"_mulhi3 right=0x{right:04x}", "_mulhi3",
              [(left, right) for left in range(65536)]) for right in mulhi_right]
    jobs.append((code, entries, "_mulhi3 random", "_mulhi3",
                 [(rng.getrandbits(16), rng.getrandbits(16))
                  for _ in range(5000 if args.quick else 100000)]))

    total = sum(len(j[4]) for j in jobs)
    print(f"{len(jobs)} batches, {total} helper calls on {args.jobs} processes")
    failed = 0
    with multiprocessing.Pool(args.jobs) as pool:
        for name, helper, count, failures in pool.imap_unordered(job, jobs):
            failed += report(name, helper, count, failures)
    print(f"Multiply helpers: {'FAIL' if failed else 'PASS'} ({failed} failures)")
    return int(failed != 0)


if __name__ == "__main__":
    sys.exit(main())
