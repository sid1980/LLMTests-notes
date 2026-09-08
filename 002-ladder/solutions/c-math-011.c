#include <stdio.h>
#include <math.h>

int main(void) {
    double x, y, z;
    if (scanf("%lf %lf %lf", &x, &y, &z) != 3) return 1;
    printf("%.6f\n", sqrt(x * x + y * y + z * z));
    return 0;
}
