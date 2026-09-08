#include <stdio.h>

int main(void) {
    int n, m;
    if (scanf("%d %d", &n, &m) != 2) return 1;
    int first = 1;
    for (int i = 0; i < n; i++)
        for (int j = 0; j < m; j++) {
            int v;
            if (scanf("%d", &v) != 1) return 1;
            if (!first) printf(" ");
            printf("%d", v);
            first = 0;
        }
    printf("\n");
    return 0;
}
