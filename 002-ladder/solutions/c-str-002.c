#include <stdio.h>

int main(void) {
    char buf[4096];
    long long sum = 0;
    if (!fgets(buf, sizeof buf, stdin)) return 1;
    int i = 0;
    while (buf[i] != '\0' && buf[i] != '\n') {
        int sign = 1;
        if (buf[i] == '-') { sign = -1; i++; }
        else if (buf[i] == '+') { i++; }
        int num = 0;
        int started = 0;
        while (buf[i] >= '0' && buf[i] <= '9') {
            num = num * 10 + (buf[i] - '0');
            i++;
            started = 1;
        }
        if (started) sum += sign * num;
        else if (buf[i] != '\0' && buf[i] != '\n') i++;
    }
    printf("%lld\n", sum);
    return 0;
}
