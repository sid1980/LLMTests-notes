#include <stdio.h>
#include <math.h>

int main(void) {
    double x, y, r;
    if (scanf("%lf %lf", &x, &y) != 2) return 1;
    double tg = tan(x);
    double ctg = 1.0 / tg;
    r = pow(1.0 - tg, ctg) + cos(x - y);
    printf("%.6f\n", r);
    return 0;
}
