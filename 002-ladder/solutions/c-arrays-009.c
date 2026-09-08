#include <stdio.h>

int main(void) {
    int m, n;
    int a[100][100], v[100];
    long long r[100];
    if (scanf("%d %d", &m, &n) != 2) return 1;
    for (int i = 0; i < m; i++)
        for (int j = 0; j < n; j++)
            if (scanf("%d", &a[i][j]) != 1) return 1;
    for (int j = 0; j < n; j++) if (scanf("%d", &v[j]) != 1) return 1;
    long long max = 0;
    for (int i = 0; i < m; i++) {
        r[i] = 0;
        for (int j = 0; j < n; j++) r[i] += (long long)a[i][j] * v[j];
        if (i == 0 || r[i] > max) max = r[i];
    }
    for (int i = 0; i < m; i++) {
        if (i) printf(" ");
        printf("%lld", r[i]);
    }
    printf("\n%lld\n", max);
    return 0;
}
