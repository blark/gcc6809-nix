#!/usr/bin/env python3
"""Compile a C program with the default GCC driver and execute installed crt0.o."""
import array
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_tests as harness

PROBE = r'''
#include <stdlib.h>
int supplied_argc __asm__ ("__argc") = 2;
char *supplied_argv[] __asm__ ("__argv") = {"one", "two", 0};
volatile unsigned int data_value = 0x1234;
volatile unsigned char zeroed[8];
volatile unsigned int ctor_seen, main_seen, atexit_seen, dtor_seen;
volatile unsigned int main_dtor_seen, goodbye_dtor_seen;
volatile unsigned int observed_argc, observed_argv, observed_sp;
static void goodbye(void) { goodbye_dtor_seen = dtor_seen; atexit_seen = 0x55; }
static void construct(void) __attribute__((constructor));
static void destruct(void) __attribute__((destructor));
static void construct(void) { ctor_seen = 0x11; }
static void destruct(void) { dtor_seen = 0x33; }
int main(int argc, char **argv) {
    unsigned int i;
    __asm__ volatile("tfr s,d\n\tstd _observed_sp");
    observed_argc = argc;
    observed_argv = (unsigned int)argv;
    main_seen = ctor_seen;
    main_dtor_seen = dtor_seen;
    for (i = 0; i < 8; ++i) if (zeroed[i] != 0) return 80 + i;
    if (data_value != 0x1234) return 90;
    if (atexit(goodbye)) return 91;
    if (argc != 2 || !argv || !argv[0] || !argv[1] || argv[2]
        || argv[0][0] != 'o' || argv[1][0] != 't') return 92;
    return 37;
}
'''
HALT = 0xfffc


def build(runner):
    crt0 = runner.toolchain / 'lib/gcc/m6809-unknown-none/4.3.6/crt0.o'
    if not crt0.is_file():
        raise RuntimeError(f'installed GCC crt0.o missing: {crt0}')
    with tempfile.TemporaryDirectory(prefix='gcc6809-crt0-installed-') as directory:
        tmp = Path(directory)
        src, image, link_map = (tmp / 'probe.c', tmp / 'probe.s19', tmp / 'probe.map')
        src.write_text(PROBE)
        # -L works around the separately filed, pre-existing symlinkJoin
        # driver search-path bug. Do not pass crt0.o or a custom entry point.
        command = [str(runner.gcc), '-O0', '-std=c99',
                   f'-I{runner.toolchain}/m6809-unknown-none/include',
                   f'-L{runner.toolchain}/m6809-unknown-none/lib',
                   str(src), '-Wl,--args', '-Wl,--map', '-o', str(image)]
        result = subprocess.run(command, cwd=tmp, capture_output=True, text=True, timeout=600)
        if result.returncode:
            raise RuntimeError(f'default GCC link failed: {result.stdout}{result.stderr}')
        record = image.read_text()
        match = re.search(r'^S903([0-9A-Fa-f]{4})', record, re.M)
        if not match:
            raise RuntimeError('linked image has no S9 entry point')
        map_text = link_map.read_text()
        symbols = {name: int(addr, 16) for addr, name in
                   re.findall(r'^\s*([0-9A-Fa-f]+)\s+([_sl][A-Za-z0-9_.]+)\b',
                              map_text, re.M)}
        for name in ('__start', '__exit', '__argc', '__argv', '__stack_ptr',
                     '_memset', 's_.bss', 'l_.bss', '_main', '_data_value', '_zeroed',
                     '_ctor_seen', '_main_seen', '_atexit_seen', '_dtor_seen',
                     '_main_dtor_seen', '_goodbye_dtor_seen',
                     '_observed_sp', '_observed_argc', '_observed_argv'):
            if name not in symbols:
                raise RuntimeError(f'missing linked symbol {name}')
        return harness.parse_s19(record), int(match.group(1), 16), symbols


