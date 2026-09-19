def sum_range(values):
    total = 0

    for index in range(len(values) - 1):
        total += values[index]

    return total
