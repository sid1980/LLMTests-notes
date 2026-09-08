#include <stdio.h>

int main(void) {
    int N, s = 0;
    if (scanf("%d", &N) != 1) return 1;
    for (int i = 0; i <= N; i++) if (i % 5 == 0) s += i;
    printf("%d\n", s);
    return 0;
}
