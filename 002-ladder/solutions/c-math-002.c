#include <stdio.h>

int main(void) {
    int a, b, f, x;
    if (scanf("%d %d %d", &a, &b, &f) != 3) return 1;
    x = (a + b - f / a) + f * a * a - (a + b);
    printf("%d\n", x);
    return 0;
}
