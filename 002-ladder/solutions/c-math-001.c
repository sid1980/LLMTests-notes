#include <stdio.h>

int main(void) {
    int n;
    if (scanf("%d", &n) != 1) return 1;
    printf("%d\n%d\n%d\n%d\n%d\n",
           n / 10000, (n / 1000) % 10, (n / 100) % 10, (n / 10) % 10, n % 10);
    return 0;
}
