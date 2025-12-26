# Build and link with libc

```bash
cd example
nix develop ..
m6809-unknown-none-gcc -Os -S $M6809_CFLAGS hello.c -o hello.s
as6809 -o hello.s
aslink -s -m -w -o hello.s19 -b .text=0x2000 hello.rel -l $M6809_LIBC
```
