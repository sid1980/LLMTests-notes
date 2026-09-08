#include <stdio.h>

int main(void) {
    int k, d1, d2;
    if (scanf("%d %d %d", &k, &d1, &d2) != 3) return 1;
    k = k * 10 + d1;
    printf("%d\n", k);
    k = k * 10 + d2;
    printf("%d\n", k);
    return 0;
}
