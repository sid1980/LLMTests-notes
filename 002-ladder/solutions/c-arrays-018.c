#include <stdio.h>

int main(void) {
    int n, m;
    if (scanf("%d %d", &n, &m) != 2) return 1;
    int a[100][100];
    int ch[100];
    for (int i = 0; i < n; i++)
        for (int j = 0; j < m; j++)
            if (scanf("%d", &a[i][j]) != 1) return 1;
    for (int j = 0; j < m; j++) {
        int s = 0;
        for (int i = 0; i < n; i++)
            if (a[i][j] < 0 && (a[i][j] % 2 != 0)) s += -a[i][j];
        ch[j] = s;
    }
    for (int j = 0; j < m; j++) {
        for (int k = j + 1; k < m; k++) {
            if (ch[k] < ch[j]) {
                int t = ch[j]; ch[j] = ch[k]; ch[k] = t;
                for (int i = 0; i < n; i++) {
                    int tmp = a[i][j]; a[i][j] = a[i][k]; a[i][k] = tmp;
                }
            }
        }
    }
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < m; j++) {
            if (j) printf(" ");
            printf("%d", a[i][j]);
        }
        printf("\n");
    }
    return 0;
}
