#include <stdio.h>

int main(void) {
    int a, b, q = 0, r;
    if (scanf("%d %d", &a, &b) != 2) return 1;
    r = a;
    while (r >= b) { r -= b; q++; }
    printf("%d %d\n", q, r);
    return 0;
}
