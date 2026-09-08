#include <stdio.h>

int main(void) {
    char buf[256];
    if (!fgets(buf, sizeof buf, stdin)) return 1;
    int i = 0;
    while (buf[i] == ' ' || buf[i] == '\t') i++;
    if (buf[i] == '+' || buf[i] == '-') i++;
    if (buf[i] < '0' || buf[i] > '9') { printf("no\n"); return 0; }
    while (buf[i] >= '0' && buf[i] <= '9') i++;
    while (buf[i] == ' ' || buf[i] == '\t' || buf[i] == '\n' || buf[i] == '\r') i++;
    if (buf[i] == '\0') printf("yes\n");
    else printf("no\n");
    return 0;
}
