#include <stdio.h>
#include <math.h>

int main(void) {
    int n;
    double s = 0.0, denom = 0.0;
    if (scanf("%d", &n) != 1) return 1;
    for (int i = 1; i <= n; i++) {
        denom += sin(i);
        s += 1.0 / denom;
    }
    printf("%.6f\n", s);
    return 0;
}
