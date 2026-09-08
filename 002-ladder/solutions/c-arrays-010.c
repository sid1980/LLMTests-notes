#include <stdio.h>

int main(void) {
    int n;
    if (scanf("%d", &n) != 1) return 1;
    int a[100][100];
    int val = 1;
    for (int d = 0; d < 2 * n - 1; d++) {
        int r_start = (d < n) ? 0 : d - (n - 1);
        int r_end = (d < n) ? d : n - 1;
        if (d % 2 == 0) {
            for (int r = r_start; r <= r_end; r++) a[r][d - r] = val++;
        } else {
            for (int r = r_end; r >= r_start; r--) a[r][d - r] = val++;
        }
    }
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            if (j) printf(" ");
            printf("%d", a[i][j]);
        }
        printf("\n");
    }
    return 0;
}
