#include <stdio.h>

int main(void) {
    int a[6][8], v[48];
    int cnt = 0;
    for (int i = 0; i < 6; i++)
        for (int j = 0; j < 8; j++) {
            if (scanf("%d", &a[i][j]) != 1) return 1;
            if (a[i][j] > 0) v[cnt++] = a[i][j];
        }
    for (int i = 0; i < cnt; i++)
        for (int k = i + 1; k < cnt; k++)
            if (v[k] < v[i]) { int t = v[i]; v[i] = v[k]; v[k] = t; }
    for (int i = 0; i < cnt; i++) {
        if (i) printf(" ");
        printf("%d", v[i]);
    }
    printf("\n");
    return 0;
}
