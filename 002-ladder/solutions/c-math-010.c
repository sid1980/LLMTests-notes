#include <stdio.h>

int main(void) {
    long long base, r = 1;
    int k;
    if (scanf("%lld %d", &base, &k) != 2) return 1;
    for (int i = 0; i < k; i++) r *= base;
    printf("%lld\n", r);
    return 0;
}
