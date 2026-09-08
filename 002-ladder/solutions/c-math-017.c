#include <stdio.h>

int main(void) {
    int n, a, b, c;
    if (scanf("%d", &n) != 1) return 1;
    a = n / 100;
    b = (n / 10) % 10;
    c = n % 10;
    if (a == b || a == c || b == c) printf("yes\n");
    else printf("no\n");
    return 0;
}
