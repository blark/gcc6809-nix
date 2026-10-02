#!/usr/bin/env python3
"""Check compiled low-byte products with a byte live across a function call.

--exhaustive checks every byte pair in four signedness combinations plus
three self-product functions at five optimization levels. Requires the
in-tree harness and SEX-corrected emulator.
"""

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_tests as harness
from run_signed_mul_review import Machine, check_emulator, command, signed

SOURCE = Path(__file__).resolve().parents[1] / "cases/mulqi3_narrow.c"
FUNCTIONS = {"narrow_ss": (True, True), "narrow_su": (True, False),
             "narrow_us": (False, True), "narrow_uu": (False, False)}
SQUARES = ("square_s", "square_u", "square_volatile")
EDGES = (0, 1, 2, 3, 127, 128, 129, 253, 254, 255)


def build(runner, opt):
    with tempfile.TemporaryDirectory(prefix="gcc6809-mulqi3-") as directory:
        tmp = Path(directory)
        assembly = tmp / "probe.s"
        command([str(runner.gcc), opt, "-std=c99", "-S", str(SOURCE),
                 "-o", str(assembly)], tmp)
        command([str(runner.asm), "-g", "-o", str(assembly)], tmp)
        command([str(runner.link), "-s", "-m", "-w", "-o", str(tmp / "probe.s19"),
                 "-b", ".text=0x2000", str(tmp / "probe.rel"), "-l", runner.libgcc], tmp)
        code = harness.parse_s19((tmp / "probe.s19").read_text())
        link_map = (tmp / "probe.map").read_text()
        entries = {}
        for name in (*FUNCTIONS, *SQUARES, "source_s", "source_u"):
            match = re.search(rf"^\s*([0-9A-Fa-f]+)\s+_{name}\b", link_map, re.M)
            if match is None:
                raise RuntimeError(f"Missing compiled symbol _{name}")
            entries[name] = int(match.group(1), 16)
        return code, entries


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
        for name, (signed_source, signed_factor) in FUNCTIONS.items():
            checked = failed = 0
            source_address = entries["source_s" if signed_source else "source_u"]
            for source in values:
                machine.memory._mem[source_address] = source
                for factor in values:
                    left = signed(source) if signed_source else source
                    right = signed(factor) if signed_factor else factor
                    expected = (left * right) & 255
                    checked += 1
                    try:
                        # Shared call checks Y/U preservation, S and canaries;
                        # QI results return in B, unlike the HI driver's X.
                        machine.call(entries[name], factor, source)
                        actual = machine.cpu.accu_b.value
                        if actual != expected:
                            raise RuntimeError(f"got {actual}, expected {expected}")
                        if machine.memory._mem[source_address] != source:
                            raise RuntimeError("volatile source changed")
                    except RuntimeError as error:
                        failed += 1
                        if failures + failed <= 12:
                            print(f"FAIL {opt} {name}({left}, {right}): {error}", flush=True)
            total += checked
            failures += failed
            print(f"{opt} {name}: {checked - failed}/{checked} passed", flush=True)
        for name in SQUARES:
            checked = failed = 0
            for value in values:
                machine.memory._mem[entries["source_s"]] = value
                checked += 1
                try:
                    machine.call(entries[name], value)
                    actual = machine.cpu.accu_b.value
                    expected = (value * value) & 255
                    if actual != expected:
                        raise RuntimeError(f"got {actual}, expected {expected}")
                    if machine.memory._mem[entries["source_s"]] != value:
                        raise RuntimeError("volatile source changed")
                except RuntimeError as error:
                    failed += 1
                    if failures + failed <= 12:
                        print(f"FAIL {opt} {name}({value}): {error}", flush=True)
            total += checked
            failures += failed
            print(f"{opt} {name}: {checked - failed}/{checked} passed", flush=True)
    print(f"Compiled low-byte multiplication: {total - failures}/{total} passed; "
          f"{failures} failures")
    return int(failures != 0)


if __name__ == "__main__":
    sys.exit(main())
