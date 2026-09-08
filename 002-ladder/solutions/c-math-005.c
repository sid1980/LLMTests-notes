#include <stdio.h>

int main(void) {
    int x, y, z;
    if (scanf("%d %d %d", &x, &y, &z) != 3) return 1;
    if (x == y || x == z || y == z) {
        printf("%d\n%d\n%d\n", x + 5, y + 5, z + 5);
    } else {
        printf("no equal\n");
    }
    return 0;
}
