#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int N;
    if (scanf("%d", &N) != 1) return 1;
    if (N < 2) { printf("\n"); return 0; }
    char *prime = (char *)malloc((size_t)(N + 1) * sizeof(char));
    if (!prime) return 1;
    for (int i = 0; i <= N; i++) prime[i] = 1;
    prime[0] = prime[1] = 0;
    for (int i = 2; i * i <= N; i++) {
        if (prime[i]) for (int j = i * i; j <= N; j += i) prime[j] = 0;
    }
    int first = 1;
    for (int i = 2; i <= N; i++) {
        if (prime[i]) {
            if (!first) printf(" ");
            printf("%d", i);
            first = 0;
        }
    }
    printf("\n");
    free(prime);
    return 0;
}
