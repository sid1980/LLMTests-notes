#include <stdio.h>
#include <math.h>

int main(void) {
    double V, T, alpha;
    const double g = 9.81;
    const double pi = 3.14159265358979323846;
    if (scanf("%lf %lf", &V, &T) != 2) return 1;
    alpha = asin(g * T / (2.0 * V)) * 180.0 / pi;
    printf("%.6f\n", alpha);
    return 0;
}
