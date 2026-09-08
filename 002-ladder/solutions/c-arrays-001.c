#include <stdio.h>

int main(void) {
    int n;
    long long trace = 0;
    if (scanf("%d", &n) != 1) return 1;
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            int v;
            if (scanf("%d", &v) != 1) return 1;
            if (i == j) trace += v;
        }
    }
    printf("%lld\n", trace);
    return 0;
}
