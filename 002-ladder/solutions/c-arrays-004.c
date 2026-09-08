#include <stdio.h>

int main(void) {
    double a[5][3];
    double best = 0;
    int bi = 0, bj = 0;
    for (int i = 0; i < 5; i++)
        for (int j = 0; j < 3; j++) {
            if (scanf("%lf", &a[i][j]) != 1) return 1;
            if (i == 0 && j == 0) { best = a[i][j]; bi = 0; bj = 0; }
            else if (a[i][j] > best) { best = a[i][j]; bi = i; bj = j; }
        }
    printf("%d %d\n", bi + 1, bj + 1);
    return 0;
}
