#include <stdio.h>
#include <math.h>

int main(void) {
    int n;
    double Z, B, A, beta, y = 0.0;
    if (scanf("%d", &n) != 1) return 1;
    for (int i = 0; i < n; i++) {
        if (scanf("%lf %lf %lf %lf", &Z, &B, &A, &beta) != 4) return 1;
        double t = tan(beta);
        y += Z * Z * Z - B + A * A / (t * t);
    }
    printf("%.6f\n", y);
    return 0;
}
