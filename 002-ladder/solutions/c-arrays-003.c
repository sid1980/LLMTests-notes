#include <stdio.h>

int main(void) {
    int n, first = 1;
    if (scanf("%d", &n) != 1) return 1;
    for (int i = 0; i < n; i++) {
        int v;
        if (scanf("%d", &v) != 1) return 1;
        if (v % 2 != 0) {
            if (!first) printf(" ");
            printf("%d", v);
            first = 0;
        }
    }
    printf("\n");
    return 0;
}
