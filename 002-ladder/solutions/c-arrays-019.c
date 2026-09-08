#include <stdio.h>

int main(void) {
    int n;
    int a[1000];
    if (scanf("%d", &n) != 1) return 1;
    for (int i = 0; i < n; i++) if (scanf("%d", &a[i]) != 1) return 1;
    int len = 0;
    for (int i = 0; i < n; i++) {
        int dup = 0;
        for (int k = 0; k < len; k++) if (a[k] == a[i]) { dup = 1; break; }
        if (!dup) a[len++] = a[i];
    }
    for (int i = 0; i < len; i++) {
        if (i) printf(" ");
        printf("%d", a[i]);
    }
    printf("\n%d\n", len);
    return 0;
}
