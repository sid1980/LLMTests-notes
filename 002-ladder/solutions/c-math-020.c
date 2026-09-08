#include <stdio.h>
#include <math.h>

int main(void) {
    double a, b, h;
    if (scanf("%lf %lf %lf", &a, &b, &h) != 3) return 1;
    for (double x = a; x <= b + 1e-9; x += h) {
        double t = tan(log(x));
        double f = 1.0 / (t * t);
        printf("%.2f %.6f\n", x, f);
    }
    return 0;
}
