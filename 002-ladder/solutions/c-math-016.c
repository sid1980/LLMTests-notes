#include <stdio.h>

int main(void) {
    int x, y;
    if (scanf("%d %d", &x, &y) != 2) return 1;
    if (x > 0 && y > 0) printf("1\n");
    else if (x < 0 && y > 0) printf("2\n");
    else if (x < 0 && y < 0) printf("3\n");
    else printf("4\n");
    return 0;
}
