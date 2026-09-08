#include <stdio.h>

int main(void) {
    unsigned int n;
    if (scanf("%u", &n) != 1) return 1;
    printf("%X\n", n);
    return 0;
}
