#include <stdio.h>

int main(void) {
    int n, composite = 0;
    if (scanf("%d", &n) != 1) return 1;
    if (n > 1) {
        for (int i = 2; i * i <= n; i++) {
            if (n % i == 0) { composite = 1; break; }
        }
    }
    printf(composite ? "yes\n" : "no\n");
    return 0;
}
