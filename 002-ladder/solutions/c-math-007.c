#include <stdio.h>

static long long ipow(long long base, int k) {
    long long r = 1;
    for (int i = 0; i < k; i++) r *= base;
    return r;
}

int main(void) {
    int N, k;
    long long s = 0;
    if (scanf("%d %d", &N, &k) != 2) return 1;
    for (int i = 1; i <= N; i++) s += ipow(i, k);
    printf("%lld\n", s);
    return 0;
}
