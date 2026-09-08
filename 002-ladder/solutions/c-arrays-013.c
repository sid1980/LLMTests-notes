#include <stdio.h>

int main(void) {
    int a[7][7];
    for (int i = 0; i < 7; i++)
        for (int j = 0; j < 7; j++)
            if (scanf("%d", &a[i][j]) != 1) return 1;
    for (int j = 0; j < 7; j++) {
        int mn = a[0][j], mx = a[0][j];
        int imn = 0, imx = 0;
        for (int i = 0; i < 7; i++) {
            if (a[i][j] < mn) { mn = a[i][j]; imn = i; }
            if (a[i][j] > mx) { mx = a[i][j]; imx = i; }
        }
        int lo = imn < imx ? imn : imx;
        int hi = imn < imx ? imx : imn;
        if (hi - lo > 1) {
            for (int i = lo + 1; i < hi; i++) {
                for (int k = i + 1; k < hi; k++) {
                    if (a[k][j] < a[i][j]) {
                        int t = a[i][j]; a[i][j] = a[k][j]; a[k][j] = t;
                    }
                }
            }
        }
    }
    for (int i = 0; i < 7; i++) {
        for (int j = 0; j < 7; j++) {
            if (j) printf(" ");
            printf("%d", a[i][j]);
        }
        printf("\n");
    }
    return 0;
}
