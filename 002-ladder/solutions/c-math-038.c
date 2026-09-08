#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int x1, y1, x2, y2;
    if (scanf("%d %d %d %d", &x1, &y1, &x2, &y2) != 4) return 1;
    int dx = abs(x1 - x2), dy = abs(y1 - y2);
    if (dx == dy && dx != 0) printf("Yes\n");
    else printf("No\n");
    return 0;
}
