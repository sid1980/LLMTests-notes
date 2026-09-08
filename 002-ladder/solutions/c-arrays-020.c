#include <stdio.h>

int main(void) {
    int n;
    int a[1000];
    if (scanf("%d", &n) != 1) return 1;
    for (int i = 0; i < n; i++) if (scanf("%d", &a[i]) != 1) return 1;
    /* selection sort */
    for (int i = 0; i < n - 1; i++) {
        int mi = i;
        for (int j = i + 1; j < n; j++) if (a[j] < a[mi]) mi = j;
        int t = a[i]; a[i] = a[mi]; a[mi] = t;
    }
    for (int i = 0; i < n; i++) {
        if (i) printf(" ");
        printf("%d", a[i]);
    }
    printf("\n");
    printf("%d\n", n * (n - 1) / 2);
    return 0;
}
