#include <stdio.h>

int main(void) {
    int n;
    if (scanf("%d", &n) != 1) return 1;
    int a[100][100];
    for (int i = 0; i < n; i++)
        for (int j = 0; j < n; j++)
            if (scanf("%d", &a[i][j]) != 1) return 1;
    int mnr = 0, mnc = 1, mxr = 0, mxc = 0;
    int mn = a[mnr][mnc], mx = a[0][0];
    for (int i = 0; i < n; i++)
        for (int j = 0; j < n; j++) {
            if (i > j) {
                if (a[i][j] < mn) { mn = a[i][j]; mnr = i; mnc = j; }
            }
            if (i + j < n - 1) {
                if (a[i][j] > mx) { mx = a[i][j]; mxr = i; mxc = j; }
            }
        }
    int t = a[mnr][mnc]; a[mnr][mnc] = a[mxr][mxc]; a[mxr][mxc] = t;
    printf("%d %d\n", mnr, mnc);
    printf("%d %d\n", mxr, mxc);
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            if (j) printf(" ");
            printf("%d", a[i][j]);
        }
        printf("\n");
    }
    return 0;
}
