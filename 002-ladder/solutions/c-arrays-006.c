#include <stdio.h>

int main(void) {
    int R, C;
    if (scanf("%d %d", &R, &C) != 2) return 1;
    int a[100][100];
    for (int i = 0; i < R; i++)
        for (int j = 0; j < C; j++)
            if (scanf("%d", &a[i][j]) != 1) return 1;
    for (int j = 0; j < C; j++) {
        int neg = 0, sum = 0;
        for (int i = 0; i < R; i++) {
            if (a[i][j] < 0) neg = 1;
            sum += a[i][j];
        }
        if (!neg) printf("%d\n", sum);
    }
    return 0;
}
