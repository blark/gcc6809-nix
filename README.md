# gcc6809-nix

Nix flake for building a GCC 4.3.6 cross-compiler targeting the Motorola 6809 CPU on macOS ARM64 (Apple Silicon).

## Quick Start

```bash
# Build the toolchain
nix build

# Enter a shell with the toolchain available
nix develop

# Compile a test program
echo 'int main() { return 42; }' > test.c
m6809-unknown-none-gcc -S test.c -o test.s
```

## What's Included

- **m6809-unknown-none-gcc** - GCC 4.3.6 cross-compiler
- **as6809** - ASxxxx assembler
- **aslink** - ASxxxx linker
- **libc.a** - Newlib C library

See [example/](example/) for linking with libc.

## Platform Support

Currently only supports `aarch64-darwin` (Apple Silicon Macs) due to ARM64-specific patches required to build GCC 4.3.6.

## License

- GCC: GPL-3.0-or-later
- Newlib: BSD-3-Clause
- Patches in this repo: Same license as the code they patch
