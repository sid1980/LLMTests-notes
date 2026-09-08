#include <stdio.h>

int main(void) {
    int x, cnt = 0;
    while (scanf("%d", &x) == 1) {
        if (x == 1) break;
        cnt++;
    }
    printf("%d\n", cnt);
    return 0;
}