def exercise(start_sp):
    runner = harness.GCC6809TestRunner()
    code, entry, symbols = build(runner)
    if entry != symbols['__start']:
        raise RuntimeError(f'S9 entry {entry:04x} != installed crt0 __start {symbols["__start"]:04x}')
    cfg = harness.Config(harness.CFG_DICT)
    memory = harness.Memory64K(cfg)
    cpu = harness.CPU(memory, cfg)
    memory._mem[:] = array.array('B', [0xa5] * 65536)
    mem = memory._mem
    for address, byte in code.items():
        mem[address] = byte

    def word(address):
        return (mem[address] << 8) | mem[address + 1]

    def observed(name):
        return word(symbols[name])

    if observed('_data_value') != 0x1234:
        raise RuntimeError('linker/loader did not populate initialized data')
    bss_start = symbols['s_.bss']
    bss_length = symbols['l_.bss']
    bss_end = bss_start + bss_length
    if not (bss_length >= 8 and bss_end == symbols['__stack_ptr']):
        raise RuntimeError('BSS extent or following stack save slot changed')
    if any(mem[address] != 0xa5 for address in range(bss_start, bss_end)):
        raise RuntimeError('BSS unexpectedly initialized before crt0 ran')
    before_bss = mem[bss_start - 1]

    # --args allows the probe to supply nonzero __argc and __argv symbols;
    # unlike the default linker placeholders, incorrect null forwarding fails.
    expected_argc = word(symbols['__argc'])
    if expected_argc != 2 or symbols['__argv'] == 0:
        raise RuntimeError('linker did not use supplied argc/argv symbols')
    mem[HALT], mem[HALT + 1] = 0x20, 0xfe
    mem[start_sp], mem[start_sp + 1] = HALT >> 8, HALT & 255
    cpu.system_stack_pointer.set(start_sp)
    cpu.program_counter.set(entry)
    cpu.set_cc(0x50)
    memset_return = None
    bss_checked = False
    for _ in range(100000):
        pc = cpu.program_counter.value
        if pc == HALT:
            break
        if pc == symbols['_memset'] and memset_return is None:
            memset_return = word(cpu.system_stack_pointer.value)
        if pc == memset_return and not bss_checked:
            if any(mem[address] != 0 for address in range(bss_start, bss_end)):
                raise RuntimeError('installed crt0 left part of .bss uncleared')
            if mem[bss_start - 1] != before_bss:
                raise RuntimeError('crt0 cleared byte before .bss')
            if word(bss_end) != start_sp:
                raise RuntimeError('crt0 overwrote saved loader stack after .bss')
            bss_checked = True
        try:
            cpu.get_and_call_next_op()
        except (Exception, SystemExit) as error:
            raise RuntimeError(f'CPU error at ${cpu.program_counter.value:04x}: {error}') from error
    else:
        raise RuntimeError(f'crt0 failed to return to loader; PC={cpu.program_counter.value:04x}')

    if not bss_checked:
        raise RuntimeError('installed crt0 never returned from BSS memset')
    if cpu.index_x.value != 37 or cpu.accu_d.value != 37:
        raise RuntimeError(f'wrong exit value: X={cpu.index_x.value} D={cpu.accu_d.value}; expected 37')
    checks = {
        'restored loader stack': (cpu.system_stack_pointer.value, start_sp + 2),
        'initialized data': (observed('_data_value'), 0x1234),
        'constructor': (observed('_ctor_seen'), 0x11),
        'constructor visible in main': (observed('_main_seen'), 0x11),
        'atexit callback': (observed('_atexit_seen'), 0x55),
        'destructor': (observed('_dtor_seen'), 0x33),
        'destructor absent in main': (observed('_main_dtor_seen'), 0),
        'destructor absent in user atexit callback': (observed('_goodbye_dtor_seen'), 0),
        'argc forwarded': (observed('_observed_argc'), expected_argc),
        'argv pointer forwarded': (observed('_observed_argv'), symbols['__argv']),
    }
    for label, (actual, expected) in checks.items():
        if actual != expected:
            raise RuntimeError(f'{label}: got 0x{actual:04x}, expected 0x{expected:04x}')
    sp = observed('_observed_sp')
    if not start_sp - 16 <= sp <= start_sp - 2:
        raise RuntimeError(f'main stack pointer 0x{sp:04x} outside entry frame')
    for i in range(8):
        if mem[symbols['_zeroed'] + i] != 0:
            raise RuntimeError(f'BSS byte {i} not cleared by installed crt0.o')
    print(f'installed crt0 PASS: S9 __start=0x{entry:04x}, '
          f'loader S=0x{start_sp:04x}, main S=0x{sp:04x}, BSS cleared, '
          'data intact, constructors/atexit/destructors, argc/argv=2, exit=37')


def main():
    for start_sp in (0xeffe, 0xdffe):
        exercise(start_sp)
    return 0


if __name__ == '__main__':
    sys.exit(main())
