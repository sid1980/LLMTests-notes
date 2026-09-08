#include <stdio.h>

static long long determinant(long long m[20][20], int n) {
    if (n == 1) return m[0][0];
    long long det = 0;
    long long sub[20][20];
    for (int col = 0; col < n; col++) {
        for (int i = 1; i < n; i++) {
            int sj = 0;
            for (int j = 0; j < n; j++) {
                if (j == col) continue;
                sub[i - 1][sj++] = m[i][j];
            }
        }
        long long term = m[0][col] * determinant(sub, n - 1);
        if (col % 2 == 0) det += term; else det -= term;
    }
    return det;
}

int main(void) {
    int N;
    long long m[20][20];
    if (scanf("%d", &N) != 1) return 1;
    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++)
            if (scanf("%lld", &m[i][j]) != 1) return 1;
    printf("%lld\n", determinant(m, N));
    return 0;
}
