#include <stdio.h>
#include <math.h>

int main(void) {
    double a, b, c, d, k;
    if (scanf("%lf %lf %lf %lf %lf", &a, &b, &c, &d, &k) != 5) return 1;
    double A = a, B = b - d, C = c - k;
    double D = B * B - 4.0 * A * C;
    if (A == 0.0) {
        if (B == 0.0) printf("no roots\n");
        else printf("%.6f\n", -C / B);
    } else if (D < 0.0) {
        printf("no roots\n");
    } else if (D == 0.0) {
        printf("%.6f\n", -B / (2.0 * A));
    } else {
        double s = sqrt(D);
        double x1 = (-B - s) / (2.0 * A);
        double x2 = (-B + s) / (2.0 * A);
        if (x1 > x2) { double t = x1; x1 = x2; x2 = t; }
        printf("%.6f %.6f\n", x1, x2);
    }
    return 0;
}
