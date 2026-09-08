#include <stdio.h>

int main(void) {
    int a, b;
    if (scanf("%d %d", &a, &b) != 2) return 1;
    if (a > b) printf("greater\n");
    else if (a < b) printf("less\n");
    else printf("equal\n");
    return 0;
}
