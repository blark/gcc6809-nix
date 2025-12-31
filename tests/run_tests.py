#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "MC6809>=0.8.0",
# ]
# ///
"""
GCC6809 Test Runner

Discovers and runs .c test files against the MC6809 emulator.

Usage:
    nix develop --command uv run tests/run_tests.py [pattern]

Test files should contain an EXPECT comment:
    // EXPECT: 42
"""

import array
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from MC6809.components.cpu6809 import CPU
from MC6809.components.memory import Memory
from MC6809.core.configs import BaseConfig


CFG_DICT = {"verbosity": None, "trace": None}


class Config(BaseConfig):
    """Full 64KB RAM, no ROM"""
    RAM_START = 0x0000
    RAM_END = 0xFFFF
    ROM_START = 0xFFFF
    ROM_END = 0x0000


class Memory64K(Memory):
    """Memory subclass that allows full 64KB address space"""

    def __init__(self, cfg, **kwargs):
        self.cfg = cfg
        self.read_bus_request_queue = kwargs.get('read_bus_request_queue')
        self.read_bus_response_queue = kwargs.get('read_bus_response_queue')
        self.write_bus_queue = kwargs.get('write_bus_queue')

        self.INTERNAL_SIZE = 0x10000
        self.RAM_SIZE = self.INTERNAL_SIZE
        self.ROM_SIZE = 0

        self._mem = array.array("B", [0x00] * self.INTERNAL_SIZE)

        self._read_byte_callbacks = {}
        self._read_word_callbacks = {}
        self._write_byte_callbacks = {}
        self._write_word_callbacks = {}
        self._read_byte_middleware = {}
        self._write_byte_middleware = {}
        self._read_word_middleware = {}
        self._write_word_middleware = {}


def parse_s19(s19_content: str) -> dict[int, int]:
    """Parse Motorola S-record (S19) format"""
    memory = {}
    for line in s19_content.strip().split('\n'):
        line = line.strip()
        if line.startswith('S1'):
            byte_count = int(line[2:4], 16)
            address = int(line[4:8], 16)
            data_hex = line[8:8 + (byte_count - 3) * 2]
            for i in range(0, len(data_hex), 2):
                memory[address] = int(data_hex[i:i+2], 16)
                address += 1
    return memory


def parse_map_for_main(map_content: str) -> int | None:
    """Parse linker map file to find _main address"""
    for line in map_content.split('\n'):
        match = re.search(r'^\s*([0-9A-Fa-f]+)\s+_main\b', line)
        if match:
            return int(match.group(1), 16)
    return None


def parse_expect(c_source: str) -> int | None:
    """Parse EXPECT comment from C source"""
    match = re.search(r'//\s*EXPECT:\s*(-?\d+)', c_source)
    if match:
        return int(match.group(1))
    return None


def find_toolchain() -> Path | None:
    """Find the gcc6809 toolchain"""
    result = Path(__file__).parent.parent / "result"
    if result.exists():
        return result
    try:
        proc = subprocess.run(["which", "m6809-unknown-none-gcc"],
                              capture_output=True, text=True)
        if proc.returncode == 0:
            return Path(proc.stdout.strip()).parent.parent
    except Exception:
        pass
    return None


