#include <stdio.h>

static void print_binary(unsigned int v) {
    for (int i = 31; i >= 0; i--) putchar((v >> i) & 1u ? '1' : '0');
    putchar('\n');
}

int main(void) {
    unsigned int x, y;
    int m, n;
    if (scanf("%u %u %d %d", &x, &y, &m, &n) != 4) return 1;
    unsigned int nx = x, ny = y;
    if (m > 0) {
        unsigned int lowmask = (m >= 32) ? 0xFFFFFFFFu : ((1u << m) - 1u);
        unsigned int highbits = (y >> (32 - m)) & lowmask;
        nx = (x & ~lowmask) | highbits;
    }
    if (n > 0) {
        unsigned int nmask = (n >= 32) ? 0xFFFFFFFFu : ((1u << n) - 1u);
        ny = y ^ nmask;
    }
    printf("%u %u %d %d\n", x, y, m, n);
    printf("x = ");
    print_binary(nx);
    printf("y = ");
    print_binary(ny);
    return 0;
}
