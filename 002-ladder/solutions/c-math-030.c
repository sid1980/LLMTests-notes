#include <stdio.h>

int main(void) {
    int n;
    double v = 1.0;
    if (scanf("%d", &n) != 1) return 1;
    for (int i = n; i >= 2; i--) v = 1.0 + 1.0 / v;
    printf("%.5f\n", v);
    return 0;
}
