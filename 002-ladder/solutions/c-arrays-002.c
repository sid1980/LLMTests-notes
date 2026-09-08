#include <stdio.h>

int main(void) {
    int a[10][10];
    int min = 0, minr = 0;
    for (int i = 0; i < 10; i++)
        for (int j = 0; j < 10; j++) {
            if (scanf("%d", &a[i][j]) != 1) return 1;
            if (i == 0 && j == 0) { min = a[i][j]; minr = 0; }
            else if (a[i][j] < min) { min = a[i][j]; minr = i; }
        }
    for (int j = 0; j < 10; j++) {
        int t = a[0][j]; a[0][j] = a[minr][j]; a[minr][j] = t;
    }
    for (int i = 0; i < 10; i++) {
        for (int j = 0; j < 10; j++) {
            if (j) printf(" ");
            printf("%d", a[i][j]);
        }
        printf("\n");
    }
    return 0;
}
