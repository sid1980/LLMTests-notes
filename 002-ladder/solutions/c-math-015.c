#include <stdio.h>

int main(void) {
    long long a, inc, m, x0;
    int n;
    if (scanf("%lld %lld %lld %lld %d", &a, &inc, &m, &x0, &n) != 5) return 1;
    long long x = x0;
    for (int i = 0; i < n; i++) {
        printf("%.6f\n", (double)x / (double)m);
        x = (a * x + inc) % m;
    }
    return 0;
}
