def find_item(items, target):
    # BUG: Off-by-one error (should be range(len(items)))
    # This misses the last element
    for i in range(len(items) - 1):
        if items[i] == target:
            return i
    return -1

def calculate_average(numbers):
    # BUG: Division by zero if list is empty
    return sum(numbers) / len(numbers)