class GCC6809TestRunner:
    """Compiles and runs tests on the MC6809 emulator"""

    def __init__(self):
        self.toolchain = find_toolchain()
        if not self.toolchain:
            raise RuntimeError("Could not find gcc6809 toolchain")

        self.gcc = self.toolchain / "bin" / "m6809-unknown-none-gcc"
        self.asm = self.toolchain / "bin" / "as6809"
        self.link = self.toolchain / "bin" / "aslink"
        self.libc = os.environ.get("M6809_LIBC",
            str(self.toolchain / "m6809-unknown-none" / "lib" / "libc.a"))
        self.libgcc = str(self.toolchain / "lib" / "gcc" / "m6809-unknown-none" / "4.3.6" / "libgcc.a")
        self.cflags = os.environ.get("M6809_CFLAGS",
            "-I" + str(self.toolchain / "m6809-unknown-none" / "include"))

    def compile_and_run(self, c_file: Path, text_addr: int = 0x2000) -> int:
        """Compile C file and run on emulator, return result"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            s_file = tmpdir / "test.s"
            rel_file = tmpdir / "test.rel"
            s19_file = tmpdir / "test.s19"
            map_file = tmpdir / "test.map"

            # Compile
            result = subprocess.run([
                str(self.gcc), "-Os", "-std=c99", "-S",
                *self.cflags.split(), str(c_file), "-o", str(s_file)
            ], capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Compile failed:\n{result.stderr}")

            # Assemble (-g makes undefined symbols global for link-time resolution)
            result = subprocess.run(
                [str(self.asm), "-g", "-o", str(s_file)],
                capture_output=True, text=True, cwd=tmpdir)
            if result.returncode != 0:
                raise RuntimeError(f"Assemble failed:\n{result.stderr}")

            # Link (with libc and libgcc)
            result = subprocess.run([
                str(self.link), "-s", "-m", "-w",
                "-o", str(s19_file), "-b", f".text={hex(text_addr)}",
                str(rel_file), "-l", self.libc, "-l", self.libgcc
            ], capture_output=True, text=True, cwd=tmpdir)
            if result.returncode != 0:
                raise RuntimeError(f"Link failed:\n{result.stderr}")

            # Parse output
            memory_map = parse_s19(s19_file.read_text())
            if not memory_map:
                raise RuntimeError("No code generated")

            main_addr = None
            if map_file.exists():
                main_addr = parse_map_for_main(map_file.read_text())
            if main_addr is None:
                main_addr = min(memory_map.keys())

            return self._run_emulator(memory_map, main_addr)

    def _run_emulator(self, memory_map: dict[int, int], start: int) -> int:
        """Run code on MC6809 emulator"""
        cfg = Config(CFG_DICT)
        memory = Memory64K(cfg)
        cpu = CPU(memory, cfg)

        # Load program
        for addr, byte in memory_map.items():
            memory._mem[addr] = byte

        # Halt loop at 0xFFFC: BRA -2
        halt_addr = 0xFFFC
        memory._mem[halt_addr] = 0x20
        memory._mem[halt_addr + 1] = 0xFE

        # Push return address onto stack
        sp = 0xFFF0
        sp -= 1
        memory._mem[sp] = halt_addr & 0xFF
        sp -= 1
        memory._mem[sp] = (halt_addr >> 8) & 0xFF

        cpu.system_stack_pointer.set(sp)
        cpu.user_stack_pointer.set(0xFEF0)
        cpu.program_counter.set(start)

        # Execute with crash detection
        max_ops = 100000
        for ops in range(max_ops):
            if cpu.program_counter.value == halt_addr:
                break

            try:
                cpu.get_and_call_next_op()
            except SystemExit as e:
                # MC6809 calls sys.exit() on unknown opcodes
                raise RuntimeError(f"CPU crash: {e}")
            except Exception as e:
                raise RuntimeError(f"CPU exception at ${cpu.program_counter.value:04X}: {e}")

        if ops >= max_ops - 1:
            raise RuntimeError(f"Timeout after {max_ops} ops")

        return cpu.index_x.value


def discover_tests(cases_dir: Path, pattern: str = "*") -> list[Path]:
    """Discover .c test files"""
    files = sorted(cases_dir.glob("*.c"))
    if pattern != "*":
        files = [f for f in files if pattern in f.stem]
    return files


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else "*"
    cases_dir = Path(__file__).parent / "cases"

    if not cases_dir.exists():
        print(f"Error: {cases_dir} not found")
        sys.exit(1)

    print("GCC6809 Test Runner")
    print("=" * 50)

    try:
        runner = GCC6809TestRunner()
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    test_files = discover_tests(cases_dir, pattern)
    if not test_files:
        print(f"No tests found matching '{pattern}'")
        sys.exit(1)

    passed = 0
    failed = 0

    for test_file in test_files:
        c_source = test_file.read_text()
        expected = parse_expect(c_source)

        if expected is None:
            print(f"\n[SKIP] {test_file.stem}: no EXPECT comment")
            continue

        print(f"\n[TEST] {test_file.stem}")

        try:
            result = runner.compile_and_run(test_file)
            if result == expected:
                print(f"  PASS: {result}")
                passed += 1
            else:
                print(f"  FAIL: expected {expected}, got {result}")
                failed += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

    print("\n" + "=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
