#include <stdio.h>

int main(void) {
    int n, d1, d2, max, min;
    if (scanf("%d", &n) != 1) return 1;
    d1 = n / 10;
    d2 = n % 10;
    max = d1 > d2 ? d1 : d2;
    min = d1 < d2 ? d1 : d2;
    printf("%d\n%d\n", max, min);
    return 0;
}
