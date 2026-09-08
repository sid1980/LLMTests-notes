#include <stdio.h>

static int to_sec(int h, int m, int s) { return h * 3600 + m * 60 + s; }

int main(void) {
    int op;
    if (scanf("%d", &op) != 1) return 1;
    if (op == 1) {
        int h, m, s, delta;
        if (scanf("%d %d %d %d", &h, &m, &s, &delta) != 4) return 1;
        int t = (to_sec(h, m, s) - delta) % 86400;
        if (t < 0) t += 86400;
        printf("%d %d %d\n", t / 3600, (t / 60) % 60, t % 60);
    } else {
        int h1, m1, s1, h2, m2, s2;
        if (scanf("%d %d %d %d %d %d", &h1, &m1, &s1, &h2, &m2, &s2) != 6) return 1;
        int d = to_sec(h1, m1, s1) - to_sec(h2, m2, s2);
        if (d < 0) d = -d;
        printf("%d\n", d);
    }
    return 0;
}
