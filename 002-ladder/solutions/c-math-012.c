#include <stdio.h>
#include <math.h>

static double mypow(double b, int e) {
    double r = 1.0;
    for (int i = 0; i < e; i++) r *= b;
    return r;
}

int main(void) {
    for (double x = -1.1; x <= 0.3 + 1e-9; x += 0.2) {
        for (int m = 1; m <= 5; m++) {
            double z = mypow(x, m) * mypow(sin(x * m), m);
            printf("%.1f %d %.6f\n", x, m, z);
        }
    }
    return 0;
}
