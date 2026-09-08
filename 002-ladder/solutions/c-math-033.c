#include <stdio.h>

int main(void) {
    double salary, tax;
    if (scanf("%lf", &salary) != 1) return 1;
    if (salary <= 800.0) tax = 0.0;
    else tax = 0.18 * (salary - 800.0);
    printf("%.2f\n", tax);
    return 0;
}
