#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int n;
    int a[1000];
    if (scanf("%d", &n) != 1) return 1;
    for (int i = 0; i < n; i++) if (scanf("%d", &a[i]) != 1) return 1;
    int mini = 0;
    for (int i = 1; i < n; i++) if (a[i] < a[mini]) mini = i;
    printf("%d\n", mini + 1);
    int neg1 = -1, neg2 = -1;
    for (int i = 0; i < n; i++) {
        if (a[i] < 0) { if (neg1 < 0) neg1 = i; else { neg2 = i; break; } }
    }
    if (neg2 < 0) printf("0\n");
    else {
        long long prod = 1;
        for (int i = neg1 + 1; i < neg2; i++) prod *= a[i];
        printf("%lld\n", prod);
    }
    int first = 1;
    for (int i = 0; i < n; i++)
        if (abs(a[i]) <= 1) { if (!first) printf(" "); printf("%d", a[i]); first = 0; }
    for (int i = 0; i < n; i++)
        if (abs(a[i]) > 1) { if (!first) printf(" "); printf("%d", a[i]); first = 0; }
    printf("\n");
    return 0;
}
