#include <stdio.h>

int main(void) {
    long long n;
    int k;
    if (scanf("%lld %d", &n, &k) != 2) return 1;
    long long t = n;
    int digits = 0;
    while (t > 0) { t /= 10; digits++; }
    if (k >= digits) {
        printf("%lld\n", n);
    } else {
        long long div = 1;
        for (int i = 0; i < digits - k; i++) div *= 10;
        printf("%lld\n", n / div);
    }
    return 0;
}
