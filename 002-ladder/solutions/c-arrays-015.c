#include <stdio.h>

int main(void) {
    int n, m;
    if (scanf("%d %d", &n, &m) != 2) return 1;
    int a[100][100];
    for (int i = 0; i < n; i++)
        for (int j = 0; j < m; j++)
            if (scanf("%d", &a[i][j]) != 1) return 1;
    int k = n < m ? n : m;
    for (int i = 0; i < k; i++) {
        if (i) printf(" ");
        printf("%d", a[i][i]);
    }
    printf("\n");
    for (int i = 0; i < k; i++) {
        if (i) printf(" ");
        printf("%d", a[i][m - 1 - i]);
    }
    printf("\n");
    return 0;
}
