#include <stdio.h>

int main(void) {
    int n;
    double x, s = 0.0;
    if (scanf("%d", &n) != 1) return 1;
    for (int i = 0; i < n; i++) {
        if (scanf("%lf", &x) != 1) return 1;
        s += x;
    }
    printf("%.6f\n", s / n);
    return 0;
}
