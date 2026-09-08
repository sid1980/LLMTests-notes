#include <stdio.h>

int main(void) {
    int R, C;
    if (scanf("%d %d", &R, &C) != 2) return 1;
    int a[100][100];
    for (int i = 0; i < R; i++)
        for (int j = 0; j < C; j++)
            if (scanf("%d", &a[i][j]) != 1) return 1;
    for (int j = 1; j < C && j <= 5; j += 2)
        for (int i = 0; i < R; i++)
            a[i][j] = 0;
    for (int i = 0; i < R; i++) {
        for (int j = 0; j < C; j++) {
            if (j) printf(" ");
            printf("%d", a[i][j]);
        }
        printf("\n");
    }
    return 0;
}
