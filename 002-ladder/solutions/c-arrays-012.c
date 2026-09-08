#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int n;
    if (scanf("%d", &n) != 1) return 1;
    int a[100][100];
    int best = -1, br = 0, bc = 0;
    for (int i = 0; i < n; i++)
        for (int j = 0; j < n; j++) {
            if (scanf("%d", &a[i][j]) != 1) return 1;
            int av = abs(a[i][j]);
            if (av > best) { best = av; br = i; bc = j; }
        }
    for (int j = 0; j < n; j++) { int t = a[br][j]; a[br][j] = a[n - 1][j]; a[n - 1][j] = t; }
    for (int i = 0; i < n; i++) { int t = a[i][bc]; a[i][bc] = a[i][n - 1]; a[i][n - 1] = t; }
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            if (j) printf(" ");
            printf("%d", a[i][j]);
        }
        printf("\n");
    }
    return 0;
}
