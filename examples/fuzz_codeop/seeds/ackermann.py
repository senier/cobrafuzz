def ack2(m, n):
    return (
        (n + 1)
        if m == 0
        else (
            (n + 2)
            if m == 1
            else (
                (2 * n + 3)
                if m == 2
                else (
                    (8 * (2**n - 1) + 5)
                    if m == 3
                    else (ack2(m - 1, 1) if n == 0 else ack2(m - 1, ack2(m, n - 1)))
                )
            )
        )
    )
