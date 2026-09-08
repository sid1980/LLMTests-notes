#include <stdio.h>

static int max3(int a, int b, int c) {
    int m = a; if (b > m) m = b; if (c > m) m = c; return m;
}
static int min3(int a, int b, int c) {
    int m = a; if (b < m) m = b; if (c < m) m = c; return m;
}

int main(void) {
    int ha, hb, x, y, z;
    if (scanf("%d %d %d %d %d", &ha, &hb, &x, &y, &z) != 5) return 1;
    int hole_min = ha < hb ? ha : hb;
    int hole_max = ha > hb ? ha : hb;
    int brick_min = min3(x, y, z);
    int brick_mid = x + y + z - brick_min - max3(x, y, z);
    if (brick_min <= hole_min && brick_mid <= hole_max) printf("yes\n");
    else printf("no\n");
    return 0;
}
