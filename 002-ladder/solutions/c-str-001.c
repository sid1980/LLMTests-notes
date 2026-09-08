#include <stdio.h>

int main(void) {
    int n, d0, d1, d3, d4;
    if (scanf("%d", &n) != 1) return 1;
    d0 = n / 10000;
    d1 = (n / 1000) % 10;
    d3 = (n / 10) % 10;
    d4 = n % 10;
    if (d0 == d4 && d1 == d3) printf("yes\n");
    else printf("no\n");
    return 0;
}
