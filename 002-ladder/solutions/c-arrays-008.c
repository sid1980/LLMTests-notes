#include <stdio.h>

int main(void) {
    int n, a[1000], i;
    if (scanf("%d", &n) != 1) return 1;
    for (int k = 0; k < n; k++) if (scanf("%d", &a[k]) != 1) return 1;
    if (scanf("%d", &i) != 1) return 1;
    for (int k = i - 1; k < n - 1; k++) a[k] = a[k + 1];
    for (int k = 0; k < n - 1; k++) {
        if (k) printf(" ");
        printf("%d", a[k]);
    }
    printf("\n");
    return 0;
}
