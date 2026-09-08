#include <stdio.h>

int main(void) {
    int n;
    long long s = 0;
    if (scanf("%d", &n) != 1) return 1;
    for (int i = 0; i < n; i++) {
        int v;
        if (scanf("%d", &v) != 1) return 1;
        s += v;
    }
    printf("%.6f\n", (double)s / n);
    return 0;
}
