#include <stdio.h>
#include <math.h>

int main(void) {
    double x;
    if (scanf("%lf", &x) != 1) return 1;
    if (x == 0.0) { printf("0.000000\n"); return 0; }
    double y = x, y1;
    for (;;) {
        y1 = 0.5 * (y + 3.0 * x / (2.0 * y * y + x / y));
        if (fabs(y1 - y) < 1e-5) break;
        y = y1;
    }
    printf("%.6f\n", y1);
    return 0;
}
