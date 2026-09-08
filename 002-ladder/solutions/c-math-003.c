#include <stdio.h>

int main(void) {
    int m;
    if (scanf("%d", &m) != 1) return 1;
    printf("%.3f\n", m / 1000.0);
    return 0;
}
